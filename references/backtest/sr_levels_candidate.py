#!/opt/miniconda3/bin/python3
"""
MATS Backtest — sr_levels_candidate.py

NOT Phase 1 production code. This is a literal, best-effort port of SKILL.md
Step 4.1-4.4 (S/R engine), built ONLY so run_backtest.py has something
deterministic to run across the frozen dataset. Per ENGINE_ARCHITECTURE.md,
this mechanism stays AI-executed in real /mats reports until it passes a
backtest -- this file exists to PRODUCE that backtest, not to replace the
AI-executed version in production.

Known, disclosed simplifications vs the real Step 4 (both sides of a
comparison are missing the same two sources, so the CANDIDATE-vs-BASELINE
comparison below is still fair -- it's the absolute realism that's reduced):
  - No Options Wall tier (Step 4.3 bullet 4) -- requires live Futu OpenD,
    not available for historical windows.
  - No Analyst Target tier -- not reliably available historically per-date
    from yfinance; omitted rather than faked.
  - Structural candidates use only swing points from the OHLC window itself
    (Step 4.1/4.2); BOLL bands + today's intraday H/L are included (Step 4.3
    bullets 2-3) since they're derivable from the same df.

Two functions:
  candidate_levels(df)  -- full 4.1+4.2+4.3+4.4 (swing points + polarity flip
                            + BOLL/intraday + confluence merge)
  baseline_levels(df)   -- naive: nearest surviving structural swing point
                            only (4.1, no flip, no BOLL, no merge) -- this is
                            the "structural-swing-points-only" baseline named
                            in ENGINE_ARCHITECTURE.md's backtest Method section
"""
import pandas as pd
import pandas_ta as ta

SWING_WINDOW = 5
CLUSTER_PCT = 0.005
CONFLUENCE_PCT = 0.01


def find_swings(df, window=SWING_WINDOW):
    highs, lows = [], []
    h, l = df["High"], df["Low"]
    for i in range(window, len(df) - window):
        seg_h = h.iloc[i - window: i + window + 1]
        seg_l = l.iloc[i - window: i + window + 1]
        if h.iloc[i] == seg_h.max():
            highs.append((df.index[i], float(h.iloc[i])))
        if l.iloc[i] == seg_l.min():
            lows.append((df.index[i], float(l.iloc[i])))
    return highs, lows


def cluster(points, pct=CLUSTER_PCT):
    if not points:
        return []
    pts = sorted(points, key=lambda x: x[1])
    clusters, cur = [], [pts[0]]
    for p in pts[1:]:
        if abs(p[1] - cur[-1][1]) / cur[-1][1] <= pct:
            cur.append(p)
        else:
            clusters.append(cur)
            cur = [p]
    clusters.append(cur)
    return [{"price": sum(p[1] for p in c) / len(c), "date": min(p[0] for p in c)} for c in clusters]


def _breach_days(df, level, date, direction):
    """direction='above': count days Close>level after date (resistance broken).
    direction='below': count days Close<level after date (support broken)."""
    after = df[df.index > date]["Close"]
    if direction == "above":
        return int((after > level).sum())
    return int((after < level).sum())


def _structural_candidates(df, current_price, include_flip=True):
    """4.1 (+ 4.2 if include_flip): returns (support_list, resistance_list),
    each a list of {'price','date','tag'} dicts, breach-filtered.
    include_flip=False isolates 4.1 alone -- used by the ablation harness to
    test whether Polarity Flip specifically helps or hurts (see
    run_backtest_ablation.py, 2026-07-23)."""
    highs, lows = find_swings(df)
    high_clusters = cluster(highs)
    low_clusters = cluster(lows)

    support, resistance = [], []

    for c in low_clusters:
        below_price = c["price"] < current_price
        broken = _breach_days(df, c["price"], c["date"], "below") >= 2
        if below_price and not broken:
            support.append({"price": c["price"], "date": c["date"], "tag": "structural_low"})
        elif include_flip and (not below_price) and broken:
            # 4.2 polarity flip: broken support above price -> resistance
            resistance.append({"price": c["price"], "date": c["date"], "tag": "flipped_support_to_resistance"})

    for c in high_clusters:
        above_price = c["price"] > current_price
        broken = _breach_days(df, c["price"], c["date"], "above") >= 2
        if above_price and not broken:
            resistance.append({"price": c["price"], "date": c["date"], "tag": "structural_high"})
        elif include_flip and (not above_price) and broken:
            # 4.2 polarity flip: broken resistance below price -> support
            support.append({"price": c["price"], "date": c["date"], "tag": "flipped_resistance_to_support"})

    return support, resistance


def _confluence_merge(items, pct=CONFLUENCE_PCT):
    """items: list of {'price','tag'} sorted by ascending distance already
    handled by caller passing pre-sorted-by-price list. Merges adjacent items
    within pct of each other into one slot; returns list of merged slots
    (each slot: {'price' (mean), 'tags': [...]})."""
    if not items:
        return []
    slots = [{"prices": [items[0]["price"]], "tags": [items[0]["tag"]]}]
    for it in items[1:]:
        last_price = slots[-1]["prices"][-1]
        if abs(it["price"] - last_price) / last_price <= pct:
            slots[-1]["prices"].append(it["price"])
            slots[-1]["tags"].append(it["tag"])
        else:
            slots.append({"prices": [it["price"]], "tags": [it["tag"]]})
    return [{"price": sum(s["prices"]) / len(s["prices"]), "tags": s["tags"]} for s in slots]


def candidate_levels(df, include_flip=True, include_boll=True):
    """Full Step 4.1-4.4 candidate. Returns {'S1','S2','R1','R2'} (price or None) + basis tags.

    Fallback tiering (user-directed correction, 2026-07-23 -- "Direction A"):
    today's intraday High/Low is NOT a co-equal pool member sorted by raw
    distance alongside structural/flip/BOLL candidates -- that flattening
    let it dominate S1/R1 ~90%+ of the time in practice (confirmed via
    diagnostic run: today_low in S1's tags 93.1% of n=216, today_high in
    R1's tags 89.8%), since it is mechanically always the nearest thing to
    the current close. Correct tiering: structural(+flip)+BOLL form the
    PRIMARY pool; today's H/L is used ONLY as a fallback when the primary
    pool on that side is completely empty (the literal DOCN-style "would
    otherwise have nothing to show" case) -- not merely "far away" (no
    validated numeric threshold exists for "too far"; inventing one here
    would just be a new n=0 constant, see conversation).

    include_flip/include_boll: ablation switches (default True = full
    candidate as specified in SKILL.md Step 4.2/4.3) -- added 2026-07-23 to
    isolate which specific mechanism drives the still-remaining gap vs
    baseline after the fallback fix (candidate S1 79.2%/R1 43.1% vs baseline
    93.7%/76.7%), instead of guessing again."""
    current_price = float(df["Close"].iloc[-1])
    support, resistance = _structural_candidates(df, current_price, include_flip=include_flip)

    if include_boll:
        bb = ta.bbands(df["Close"], length=20, std=2)
        boll_lower = float(bb.filter(like="BBL").iloc[-1, 0])
        boll_upper = float(bb.filter(like="BBU").iloc[-1, 0])
        if boll_lower < current_price:
            support.append({"price": boll_lower, "date": df.index[-1], "tag": "boll_lower"})
        if boll_upper > current_price:
            resistance.append({"price": boll_upper, "date": df.index[-1], "tag": "boll_upper"})

    if not support:
        today_low = float(df["Low"].iloc[-1])
        if today_low < current_price:
            support.append({"price": today_low, "date": df.index[-1], "tag": "today_low_fallback"})
    if not resistance:
        today_high = float(df["High"].iloc[-1])
        if today_high > current_price:
            resistance.append({"price": today_high, "date": df.index[-1], "tag": "today_high_fallback"})

    support_sorted = sorted(support, key=lambda x: current_price - x["price"])
    resistance_sorted = sorted(resistance, key=lambda x: x["price"] - current_price)

    support_merged = _confluence_merge(support_sorted)
    resistance_merged = _confluence_merge(resistance_sorted)

    return {
        "current_price": current_price,
        "S1": support_merged[0]["price"] if len(support_merged) > 0 else None,
        "S2": support_merged[1]["price"] if len(support_merged) > 1 else None,
        "R1": resistance_merged[0]["price"] if len(resistance_merged) > 0 else None,
        "R2": resistance_merged[1]["price"] if len(resistance_merged) > 1 else None,
        "S1_tags": support_merged[0]["tags"] if len(support_merged) > 0 else [],
        "R1_tags": resistance_merged[0]["tags"] if len(resistance_merged) > 0 else [],
    }


def baseline_levels(df):
    """Naive baseline: nearest surviving structural swing point only (4.1,
    no polarity flip, no BOLL/intraday, no confluence merge)."""
    current_price = float(df["Close"].iloc[-1])
    highs, lows = find_swings(df)
    high_clusters = cluster(highs)
    low_clusters = cluster(lows)

    support = []
    for c in low_clusters:
        if c["price"] < current_price and _breach_days(df, c["price"], c["date"], "below") < 2:
            support.append(c["price"])
    resistance = []
    for c in high_clusters:
        if c["price"] > current_price and _breach_days(df, c["price"], c["date"], "above") < 2:
            resistance.append(c["price"])

    support.sort(key=lambda p: current_price - p)
    resistance.sort(key=lambda p: p - current_price)

    return {
        "current_price": current_price,
        "S1": support[0] if support else None,
        "R1": resistance[0] if resistance else None,
    }
