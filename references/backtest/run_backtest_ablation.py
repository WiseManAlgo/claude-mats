#!/opt/miniconda3/bin/python3
"""
MATS Backtest — run_backtest_ablation.py

Follow-up to run_backtest.py's first honest result: after fixing the
today's-H/L fallback bug (see sr_levels_candidate.py docstring), candidate
S1/R1 hold rates (79.2%/43.1%) still trail baseline (93.7%/76.7%). Rather
than guess again which piece is responsible, this isolates each addition
on top of the same baseline:

  A) baseline        -- structural swing points only (4.1), no flip, no BOLL
  B) +flip           -- 4.1 + Polarity Flip (4.2), no BOLL
  C) +flip+BOLL      -- full candidate (4.1+4.2+4.3 minus Options
                         Wall/analyst target, same as run_backtest.py's
                         "candidate")

Same dataset, same windows, same hold-check method (5 sessions) as
run_backtest.py -- only the candidate construction varies, so any
difference in hold rate between A/B/C is attributable to the specific
mechanism added at that step, not to a different sample or scoring rule.

Run:
    python3 run_backtest_ablation.py
"""
import sys
import os
import json
import yfinance as yf

sys.path.insert(0, os.path.dirname(__file__))
from sr_levels_candidate import candidate_levels

DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset.json")
HOLD_CHECK_SESSIONS = 5


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
        except Exception:
            pass
    return out


def eval_config(df_hist200, df_fwd, include_flip, include_boll):
    levels = candidate_levels(df_hist200, include_flip=include_flip, include_boll=include_boll)
    fwd_closes = df_fwd["Close"].iloc[:HOLD_CHECK_SESSIONS]
    out = {}
    s1, r1 = levels.get("S1"), levels.get("R1")
    if s1 is not None and len(fwd_closes) > 0:
        out["s1_evaluated"] = True
        out["s1_held"] = bool((fwd_closes >= s1).all())
    else:
        out["s1_evaluated"] = False
    if r1 is not None and len(fwd_closes) > 0:
        out["r1_evaluated"] = True
        out["r1_held"] = bool((fwd_closes <= r1).all())
    else:
        out["r1_evaluated"] = False
    return out


def main():
    with open(DATASET_PATH) as f:
        ds = json.load(f)

    tickers = sorted({s["ticker"] for s in ds["samples"]})
    all_data = fetch_all(tickers)

    configs = {
        "A_structural_only": {"include_flip": False, "include_boll": False},
        "B_plus_flip": {"include_flip": True, "include_boll": False},
        "C_plus_flip_boll": {"include_flip": True, "include_boll": True},
    }
    results = {name: [] for name in configs}

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
            for name, cfg in configs.items():
                try:
                    results[name].append(eval_config(df_hist200, df_fwd, **cfg))
                except Exception as e:
                    results[name].append({"error": str(e)})

    def rate(lst):
        return {"n": len(lst), "hold_rate": round(sum(lst) / len(lst), 4) if lst else None}

    summary = {}
    for name, recs in results.items():
        s1_vals = [r["s1_held"] for r in recs if r.get("s1_evaluated")]
        r1_vals = [r["r1_held"] for r in recs if r.get("r1_evaluated")]
        summary[name] = {
            "S1_support_hold": rate(s1_vals),
            "R1_resistance_hold": rate(r1_vals),
        }

    print(json.dumps({"_meta": {"note": "ablation -- same dataset/scoring as run_backtest.py, "
                                          "only candidate construction varies"},
                       "results": summary}, indent=2))


if __name__ == "__main__":
    main()
