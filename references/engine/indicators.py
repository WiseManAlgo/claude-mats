#!/opt/miniconda3/bin/python3
"""
MATS Engine — indicators.py (Phase 1, see ENGINE_ARCHITECTURE.md)

Pure math from OHLC data: KDJ, BOLL, ATR14/ATR10, EMA10/21, RSI2, SMA5/20/50/200.
Does NOT include TV MCP's RSI(14)/MACD/SMA — those are agent-layer-only (see
ENGINE_ARCHITECTURE.md "Layer split") and must come from the actual MCP tool call,
never approximated here.

CLI:
    python3 indicators.py TICKER
Prints one JSON object to stdout.
"""
import sys
import json
import yfinance as yf
import pandas_ta as ta
import numpy as np


def compute_indicators(df):
    """df: yfinance OHLCV DataFrame (Open/High/Low/Close/Volume), >=200 rows recommended."""
    close = df['Close']
    high = df['High']
    low = df['Low']

    current_price = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    pct_chg = (current_price - prev_close) / prev_close * 100
    vol_today = float(df['Volume'].iloc[-1])
    avg_vol_20d = float(df['Volume'].rolling(20).mean().iloc[-1])
    vol_ratio = vol_today / avg_vol_20d if avg_vol_20d else None

    atr14 = float(ta.atr(high, low, close, length=14).iloc[-1])
    atr10 = float(ta.atr(high, low, close, length=10).iloc[-1])

    ema10 = close.ewm(span=10, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()

    sma5 = float(close.rolling(5).mean().iloc[-1])
    sma20 = float(close.rolling(20).mean().iloc[-1])
    sma50 = float(close.rolling(50).mean().iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

    rsi2 = float(ta.rsi(close, length=2).iloc[-1])

    low9 = low.rolling(9).min()
    high9 = high.rolling(9).max()
    rsv = (close - low9) / (high9 - low9) * 100
    k = rsv.ewm(com=2).mean()
    d = k.ewm(com=2).mean()
    j = 3 * k - 2 * d

    bb = ta.bbands(close, length=20, std=2)
    boll_upper = float(bb.filter(like='BBU').iloc[-1, 0])
    boll_mid = float(bb.filter(like='BBM').iloc[-1, 0])
    boll_lower = float(bb.filter(like='BBL').iloc[-1, 0])
    boll_touch_upper = bool(high.iloc[-1] >= boll_upper)
    boll_touch_lower = bool(low.iloc[-1] <= boll_lower)

    macd = ta.macd(close, fast=12, slow=26, signal=9)
    macd_last5 = [round(float(x), 2) for x in macd['MACDh_12_26_9'].iloc[-5:]]

    pivot_recent = float(high.iloc[-11:-1].max())
    pivot_date = str(high.iloc[-11:-1].idxmax().date())

    today_open = float(df['Open'].iloc[-1])
    gap_pct = (today_open - prev_close) / prev_close * 100
    gap_up_unfilled = bool(today_open > prev_close and float(low.iloc[-1]) > prev_close)
    gap_down_unfilled = bool(today_open < prev_close and float(high.iloc[-1]) < prev_close)

    return {
        "current_price": round(current_price, 2),
        "prev_close": round(prev_close, 2),
        "pct_chg": round(pct_chg, 2),
        "vol_today": vol_today,
        "avg_vol_20d": round(avg_vol_20d, 2) if avg_vol_20d else None,
        "vol_ratio": round(vol_ratio, 3) if vol_ratio is not None else None,
        "atr14": round(atr14, 2),
        "atr10": round(atr10, 2),
        "ema10": round(float(ema10.iloc[-1]), 2),
        "ema21": round(float(ema21.iloc[-1]), 2),
        "ema21_rising_6d": bool(ema21.iloc[-1] > ema21.iloc[-6]),
        "price_above_ema21": bool(current_price > ema21.iloc[-1]),
        "ema10_above_ema21": bool(ema10.iloc[-1] > ema21.iloc[-1]),
        "sma5": round(sma5, 2),
        "sma20": round(sma20, 2),
        "sma50": round(sma50, 2),
        "sma200": round(sma200, 2) if sma200 is not None else None,
        "sma200_available": sma200 is not None,
        "rsi2": round(rsi2, 2),
        "kdj_k": round(float(k.iloc[-1]), 2),
        "kdj_d": round(float(d.iloc[-1]), 2),
        "kdj_j": round(float(j.iloc[-1]), 2),
        "boll_upper": round(boll_upper, 2),
        "boll_mid": round(boll_mid, 2),
        "boll_lower": round(boll_lower, 2),
        "boll_touch_upper": boll_touch_upper,
        "boll_touch_lower": boll_touch_lower,
        "macd_hist_last5": macd_last5,
        "pivot_recent": round(pivot_recent, 2),
        "pivot_date": pivot_date,
        "gap_pct": round(gap_pct, 2),
        "gap_up_unfilled": gap_up_unfilled,
        "gap_down_unfilled": gap_down_unfilled,
        "_note": "tv_rsi14/tv_macd_hist/tv_sma20/tv_sma50/tv_sma200 are NOT computed here — "
                 "those come from the TradingView MCP combined_analysis call, agent-layer only. "
                 "See ENGINE_ARCHITECTURE.md Layer split table.",
    }


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: indicators.py TICKER"}))
        sys.exit(1)
    ticker = sys.argv[1]
    df = yf.Ticker(ticker).history(period='200d', interval='1d')
    if df.empty:
        print(json.dumps({"error": f"no data for {ticker}"}))
        sys.exit(1)
    result = compute_indicators(df)
    result["_meta"] = {"ticker": ticker, "bars": len(df)}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
