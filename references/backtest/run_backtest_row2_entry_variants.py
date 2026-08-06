#!/opt/miniconda3/bin/python3
"""
MATS Backtest — Row 2 entry-location variants (option A).

User's real problem: not "hard to operate" — Row 2 breakout LOSES money
(a 20%+ drawdown on LITE). This tests whether changing WHERE/HOW you enter
the breakout fixes the expectancy.

MODELING CORRECTION vs run_backtest_row2_tightbase.py: SKILL.md Row 2 is
  Entry = pivot_recent (+1 tick)      -- a LIMIT at the pivot
  Stop  = pivot_recent - 0.5*ATR14
so stop distance is ALWAYS 0.5*ATR (risk is pure ATR), and entry ≈ pivot.
The earlier script used entry = breakout-bar close, which inflated the stop
distance and the 2R target. This one models entry = pivot, matching the rule.

Headline metric = EXPECTANCY in R per trade (not just win rate):
  target_first -> +2R ; stop_first -> -1R ; neither in H bars ->
  mark-to-market (close[t+H]-entry)/stop_dist. Positive avg R = profitable.

Variants (all: entry=pivot, stop=pivot-0.5ATR, target=entry+2*stop_dist=pivot+1*ATR):
  V0  baseline   chase cap 5%   enter on the breakout cross
  V1  chase 3%   reject breakouts that closed >3% above pivot (gap-aways)
  V2  chase 2%   reject breakouts that closed >2% above pivot
  V3  retest     after breakout+confirm, wait up to 5 bars for a pullback
                 that touches the pivot again, enter at pivot then (skip if
                 no retest) -- the "don't buy the spike, buy the retest" idea
Also reports per-trade risk% (0.5*ATR/pivot) and MAE (接火棒 depth).

Run: python3 run_backtest_row2_entry_variants.py
"""
import sys, os, json
import numpy as np
import pandas as pd
import yfinance as yf
import pandas_ta as ta

sys.path.insert(0, os.path.dirname(__file__))
DATASET_PATH = os.path.join(os.path.dirname(__file__), "dataset.json")
OUT_PATH = os.path.join(os.path.dirname(__file__), "results_row2_entry_variants.json")
H = 10
RETEST_WAIT = 5


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


def outcome_from(entry, stop, target, high, low, close, start, horizon):
    """Walk forward [start, start+horizon); return (R, mae_pct)."""
    stop_dist = entry - stop
    end = min(start + horizon, len(close))
    mae = 0.0
    for j in range(start, end):
        mae = min(mae, low[j] / entry - 1.0)
        if low[j] <= stop:
            return -1.0, mae
        if high[j] >= target:
            return 2.0, mae
    # mark-to-market
    return (close[end - 1] - entry) / stop_dist, mae


def scan(df):
    """Yield breakout events with per-variant results."""
    close = df["Close"].values; high = df["High"].values
    low = df["Low"].values; vol = df["Volume"].values
    atr = ta.atr(df["High"], df["Low"], df["Close"], length=14).values
    avgvol = pd.Series(vol).rolling(20).mean().values
    n = len(df)
    evs = []
    for i in range(20, n - H - RETEST_WAIT):
        a = atr[i]
        if not np.isfinite(a) or a <= 0 or not np.isfinite(avgvol[i]) or avgvol[i] <= 0:
            continue
        pivot = high[i - 10:i].max()
        prev_close = close[i - 1]; c = close[i]
        if not (prev_close <= pivot < c and vol[i] >= 1.5 * avgvol[i]):
            continue
        close_above_pct = (c - pivot) / pivot * 100
        entry = pivot
        stop = pivot - 0.5 * a
        target = entry + 2 * (entry - stop)
        risk_pct = (entry - stop) / entry * 100

        ev = {"close_above_pct": float(close_above_pct), "risk_pct": float(risk_pct)}
        # V0/V1/V2: enter at pivot on this bar; chase cap filters by close_above
        R, mae = outcome_from(entry, stop, target, high, low, close, i + 1, H)
        ev["direct"] = {"R": float(R), "mae": float(mae)}

        # Interpretation B — "confirm then enter": enter at the breakout bar's
        # CLOSE (what a human does after seeing the close-above-on-volume
        # confirmation), stop still pivot-0.5ATR, target = entry + 2*stop_dist.
        entryB = c
        stopB = pivot - 0.5 * a
        if entryB - stopB > 0:
            targetB = entryB + 2 * (entryB - stopB)
            Rb, maeb = outcome_from(entryB, stopB, targetB, high, low, close, i + 1, H)
            ev["confirm_close"] = {"R": float(Rb), "mae": float(maeb),
                                    "risk_pct": float((entryB - stopB) / entryB * 100)}
        # Interpretation B' — enter at NEXT day's open (realistic for a
        # daily-close-confirmed signal you act on the following session).
        if i + 1 < n:
            entryO = df["Open"].values[i + 1]
            stopO = pivot - 0.5 * a
            if entryO - stopO > 0:
                targetO = entryO + 2 * (entryO - stopO)
                Ro, maeo = outcome_from(entryO, stopO, targetO, high, low, close, i + 1, H)
                ev["next_open"] = {"R": float(Ro), "mae": float(maeo),
                                    "risk_pct": float((entryO - stopO) / entryO * 100)}

        # V3 retest: need a pullback to pivot within RETEST_WAIT bars, then enter at pivot
        ev["retest"] = None
        for k in range(i + 1, i + 1 + RETEST_WAIT):
            if low[k] <= pivot:  # touched pivot again
                Rr, maer = outcome_from(entry, stop, target, high, low, close, k + 1, H)
                ev["retest"] = {"R": float(Rr), "mae": float(maer)}
                break
        evs.append(ev)
    return evs


def summ(rows, label):
    if not rows:
        return {"label": label, "n": 0}
    Rs = [r["R"] for r in rows]; maes = [r["mae"] for r in rows]
    wins = sum(1 for r in rows if r["R"] == 2.0)
    losses = sum(1 for r in rows if r["R"] == -1.0)
    return {
        "label": label, "n": len(rows),
        "expectancy_R": round(float(np.mean(Rs)), 4),
        "win_2R_rate": round(wins / len(rows), 4),
        "stop_rate": round(losses / len(rows), 4),
        "median_mae": round(float(np.median(maes)), 4),
        "avg_risk_pct": round(float(np.mean([r.get("risk_pct", np.nan) for r in rows])), 3),
    }


def main():
    with open(DATASET_PATH) as f:
        ds = json.load(f)
    tickers = sorted({s["ticker"] for s in ds["samples"]})
    data = fetch_all(tickers)
    events = []
    for t, df in data.items():
        for ev in scan(df):
            events.append(ev)

    # attach risk_pct into each outcome record for reporting
    def with_risk(subset_key, filt=None):
        out = []
        for e in events:
            if filt and not filt(e):
                continue
            rec = e.get(subset_key)
            if rec is None:
                continue
            out.append({**rec, "risk_pct": e["risk_pct"]})
        return out

    rows = []
    rows.append(summ(with_risk("direct"), "V0 baseline: LIMIT at pivot (interp A)"))
    rows.append(summ(with_risk("direct", lambda e: e["close_above_pct"] <= 3.0), "V1 limit@pivot, chase 3%"))
    rows.append(summ(with_risk("direct", lambda e: e["close_above_pct"] <= 2.0), "V2 limit@pivot, chase 2%"))
    rows.append(summ(with_risk("direct", lambda e: e["close_above_pct"] <= 1.0), "V2b limit@pivot, chase 1%"))
    rows.append(summ(with_risk("retest"), "V3 break-and-retest (pullback to pivot)"))
    # entry-interpretation comparison, chase-cap 5% population
    rows.append(summ([{**e["confirm_close"]} for e in events if e.get("confirm_close")],
                     "B  enter at breakout CLOSE (confirm-then-market, chase5%)"))
    rows.append(summ([{**e["confirm_close"]} for e in events
                      if e.get("confirm_close") and e["close_above_pct"] <= 5.0],
                     "B  enter at CLOSE, only if close<=5% over pivot"))
    rows.append(summ([{**e["next_open"]} for e in events if e.get("next_open")],
                     "B' enter at NEXT day OPEN"))

    out = {"_meta": {"n_events": len(events), "horizon": H, "retest_wait": RETEST_WAIT,
                     "note": "entry=pivot model (corrected). expectancy_R>0 = profitable. "
                             "target_first=+2R, stop_first=-1R, else mark-to-market. raw stats, no pass/fail."},
           "comparison": rows}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    with open(OUT_PATH, "w") as f:
        json.dump({"summary": out, "n_events": len(events)}, f, indent=2)
    print(f"\n-> {OUT_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
