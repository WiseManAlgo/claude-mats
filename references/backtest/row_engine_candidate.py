#!/opt/miniconda3/bin/python3
"""
MATS Backtest — row_engine_candidate.py

NOT Phase 1 production code (same status as sr_levels_candidate.py -- see its
docstring). Literal port of SKILL.md Standard Mode Row 0/1/2/3 (lines
~543-661) so run_backtest.py can score these entry-anchor rules against the
frozen dataset. Targets (T1/T2) are simplified to use only the candidate S/R
engine's R1/R2 (no Options Wall, no analyst target -- same disclosed gap as
sr_levels_candidate.py).

compute_rows(df, sr) -> dict with row0/row1/row2/row3, each carrying
status (TRIGGERED/PENDING), entry, stop, t1 (None if no qualifying target).
"""
import pandas_ta as ta


def _regime(df):
    high, low, close = df["High"], df["Low"], df["Close"]
    adx_df = ta.adx(high, low, close, length=14)
    adx_val = float(adx_df.filter(like="ADX_").iloc[-1, 0])
    er_path = close.diff().abs().iloc[-10:].sum()
    er = abs(close.iloc[-1] - close.iloc[-11]) / er_path if er_path > 0 else 0.0
    tr = ta.true_range(high, low, close)
    hl_range = high.iloc[-14:].max() - low.iloc[-14:].min()
    import numpy as np
    chop = 100 * np.log10(tr.iloc[-14:].sum() / hl_range) / np.log10(14) if hl_range > 0 else 100.0

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
        return "TREND"
    if votes["RANGE"] >= 2:
        return "RANGE"
    return "AMBIGUOUS"


def _target_chain(anchor, atr14, candidates):
    pool = sorted(c for c in candidates if c is not None and c > anchor)
    targets, last = [], anchor
    for c in pool:
        if (c - last) >= 0.5 * atr14:
            targets.append(c)
            last = c
        if len(targets) == 2:
            break
    return (targets + [None, None])[:2]


def compute_rows(df, sr):
    close = df["Close"]
    current_price = float(close.iloc[-1])
    atr14 = float(ta.atr(df["High"], df["Low"], close, length=14).iloc[-1])
    atr10 = float(ta.atr(df["High"], df["Low"], close, length=10).iloc[-1])
    ema10 = close.ewm(span=10, adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    sma5 = float(close.rolling(5).mean().iloc[-1])
    sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    rsi2 = float(ta.rsi(close, length=2).iloc[-1])
    vol_today = float(df["Volume"].iloc[-1])
    avg_vol_20d = float(df["Volume"].rolling(20).mean().iloc[-1])

    trend_ok = bool(current_price > ema21.iloc[-1] and ema10.iloc[-1] > ema21.iloc[-1]
                     and ema21.iloc[-1] > ema21.iloc[-6])
    pivot_recent = float(df["High"].iloc[-11:-1].max())

    result = {"regime": _regime(df), "current_price": current_price}

    # Row 0
    z1 = pivot_recent is not None and current_price <= pivot_recent * 1.05 and current_price >= pivot_recent
    result["row0"] = {"z1_breakout_zone": bool(z1)}

    # Row 1 -- Pullback, anchor EMA10
    entry1 = float(ema10.iloc[-1])
    stop1 = entry1 - 0.5 * atr14
    t1_1, t2_1 = _target_chain(entry1, atr14, [pivot_recent, sr.get("R1"), sr.get("R2")])
    result["row1"] = {
        "status": "TRIGGERED" if trend_ok else "PENDING",
        "entry": entry1, "stop": stop1, "t1": t1_1, "t2": t2_1,
    }

    # Row 2 -- Breakout, anchor pivot_recent
    entry2 = pivot_recent
    stop2 = pivot_recent - 0.5 * atr14
    chase_ok = current_price >= entry2 and entry2 <= current_price * 1.05
    t1_2, t2_2 = _target_chain(entry2, atr14, [sr.get("R1"), sr.get("R2")])
    result["row2"] = {
        "status": "TRIGGERED" if chase_ok else "PENDING",
        "entry": entry2, "stop": stop2, "t1": t1_2, "t2": t2_2,
    }

    # Row 3 -- Mean Reversion, Connors RSI(2)
    entry3 = current_price
    stop3 = entry3 - 2 * atr10
    t1_3 = sma5
    mr_ok = (result["regime"] == "RANGE") and (sma200 is not None and current_price > sma200) and (rsi2 < 10)
    result["row3"] = {
        "status": "TRIGGERED" if mr_ok else "PENDING",
        "entry": entry3, "stop": stop3, "t1": t1_3,
        "conditions": {"regime_range": result["regime"] == "RANGE",
                       "above_sma200": bool(sma200 is not None and current_price > sma200),
                       "rsi2_lt_10": bool(rsi2 < 10)},
    }

    return result
