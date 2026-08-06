#!/opt/miniconda3/bin/python3
"""
MATS Backtest — Row 2 breakout: current pivot vs tight-base-gated pivot.

Question (user, 2026-07-23): the current Row 2 pivot = 10-bar high with NO
consolidation/tightness check, so it fires "breakouts" where price recovered
to a distant prior high (extended, buys into profit-taking). Literature
(O'Neil/Minervini) requires the pivot to be the top of a TIGHT base. Does
adding a tightness gate actually improve breakout quality on our data?

Method — event-scan (not single-snapshot, which gave only n=8):
  For every ticker in dataset.json, over its full fetched history, find every
  BREAKOUT EVENT: today's Close crosses above the 10-bar pivot (max High of
  the 10 completed bars before today), with volume >= 1.5x its 20d average,
  and within the chase cap (Close <= pivot * 1.05). This is exactly the live
  Row-2 trigger condition, scanned through time.

  For each event record base geometry:
    base_low  = min Low of the 10 bars forming the pivot
    span_atr  = (pivot - base_low) / atr14      (base height in ATR units)
    span_pct  = (pivot - base_low) / pivot * 100 (base height in %)

  Forward outcome over the next H=10 sessions (target-agnostic, so the
  entry-LOCATION quality is measured, not a target-selection artifact):
    fwd_ret_10 = close[t+10]/entry - 1
    mae_10     = min(low[t+1..t+10])/entry - 1   (max adverse excursion =
                 the "接火棒" drawdown depth the user is complaining about)
    win_2R     = did price reach entry + 2*stop_dist before hitting
                 stop = pivot - 0.5*atr14, walking bars forward (H=10)

  Then compare the SAME events, unfiltered vs. gated by tightness thresholds,
  in BOTH ATR-units and %-units, so we can see which parameterization (if
  either) raises win rate / cuts drawdown. No pass/fail declared.

Run: python3 run_backtest_row2_tightbase.py
"""
import sys, os, json
import numpy as np
import pandas as pd
import yfinance as yf
import pandas_ta as ta

sys.path.insert(0, os.path.dirname(__file__))
DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "results_row2_tightbase.json")
H = 10  # forward horizon in sessions


def fetch_all(tickers):
    print(f"fetching {len(tickers)} tickers...", file=sys.stderr)
    data = yf.download(tickers, period="10y", interval="1d", group_by="ticker",
                        threads=True, progress=False, auto_adjust=True)
    out = {}
    for t in tickers:
        try:
            df = data[t].dropna(how="all") if len(tickers) > 1 else data.dropna(how="all")
            if df is not None and len(df) > 300:
                out[t] = df
        except Exception:
            pass
    return out


def scan_ticker(df):
    """Return list of breakout-event dicts for one ticker."""
    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    vol = df["Volume"].values
    atr = ta.atr(df["High"], df["Low"], df["Close"], length=14).values
    avgvol = pd.Series(vol).rolling(20).mean().values

    events = []
    n = len(df)
    for i in range(20, n - H):
        a = atr[i]
        if not np.isfinite(a) or a <= 0 or not np.isfinite(avgvol[i]) or avgvol[i] <= 0:
            continue
        pivot = high[i - 10:i].max()          # 10 completed bars before today
        base_low = low[i - 10:i].min()
        prev_close = close[i - 1]
        c = close[i]
        # Row-2 trigger: cross above pivot today, on volume, within chase cap
        crossed = prev_close <= pivot < c
        vol_ok = vol[i] >= 1.5 * avgvol[i]
        chase_ok = c <= pivot * 1.05
        if not (crossed and vol_ok and chase_ok):
            continue

        entry = c
        stop = pivot - 0.5 * a
        stop_dist = entry - stop
        if stop_dist <= 0:
            continue
        target = entry + 2 * stop_dist

        # forward walk for 2R outcome
        outcome = "undecided"
        for j in range(i + 1, i + 1 + H):
            if low[j] <= stop:
                outcome = "stop_first"; break
            if high[j] >= target:
                outcome = "target_first"; break
        fwd_ret = close[i + H] / entry - 1.0
        mae = low[i + 1:i + 1 + H].min() / entry - 1.0

        events.append({
            "span_atr": float((pivot - base_low) / a),
            "span_pct": float((pivot - base_low) / pivot * 100),
            "outcome": outcome,
            "fwd_ret_10": float(fwd_ret),
            "mae_10": float(mae),
        })
    return events


def summarize(events, label):
    n = len(events)
    if n == 0:
        return {"label": label, "n": 0}
    decided = [e for e in events if e["outcome"] in ("target_first", "stop_first")]
    wins = sum(1 for e in decided if e["outcome"] == "target_first")
    return {
        "label": label,
        "n_events": n,
        "win_2R": round(wins / len(decided), 4) if decided else None,
        "n_decided": len(decided),
        "avg_fwd_ret_10": round(float(np.mean([e["fwd_ret_10"] for e in events])), 4),
        "median_fwd_ret_10": round(float(np.median([e["fwd_ret_10"] for e in events])), 4),
        "avg_mae_10": round(float(np.mean([e["mae_10"] for e in events])), 4),
        "median_mae_10": round(float(np.median([e["mae_10"] for e in events])), 4),
    }


def main():
    with open(DATASET_PATH) as f:
        ds = json.load(f)
    tickers = sorted({s["ticker"] for s in ds["samples"]})
    data = fetch_all(tickers)

    all_events = []
    for t, df in data.items():
        all_events.extend(scan_ticker(df))

    rows = []
    rows.append(summarize(all_events, "BASELINE (no tightness gate)"))
    for k in (1.5, 2.5, 4.0):
        rows.append(summarize([e for e in all_events if e["span_atr"] <= k],
                              f"gate: base span <= {k} x ATR"))
    for p in (8.0, 12.0, 20.0):
        rows.append(summarize([e for e in all_events if e["span_pct"] <= p],
                              f"gate: base depth <= {p}%"))

    out = {"_meta": {"n_total_events": len(all_events), "horizon_sessions": H,
                     "note": "raw stats only, no pass/fail. mae_10 = drawdown depth after entry "
                             "(the 接火棒 pain). All events are live Row-2 triggers scanned through time."},
           "comparison": rows}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    with open(OUT_PATH, "w") as f:
        json.dump({"summary": out, "events": all_events}, f, indent=2)
    print(f"\nfull results -> {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
