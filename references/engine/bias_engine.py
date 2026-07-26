#!/opt/miniconda3/bin/python3
"""
MATS Engine — bias_engine.py (Phase 1, see ENGINE_ARCHITECTURE.md)

adjust_bias() ported verbatim from SKILL.md Step 1.5 — already proven correct
across 2 live LITE runs before this port.

CORRECTION (caught in evidence-dialogue-loop review, 2026-07-23): an earlier
draft of this docstring claimed this file "also includes the market_context
fetch" — that was never true, this file has no data-fetching code and never
did. This module is a pure function of three strings (initial_bias, broad,
sector) that the CALLER must supply. To get broad/sector, call
market_context.py separately first and pass its output in here — the two
scripts are not wired together, by design (see ENGINE_ARCHITECTURE.md
"Not yet built" note on orchestration).

CLI:
    python3 bias_engine.py INITIAL_BIAS BROAD SECTOR
    e.g. python3 bias_engine.py NEUTRAL Risk-On Bearish
Prints one JSON object to stdout.
"""
import sys
import json


def adjust_bias(initial_bias, broad, sector):
    """Returns (final_bias, note_or_None). Verbatim logic from SKILL.md Step 1.5."""
    adjusted = initial_bias
    diverging_note = None

    if broad == "Risk-Off" and sector == "Bearish":
        adjusted = {"LONG": "NEUTRAL", "NEUTRAL": "SHORT"}.get(initial_bias, initial_bias)
    elif broad == "Risk-Off" and sector == "Neutral":
        adjusted = {"LONG": "NEUTRAL"}.get(initial_bias, initial_bias)
    elif broad == "Risk-Off" and sector == "Bullish":
        diverging_note = "板塊與大市背離（大市Risk-Off但板塊強勢），偏向不調整，於Section 2註記"
    elif broad == "Neutral" and sector == "Bearish":
        adjusted = {"LONG": "NEUTRAL"}.get(initial_bias, initial_bias)
    # Neutral/Neutral and Risk-On/Any: no change

    note = None
    if adjusted != initial_bias:
        note = f"⚠ 大市/板塊偏弱（{broad} + 板塊{sector}），偏向由 {initial_bias} 調整為 {adjusted}"

    return adjusted, note, diverging_note


def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "usage: bias_engine.py INITIAL_BIAS BROAD SECTOR"}))
        sys.exit(1)
    initial_bias, broad, sector = sys.argv[1], sys.argv[2], sys.argv[3]
    final_bias, note, diverging_note = adjust_bias(initial_bias, broad, sector)
    result = {
        "initial_bias": initial_bias,
        "broad": broad,
        "sector": sector,
        "final_bias": final_bias,
        "note": note,
        "diverging_note": diverging_note,
        "log_line": f"BIAS: initial={initial_bias} broad={broad} sector={sector} -> final={final_bias}",
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
