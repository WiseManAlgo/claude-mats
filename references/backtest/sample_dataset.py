#!/opt/miniconda3/bin/python3
"""
MATS Backtest — sample_dataset.py (see ENGINE_ARCHITECTURE.md "Backtest process")

Generates backtest/dataset.json ONCE. Per the architecture doc: stratified by
sector (12 SECTOR_ETF buckets from market_context.py, + 1 crypto bucket) x
volatility tercile (low/med/high, global cutoffs across the whole universe),
target ~3-4 tickers per (sector x tier) cell, 2 non-overlapping 200-trading-day
windows per ticker from different points in history.

Determinism: random.seed(SEED) fixed below. Universe lists are hard-coded
(not fetched from a live index membership API) so the candidate pool itself
does not silently drift between runs.

DO NOT re-run this after dataset.json has been used for a backtest to get a
"better" sample — that defeats stratification's purpose. Bump DATASET_VERSION
and keep the old file if a real re-sample is ever needed.

Run:
    python3 sample_dataset.py
Writes backtest/dataset.json.
"""
import json
import os
import random
import sys
import numpy as np
import pandas as pd
import yfinance as yf

SEED = 20260723
DATASET_VERSION = "v1"
OUT_PATH = os.path.join(os.path.dirname(__file__), "dataset.json")

TARGET_PER_CELL = 4
BUFFER_DAYS = 15       # trading days left after each window's end, reserved for outcome scoring
WINDOW_LEN = 200
GAP_DAYS = 400         # rows between the two windows' end-points, guarantees non-overlap + different-year spread
FETCH_PERIOD = "8y"

# Same 12 sector buckets as engine/market_context.py's SECTOR_ETF, + 1 crypto bucket.
UNIVERSE = {
    "Technology": ["MSFT", "AAPL", "ORCL", "ADBE", "CRM", "INTU", "IBM", "NOW", "ADSK", "PANW", "CSCO", "ACN"],
    "Semiconductors": ["NVDA", "AVGO", "TXN", "QCOM", "AMD", "MU", "MRVL", "ON", "LRCX", "KLAC", "ADI", "MCHP"],
    "Communication Services": ["GOOGL", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS", "EA", "WBD", "OMC", "MTCH"],
    "Consumer Discretionary": ["AMZN", "TSLA", "HD", "MCD", "NKE", "LOW", "SBUX", "BKNG", "TJX", "MAR", "GM", "F"],
    "Consumer Staples": ["PG", "KO", "PEP", "WMT", "COST", "CL", "MO", "PM", "MDLZ", "KMB", "GIS", "STZ"],
    "Healthcare": ["UNH", "JNJ", "LLY", "PFE", "ABBV", "MRK", "TMO", "ABT", "DHR", "BMY", "AMGN", "GILD"],
    "Financials": ["JPM", "BAC", "WFC", "GS", "MS", "C", "SCHW", "BLK", "AXP", "USB", "PNC", "TFC"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "PXD", "MPC", "PSX", "VLO", "OXY", "WMB", "KMI"],
    "Industrials": ["BA", "CAT", "HON", "UNP", "GE", "LMT", "RTX", "UPS", "DE", "MMM", "GD", "NOC"],
    "Materials": ["LIN", "APD", "ECL", "SHW", "NEM", "FCX", "DOW", "DD", "NUE", "VMC", "MLM", "ALB"],
    "Real Estate": ["PLD", "AMT", "EQIX", "PSA", "O", "SPG", "DLR", "WELL", "AVB", "EQR", "VTR", "ESS"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "EXC", "SRE", "XEL", "ED", "PEG", "WEC", "ES"],
    "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD", "XRP-USD", "ADA-USD", "AVAX-USD",
               "DOGE-USD", "DOT-USD", "LINK-USD", "MATIC-USD", "LTC-USD", "TRX-USD", "ATOM-USD", "NEAR-USD"],
}


def _atr14_pct(df):
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean().iloc[-1]
    last_close = close.iloc[-1]
    return float(atr14 / last_close * 100)


def fetch_all():
    """Returns {ticker: (sector, df)} for every ticker in UNIVERSE, skipping fetch failures."""
    out = {}
    for sector, tickers in UNIVERSE.items():
        print(f"fetching {sector} ({len(tickers)} tickers)...", file=sys.stderr)
        data = yf.download(tickers, period=FETCH_PERIOD, interval="1d", group_by="ticker",
                            threads=True, progress=False, auto_adjust=True)
        for t in tickers:
            try:
                df = data[t].dropna(how="all") if len(tickers) > 1 else data.dropna(how="all")
                if df is None or df.empty or len(df) < (2 * WINDOW_LEN + GAP_DAYS + BUFFER_DAYS):
                    print(f"  SKIP {t}: insufficient history ({0 if df is None else len(df)} rows)", file=sys.stderr)
                    continue
                out[t] = (sector, df)
            except Exception as e:
                print(f"  SKIP {t}: {e}", file=sys.stderr)
    return out


def classify_tiers(atr_pcts):
    """Global tercile cutoffs across the whole fetched universe."""
    values = np.array(list(atr_pcts.values()))
    low_cut, high_cut = np.percentile(values, [33.33, 66.67])
    tiers = {}
    for t, v in atr_pcts.items():
        if v <= low_cut:
            tiers[t] = "low"
        elif v <= high_cut:
            tiers[t] = "med"
        else:
            tiers[t] = "high"
    return tiers, float(low_cut), float(high_cut)


def make_windows(df):
    """Two non-overlapping 200-trading-day windows, most-recent-first, with a
    scoring buffer left after each window's end. Returns list of 2 dicts."""
    n = len(df)
    end_b = n - 1 - BUFFER_DAYS
    start_b = end_b - (WINDOW_LEN - 1)
    end_a = end_b - GAP_DAYS
    start_a = end_a - (WINDOW_LEN - 1)

    idx = df.index
    windows = []
    for label, s, e in [("A_older", start_a, end_a), ("B_recent", start_b, end_b)]:
        windows.append({
            "window_id": label,
            "start_date": str(idx[s].date()),
            "end_date": str(idx[e].date()),
        })
    return windows


def main():
    random.seed(SEED)
    fetched = fetch_all()
    if not fetched:
        print("ERROR: no tickers fetched successfully", file=sys.stderr)
        sys.exit(1)

    atr_pcts = {t: _atr14_pct(df) for t, (sector, df) in fetched.items()}
    tiers, low_cut, high_cut = classify_tiers(atr_pcts)

    # group by (sector, tier)
    cells = {}
    for t, (sector, df) in fetched.items():
        key = (sector, tiers[t])
        cells.setdefault(key, []).append(t)

    selected = []
    cell_summary = []
    for (sector, tier), candidates in sorted(cells.items()):
        candidates_sorted = sorted(candidates)
        random.shuffle(candidates_sorted)
        chosen = candidates_sorted[:TARGET_PER_CELL]
        cell_summary.append({
            "sector": sector, "vol_tier": tier,
            "n_candidates": len(candidates_sorted), "n_selected": len(chosen),
            "tickers": chosen,
        })
        for t in chosen:
            df = fetched[t][1]
            windows = make_windows(df)
            selected.append({
                "ticker": t,
                "sector": sector,
                "vol_tier": tier,
                "atr14_pct_at_sample_time": round(atr_pcts[t], 3),
                "windows": windows,
            })

    result = {
        "_meta": {
            "purpose": "Frozen stratified sample for MATS Phase 2 backtests (see ENGINE_ARCHITECTURE.md). "
                       "DO NOT re-run sample_dataset.py to regenerate this file after any backtest has used "
                       "it -- bump DATASET_VERSION and keep this file if a genuine re-sample is needed.",
            "dataset_version": DATASET_VERSION,
            "created": "2026-07-23",
            "seed": SEED,
            "target_per_cell": TARGET_PER_CELL,
            "window_len_trading_days": WINDOW_LEN,
            "gap_days_between_windows": GAP_DAYS,
            "buffer_days_after_window_end": BUFFER_DAYS,
            "fetch_period_used": FETCH_PERIOD,
            "global_atr14_pct_tercile_cutoffs": {"low_max": round(low_cut, 3), "high_min": round(high_cut, 3)},
            "n_tickers_fetched_successfully": len(fetched),
            "n_tickers_selected": len(selected),
            "how_to_regenerate": "python3 sample_dataset.py -- deterministic given SEED and today's "
                                  "yfinance data availability; universe lists are hard-coded above.",
        },
        "cell_summary": cell_summary,
        "samples": selected,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"wrote {OUT_PATH} — {len(selected)} tickers across {len(cell_summary)} cells", file=sys.stderr)


if __name__ == "__main__":
    main()
