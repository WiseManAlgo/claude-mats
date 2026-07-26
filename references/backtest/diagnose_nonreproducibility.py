#!/opt/miniconda3/bin/python3
"""
Diagnose WHY run_backtest_ablation.py is not bit-reproducible.
NO speculation: fetch the data TWICE, save both raw OHLC snapshots to disk,
diff every ticker/row/column, and pinpoint the exact case(s) whose S1/R1
hold-verdict flipped between the two fetches — then show the actual numbers
that changed. If nothing in the OHLC changed, that rules out the data and
points at the code (RNG, ordering, float nondeterminism) instead.
"""
import sys, os, json, pickle
import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, os.path.dirname(__file__))
from sr_levels_candidate import candidate_levels

DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset.json")
SNAP_A = os.path.join(os.path.dirname(__file__), "_ohlc_snapshot_A.pkl")
SNAP_B = os.path.join(os.path.dirname(__file__), "_ohlc_snapshot_B.pkl")
HOLD_CHECK_SESSIONS = 5


def fetch(tickers):
    data = yf.download(tickers, period="10y", interval="1d", group_by="ticker",
                        threads=True, progress=False, auto_adjust=True)
    out = {}
    for t in tickers:
        try:
            df = data[t].dropna(how="all")
            if df is not None and not df.empty:
                out[t] = df[["Open", "High", "Low", "Close"]].copy()
        except Exception:
            pass
    return out


def b_verdicts(snapshot, samples):
    """Config B (flip, no boll). Returns {case_id: (s1, r1, s1_held, r1_held)}."""
    res = {}
    for s in samples:
        t = s["ticker"]
        if t not in snapshot:
            continue
        df = snapshot[t]
        for w in s["windows"]:
            end_date = w["end_date"]
            df_hist = df[df.index <= end_date]
            if len(df_hist) < 200:
                continue
            df_hist200 = df_hist.tail(200)
            df_fwd = df[df.index > end_date]
            if df_fwd.empty:
                continue
            # candidate_levels needs Volume for nothing in flip/no-boll path; but bbands off
            lv = candidate_levels(df_hist200, include_flip=True, include_boll=False)
            fwd = df_fwd["Close"].iloc[:HOLD_CHECK_SESSIONS]
            s1, r1 = lv.get("S1"), lv.get("R1")
            s1_held = bool((fwd >= s1).all()) if s1 is not None else None
            r1_held = bool((fwd <= r1).all()) if r1 is not None else None
            res[f"{t}/{w['window_id']}"] = (s1, r1, s1_held, r1_held)
    return res


def main():
    with open(DATASET_PATH) as f:
        ds = json.load(f)
    samples = ds["samples"]
    tickers = sorted({s["ticker"] for s in samples})

    print("=== FETCH A ===", file=sys.stderr)
    snap_a = fetch(tickers)
    with open(SNAP_A, "wb") as f:
        pickle.dump(snap_a, f)
    print("=== FETCH B ===", file=sys.stderr)
    snap_b = fetch(tickers)
    with open(SNAP_B, "wb") as f:
        pickle.dump(snap_b, f)

    # 1) Diff the raw OHLC between the two fetches
    print("\n=== RAW OHLC DIFF (A vs B) ===")
    changed_tickers = {}
    for t in tickers:
        if t not in snap_a or t not in snap_b:
            print(f"  {t}: present in A={t in snap_a} B={t in snap_b} (skipped from one)")
            continue
        a, b = snap_a[t], snap_b[t]
        idx = a.index.intersection(b.index)
        a2, b2 = a.loc[idx], b.loc[idx]
        if len(a.index) != len(b.index):
            changed_tickers[t] = f"row count A={len(a.index)} B={len(b.index)}"
            continue
        diff = (a2 - b2).abs()
        max_diff = float(diff.max().max())
        if max_diff > 0:
            n_cells = int((diff > 0).sum().sum())
            changed_tickers[t] = f"max_cell_diff={max_diff:.6f}, {n_cells} cells changed"
    if changed_tickers:
        print(f"  {len(changed_tickers)} ticker(s) with OHLC differences:")
        for t, msg in changed_tickers.items():
            print(f"    {t}: {msg}")
    else:
        print("  NO OHLC differences between the two fetches — data is identical.")

    # 2) Verdict-level diff for config B
    va = b_verdicts(snap_a, samples)
    vb = b_verdicts(snap_b, samples)
    print("\n=== CONFIG B VERDICT DIFF ===")
    def rate(v, key_idx):
        vals = [x[key_idx] for x in v.values() if x[key_idx] is not None]
        return len(vals), (sum(vals) / len(vals) if vals else None)
    na_s1, ra_s1 = rate(va, 2); nb_s1, rb_s1 = rate(vb, 2)
    na_r1, ra_r1 = rate(va, 3); nb_r1, rb_r1 = rate(vb, 3)
    print(f"  A: S1 n={na_s1} rate={ra_s1:.4f} | R1 n={na_r1} rate={ra_r1:.4f}")
    print(f"  B: S1 n={nb_s1} rate={rb_s1:.4f} | R1 n={nb_r1} rate={rb_r1:.4f}")

    print("\n  Cases whose R1 verdict FLIPPED between fetches:")
    flipped = 0
    for case in sorted(set(va) | set(vb)):
        xa, xb = va.get(case), vb.get(case)
        if xa is None or xb is None:
            print(f"    {case}: present A={xa is not None} B={xb is not None}")
            flipped += 1
            continue
        if xa[3] != xb[3]:  # r1_held differs
            flipped += 1
            print(f"    {case}: R1 held {xa[3]}->{xb[3]} | R1 level A={xa[1]} B={xb[1]}")
    if flipped == 0:
        print("    none — R1 verdicts identical (then the earlier nonreproducibility was elsewhere)")
    print(f"\n  total flipped: {flipped}")


if __name__ == "__main__":
    main()
