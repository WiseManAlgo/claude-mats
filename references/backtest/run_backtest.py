#!/opt/miniconda3/bin/python3
"""
MATS Backtest — run_backtest.py (see ENGINE_ARCHITECTURE.md "Backtest process")

Runs the three Phase 2 candidate mechanisms against the frozen dataset.json
(sampled by sample_dataset.py) and reports RAW stats -- it does NOT declare
pass/fail. Per ENGINE_ARCHITECTURE.md: "Pass/fail threshold: set by the user
at the time each mechanism's backtest is designed." This script produces the
numbers; the user decides what counts as good enough.

Mechanisms tested:
  1. S/R engine: candidate (sr_levels_candidate.candidate_levels -- Step
     4.1-4.4: swing points + polarity flip + confluence merge + BOLL/intraday)
     vs baseline (structural swing points only, no flip/merge) -- "did S1
     hold as support / R1 hold as resistance over the next 5 sessions".
  2. Row 1/Row 2 entry-anchor logic: for TRIGGERED signals, did price hit T1
     before Stop within the post-window buffer.
  3. Mean-Reversion R/R gate threshold (0.5): for TRIGGERED Row 3 signals,
     does the computed R/R actually correlate with the trade winning (T1
     before Stop) -- i.e. is 0.5 doing real separating work.

Method note: each ticker/window's forward-looking evaluation uses ONLY the
BUFFER_DAYS (15 trading days) of data sample_dataset.py already reserved
after each window's end_date -- no additional live fetch needed, and no
lookahead beyond what was designed in for exactly this purpose.

Run:
    python3 run_backtest.py
Writes results_phase2_v1.json in this directory and prints a summary.
"""
import sys
import os
import json
import yfinance as yf

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "engine"))

from sr_levels_candidate import candidate_levels, baseline_levels
from row_engine_candidate import compute_rows
from rr_gate import compute_rr, check_gate

DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "results_phase2_v1.json")
HOLD_CHECK_SESSIONS = 5   # "next 3-5 sessions" per ENGINE_ARCHITECTURE.md Method


def fetch_all(tickers):
    print(f"fetching {len(tickers)} unique tickers...", file=sys.stderr)
    data = yf.download(tickers, period="10y", interval="1d", group_by="ticker",
                        threads=True, progress=False, auto_adjust=True)
    out = {}
    for t in tickers:
        try:
            df = data[t].dropna(how="all") if len(tickers) > 1 else data.dropna(how="all")
            if df is not None and not df.empty:
                out[t] = df
        except Exception as e:
            print(f"  SKIP {t}: {e}", file=sys.stderr)
    return out


def score_sr(df_hist200, df_fwd):
    cand = candidate_levels(df_hist200)
    base = baseline_levels(df_hist200)
    out = {"candidate": {}, "baseline": {}}

    fwd_closes = df_fwd["Close"].iloc[:HOLD_CHECK_SESSIONS]
    for name, levels in [("candidate", cand), ("baseline", base)]:
        s1, r1 = levels.get("S1"), levels.get("R1")
        rec = {}
        if s1 is not None and len(fwd_closes) > 0:
            rec["s1_evaluated"] = True
            rec["s1_held"] = bool((fwd_closes >= s1).all())
        else:
            rec["s1_evaluated"] = False
        if r1 is not None and len(fwd_closes) > 0:
            rec["r1_evaluated"] = True
            rec["r1_held"] = bool((fwd_closes <= r1).all())
        else:
            rec["r1_evaluated"] = False
        out[name] = rec
    return out


def score_trade(entry, stop, t1, df_fwd):
    """Walk forward bars; return 'target_first', 'stop_first', or 'undetermined'."""
    if t1 is None or df_fwd.empty:
        return "undetermined", None
    is_long = t1 > entry
    for _, row in df_fwd.iterrows():
        hi, lo = float(row["High"]), float(row["Low"])
        if is_long:
            stop_hit = lo <= stop
            target_hit = hi >= t1
        else:
            stop_hit = hi >= stop
            target_hit = lo <= t1
        if stop_hit and target_hit:
            return "same_bar_ambiguous", None
        if stop_hit:
            return "stop_first", None
        if target_hit:
            return "target_first", None
    return "undetermined", None


def main():
    with open(DATASET_PATH) as f:
        ds = json.load(f)

    tickers = sorted({s["ticker"] for s in ds["samples"]})
    all_data = fetch_all(tickers)

    sr_results = []
    row1_results = []
    row2_results = []
    row3_results = []

    for s in ds["samples"]:
        t = s["ticker"]
        if t not in all_data:
            continue
        df = all_data[t]
        for w in s["windows"]:
            end_date = w["end_date"]
            df_hist = df[df.index <= end_date]
            if len(df_hist) < 200:
                continue
            df_hist200 = df_hist.tail(200)
            df_fwd = df[df.index > end_date]
            if df_fwd.empty:
                continue

            case_id = f"{t}/{w['window_id']}"

            try:
                sr_results.append({"case": case_id, **score_sr(df_hist200, df_fwd)})
            except Exception as e:
                sr_results.append({"case": case_id, "error": str(e)})

            try:
                sr_cand = candidate_levels(df_hist200)
                rows = compute_rows(df_hist200, sr_cand)
            except Exception as e:
                continue

            r1 = rows["row1"]
            if r1["status"] == "TRIGGERED" and r1["t1"] is not None:
                outcome, _ = score_trade(r1["entry"], r1["stop"], r1["t1"], df_fwd)
                rr = compute_rr(r1["entry"], r1["stop"], r1["t1"])
                gate_pass, _ = check_gate(rr, "pullback")
                row1_results.append({"case": case_id, "rr": rr, "gate_pass": gate_pass, "outcome": outcome})

            r2 = rows["row2"]
            if r2["status"] == "TRIGGERED" and r2["t1"] is not None:
                outcome, _ = score_trade(r2["entry"], r2["stop"], r2["t1"], df_fwd)
                rr = compute_rr(r2["entry"], r2["stop"], r2["t1"])
                gate_pass, _ = check_gate(rr, "breakout")
                row2_results.append({"case": case_id, "rr": rr, "gate_pass": gate_pass, "outcome": outcome})

            r3 = rows["row3"]
            if r3["status"] == "TRIGGERED" and r3["t1"] is not None:
                outcome, _ = score_trade(r3["entry"], r3["stop"], r3["t1"], df_fwd)
                rr = compute_rr(r3["entry"], r3["stop"], r3["t1"])
                gate_pass, _ = check_gate(rr, "meanrev")
                row3_results.append({"case": case_id, "rr": rr, "gate_pass": gate_pass, "outcome": outcome})

    def sr_summary():
        cand_eval_s1 = [r["candidate"]["s1_held"] for r in sr_results if r.get("candidate", {}).get("s1_evaluated")]
        base_eval_s1 = [r["baseline"]["s1_held"] for r in sr_results if r.get("baseline", {}).get("s1_evaluated")]
        cand_eval_r1 = [r["candidate"]["r1_held"] for r in sr_results if r.get("candidate", {}).get("r1_evaluated")]
        base_eval_r1 = [r["baseline"]["r1_held"] for r in sr_results if r.get("baseline", {}).get("r1_evaluated")]
        def rate(lst):
            return {"n": len(lst), "hold_rate": round(sum(lst) / len(lst), 4) if lst else None}
        return {
            "candidate_S1_support_hold": rate(cand_eval_s1),
            "baseline_S1_support_hold": rate(base_eval_s1),
            "candidate_R1_resistance_hold": rate(cand_eval_r1),
            "baseline_R1_resistance_hold": rate(base_eval_r1),
        }

    def row_summary(results):
        n = len(results)
        target_first = sum(1 for r in results if r["outcome"] == "target_first")
        stop_first = sum(1 for r in results if r["outcome"] == "stop_first")
        undetermined = n - target_first - stop_first
        gate_pass = [r for r in results if r["gate_pass"]]
        gate_fail = [r for r in results if not r["gate_pass"]]
        def win_rate(subset):
            decided = [r for r in subset if r["outcome"] in ("target_first", "stop_first")]
            wins = sum(1 for r in decided if r["outcome"] == "target_first")
            return {"n_decided": len(decided), "win_rate": round(wins / len(decided), 4) if decided else None}
        return {
            "n_triggered": n,
            "target_first": target_first, "stop_first": stop_first, "undetermined": undetermined,
            "win_rate_all_decided": win_rate(results),
            "win_rate_gate_pass": win_rate(gate_pass),
            "win_rate_gate_fail": win_rate(gate_fail),
            "n_gate_pass": len(gate_pass), "n_gate_fail": len(gate_fail),
        }

    summary = {
        "_meta": {
            "dataset_version": ds["_meta"]["dataset_version"],
            "n_samples": len(ds["samples"]),
            "hold_check_sessions": HOLD_CHECK_SESSIONS,
            "note": "raw stats only -- no pass/fail declared, see ENGINE_ARCHITECTURE.md Backtest process",
        },
        "sr_engine": sr_summary(),
        "row1_pullback": row_summary(row1_results),
        "row2_breakout": row_summary(row2_results),
        "row3_meanrev_gate_0.5": row_summary(row3_results),
    }

    out = {"summary": summary, "sr_results": sr_results,
           "row1_results": row1_results, "row2_results": row2_results, "row3_results": row3_results}
    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(json.dumps(summary, indent=2))
    print(f"\nfull results written to {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
