#!/opt/miniconda3/bin/python3
"""
MATS Engine — market_context.py (Phase 1, see ENGINE_ARCHITECTURE.md)

Broad market index + sector ETF trend classification (SKILL.md Step 1.5).
Risk-On/Risk-Off/Neutral (broad) and Bullish/Bearish/Neutral (sector) —
same criteria applied to both: {above SMA20 AND last-3-days trending up} vs
{below SMA20 OR last-3-days trending down} vs mixed.

Sector -> ETF mapping (US only here; HK/CN proxies listed in SKILL.md Step 1.5
table but not all have a clean yfinance ticker — pass None for sector_etf to
skip sector classification).

CLI:
    python3 market_context.py us_equity Technology
    python3 market_context.py hk_equity None
Prints one JSON object to stdout.
"""
import sys
import json
import yfinance as yf

BROAD_INDEX = {
    "us_equity": "^GSPC",
    "hk_equity": "^HSI",
    "cn_equity": "000300.SS",
    "crypto": "BTC-USD",
}

SECTOR_ETF = {
    "Technology": "XLK",
    "Semiconductors": "SMH",
    "Communication Services": "XLC",
    "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
}


def _classify(df):
    """Shared Risk-On/Off (or Bullish/Bearish) classifier — same rule, different labels by caller."""
    closes = df["Close"]
    sma20 = closes.rolling(20).mean()
    last_close = float(closes.iloc[-1])
    last_sma20 = float(sma20.iloc[-1])
    last3 = closes.iloc[-3:]
    trending_up = bool(last3.iloc[-1] > last3.iloc[-2] > last3.iloc[-3])
    trending_down = bool(last3.iloc[-1] < last3.iloc[-2] < last3.iloc[-3])

    above_sma20 = last_close > last_sma20
    if above_sma20 and trending_up:
        verdict = "on"   # Risk-On / Bullish
    elif (not above_sma20) or trending_down:
        verdict = "off"  # Risk-Off / Bearish
    else:
        verdict = "neutral"

    return {
        "close": round(last_close, 2),
        "sma20": round(last_sma20, 2),
        "trending_up_3d": trending_up,
        "trending_down_3d": trending_down,
        "verdict": verdict,
        "last3_closes": [round(float(x), 2) for x in last3],
    }


def get_market_context(asset_type, sector=None):
    index_ticker = BROAD_INDEX.get(asset_type)
    if not index_ticker:
        return {"error": f"unknown asset_type '{asset_type}'"}

    idx_df = yf.Ticker(index_ticker).history(period="30d", interval="1d")
    broad_raw = _classify(idx_df)
    broad = {"on": "Risk-On", "off": "Risk-Off", "neutral": "Neutral"}[broad_raw["verdict"]]

    result = {
        "asset_type": asset_type,
        "broad_index": index_ticker,
        "broad": broad,
        "broad_detail": broad_raw,
    }

    if sector and sector in SECTOR_ETF:
        etf = SECTOR_ETF[sector]
        etf_df = yf.Ticker(etf).history(period="30d", interval="1d")
        sector_raw = _classify(etf_df)
        sector_verdict = {"on": "Bullish", "off": "Bearish", "neutral": "Neutral"}[sector_raw["verdict"]]
        result["sector"] = sector_verdict
        result["sector_etf"] = etf
        result["sector_detail"] = sector_raw
    else:
        result["sector"] = None
        result["sector_etf"] = None
        result["_sector_note"] = ("no sector provided or no US ETF mapping for this sector — "
                                    "HK/CN sector proxies (HSTECH, 科創50 etc.) need their own "
                                    "yfinance-resolvable ticker before this can classify them")

    return result


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: market_context.py ASSET_TYPE [SECTOR]"}))
        sys.exit(1)
    asset_type = sys.argv[1]
    sector = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] != "None" else None
    result = get_market_context(asset_type, sector)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
