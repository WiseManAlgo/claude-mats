#!/opt/miniconda3/bin/python3
"""
MATS Engine — futu_check.py (Phase 1, see ENGINE_ARCHITECTURE.md)

Futu OpenD connectivity, capital flow, and options wall.

INCIDENT HISTORY — read before touching this file:
- 2026-07-20 (NKE): "unavailable" was asserted from assumption, zero attempt made.
- 2026-07-23 (LITE, x3 reports): a real attempt was wrapped in signal.alarm(8) for
  "safety" and hung past the alarm without the handler ever firing (get_global_state()
  blocks on a C-extension socket read that does not reliably honor SIGALRM) — the
  wrapper silently manufactured the exact false-negative it was meant to prevent.
  The fix both times: a BARE, UNWRAPPED synchronous call. It has returned in ~1-2
  seconds every time it has actually been allowed to run. DO NOT re-add a timeout
  wrapper of any kind around opend_available() below.
- 2026-07-23 (LITE): confirmed against Futu's own official docs
  (https://openapi.futunn.com/futu-api-doc/en/intro/authority.html) — options quota
  is a SEPARATE pool from the general quote quota, and requires either total account
  assets > $3,000 USD or a purchased OPRA real-time quote add-on. A "0 remaining"
  options quota with headroom in the general quote pool is expected/documented
  behavior, not a bug — do not re-diagnose this from scratch each time.

CLI:
    python3 futu_check.py check          # just connectivity
    python3 futu_check.py capital_flow US.LITE
    python3 futu_check.py options_wall US.LITE 2026-07-24 2026-09-18
    python3 futu_check.py full US.LITE 2026-07-24 2026-09-18   # everything
Prints one JSON object to stdout.
"""
import sys
import json


def _silence_futu_console_log():
    """The futu SDK's own logger writes INFO-level connection noise straight to
    sys.stdout by default (confirmed via source: futu.common.ft_logger.FTLog
    wires logging.StreamHandler(sys.stdout) — NOT stderr, so `2>/dev/null` does
    not hide it). Left on, every script here would emit non-JSON lines mixed
    into stdout, breaking any caller trying to parse the output as pure JSON.
    Official switch, not a hack — call once before the first OpenQuoteContext."""
    try:
        from futu import SysConfig
        SysConfig.enable_console_log(False)
    except Exception:
        pass


_silence_futu_console_log()


def opend_available():
    """Bare, unwrapped round-trip call. See incident history above — do not wrap in a timeout."""
    try:
        from futu import OpenQuoteContext, RET_OK
        quote_ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
        ret, state = quote_ctx.get_global_state()
        available = (ret == RET_OK) and state.get("qot_logined", False)
        quote_ctx.close()
        return available, (state if available else None)
    except Exception as e:
        return False, str(e)


def get_capital_flow(futu_code):
    from futu import OpenQuoteContext, RET_OK
    quote_ctx = OpenQuoteContext(host="127.0.0.1", port=11111)
    try:
        ret, dist = quote_ctx.get_capital_distribution(futu_code)
        if ret != RET_OK:
            return {"available": False, "reason": str(dist)}
        d = dist.iloc[0]
        net_super = float(d["capital_in_super"] - d["capital_out_super"])
        net_big = float(d["capital_in_big"] - d["capital_out_big"])
        net_mid = float(d["capital_in_mid"] - d["capital_out_mid"])
        net_small = float(d["capital_in_small"] - d["capital_out_small"])
        return {
            "available": True,
            "net_super": round(net_super, 2),
            "net_big": round(net_big, 2),
            "net_mid": round(net_mid, 2),
            "net_small": round(net_small, 2),
            "main_net": round(net_super + net_big, 2),
            "retail_net": round(net_mid + net_small, 2),
            "update_time": str(d["update_time"]),
        }
    finally:
        quote_ctx.close()


def get_options_wall(futu_code, near_expiry, mid_expiry):
    from futu import OpenQuoteContext, RET_OK, SubType
    quote_ctx = OpenQuoteContext(host="127.0.0.1", port=11111)

    def _wall_for_expiry(expiry_date):
        ret, chain = quote_ctx.get_option_chain(futu_code, start=expiry_date, end=expiry_date)
        if ret != RET_OK:
            return {"available": False, "reason": f"chain fetch failed: {chain}"}
        codes = chain["code"].tolist()
        ret_sub, sub_err = quote_ctx.subscribe(codes, [SubType.QUOTE], subscribe_push=False)
        if ret_sub != RET_OK:
            return {"available": False, "reason": f"subscribe failed (likely 0 options quota — "
                                                     f"see incident history docstring): {sub_err}"}
        ret_snap, snap = quote_ctx.get_market_snapshot(codes)
        if ret_snap != RET_OK:
            return {"available": False, "reason": f"snapshot failed: {snap}"}
        calls = snap[snap["option_type"] == "CALL"]
        puts = snap[snap["option_type"] == "PUT"]
        call_row = calls.loc[calls["option_open_interest"].idxmax()]
        put_row = puts.loc[puts["option_open_interest"].idxmax()]
        quote_ctx.unsubscribe(codes, [SubType.QUOTE])
        return {
            "available": True,
            "call_wall": float(call_row["option_strike_price"]),
            "call_wall_oi": float(call_row["option_open_interest"]),
            "put_wall": float(put_row["option_strike_price"]),
            "put_wall_oi": float(put_row["option_open_interest"]),
        }

    try:
        near = _wall_for_expiry(near_expiry)
        mid = _wall_for_expiry(mid_expiry)
        return {"near": near, "mid": mid}
    finally:
        quote_ctx.close()


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "usage: futu_check.py check|capital_flow|options_wall|full ..."}))
        sys.exit(1)
    mode = sys.argv[1]

    available, state_or_err = opend_available()
    result = {"opend_available": available, "state_or_error": state_or_err}

    if mode == "check":
        print(json.dumps(result, indent=2))
        return

    if not available:
        print(json.dumps(result, indent=2))
        return

    if mode in ("capital_flow", "full"):
        futu_code = sys.argv[2]
        result["capital_flow"] = get_capital_flow(futu_code)

    if mode in ("options_wall", "full"):
        futu_code = sys.argv[2]
        near_expiry = sys.argv[3]
        mid_expiry = sys.argv[4]
        result["options_wall"] = get_options_wall(futu_code, near_expiry, mid_expiry)

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
