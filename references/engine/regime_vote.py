#!/opt/miniconda3/bin/python3
"""
MATS Engine — regime_vote.py (Phase 1, see ENGINE_ARCHITECTURE.md)

ADX / Efficiency Ratio / Choppiness Index three-vote majority regime classifier.
Same-family sanity check, NOT independent-source triangulation (see SKILL.md
Step 4b Regime Detection section) — gates the Mean-Reversion row only.

CLI:
    python3 regime_vote.py TICKER
Prints one JSON object to stdout.
"""
import sys
import json
import numpy as np
import yfinance as yf
import pandas_ta as ta


def compute_regime(df):
    """df: yfinance OHLCV DataFrame, >=14 rows minimum, 200 recommended."""
    close = df['Close']
    high = df['High']
    low = df['Low']

    adx_df = ta.adx(high, low, close, length=14)
    adx_val = float(adx_df.filter(like='ADX_').iloc[-1, 0])

    er_path = float(close.diff().abs().iloc[-10:].sum())
    er = abs(float(close.iloc[-1]) - float(close.iloc[-11])) / er_path if er_path > 0 else 0.0

    tr_s = ta.true_range(high, low, close)
    hl_range = float(high.iloc[-14:].max() - low.iloc[-14:].min())
    chop = 100 * np.log10(float(tr_s.iloc[-14:].sum()) / hl_range) / np.log10(14) if hl_range > 0 else 100.0

    votes = {"TREND": 0, "RANGE": 0}
    if adx_val > 25:
        votes["TREND"] += 1
    elif adx_val < 20:
        votes["RANGE"] += 1

    votes["TREND" if er > 0.3 else "RANGE"] += 1

    if chop < 38.2:
        votes["TREND"] += 1
    elif chop > 61.8:
        votes["RANGE"] += 1

    if votes["TREND"] >= 2:
        verdict = "TREND"
    elif votes["RANGE"] >= 2:
        verdict = "RANGE"
    else:
        verdict = "AMBIGUOUS"

    return {
        "adx": round(adx_val, 2),
        "er": round(er, 3),
        "chop": round(chop, 2),
        "votes": votes,
        "verdict": verdict,
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: regime_vote.py TICKER"}))
        sys.exit(1)
    ticker = sys.argv[1]
    df = yf.Ticker(ticker).history(period='200d', interval='1d')
    if df.empty:
        print(json.dumps({"error": f"no data for {ticker}"}))
        sys.exit(1)
    result = compute_regime(df)
    result["_meta"] = {"ticker": ticker, "bars": len(df)}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
