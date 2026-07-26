#!/opt/miniconda3/bin/python3
"""
MATS Engine — run_report.py (Phase 1 orchestration, see ENGINE_ARCHITECTURE.md)

Wires the six Phase 1 scripts into ONE JSON output for a given ticker. This is
the "not yet built" orchestration item ENGINE_ARCHITECTURE.md flagged — built
2026-07-23 only after the six scripts were individually fixture-tested and the
fixes independently re-verified (not just claimed) in the same session.

What this does NOT do (see ENGINE_ARCHITECTURE.md Layer split table — still true):
  - Does NOT call TradingView MCP (agent-layer only). tv_rsi14/tv_macd_hist/
    tv_sma20/tv_sma50/tv_sma200 are left null with a note. The AI must call
    combined_analysis itself and paste the raw values in verbatim (see the
    Transcription-loophole mitigation section of ENGINE_ARCHITECTURE.md).
  - Does NOT call WebSearch / financial_news (agent-layer only).
  - Does NOT decide initial_bias — that requires reading the bull/bear drivers,
    which is judgment, not computation. If --initial-bias is not passed, the
    bias section is left with adjusted=null and the AI must call
    `bias_engine.adjust_bias(initial_bias, broad, sector)` itself once it has
    decided initial_bias from the drivers section it writes.
  - Does NOT touch Phase 2 logic (S/R levels, Row 0/1/2/3 entry engine) —
    those stay AI-executed + Verification Cell per the Phase boundary in
    ENGINE_ARCHITECTURE.md, not because this script forgot them.

CLI:
    python3 run_report.py TICKER ASSET_TYPE [--sector SECTOR] [--initial-bias BIAS]
    e.g. python3 run_report.py LITE us_equity --sector Technology --initial-bias NEUTRAL
Prints one JSON object to stdout — this IS the machine-computed half of a
/mats report; the AI reads it and supplies the judgment half (news, drivers,
prose, Phase 2 levels) on top.
"""
import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(__file__))

from indicators import compute_indicators
from regime_vote import compute_regime
from market_context import get_market_context
from bias_engine import adjust_bias
import yfinance as yf


def build_report(ticker, asset_type, sector=None, initial_bias=None, futu_code=None):
    result = {"_meta": {"ticker": ticker, "asset_type": asset_type, "sector": sector}}

    # --- Price/OHLC-derived, pure math (Phase 1) ---
    df = yf.Ticker(ticker).history(period="200d", interval="1d")
    if df.empty:
        return {"error": f"no data for {ticker}"}
    result["indicators"] = compute_indicators(df)
    result["regime"] = compute_regime(df)

    # --- Market context (Phase 1) ---
    result["market_context"] = get_market_context(asset_type, sector)

    # --- Bias adjustment (Phase 1 function, but needs AI-supplied initial_bias) ---
    broad = result["market_context"].get("broad")
    sector_verdict = result["market_context"].get("sector")
    if initial_bias is not None and broad and sector_verdict:
        final_bias, note, diverging_note = adjust_bias(initial_bias, broad, sector_verdict)
        result["bias"] = {
            "initial_bias": initial_bias, "broad": broad, "sector": sector_verdict,
            "final_bias": final_bias, "note": note, "diverging_note": diverging_note,
        }
    else:
        result["bias"] = {
            "initial_bias": initial_bias, "broad": broad, "sector": sector_verdict,
            "final_bias": None,
            "_note": "initial_bias not supplied (needs AI judgment from drivers) — "
                     "call bias_engine.adjust_bias(initial_bias, broad, sector) once decided",
        }

    # --- Futu OpenD (Phase 1) — equity only ---
    if asset_type in ("us_equity", "hk_equity", "cn_equity"):
        try:
            from futu_check import opend_available, get_capital_flow
            available, state_or_err = opend_available()
            result["futu"] = {"opend_available": available}
            if available and futu_code:
                result["futu"]["capital_flow"] = get_capital_flow(futu_code)
            elif available and not futu_code:
                result["futu"]["_note"] = "opend_available=True but no futu_code passed — " \
                                            "capital_flow/options_wall not attempted"
            else:
                result["futu"]["state_or_error"] = state_or_err
        except Exception as e:
            result["futu"] = {"opend_available": False, "error": str(e)}
    else:
        result["futu"] = {"_note": "skipped — crypto has no OpenD equity data"}

    # --- Agent-layer-only fields, explicitly null (see module docstring) ---
    result["tv_mcp"] = {
        "tv_rsi14": None, "tv_macd_hist": None, "tv_sma20": None, "tv_sma50": None,
        "tv_sma200": None,
        "_note": "NOT fetched here — agent must call TradingView MCP combined_analysis "
                 "and paste these five values in verbatim (see ENGINE_ARCHITECTURE.md "
                 "Transcription-loophole mitigation).",
    }
    result["news"] = {
        "_note": "NOT fetched here — agent must call TradingView MCP financial_news "
                 "and/or WebSearch fallback per SKILL.md Step 5.",
    }
    result["phase2_not_computed"] = {
        "_note": "S/R levels (S1/S2/R1/R2), Row 0/1/2/3 entry engine, R/R targets — "
                 "stay AI-executed + Verification Cell per ENGINE_ARCHITECTURE.md Phase "
                 "boundary. Not an omission — a deliberate, documented scope limit.",
    }

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("asset_type", choices=["us_equity", "hk_equity", "cn_equity", "crypto"])
    parser.add_argument("--sector", default=None)
    parser.add_argument("--initial-bias", default=None, choices=[None, "LONG", "NEUTRAL", "SHORT"])
    parser.add_argument("--futu-code", default=None)
    args = parser.parse_args()

    result = build_report(args.ticker, args.asset_type, args.sector,
                            args.initial_bias, args.futu_code)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
