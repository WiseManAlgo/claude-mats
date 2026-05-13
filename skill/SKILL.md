---
name: mats
description: Generate structured 1-2 day trading signal briefs for crypto (BTC, ETH, SOL...), US equities (AAPL, NVDA, TSLA...), and HK equities (700, 9988, 0005...). Trigger on /mats [SYMBOL] or natural language: "analyze AAPL", "signal on 700", "report on ETH", "run NVDA for me", "give me a brief on TSLA", "crypto report on BTC". Covers all asset types through a unified workflow — auto-detects asset class, routes to the correct data and analysis module, and outputs a consistent signal brief format optimized for algo traders.
---

# Multi-Asset Trading Analysis Skill — MATS v2

Produces concise signal briefs for algo traders and systematic investors across crypto, US equities, and HK equities. Unified workflow: auto-detect → fetch → compute → search → write. Output is identical in structure across all asset classes — 5-line header, indicator snapshot, 3+3 material drivers, merged levels-and-triggers table with explicit R/R and entry conditions. Mandatory symmetric bull/bear analysis. Live data only. No narrative padding.

## Scope

| Aspect | Coverage |
|---|---|
| Asset classes | Crypto, US equity, HK equity |
| Command | `/mats [SYMBOL]` |
| Bar interval | Daily candles (fixed) |
| Crypto universe | Any symbol resolvable as `{SYMBOL}-USD` via yfinance |
| US equity universe | Any symbol listed on NYSE / NASDAQ via yfinance |
| HK equity universe | Any 1–4 digit numeric symbol listed on HKEX via yfinance |

If user requests a different bar interval: `This skill uses daily candles as the fixed interval for 1-2 day swing analysis. For intraday timeframes, use a charting tool like TradingView.`

---

## Activation Triggers

### Primary: slash command
- `/mats BTC`
- `/mats AAPL`
- `/mats 700` or `/mats 0700`

### Secondary: natural language
- "Analyze TSLA for the next couple of days"
- "Give me a trading report on ETH"
- "Run a signal brief on 9988"
- "Should I look at NVDA right now?"
- "Crypto report on SOL"

When triggering on natural language, internally treat as `/mats {SYMBOL}` and proceed.

---

## Workflow (follow in strict order)

### Step 0: Detect Asset Type

Write and execute this Python logic at runtime:

```python
import yfinance as yf

def detect_asset_type(raw):
    s = raw.strip().upper()

    # Explicit crypto suffix — deterministic
    for sfx in ['/USDT', '/USD', '-USDT', '-USD']:
        if s.endswith(sfx):
            base = s[:-len(sfx)]
            return base + '-USD', 'crypto'

    # HK equity — numeric input (handles 700, 0700, 0700.HK)
    clean = s.replace('.HK', '')
    if clean.isdigit():
        return clean.zfill(4) + '.HK', 'hk_equity'

    # Try crypto via yfinance (covers BTC, ETH, PEPE, WIF, etc.)
    try:
        df_test = yf.Ticker(s + '-USD').history(period='5d')
        if not df_test.empty:
            return s + '-USD', 'crypto'
    except Exception:
        pass

    # Try US equity via yfinance
    try:
        df_test = yf.Ticker(s).history(period='5d')
        if not df_test.empty:
            return s, 'us_equity'
    except Exception:
        pass

    return None, 'unknown'
```

If `unknown`: abort with `Symbol {X} not found. Check the ticker and resubmit.`

Rare collision (symbol resolves as both crypto and equity): crypto takes precedence. Add note: `{SYMBOL} resolved as crypto. Resubmit with clarification if you intended the equity.`

### Step 1: Parse and Validate

1. Extract base symbol from input. Normalize:
   - `BTC/USDT`, `BTC/USD`, `BTC-USDT` → `BTC`
   - `700`, `0700`, `0700.hk` → `0700.HK`
   - `aapl`, `AAPL ` → `AAPL`
2. Run `detect_asset_type()` → get yfinance symbol and asset class.
3. Add assumption note below header in report:
   - Crypto: `Note: This analysis assumes {SYMBOL} refers to {Full Name} on the spot crypto market.`
   - US equity: `Note: This analysis assumes {SYMBOL} refers to {Full Company Name} listed on {NASDAQ/NYSE}.`
   - HK equity: `Note: This analysis assumes {SYMBOL} refers to {Full Company Name} listed on HKEX.`

### Step 2: Fetch Market Data

Write Python inline at runtime — do not use a pre-built script.

**All assets:**
```python
import yfinance as yf

ticker = yf.Ticker(yf_symbol)
df   = ticker.history(period='200d', interval='1d')   # daily: indicators + S/R
df_w = ticker.history(period='1y',   interval='1wk')  # weekly: trend context

if df.empty or df_w.empty:
    # Abort — do not generate report with incomplete data
    raise ValueError(f'Insufficient data for {yf_symbol}. Verify ticker and retry.')
```

Required derived values (all assets):
- Latest close: `df['Close'].iloc[-1]`
- 24H change %: `(df['Close'].iloc[-1] - df['Close'].iloc[-2]) / df['Close'].iloc[-2] * 100`
- 24H volume in native currency: `df['Volume'].iloc[-1] * df['Close'].iloc[-1]`

**Weekly MA (all assets — fixed at MA50 + MA200):**
```python
df_w['WMA50']  = df_w['Close'].rolling(50).mean()
df_w['WMA200'] = df_w['Close'].rolling(200).mean()
weekly_bars = int(df_w['WMA50'].notna().sum())

# Weekly trend determination
latest_close = df['Close'].iloc[-1]
wma50  = df_w['WMA50'].iloc[-1]
wma200 = df_w['WMA200'].iloc[-1]

if weekly_bars >= 100:
    if latest_close > wma50 > wma200:
        weekly_trend = 'Bullish'
    elif latest_close < wma50 < wma200:
        weekly_trend = 'Bearish'
    else:
        weekly_trend = 'Sideways'
else:
    # Insufficient history for WMA200 — use WMA50 only
    weekly_trend = 'Bullish' if latest_close > wma50 else 'Bearish'
    weekly_trend += ' (weekly MA200 unavailable — insufficient history)'
```

**Equity only — fetch fundamentals:**
```python
info = ticker.info
fundamentals = {
    'market_cap':     info.get('marketCap'),
    'trailing_pe':    info.get('trailingPE'),
    'forward_pe':     info.get('forwardPE'),
    'eps_ttm':        info.get('trailingEps'),
    'pb_ratio':       info.get('priceToBook'),
    'dividend_yield': info.get('dividendYield'),
    'beta':           info.get('beta'),
    'sector':         info.get('sector'),
    'industry':       info.get('industry'),
    'week52_high':    info.get('fiftyTwoWeekHigh'),
    'week52_low':     info.get('fiftyTwoWeekLow'),
    'analyst_target': info.get('targetMeanPrice'),
    'avg_vol_20d':    info.get('averageVolume'),
}
# Any None value → flag for web search fallback in Step 5
```

### Step 3: Compute Indicators

Write inline at runtime. Applies to all asset types.

```python
import pandas_ta as ta

df['RSI']    = ta.rsi(df['Close'], length=14)
macd         = ta.macd(df['Close'], fast=12, slow=26, signal=9)
df['MACD_h'] = macd['MACDh_12_26_9']
df['SMA20']  = df['Close'].rolling(20).mean()
df['SMA50']  = df['Close'].rolling(50).mean()
df['SMA200'] = df['Close'].rolling(200).mean()

# KDJ (9,3,3) — hand-implemented; not available in pandas-ta
low9  = df['Low'].rolling(9).min()
high9 = df['High'].rolling(9).max()
rsv   = (df['Close'] - low9) / (high9 - low9) * 100
df['K'] = rsv.ewm(com=2).mean()
df['D'] = df['K'].ewm(com=2).mean()
df['J'] = 3 * df['K'] - 2 * df['D']

# MACD last 5 sessions — for deceleration/acceleration detection
macd_last5 = df['MACD_h'].iloc[-5:].round(2).tolist()

# Volume baseline — equity only
if asset_type in ('us_equity', 'hk_equity'):
    avg_vol_20d = df['Volume'].rolling(20).mean().iloc[-1]
    breakout_vol_threshold = avg_vol_20d * 1.5
```

Round all output indicator values to **exactly 2 decimal places**.

### Step 4: Identify Support & Resistance

From the 200-day daily window. Applies to all asset types.

1. Identify swing highs: candle whose High exceeds every High in 5 bars left and 5 bars right. Symmetric for swing lows.
2. Cluster swings within ±0.5% of each other into single zones.
3. PROXIMITY FILTER (apply before scoring):
   - Support candidates: keep only clustered zones whose midpoint is BELOW current price.
   - Resistance candidates: keep only clustered zones whose midpoint is ABOVE current price.
4. Sort each filtered set by distance from current price ascending (nearest first).
5. Score within the filtered + sorted set by: (a) number of touches, (b) recency.
6. Select S1 (nearest support), S2 (second-nearest support), R1 (nearest resistance), R2 (second-nearest resistance). No additional tiers.
7. Round to trader-friendly values per asset scale — see Numerical Formatting Rules.

### Step 4b: R/R Calculation and Setup Grade

**R/R formula:** `R/R = (Target − Entry) ÷ (Entry − Stop)`

Support entry:
- Entry = S1 midpoint
- Stop = nearest clean level below S1 bottom (per asset rounding rules)
- T1 = R1 midpoint; T2 = R2 midpoint

Breakout entry:
- Entry = R1 top
- Stop = S1 midpoint
- T1 = R2 midpoint; T2 = omit if R2 is the only meaningful target

State risk as % from entry. Calculate both entry types.

**Setup Grade:**
- **A**: R/R (T1) > 3:1 AND daily trend clear AND weekly trend not opposing
- **B**: R/R (T1) 1.5–3:1 AND daily trend clear; or strong setup despite weekly headwind
- **C**: R/R (T1) < 1.5:1; or daily/weekly trend conflict; or extreme indicator readings

**Bias:**
- **LONG**: bull drivers materially outweigh bear; setup favors upside entry
- **SHORT**: bear drivers materially outweigh bull; setup favors downside or avoidance of longs
- **NEUTRAL**: drivers balanced; no clear directional edge — monitor, do not enter

### Step 5: Web Searches

**Crypto — 6 searches:**

| # | Purpose | Query |
|---|---|---|
| 1 | Bull news | `{ASSET} positive catalysts last 48 hours coindesk OR cointelegraph` |
| 2 | Bull news | `{ASSET} institutional inflows ETF approval last 48 hours` |
| 3 | Bear news | `{ASSET} regulatory risk negative news last 48 hours` |
| 4 | Bear news | `{ASSET} sell-off liquidations whale dumping last 48 hours` |
| 5 | Macro | `Federal Reserve rates crypto macro {month} {year}` |
| 6 | Sentiment | `crypto fear greed index sentiment {date}` |
| 7 | (Fallback only) | Run if any of 1–6 returned fewer than 2 substantive results |

**Equity — 4 searches + fundamentals fallback:**

| # | Purpose | Query |
|---|---|---|
| 1 | Bull news | `{COMPANY NAME} positive catalyst earnings beat upgrade last 48 hours` |
| 2 | Bear news | `{COMPANY NAME} downgrade miss risk negative news last 48 hours` |
| 3a | US — analyst | `{TICKER} analyst price target consensus {month} {year} site:reuters.com OR site:cnbc.com` |
| 3b | HK — filings | `{COMPANY NAME} HKEX announcement results {month} {year}` |
| 4 | Sector/macro | `{SECTOR} sector outlook {month} {year} Reuters OR Bloomberg` |

Equity fundamentals fallback (triggered per None field from Step 2):
- PE → `{TICKER} PE ratio trailing forward {year}`
- EPS → `{TICKER} EPS earnings per share TTM {year}`
- PB → `{TICKER} price to book ratio {year}`
- ROE → `{TICKER} return on equity ROE {year}` *(always run — yfinance unreliable for ROE)*
- Earnings beat/miss → `{TICKER} earnings beat miss consensus Q{N} {year}` *(always run)*

Cap equity fallback at 3 searches total. Remaining None fields → `Data not available`.

For each search: run `web_fetch` on the single most relevant URL only.

### Step 6: Draft Bull/Bear Lists (before writing report)

Internally enumerate all candidate drivers:

**Crypto:** bull/bear technical + bull/bear fundamental (ETF flows, on-chain, regulatory, macro, sentiment). See `references/crypto.md`.

**Equity:** bull/bear technical + bull/bear fundamental (earnings, analyst action, sector, macro, insider activity). See `references/equity.md`.

Materiality filter: near-term (48h) catalysts only. No structural macro padding.
Cap at 3 per side. Apply Symmetry Guard before writing.

### Step 7: Score News Sentiment

Apply weighted scoring rubric — see News Sentiment Rubric section.
Asset-class-specific definitions for high-impact and speculative items apply.

### Step 8: Write Report

See Report Structure section below. Match structure, density, and tone of the relevant gold-standard example.

### Step 9: Pre-Output Checklist

- [ ] Asset type correctly detected; correct module applied
- [ ] Assumption note present and correct (market, exchange)
- [ ] Signal header complete — all 5 lines populated
- [ ] Correct currency: `$` (USD) or `HK$` throughout
- [ ] Indicator table: 6 rows, all values to 2dp
- [ ] Fundamentals block: present for equity; absent for crypto
- [ ] Weekly MA: WMA50 + WMA200; note present if MA200 unavailable
- [ ] Only S1/S2 + R1/R2 — no additional tiers
- [ ] R/R calculated from actual levels; formula shown
- [ ] Grade A/B/C assigned per definition
- [ ] Volume trigger: `1.5× 20-day avg` (equity) or USD threshold (crypto)
- [ ] Drivers: 3 per side max; near-term only; symmetry guard applied
- [ ] Banned phrases absent
- [ ] "24/7 market" note: crypto reports only
- [ ] Correct disclaimer line (crypto vs securities)
- [ ] Past performance inline note appended to any historical-pattern reference

---

## Report Structure (fixed — do not modify)

### Signal Header

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 {ASSET CLASS} SIGNAL BRIEF — {SYMBOL} — {DATE UTC}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 PRICE  {price}   24H  {change%}   VOL  {volume}
 BIAS   {LONG/SHORT/NEUTRAL}   GRADE  {A/B/C}   SENTIMENT  {tier}
 R/R    {support R/R} (support) | {breakout R/R} (breakout)
 WATCH  {single most critical level — why}
 WEEKLY {Bullish/Bearish/Sideways} — {one-line structural implication}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

`{ASSET CLASS}`: `CRYPTO` for crypto assets; `EQUITY` for US and HK stocks.

Currency in PRICE line and throughout:
- Crypto + US equity: `$`
- HK equity: `HK$`

Volume format:
- Crypto: `$XXB` (USD-denominated)
- US equity: `XXM shares ($XXB)`
- HK equity: `XXM shares (HK$XXB)`

Below header: assumption note (see Step 1).

### Section 1. Market Snapshot

**Indicator table (all assets — 6 rows fixed):**

| Indicator | Value | Signal |
|---|---|---|
| RSI(14) | {value} | {distance from 70/30; overbought / oversold / healthy} |
| MACD Histogram | {value} | {last 5 sessions if directional change detected; decel/accel note} |
| KDJ K / D | {K} / {D} | {K above or below D; short-term momentum implication} |
| SMA20 / SMA50 | {SMA20} / {SMA50} | {price above/below both; near/medium-term trend state} |
| SMA200 | {SMA200} | {price above/below; structural ceiling or floor} |
| Weekly trend | {Bullish/Bearish/Sideways} | {WMA50 + WMA200 context; one phrase} |

*Data: Yahoo Finance daily close via yfinance. MAs are Simple Moving Averages (SMA). RSI and MACD use EMA-based smoothing (pandas-ta defaults). Values may differ ±5–15pt from platforms using Wilder's smoothing or different price feeds.*

**Fundamentals block (equity only — insert after indicator table):**

| | Value | Note |
|---|---|---|
| Market Cap | {$XB / HK$XB} | {Large / Mid / Small cap} |
| PE (trailing / fwd) | {X} / {X} | {above / below sector avg if available; or Data not available} |
| EPS (TTM) | {$X / HK$X} | {beat / in-line / miss vs last consensus} |
| Analyst Target | {$X / HK$X} | {+/−X% upside/downside from current price} |

If any field unavailable after web fallback: `Data not available`.
This block is equity-only — never appears in crypto reports.

**Trend state (2 sentences max):** Primary trend classification + key justification. Short-term state + key justification.

**Sentiment (2 sentences max):** Rating + news-based justification. Source and recency window.

### Section 2. Key Drivers

**Bull** — 3 most material points, 1–2 lines each. Near-term catalysts only.
**Bear** — 3 most material points, 1–2 lines each. Near-term risks only.

Driver checklist by asset: crypto → `references/crypto.md`; equity → `references/equity.md`.

If asymmetric (genuine imbalance): state explicitly. Do not pad.

Close with one line: near-term vs structural bias. Example: `Near-term (1-2 day) bias: bull. Structural (1-3 week) bias: bear.`

### Section 3. Levels & Entry Conditions

**Price Zones:**

| | Zone | Basis |
|---|---|---|
| S1 — Immediate | {level} | {basis — swing low, MA, psychological level} |
| S2 — Intermediate | {level} | {basis} |
| R1 — Immediate | {level} | {basis} |
| R2 — Intermediate | {level} | {basis} |

**Trade Setup:**
*(R/R = (Target − Entry) ÷ (Entry − Stop))*

| Type | Trigger | Entry | Stop | Risk | T1 | R/R | T2 | R/R |
|---|---|---|---|---|---|---|---|---|
| Support | {exact condition} | {level} | {level} | {%} | {level} | {ratio} | {level or —} | {ratio or —} |
| Breakout | {exact condition} | {level} | {level} | {%} | {level} | {ratio} | {level or —} | {ratio or —} |

Breakout volume trigger:
- Crypto: `vol > ${X}B` (use 1.5× recent 20-day average daily USD volume)
- Equity: `vol > 1.5× 20-day avg (≈ {X}M shares)`

**Invalidation:** {exact price condition} OR {exact indicator condition}.

*All conditions reference daily close — not intraday prints.*
*Crypto only: 24/7 market — stops can trigger at any hour.*

### Disclaimer (always last — single line, no section header)

Select the correct line from `references/disclaimers.md`:
- Crypto: `⚠ Educational purposes only. Not investment advice. Crypto trading carries substantial risk of loss.`
- Equity: `⚠ Educational purposes only. Not investment advice. Securities trading carries substantial risk of loss.`

---

## News Sentiment Rubric

### Scoring formula (all assets)
- **Recency weight:** last 24h = 3×; last 25–48h = 2×; older = 1× (1× valid only for macro/sentiment searches)
- **Polarity:** positive (+1), neutral (0), negative (−1)
- **High-impact multiplier:** 2× on top of recency weight

### High-impact items

**Crypto:**
- Regulatory action: SEC, CFTC, EU MiCA, China bans/approvals, ETF approvals/denials
- Exchange events: hacks, insolvencies, major listings/delistings
- Protocol events: halvings, major upgrades, exploit patches
- Institutional moves >$100M: BlackRock, Fidelity, MicroStrategy purchases or sales
- Macro shocks: surprise Fed decisions, major-economy currency or credit crises

**Equity:**
- Earnings release: EPS or revenue vs consensus (beat or miss)
- Full-year guidance revision: raised or cut
- Fed rate decision or FOMC statement
- Major analyst action by top-tier firm (Goldman, Morgan Stanley, JPMorgan): upgrade or downgrade with new price target
- M&A announcement: acquisition, merger, takeover bid
- Major regulatory action: SEC enforcement, antitrust ruling, government investigation

### Speculative items

**Crypto:** Price predictions ("$X target", "to the moon"), influencer opinion pieces, technical inevitabilities
**Equity:** Price target with no underlying model or new catalyst, analyst cheerleading with no new information, social media / Reddit momentum without fundamental backing

### Tier mapping
Calculate: weighted positive score / (weighted positive + weighted negative) as a percentage.

| Tier | Trigger |
|---|---|
| **Panic** | ≥70% weighted negative AND ≥2 high-impact negative items |
| **Bearish** | 55–70% weighted negative |
| **Neutral** | 45–55% on either side |
| **Bullish** | 55–70% weighted positive |
| **Overexcited** | ≥70% weighted positive AND ≥2 speculative items |

If Panic AND Overexcited both fire: Panic takes precedence.

---

## Non-Negotiable Guardrails

### Symmetry Guard
Both sides must be presented in good faith with all material findings. If asymmetric, state explicitly:
- `Bull case outweighs bear 4:1; only minor near-term risks identified.`
- `Bear case dominates; the only constructive factor is oversold RSI.`
Do NOT pad the weaker side. Do NOT suppress the stronger side.

### Anti-Fabrication Guard
Every numerical data point tied to a yfinance result or a specific search-returned URL. Missing data → `Data not available`. Never infer, never guess. Rounding permitted within scale rules below — must not materially distort values.

### Precision Rule

**Banned phrases:**
`may want to`, `might consider`, `could buy`, `should look at`, `guaranteed`, `risk-free`, `all-in`, `buy the dip`, `must buy`, `must sell`

**Permitted phrases:**
`failure to hold X targets a retest of Z`, `bullish catalysts outweigh risks`, `setup increases the probability of [specific outcome]`, `hold above X historically precedes moves to Y`, `near-term momentum favors upside`

### Position Sizing Rule
- DO state risk as % from entry: `stop at $X represents −Y% from entry`
- DO NOT recommend % portfolio allocations, position sizes, or exit split ratios
- DO NOT recommend specific leverage multiples
- Crypto perpetuals context: add `leverage amplifies both gains and losses`

### Numerical Formatting Rules

Indicator values: exactly 2 decimal places.

| Asset | Current price | S/R levels |
|---|---|---|
| BTC | 2dp | nearest $500 |
| ETH | 2dp | nearest $50 |
| Sub-$100 crypto (SOL, BNB, etc.) | 2dp | nearest $1 |
| Sub-$1 crypto (DOGE, SHIB, etc.) | up to 6 sig figs | nearest $0.0001 |
| US large-cap (>$100) | 2dp | nearest $1.00 |
| US mid-cap ($20–$100) | 2dp | nearest $0.50 |
| US small-cap (<$20) | 2dp | nearest $0.25 |
| HK stocks (>HK$20) | 2dp | nearest HK$0.50 |
| HK stocks (<HK$20) | 2dp | nearest HK$0.10 |

### Past Performance Rule
Any sentence referencing historical pattern outcomes must be followed inline by: `(Past performance is not indicative of future results.)`

---

## Reference Files

- `references/crypto.md` — Crypto driver checklist + on-chain search guidance. Read before writing Section 2 for crypto assets.
- `references/equity.md` — Equity driver checklist + yfinance field reference + web fallback queries. Read before writing Section 2 for equity assets.
- `references/disclaimers.md` — Exact disclaimer lines by asset class.
- `examples/btc_full_report.md` — Gold-standard crypto output. Match structure, density, and tone.
- `examples/aapl_report.md` — Gold-standard US equity output. Match structure, density, and tone.
