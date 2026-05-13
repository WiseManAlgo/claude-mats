# Example: Gold-Standard BTC Signal Brief

This is the reference output format. Every report must match this structure, density, and tone. Numbers are from the 2026-05-10 real run — do NOT reuse in live reports.

---

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 CRYPTO SIGNAL BRIEF — BTC — 2026-05-10 UTC
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PRICE  $80,869   24H  +0.25%   VOL  $16.62B
 BIAS   LONG      GRADE  B      SENTIMENT  BULLISH
 R/R    1.5:1 (support) | 1.5:1 (breakout)
 WATCH  $83,000 — MA200 breakout confirmation
 WEEKLY Bearish — primary trend not recovered; trade with reduced size
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

*Note: This analysis assumes BTC refers to Bitcoin on the spot crypto market.*

---

### 1. Market Snapshot

| Indicator | Value | Signal |
|---|---|---|
| RSI(14) | 64.61 | Positive — 5.4pts before overbought (70) |
| MACD Histogram | 29.98 | Positive but 5-session decel: 195→128→74→50→29 ⚠ |
| KDJ K / D | 66.54 / 70.01 | K crossed below D — short-term caution |
| SMA20 / SMA50 | $78,582 / $73,888 | Price above both — near/medium-term bullish |
| SMA200 | $82,719 | Price below — structural ceiling unbroken |
| Weekly trend | Bearish | Below weekly MA50 and MA200 |

*Data: Yahoo Finance daily close via yfinance. MAs are Simple Moving Averages (SMA). RSI and MACD use EMA-based smoothing (pandas-ta defaults). Values may differ ±5–15pt from platforms using Wilder's smoothing or different price feeds.*

**Trend: Sideways with Short-Term Bullish Bias.** MA20/MA50 stack bullish; price below MA200 — long-term structure not yet recovered. MACD 5-session deceleration is the primary near-term risk flag.

**Sentiment: Bullish.** $2.7B ETF inflows over 3 weeks, whale net longs at 2026 highs, Fear & Greed 49→50. Offset by Fed rate-cut expectations being scrapped. *(CoinDesk, The Block — last 48h)*

---

### 2. Key Drivers

**Bull**
- **ETF inflows sustained:** 3-week consecutive net inflows (~$2.7B). Institutional positioning confirmed.
- **Short-squeeze tailwind:** $300M+ short liquidations in May; whale net longs at 2026 high (~$3.5B on Hyperliquid). Remaining shorts add fuel on any push higher.
- **$80,000 floor holding:** Multiple intraday tests absorbed without daily close below — active demand confirmed at this zone.

**Bear**
- **MA200 ($82,719) unbroken:** Not reclaimed since 2025 ATH decline. Failure to close above confirms primary trend remains bearish.
- **MACD near zero-cross:** 85% histogram collapse in 5 sessions (195→29). A cross below zero triggers systematic sell signals.
- **Compression at resistance:** 0.40% daily range at structural ceiling. Low-volatility compression at resistance historically precedes a sharp directional break — direction uncertain.

*Near-term (1-2 day) bias: bull. Structural (1-3 week) bias: bear.*

---

### 3. Levels & Entry Conditions

**Price Zones**

| | Zone | Basis |
|---|---|---|
| S1 — Immediate | $79,500–$80,000 | Intraday floor + psychological level |
| S2 — Intermediate | $75,000–$75,500 | April 2026 swing low; rising MA20 |
| R1 — Immediate | $82,500–$83,000 | MA200 ($82,719) — structural ceiling |
| R2 — Intermediate | $90,000–$91,000 | December 2025 swing high |

**Trade Setup**
*(R/R = (Target − Entry) ÷ (Entry − Stop))*

| Type | Trigger | Entry | Stop | Risk | T1 | R/R | T2 | R/R |
|---|---|---|---|---|---|---|---|---|
| Support | Price in $79,500–$80,000 AND MACD hist > 0 | $80,000 | $78,000 | −2.5% | $83,000 | 1.5:1 | $90,500 | 5.25:1 |
| Breakout | Daily close > $83,000 AND vol > $24.9B | $83,000 | $78,000 | −6.0% | $90,500 | 1.5:1 | — | — |

**Invalidation:** Daily close below $78,000 OR MACD histogram crosses below zero.

*All conditions reference daily close — not intraday prints. 24/7 market: stops can trigger at any hour.*

---

*⚠ Educational purposes only. Not investment advice. Crypto trading carries substantial risk of loss.*

---

## Rules demonstrated in this example

| Rule | Where |
|---|---|
| Signal header — 5 lines, all fields populated | Top block |
| Assumption note | Below header |
| Indicator table — 6 rows, values to 2dp | Section 1 |
| Trend state — 2 sentences max | Section 1 |
| Sentiment — 2 sentences, source cited | Section 1 |
| Drivers — 3 bull + 3 bear, near-term only | Section 2 |
| Near-term vs structural bias stated | Section 2 close |
| S1/S2 + R1/R2 only — no far tiers | Section 3 |
| Merged Trade Setup table — trigger + R/R in one row | Section 3 |
| Invalidation — explicit condition | Section 3 |
| No 1/3 split language | Throughout |
| No structural macro in drivers | Section 2 |
| Disclaimer — single footnote line only | Bottom |
