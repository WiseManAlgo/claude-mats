#!/opt/miniconda3/bin/python3
"""
MATS Engine — regression test against frozen fixtures (see ENGINE_ARCHITECTURE.md).

Why this exists: the six Phase 1 scripts were originally "verified" only by
manually eyeballing JSON output against numbers recalled earlier in a chat
session — that verification evaporates when the session ends. This script
makes it persistent and re-runnable: fixed historical data in, hard-coded
expected values in fixtures_LITE_2026-07-17.json, plain assert statements.

Does NOT test market_context.py or the options-wall-success path in
futu_check.py — both still depend on live/moving data (today's SPX close,
or an options quota this account doesn't have) and have no fixed historical
fixture yet. That is a known, disclosed gap, not silently ignored.

Run:
    python3 test_engine_fixtures.py
Exits 0 and prints "ALL PASS" if everything matches; otherwise prints each
failure and exits 1.
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

import yfinance as yf
from indicators import compute_indicators
from regime_vote import compute_regime
from bias_engine import adjust_bias
from rr_gate import compute_rr, check_gate, check_entry_distance_invariant

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures_LITE_2026-07-17.json")

failures = []


def check(name, actual, expected, tol=0.005):
    """
    2026-07-23 tightened from tol=0.05 (evidence-dialogue-loop review, round 2): the
    fixture stores round(x, 2) output re-derived from the SAME deterministic function
    on the SAME frozen historical data — a real match should be bit-exact modulo float
    noise. 0.05 was loose enough to silently pass a genuine 2nd-decimal regression
    (e.g. atr14 quietly drifting from 73.10 to 73.13). 0.005 = half the rounding
    granularity: tight enough to catch that, loose enough to absorb float-repr noise.

    isinstance ordering fixed same review: `bool` is a subclass of `int` in Python, so
    `isinstance(True, int)` is True — the old `isinstance(expected, float) or
    isinstance(expected, int)` check silently routed booleans through the NUMERIC
    tolerance branch instead of exact equality. It happened to produce the right
    answer every time so far (True==1, False==0, and no case landed exactly on the
    tol boundary), which is accidental correctness, not correct-by-design — explicit
    bool check now comes first so this stops being luck.
    """
    if isinstance(expected, bool):
        ok = actual == expected
    elif isinstance(expected, (float, int)):
        ok = abs(actual - expected) <= tol
    else:
        ok = actual == expected
    status = "PASS" if ok else "FAIL"
    print(f"{status}: {name}" + ("" if ok else f" — expected {expected}, got {actual}"))
    if not ok:
        failures.append(name)


def main():
    with open(FIXTURE_PATH) as f:
        fx = json.load(f)

    anchor_date = fx["_meta"]["anchor_date"]
    ticker = fx["_meta"]["ticker"]
    period = fx["_meta"]["fetch_period_used"]

    print(f"=== indicators.py + regime_vote.py vs {ticker} frozen at {anchor_date} ===")
    df = yf.Ticker(ticker).history(period=period, interval="1d")
    df_frozen = df[df.index <= anchor_date]
    if len(df_frozen) < 200:
        print(f"FAIL: fixture setup — only {len(df_frozen)} rows before {anchor_date}, need >=200")
        failures.append("fixture_data_availability")
    else:
        ind = compute_indicators(df_frozen)
        for key, expected in fx["indicators"].items():
            if key == "macd_hist_last5":
                for i, (a, e) in enumerate(zip(ind[key], expected)):
                    check(f"indicators.macd_hist_last5[{i}]", a, e)
            else:
                check(f"indicators.{key}", ind[key], expected)

        reg = compute_regime(df_frozen)
        for key, expected in fx["regime"].items():
            if key == "votes":
                check("regime.votes.TREND", reg["votes"]["TREND"], expected["TREND"], tol=0)
                check("regime.votes.RANGE", reg["votes"]["RANGE"], expected["RANGE"], tol=0)
            else:
                check(f"regime.{key}", reg[key], expected)

    print("\n=== bias_engine.py ===")
    for case in fx["bias_cases"]:
        final_bias, note, _ = adjust_bias(case["initial_bias"], case["broad"], case["sector"])
        check(f"bias({case['initial_bias']}/{case['broad']}/{case['sector']}).final",
              final_bias, case["expected_final"], tol=0)
        note_is_null = note is None
        check(f"bias({case['initial_bias']}/{case['broad']}/{case['sector']}).note_is_null",
              note_is_null, case["expected_note_is_null"], tol=0)

    print("\n=== rr_gate.py (rr + gate) ===")
    for case in fx["rr_cases"]:
        rr = compute_rr(case["entry"], case["stop"], case["target"])
        check(f"rr({case['entry']}/{case['stop']}/{case['target']})", rr, case["expected_rr"])
        passed, _ = check_gate(rr, case["family"])
        check(f"gate({case['family']}, rr={rr})", passed, case["expected_gate_pass"], tol=0)

    print("\n=== rr_gate.py (entry-distance invariant) ===")
    for case in fx["invariant_cases"]:
        result = check_entry_distance_invariant(
            case["entry"], case["current_price"], case["atr14"], case["status"])
        check(f"invariant(status={case['status']}).applicable",
              result["applicable"], case["expected_applicable"], tol=0)
        if case["expected_applicable"]:
            check(f"invariant(status={case['status']}).pass",
                  result["pass"], case["expected_pass"], tol=0)

    print("\n" + "=" * 40)
    if failures:
        print(f"FAILED: {len(failures)} check(s) — {failures}")
        sys.exit(1)
    else:
        print("ALL PASS")
        sys.exit(0)


if __name__ == "__main__":
    main()
