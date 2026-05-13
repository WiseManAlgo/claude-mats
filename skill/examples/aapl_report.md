# Example: Gold-Standard AAPL Equity Signal Brief

This is the reference output format for US equity reports. Every equity report must match this structure, density, and tone. Numbers are illustrative — do NOT reuse in live reports. Run a fresh yfinance fetch for every live report.

---

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 EQUITY SIGNAL BRIEF — AAPL — 2026-05-12 UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PRICE  $211.26   24H  +1.34%   VOL  52.3M shares ($11.06B)
 BIAS   LONG      GRADE  B      SENTIMENT  BULLISH
 R/R    3.5:1 (support) | 0.7:1 (breakout — avoid)
 WATCH  $208 — SMA20/SMA200 confluence; loss of this zone invalidates setup
 WEEKLY Bullish — above WMA50 and WMA200; primary trend recovered
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

*Note: This analysis assumes AAPL refers to Apple Inc. listed on NASDAQ.*

---

### 1. Market Snapshot

| Indicator | Value | Signal |
|---|---|---|
| RSI(14) | 61.44 | Healthy — 8.6pts below overbought (70); momentum intact |
| MACD Histogram | 0.87 | Accelerating — 3-session build: 0.12→0.45→0.87 ✅ |
| KDJ K / D | 68.23 / 62.58 | K above D — short-term momentum confirmed bullish |
| SMA20 / SMA50 | $207.50 / $199.75 | Price above both — near/medium-term trend bullish |
| SMA200 | $208.40 | Price above — structural trend recently recovered |
| Weekly trend | Bullish | Above WMA50 and WMA200; primary trend intact |

*Data: Yahoo Finance daily close via yfinance. MAs are Simple Moving Averages (SMA). RSI and MACD use EMA-based smoothing (pandas-ta defaults). Values may differ ±5–15pt from platforms using Wilder's smoothing or different price feeds.*

| | Value | Note |
|---|---|---|
| Market Cap | $3.19T | Mega-cap |
| PE (trailing / fwd) | 31.80 / 27.40 | In line with large-cap tech peers |
| EPS (TTM) | $6.64 | Beat consensus by $0.09 last quarter |
| Analyst Target | $242.00 | +14.5% upside from current price |

**Trend: Bullish.** Full SMA stack aligned (price > SMA20 > SMA50 > SMA200); SMA200 reclaimed 3 sessions ago — first structural recovery since the Q1 2026 correction. MACD acceleration is the primary near-term confirmation signal.

**Sentiment: Bullish.** Q2 earnings beat + Goldman price target raise to $250 drive institutional positioning. Offset by ongoing EU DMA compliance costs and China market softness. *(Reuters, CNBC — last 48h)*

---

### 2. Key Drivers

**Bull**
- **Earnings beat sustained:** Q2 EPS $1.71 vs $1.62 consensus (+5.6% beat). Services revenue +15% YoY — seventh consecutive quarter of double-digit growth. Institutional accumulation confirmed post-print.
- **SMA200 reclaimed:** First close above the 200-day moving average since February 2026. Historically, reclaims of this level after extended consolidations precede multi-week trending moves. (Past performance is not indicative of future results.)
- **Analyst upgrade cycle:** Goldman Sachs raised price target to $250 (from $230); Morgan Stanley reiterated Overweight with $245 target. Consensus upgrades increase index-fund rebalancing pressure to the upside.

**Bear**
- **EU regulatory drag:** Digital Markets Act compliance costs estimated at $1.2B annually — margin headwind not yet fully priced. New restrictions on App Store fees effective Q3 2026.
- **China softness persists:** Greater China revenue -8% YoY for second consecutive quarter. No catalyst for reversal identified in near term; local competition (Huawei, Xiaomi) gaining share.
- **Valuation ceiling:** Forward PE of 27.4× sits at the 85th percentile of AAPL's 5-year range. Multiple expansion limited at current rates environment; any earnings miss risks sharp de-rating.

*Near-term (1-2 day) bias: bull. Structural (1-3 week) bias: bull with caveat — China and EU headwinds cap upside multiple.*

---

### 3. Levels & Entry Conditions

**Price Zones**

| | Zone | Basis |
|---|---|---|
| S1 — Immediate | $207–$208 | SMA20 ($207.50) + SMA200 ($208.40) confluence — double support |
| S2 — Intermediate | $199–$200 | SMA50 ($199.75) + psychological $200 level |
| R1 — Immediate | $218–$219 | March 2026 swing high; prior distribution zone |
| R2 — Intermediate | $226–$227 | January 2026 swing high; 52-week high zone |

**Trade Setup**
*(R/R = (Target − Entry) ÷ (Entry − Stop))*

| Type | Trigger | Entry | Stop | Risk | T1 | R/R | T2 | R/R |
|---|---|---|---|---|---|---|---|---|
| Support | Price in $207–$208 AND MACD hist > 0 | $208 | $205 | −1.4% | $218.50 | 3.5:1 | $226.50 | 6.2:1 |
| Breakout | Daily close > $219 AND vol > 92.1M shares | $219 | $208 | −5.0% | $226.50 | 0.7:1 | — | — |

**Invalidation:** Daily close below $205 OR MACD histogram crosses below zero.

*All conditions reference daily close — not intraday prints.*

---

*⚠ Educational purposes only. Not investment advice. Securities trading carries substantial risk of loss.*

---

## Rules demonstrated in this example

| Rule | Where |
|---|---|
| Header label: `EQUITY SIGNAL BRIEF` (not CRYPTO) | Top block |
| Volume: shares + USD equivalent | PRICE line |
| R/R shown for both setups; breakout explicitly labelled "avoid" | R/R line |
| Assumption note: company name + exchange | Below header |
| Indicator table: same 6 rows as crypto | Section 1 |
| Fundamentals block: equity-only, after indicator table | Section 1 |
| EPS beat/miss stated in fundamentals note | Fundamentals block |
| Sentiment: analyst action + earnings, not Fear & Greed | Section 1 |
| SMA200 reclaim as both S/R basis and key driver | Sections 1 + 2 + 3 |
| Past performance note appended to historical pattern reference | Section 2 Bull |
| Breakout volume trigger: 1.5× 20-day avg in shares | Section 3 |
| No "24/7 market" note | Section 3 |
| Securities disclaimer (not crypto) | Bottom |
| Grade B: support entry is A-grade; breakout entry is C-grade; report-level B reflects mixed setup | Header |
