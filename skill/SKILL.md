---
name: mats
description: Generate structured 1-2 day trading signal briefs for crypto (BTC, ETH, SOL...), US equities (AAPL, NVDA, TSLA...), and HK equities (700, 9988, 0005...). Trigger on /mats [SYMBOL] or natural language: "analyze AAPL", "signal on 700", "report on ETH", "run NVDA for me", "give me a brief on TSLA", "crypto report on BTC". Covers all asset types through a unified workflow — auto-detects asset class, routes to the correct data and analysis module, and outputs a consistent signal brief format optimized for algo traders.
---

# Multi-Asset Trading Analysis Skill — MATS v2

Produces concise signal briefs for algo traders and systematic investors across crypto, US equities, and HK equities. Unified workflow: auto-detect → fetch → compute → search → write. Output is identical in structure across all asset classes — 5-line header, indicator snapshot, 3+3 material drivers, merged levels-and-triggers table with explicit R/R and entry conditions. Mandatory symmetric bull/bear analysis. Live data only. No narrative padding.

## Scope

| Aspect | Coverage |
|---|---|
| Asset classes | Crypto, US equity, HK equity, China A-share |
| Command | `/mats [SYMBOL]` |
| Bar interval | Daily candles (fixed) |
| Crypto universe | Any symbol resolvable as `{SYMBOL}-USD` via yfinance |
| US equity universe | Any symbol listed on NYSE / NASDAQ via yfinance |
| HK equity universe | Any 1–4 digit numeric symbol listed on HKEX via yfinance |
| China A-share universe | Any 6-digit numeric (SSE/SZSE/ChiNext) via AkShare |

If user requests a different bar interval: `This skill uses daily candles as the fixed interval for 1-2 day swing analysis. For intraday timeframes, use a charting tool like TradingView.`

---

## Activation Triggers

### Primary: slash command
- `/mats BTC`
- `/mats AAPL`
- `/mats 700` or `/mats 0700`
- `/mats 300782` or `/mats 600519` or `/mats 000001`

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

    # China A-share: explicit suffix
    for sfx in ['.SZ', '.SS', '.SH']:
        if s.endswith(sfx):
            return s.replace(sfx, ''), 'cn_equity'

    # China A-share: 6-digit numeric (SSE starts 6xx,
    # SZSE/ChiNext starts 0xx or 3xx)
    if clean.isdigit() and len(clean) == 6:
        if clean[0] in ('0', '3', '6'):
            return clean, 'cn_equity'

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
   - cn_equity (starts with 6): `Note: This analysis assumes {SYMBOL} refers to {Full Company Name} listed on Shanghai Stock Exchange (SSE).`
   - cn_equity (starts with 0): `Note: This analysis assumes {SYMBOL} refers to {Full Company Name} listed on Shenzhen Stock Exchange (SZSE).`
   - cn_equity (starts with 3): `Note: This analysis assumes {SYMBOL} refers to {Full Company Name} listed on Shenzhen ChiNext board.`

### Step 2: Fetch Market Data

Write Python inline at runtime — do not use a pre-built script.

```python
# ── China A-share: use AkShare ──────────────────────
if asset_type == 'cn_equity':
    import akshare as ak
    from datetime import datetime, timedelta

    end_date    = datetime.now().strftime('%Y%m%d')
    start_daily = (datetime.now() - timedelta(days=300)).strftime('%Y%m%d')
    start_weekly= (datetime.now() - timedelta(days=365*5)).strftime('%Y%m%d')

    col_map = {
        '日期':'Date','开盘':'Open','收盘':'Close',
        '最高':'High','最低':'Low',
        '成交量':'Volume','成交额':'Amount'
    }

    # Daily bars
    df = ak.stock_zh_a_hist(
        symbol=symbol, period='daily',
        start_date=start_daily, end_date=end_date,
        adjust='qfq'
    ).rename(columns=col_map)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.set_index('Date')

    # Weekly bars
    df_w = ak.stock_zh_a_hist(
        symbol=symbol, period='weekly',
        start_date=start_weekly, end_date=end_date,
        adjust='qfq'
    ).rename(columns=col_map)
    df_w['Date'] = pd.to_datetime(df_w['Date'])
    df_w = df_w.set_index('Date')

    if df.empty or df_w.empty:
        raise ValueError(f'No data returned for {symbol} via AkShare.')

    # Fundamentals via AkShare
    try:
        info_raw  = ak.stock_individual_info_em(symbol=symbol)
        info_dict = dict(zip(info_raw['item'], info_raw['value']))
    except Exception:
        info_dict = {}

    fundamentals = {
        'market_cap':     info_dict.get('总市值'),
        'trailing_pe':    info_dict.get('市盈率TTM'),
        'forward_pe':     info_dict.get('市盈率(动)'),
        'eps_ttm':        info_dict.get('每股收益TTM'),
        'pb_ratio':       info_dict.get('市净率'),
        'dividend_yield': info_dict.get('股息率TTM'),
        'beta':           info_dict.get('Beta'),
        'sector':         info_dict.get('行业'),
        'analyst_target': None,  # web search fallback
    }
    currency = '¥'

# ── All other assets: use yfinance ──────────────────
else:
    import yfinance as yf

    ticker = yf.Ticker(yf_symbol)
    df   = ticker.history(period='200d', interval='1d')   # daily: indicators + S/R
    df_w = ticker.history(period='5y',   interval='1wk')  # weekly: trend context (5y needed for WMA200)

    if df.empty or df_w.empty:
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
    weekly_trend = 'Bullish' if latest_close > wma50 else 'Bearish'
    weekly_trend += ' (weekly MA200 unavailable — insufficient history)'
```

**US/HK equity only — fetch fundamentals via yfinance (cn_equity uses AkShare block above):**
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
if asset_type in ('us_equity', 'hk_equity', 'cn_equity'):
    avg_vol_20d = df['Volume'].rolling(20).mean().iloc[-1]
    breakout_vol_threshold = avg_vol_20d * 1.5
```

Round all output indicator values to exactly 2 decimal places.

### Step 4: Identify Support & Resistance

From the 200-day daily window. Applies to all asset types.

1. Swing high: candle whose High exceeds every High in 5 bars left and 5 bars right. Symmetric for swing lows.
2. Cluster swings within ±0.5% of each other into single zones.
3. PROXIMITY FILTER (apply before scoring):
   - Support candidates: keep only clustered zones whose midpoint is BELOW current price.
   - Resistance candidates: keep only clustered zones whose midpoint is ABOVE current price.
4. Sort each filtered set by distance from current price ascending (nearest first).
5. Score within the filtered + sorted set by: (a) number of touches, (b) recency.
6. Select S1 (nearest support), S2 (second-nearest support), R1 (nearest resistance), R2 (second-nearest resistance). No additional tiers.
7. Round to trader-friendly values per asset scale — see Numerical Formatting Rules.

### Step 4b: R/R Calculation and Setup Grade

R/R formula: `R/R = (Target − Entry) ÷ (Entry − Stop)`

Support entry:
- Entry = S1 midpoint
- Stop = nearest clean level below S1 bottom (per asset rounding rules)
- T1 = R1 midpoint; T2 = R2 midpoint

Breakout entry:
- Entry = R1 top
- Stop = S1 midpoint
- T1 = R2 midpoint; T2 = omit if R2 is the only meaningful target

State risk as % from entry. Calculate both entry types.

Grade:
- A: R/R (T1) > 3:1 AND daily trend clear AND weekly trend not opposing
- B: R/R (T1) 1.5–3:1 AND daily trend clear; or strong setup despite weekly headwind
- C: R/R (T1) < 1.5:1; or daily/weekly trend conflict; or extreme indicator readings

Bias:
- LONG: bull drivers materially outweigh bear; setup favors upside entry
- SHORT: bear drivers materially outweigh bull; setup favors downside or avoidance of longs
- NEUTRAL: drivers balanced; no clear directional edge — monitor, do not enter

### Step 5: Web Searches

Crypto — 6 searches:

| # | Purpose | Query |
|---|---|---|
| 1 | Bull news | `{ASSET} positive catalysts last 48 hours coindesk OR cointelegraph` |
| 2 | Bull news | `{ASSET} institutional inflows ETF approval last 48 hours` |
| 3 | Bear news | `{ASSET} regulatory risk negative news last 48 hours` |
| 4 | Bear news | `{ASSET} sell-off liquidations whale dumping last 48 hours` |
| 5 | Macro | `Federal Reserve rates crypto macro {month} {year}` |
| 6 | Sentiment | `crypto fear greed index sentiment {date}` |
| 7 | (Fallback only) | Run if any of 1–6 returned fewer than 2 substantive results |

Equity — 4 searches + fundamentals fallback:

| # | Purpose | Query |
|---|---|---|
| 1 | Bull news | `{COMPANY NAME} positive catalyst earnings beat upgrade last 48 hours` |
| 2 | Bear news | `{COMPANY NAME} downgrade miss risk negative news last 48 hours` |
| 3a | US — analyst | `{TICKER} analyst price target consensus {month} {year} site:reuters.com OR site:cnbc.com` |
| 3b | HK — filings | `{COMPANY NAME} HKEX announcement results {month} {year}` |
| 3c | CN — analyst/filings | `{TICKER} 目标价 分析师 {year}` |
| 4 | Sector/macro | `{SECTOR} sector outlook {month} {year} Reuters OR Bloomberg` |

China A-share fundamentals fallback (triggered per None field from AkShare):
- Analyst target: `{TICKER} 目标价 分析师 {year}`
- Earnings beat/miss: `{TICKER} 业绩 超预期 不及预期 {quarter} {year}`
- Insider activity: `{TICKER} 大股东 减持 增持 {year}`
- ROE (always run): `{TICKER} 净资产收益率 ROE {year}`

Equity fundamentals fallback (triggered per None field from Step 2):
- PE: `{TICKER} PE ratio trailing forward {year}`
- EPS: `{TICKER} EPS earnings per share TTM {year}`
- PB: `{TICKER} price to book ratio {year}`
- ROE (always run): `{TICKER} return on equity ROE {year}`
- Earnings beat/miss (always run): `{TICKER} earnings beat miss consensus Q{N} {year}`

Cap equity fallback at 3 searches total. Remaining None fields → Data not available.
For each search: run web_fetch on the single most relevant URL only.

### Step 6: Draft Bull/Bear Lists (before writing report)

Internally enumerate all candidate drivers:

Crypto: bull/bear technical + bull/bear fundamental (ETF flows, on-chain, regulatory, macro, sentiment). See references/crypto.md.
Equity: bull/bear technical + bull/bear fundamental (earnings, analyst action, sector, macro, insider activity). See references/equity.md.

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
- [ ] Correct currency: $ (USD), HK$ (HKD), or ¥ (CNY) throughout
- [ ] Indicator table: 6 rows, all values to 2dp
- [ ] Fundamentals block: present for equity; absent for crypto
- [ ] Weekly MA: WMA50 + WMA200; note present if MA200 unavailable
- [ ] Only S1/S2 + R1/R2 — no additional tiers
- [ ] R/R calculated from actual levels; formula shown
- [ ] Grade A/B/C assigned per definition
- [ ] Volume trigger: 1.5x 20-day avg (equity) or USD threshold (crypto)
- [ ] Drivers: 3 per side max; near-term only; symmetry guard applied
- [ ] Each driver ≤ 40 words including label; max 2 lines
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

{ASSET CLASS}: CRYPTO for crypto assets; EQUITY for US, HK, and China A-share stocks.
Currency: $ for USD assets; HK$ for HK stocks; ¥ for China A-shares (CNY) — applied to PRICE and throughout.
Volume: crypto $XXB; US equity XXM shares ($XXB); HK equity XXM shares (HK$XXB); China A-share XXM shares (¥XXB).

Below header: assumption note (see Step 1).

### Section 1. Market Snapshot

Indicator table (all assets — 6 rows fixed):

| Indicator | Value | Signal |
|---|---|---|
| RSI(14) | {value} | {distance from 70/30; overbought / oversold / healthy} |
| MACD Histogram | {value} | {last 5 sessions if directional change detected; decel/accel note} |
| KDJ K / D | {K} / {D} | {K above or below D; short-term momentum implication} |
| SMA20 / SMA50 | {SMA20} / {SMA50} | {price above/below both; near/medium-term trend state} |
| SMA200 | {SMA200} | {price above/below; structural ceiling or floor} |
| Weekly trend | {Bullish/Bearish/Sideways} | {WMA50 + WMA200 context; one phrase} |

Data footnote (always include):
Data: Yahoo Finance daily close via yfinance. MAs are Simple Moving Averages (SMA). RSI and MACD use EMA-based smoothing (pandas-ta defaults). Values may differ ±5–15pt from platforms using Wilder's smoothing or different price feeds.
China A-share data sourced via AkShare from East Money (东方财富). Forward-adjusted (前复权) prices used.

Fundamentals block (equity only — insert after indicator table):

| | Value | Note |
|---|---|---|
| Market Cap | {$XB / HK$XB} | {Large / Mid / Small cap} |
| PE (trailing / fwd) | {X} / {X} | {above / below sector avg if available} |
| EPS (TTM) | {$X / HK$X} | {beat / in-line / miss vs last consensus} |
| Analyst Target | {$X / HK$X} | {+/−X% from current price} |

If any field unavailable after web fallback: Data not available.
This block is equity-only — never appears in crypto reports.

Trend state (2 sentences max): Primary trend + justification. Short-term state + justification.

Sentiment (2 sentences max): Rating + news-based justification. Source and recency window.

### Section 2. Key Drivers

Bull — 3 most material points, 1–2 lines each. Near-term catalysts only.
Bear — 3 most material points, 1–2 lines each. Near-term risks only.

Driver checklist: crypto → references/crypto.md; equity → references/equity.md.
If asymmetric: state explicitly. Do not pad.
Close with one line: near-term vs structural bias.

### Section 3. Levels & Entry Conditions

Price Zones:

| | Zone | Basis |
|---|---|---|
| S1 — Immediate | {level} | {basis} |
| S2 — Intermediate | {level} | {basis} |
| R1 — Immediate | {level} | {basis} |
| R2 — Intermediate | {level} | {basis} |

Trade Setup:
(R/R = (Target − Entry) ÷ (Entry − Stop))

| Type | Trigger | Entry | Stop | Risk | T1 | R/R | T2 | R/R |
|---|---|---|---|---|---|---|---|---|
| Support | {exact condition} | {level} | {level} | {%} | {level} | {ratio} | {level or —} | {ratio or —} |
| Breakout | {exact condition} | {level} | {level} | {%} | {level} | {ratio} | {level or —} | {ratio or —} |

Volume trigger:
- Crypto: vol > ${X}B (use 1.5x recent 20-day average daily USD volume)
- Equity: vol > 1.5x 20-day avg (≈ {X}M shares)

Invalidation: {exact price condition} OR {exact indicator condition}.

All conditions reference daily close — not intraday prints.
Crypto only: 24/7 market — stops can trigger at any hour.

### Disclaimer (always last — single line, no section header)

- Crypto: ⚠ Educational purposes only. Not investment advice. Crypto trading carries substantial risk of loss.
- Equity: ⚠ Educational purposes only. Not investment advice. Securities trading carries substantial risk of loss.

---

## News Sentiment Rubric

Scoring formula (all assets):
- Recency weight: last 24h = 3x; last 25–48h = 2x; older = 1x (1x valid only for macro/sentiment searches)
- Polarity: positive (+1), neutral (0), negative (−1)
- High-impact multiplier: 2x on top of recency weight

High-impact items — Crypto:
- Regulatory action (SEC, CFTC, MiCA, ETF approvals/denials)
- Exchange events (hacks, insolvencies, major listings/delistings)
- Protocol events (halvings, major upgrades, exploit patches)
- Institutional moves >$100M (BlackRock, Fidelity, MicroStrategy)
- Macro shocks (surprise Fed decisions, major currency/credit crises)

High-impact items — Equity:
- Earnings release: EPS or revenue vs consensus (beat or miss)
- Full-year guidance revision (raised or cut)
- Fed rate decision or FOMC statement
- Major analyst action by top-tier firm: upgrade/downgrade with new price target
- M&A announcement (acquisition, merger, takeover bid)
- Major regulatory action (SEC enforcement, antitrust ruling)

Speculative items — Crypto: price predictions, influencer calls, technical inevitabilities
Speculative items — Equity: price target with no model/catalyst, analyst cheerleading, Reddit momentum

Tier mapping (weighted positive / (weighted positive + weighted negative)):

| Tier | Trigger |
|---|---|
| Panic | ≥70% weighted negative AND ≥2 high-impact negative items |
| Bearish | 55–70% weighted negative |
| Neutral | 45–55% on either side |
| Bullish | 55–70% weighted positive |
| Overexcited | ≥70% weighted positive AND ≥2 speculative items |

If Panic AND Overexcited both fire: Panic takes precedence.

---

## Non-Negotiable Guardrails

### Symmetry Guard
Both sides in good faith. State imbalance explicitly if genuine. Do not pad. Do not suppress.
- Bull case outweighs bear 4:1; only minor near-term risks identified.
- Bear case dominates; the only constructive factor is oversold RSI.

### Driver Length Rule
Each bull or bear driver must follow this exact format:
- **Bold label (3-5 words max):** One key data point.
  One implication. Maximum 2 lines. Maximum 40 words total
  per driver including the label.

Bad example (too long — reject):
- **ETF inflows sustained:** Three-week consecutive net
  inflows of approximately $2.7B have been recorded.
  Institutional positioning is confirmed. BlackRock and
  Fidelity are the primary accumulators and this directly
  signals that demand is rebuilding at current levels.

Good example (correct format):
- **ETF inflows sustained:** 3-week net inflows ~$2.7B.
  BlackRock + Fidelity leading — institutional demand
  confirmed at current levels.

This rule applies to ALL asset classes. No exceptions.
Violating drivers must be rewritten before output.

### Anti-Fabrication Guard
Every data point tied to yfinance output, AkShare output, or a specific search URL. Missing: Data not available.
Never infer, never guess. Rounding permitted within scale rules below.

### Precision Rule

Banned phrases: may want to, might consider, could buy, should look at, guaranteed, risk-free, all-in, buy the dip, must buy, must sell

Permitted phrases: failure to hold X targets Z, bullish catalysts outweigh risks, setup increases the probability of [outcome], hold above X historically precedes moves to Y, near-term momentum favors upside

### Position Sizing Rule
- DO state risk as % from entry
- DO NOT recommend % allocations, position sizes, or exit split ratios
- DO NOT recommend specific leverage multiples
- Crypto perpetuals: add leverage amplifies both gains and losses

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
| China A-share (>¥50) | 2dp | nearest ¥0.50 |
| China A-share (¥10–¥50) | 2dp | nearest ¥0.10 |
| China A-share (<¥10) | 2dp | nearest ¥0.05 |

### Past Performance Rule
Any historical pattern reference must be followed inline by: (Past performance is not indicative of future results.)

---

## Reference Files

- references/crypto.md — Crypto driver checklist + on-chain search guidance.
- references/equity.md — Equity driver checklist + yfinance field reference + AkShare field reference + web fallback queries.
- references/disclaimers.md — Exact disclaimer lines by asset class.
- examples/btc_full_report.md — Gold-standard crypto output.
- examples/aapl_report.md — Gold-standard US equity output.
