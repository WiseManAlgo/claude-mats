#!/opt/miniconda3/bin/python3
"""
MATS Engine — rr_gate.py (Phase 1, see ENGINE_ARCHITECTURE.md)

R/R arithmetic + the three family gate thresholds + entry-distance invariant.
Formula: R/R = (Target - Entry) / (Entry - Stop)  [SKILL.md Step 4b]

Family gate thresholds (SKILL.md Step 4b R/R Trade-Viability Gate):
    pullback (trend-following) >= 2.0
    breakout (momentum)        >= 1.5
    meanrev  (Connors RSI(2))  >= 0.5

Entry-distance invariant (SKILL.md Step 4b): a TRIGGERED entry must sit within
2.5x ATR14 of current price. PENDING rows are exempt.

CLI:
    python3 rr_gate.py rr ENTRY STOP TARGET FAMILY
    python3 rr_gate.py invariant ENTRY CURRENT_PRICE ATR14 STATUS
    e.g. python3 rr_gate.py rr 785.77 750.00 843.00 pullback
    e.g. python3 rr_gate.py invariant 844.00 835.00 71.54 TRIGGERED
Prints one JSON object to stdout.

CHANGE LOG: CLI reworked 2026-07-23 to add the 'invariant' mode — the
entry-distance invariant function existed since first build but was never
actually exercised by the CLI (caught in evidence-dialogue-loop review).
The old 4-positional-arg form (no subcommand) no longer works; both callers
of this script must use the 'rr'/'invariant' subcommand form now.
"""
import sys
import json

GATE_THRESHOLDS = {"pullback": 2.0, "breakout": 1.5, "meanrev": 0.5}


def compute_rr(entry, stop, target):
    risk = entry - stop
    if risk == 0:
        return None
    return round((target - entry) / risk, 2)


def check_gate(rr, family):
    if family not in GATE_THRESHOLDS:
        raise ValueError(f"unknown family '{family}', must be one of {list(GATE_THRESHOLDS)}")
    threshold = GATE_THRESHOLDS[family]
    passed = rr is not None and rr >= threshold
    return passed, threshold


def check_entry_distance_invariant(entry, current_price, atr14, status):
    """PENDING rows are exempt by design — only TRIGGERED rows must satisfy this."""
    if status != "TRIGGERED":
        return {"applicable": False, "reason": "PENDING rows are exempt from this invariant"}
    limit = 2.5 * atr14
    dist = abs(entry - current_price)
    return {"applicable": True, "distance": round(dist, 2), "limit": round(limit, 2),
             "pass": dist <= limit}


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: rr_gate.py rr ENTRY STOP TARGET FAMILY "
                                     "| rr_gate.py invariant ENTRY CURRENT_PRICE ATR14 STATUS"}))
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "rr":
        if len(sys.argv) < 6:
            print(json.dumps({"error": "usage: rr_gate.py rr ENTRY STOP TARGET FAMILY"}))
            sys.exit(1)
        entry, stop, target = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
        family = sys.argv[5]
        rr = compute_rr(entry, stop, target)
        passed, threshold = check_gate(rr, family)
        result = {
            "entry": entry, "stop": stop, "target": target, "family": family,
            "rr": rr, "gate_threshold": threshold, "gate_pass": passed,
            "no_trade_label": (not passed),
        }
        print(json.dumps(result, indent=2))

    elif mode == "invariant":
        if len(sys.argv) < 6:
            print(json.dumps({"error": "usage: rr_gate.py invariant ENTRY CURRENT_PRICE ATR14 STATUS"}))
            sys.exit(1)
        entry, current_price, atr14 = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
        status = sys.argv[5]
        result = check_entry_distance_invariant(entry, current_price, atr14, status)
        result.update({"entry": entry, "current_price": current_price, "atr14": atr14, "status": status})
        print(json.dumps(result, indent=2))

    else:
        print(json.dumps({"error": f"unknown mode '{mode}', use 'rr' or 'invariant'"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
