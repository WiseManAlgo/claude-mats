#!/usr/bin/env python3
"""
install_mats_skill.py
=====================
Installer for MATS (Multi-Asset Trading Analysis Skill) v2.
Writes all skill files to ~/.claude/skills/mats/ and installs dependencies.

Usage:
    python3 install_mats_skill.py           # fresh install
    python3 install_mats_skill.py --update  # overwrite existing installation
    python3 install_mats_skill.py --verify  # check installation only

Requirements:
    Python 3.8+
    Claude Code (https://claude.ai/code)
"""

import os
import sys
import shutil
import subprocess
import argparse
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# PRE-FLIGHT CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def check_python_version():
    if sys.version_info < (3, 8):
        print(f"ERROR: Python 3.8+ required. You have {sys.version}")
        sys.exit(1)
    print(f"  python   {sys.version.split()[0]} ✓")


def check_claude_code():
    if shutil.which("claude") is None:
        print("  WARNING: 'claude' command not found in PATH.")
        print("           Install Claude Code from https://claude.ai/code")
        print("           Skill files will still be written — install Claude Code before use.")
    else:
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True, text=True, timeout=5
            )
            version = result.stdout.strip() or result.stderr.strip() or "installed"
            print(f"  claude   {version} ✓")
        except Exception:
            print("  claude   installed ✓")


def install_dependencies():
    deps = ["yfinance", "pandas-ta", "pandas"]
    print("  Installing dependencies...")
    for dep in deps:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", dep, "-q"],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                print(f"    {dep} ✓")
            else:
                print(f"    {dep} FAILED — {result.stderr.strip()[:80]}")
        except subprocess.TimeoutExpired:
            print(f"    {dep} TIMEOUT — install manually: pip install {dep}")
        except Exception as e:
            print(f"    {dep} ERROR — {e}")


def verify_dependencies():
    deps = ["yfinance", "pandas_ta", "pandas"]
    all_ok = True
    for dep in deps:
        try:
            __import__(dep)
            print(f"  {dep.replace('_','-')}   ✓")
        except ImportError:
            print(f"  {dep.replace('_','-')}   MISSING — run: pip install {dep.replace('_','-')}")
            all_ok = False
    return all_ok


# ─────────────────────────────────────────────────────────────────────────────
# FILE CONTENTS
# ─────────────────────────────────────────────────────────────────────────────

SKILL_MD = r"""---
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
df_w = ticker.history(period='5y',   interval='1wk')  # weekly: 5y needed for WMA200

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

Round all output indicator values to exactly 2 decimal places.

### Step 4: Identify Support & Resistance

From the 200-day daily window. Applies to all asset types.

1. Swing high: candle whose High exceeds every High in 5 bars left and 5 bars right. Symmetric for swing lows.
2. Cluster swings within ±0.5% of each other into single zones.
3. Score zones by: (a) number of touches, (b) recency.
4. Select S1 (immediate) + S2 (intermediate) and R1 (immediate) + R2 (intermediate) only. No additional tiers.
5. Round to trader-friendly values per asset scale — see Numerical Formatting Rules.

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
| 4 | Sector/macro | `{SECTOR} sector outlook {month} {year} Reuters OR Bloomberg` |

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
- [ ] Correct currency: $ (USD) or HK$ throughout
- [ ] Indicator table: 6 rows, all values to 2dp
- [ ] Fundamentals block: present for equity; absent for crypto
- [ ] Weekly MA: WMA50 + WMA200 (5y fetch); note if MA200 unavailable
- [ ] Only S1/S2 + R1/R2 — no additional tiers
- [ ] R/R calculated from actual levels; formula shown
- [ ] Grade A/B/C assigned per definition
- [ ] Volume trigger: 1.5x 20-day avg (equity) or USD threshold (crypto)
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

{ASSET CLASS}: CRYPTO for crypto assets; EQUITY for US and HK stocks.
Currency: $ for USD assets; HK$ for HK stocks — applied to PRICE and throughout.
Volume: crypto $XXB; US equity XXM shares ($XXB); HK equity XXM shares (HK$XXB).

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

### Anti-Fabrication Guard
Every data point tied to yfinance output or a specific search URL.
Missing: Data not available. Never infer, never guess.

### Precision Rule
Banned: may want to, might consider, could buy, should look at, guaranteed, risk-free, all-in, buy the dip, must buy, must sell
Permitted: failure to hold X targets Z, bullish catalysts outweigh risks, setup increases the probability of [outcome], hold above X historically precedes moves to Y

### Position Sizing Rule
- DO state risk as % from entry
- DO NOT recommend % allocations, position sizes, or exit split ratios
- DO NOT recommend specific leverage multiples

### Numerical Formatting Rules

| Asset | Current price | S/R levels |
|---|---|---|
| BTC | 2dp | nearest $500 |
| ETH | 2dp | nearest $50 |
| Sub-$100 crypto | 2dp | nearest $1 |
| Sub-$1 crypto | up to 6 sig figs | nearest $0.0001 |
| US large-cap (>$100) | 2dp | nearest $1.00 |
| US mid-cap ($20–$100) | 2dp | nearest $0.50 |
| US small-cap (<$20) | 2dp | nearest $0.25 |
| HK stocks (>HK$20) | 2dp | nearest HK$0.50 |
| HK stocks (<HK$20) | 2dp | nearest HK$0.10 |

### Past Performance Rule
Any historical pattern reference must be followed by: (Past performance is not indicative of future results.)

---

## Reference Files

- references/crypto.md — Crypto driver checklist + on-chain search guidance.
- references/equity.md — Equity driver checklist + yfinance field reference + web fallback queries.
- references/disclaimers.md — Exact disclaimer lines by asset class.
- examples/btc_full_report.md — Gold-standard crypto output.
- examples/aapl_report.md — Gold-standard US equity output.
"""

EQUITY_MD = r"""# Equity Reference — MATS v2

Coding and analysis reference for US and HK equity signal briefs.
Read before writing Section 2 drivers and Section 1 fundamentals block.

---

## Bull Driver Checklist

Near-term (48h) catalysts only. Apply materiality filter before selecting final 3.

### Fundamental
- **Earnings beat:** EPS above consensus estimate last quarter
- **Revenue acceleration:** revenue growth rate increasing vs prior quarter
- **Analyst upgrade:** upgrade or price target raise by top-tier firm (last 30 days)
- **Buyback:** share repurchase announcement or active program increase
- **Guidance raise:** positive full-year EPS or revenue revision
- **Sector tailwind:** rate cut beneficiary, capex cycle, policy support with near-term catalyst
- **Insider buying:** US Form 4 filings; HK director purchase disclosures

### Technical
- Price above SMA20, SMA50, and SMA200 (full bull stack confirmed)
- Breakout above 52-week high on volume > 1.5x 20-day average
- RSI in healthy range (50–65) with upward momentum
- MACD histogram expanding (acceleration — not decelerating)
- KDJ K crossed above D (short-term momentum confirmation)
- Key support holding on multiple tests — active demand zone confirmed

---

## Bear Driver Checklist

Near-term risks only. Materiality filter applies.

### Fundamental
- **Earnings miss:** EPS below consensus; or guidance cut
- **Revenue deceleration:** growth slowing or contracting vs prior quarter
- **Analyst downgrade:** downgrade or price target cut by top-tier firm (last 30 days)
- **Margin compression:** gross or operating margin deteriorating
- **Insider selling:** scale selling >$1M for US; material % of holdings for HK
- **Sector headwind:** rate sensitivity, regulatory action, demand slowdown with near-term impact
- **Dilution event:** secondary offering, convertible note, lock-up expiry approaching

### Technical
- Price below SMA200 — structural trend not recovered
- Death cross proximity: SMA50 approaching or recently crossed below SMA200
- RSI overbought (>70) or showing bearish divergence vs price
- MACD histogram decelerating sharply or near zero-cross
- KDJ K crossed below D (short-term caution)
- Low-volatility compression at structural resistance

---

## yfinance .info Field Reference (coding)

| Field | yfinance key | Notes |
|---|---|---|
| Market cap | `marketCap` | Native currency (USD or HKD) |
| Trailing PE | `trailingPE` | Often None for HK small-caps |
| Forward PE | `forwardPE` | Often None for HK stocks |
| EPS TTM | `trailingEps` | Native currency |
| PB ratio | `priceToBook` | Often None for HK stocks |
| Dividend yield | `dividendYield` | Decimal — multiply by 100 for % display |
| Beta | `beta` | vs benchmark index |
| Sector | `sector` | e.g. "Technology" |
| Industry | `industry` | e.g. "Consumer Electronics" |
| 52-week high | `fiftyTwoWeekHigh` | Native currency |
| 52-week low | `fiftyTwoWeekLow` | Native currency |
| Analyst mean target | `targetMeanPrice` | Often None for HK stocks |
| 20-day avg volume | `averageVolume` | In shares |

HK stock note: yfinance .info coverage is materially sparser for HKEX listings.
Expect more None values — trigger web fallback accordingly. Prices returned in HKD.

---

## Web Search Fallback Queries

Triggered when .info returns None. Cap total fallback searches at 3 per report.
Also always run the bottom two (ROE, earnings) regardless of None status.

| Trigger | Search query |
|---|---|
| `trailingPE` is None | `{TICKER} PE ratio trailing forward {year}` |
| `trailingEps` is None | `{TICKER} EPS earnings per share TTM {year}` |
| `priceToBook` is None | `{TICKER} price to book ratio {year}` |
| ROE — always run | `{TICKER} return on equity ROE {year}` |
| Earnings beat/miss — always run | `{TICKER} earnings beat miss consensus Q{N} {year}` |

Remaining None fields after cap → Data not available in report.

---

## Trusted News Sources

US equities: Reuters (reuters.com), Bloomberg (bloomberg.com), CNBC (cnbc.com), Barron's (barrons.com)
HK equities: SCMP (scmp.com), HKEX newsroom (hkexnews.hk), Reuters Asia

For HK stocks: check hkexnews.hk for regulatory filings and results announcements — these are primary sources.
"""

CRYPTO_MD = r"""# Crypto Reference — MATS v2

Analysis reference for crypto signal briefs.
Read before writing Section 2 drivers.

---

## Bull Driver Checklist

Near-term (48h) catalysts only. Apply materiality filter before selecting final 3.

### Fundamental
- **ETF inflows:** spot ETF net inflows sustained — institutional positioning confirmed
- **Institutional buying:** major purchase >$100M (BlackRock, Fidelity, MicroStrategy)
- **Regulatory clarity:** ETF approval, favorable legal ruling, framework progress with near-term impact
- **Short-squeeze setup:** elevated short interest + whale net longs building
- **On-chain accumulation:** sustained exchange outflows, whale wallet growth
- **Protocol event:** halving, major upgrade, or exploit patch with near-term supply or confidence impact
- **Sentiment recovery:** Fear & Greed recovering from oversold (<20) — contrarian signal

### Technical
- Price above SMA20 and SMA50 (near/medium-term bull stack)
- SMA200 reclaim in progress — structural recovery attempt
- RSI in healthy range (50–65) with upward momentum
- MACD histogram expanding (acceleration)
- KDJ K crossed above D (short-term confirmation)
- Key support holding on multiple intraday tests — active demand confirmed

---

## Bear Driver Checklist

Near-term risks only. Materiality filter applies.

### Fundamental
- **ETF outflows:** spot ETF net outflows — institutional distribution
- **Institutional selling:** major sell >$100M confirmed
- **Regulatory crackdown:** SEC/CFTC enforcement, China ban, MiCA restriction with near-term impact
- **Exchange event:** hack, insolvency, major delisting
- **On-chain deterioration:** exchange inflows rising, whale distribution confirmed
- **Token unlock:** large scheduled unlock creating near-term supply overhang
- **Overexcited sentiment:** Fear & Greed >80 — historically precedes mean reversion (Past performance is not indicative of future results.)

### Technical
- Price below SMA200 — structural ceiling unbroken
- MACD histogram decelerating sharply or near zero-cross (systematic sell trigger risk)
- KDJ K crossed below D (short-term caution)
- Low-volatility compression at resistance — directional break imminent, direction uncertain
- RSI overbought (>70) or bearish divergence vs price

---

## On-Chain Search Guidance

BTC: `Bitcoin exchange outflows inflows whale accumulation {date}` → CoinDesk, Glassnode, CryptoQuant
ETH: `Ethereum staking flows whale wallets {date}` → The Block, Glassnode
Others: `{ASSET} on-chain metrics whale activity {date}` → CoinDesk, Cointelegraph

---

## Trusted Sources

CoinDesk (coindesk.com), The Block (theblock.co), Cointelegraph (cointelegraph.com), Reuters, MarketWatch, CNBC
"""

DISCLAIMERS_MD = r"""# Disclaimers — MATS v2

Use the single line matching the asset class detected in Step 0.
Always placed as the final line of the report — no section header, no additional text.

---

## Crypto
⚠ Educational purposes only. Not investment advice. Crypto trading carries substantial risk of loss.

## Securities (US Equity / HK Equity)
⚠ Educational purposes only. Not investment advice. Securities trading carries substantial risk of loss.
"""

BTC_EXAMPLE = r"""# Example: Gold-Standard BTC Signal Brief

This is the reference output format. Every crypto report must match this structure, density, and tone.
Numbers are from the 2026-05-10 real run — do NOT reuse in live reports.

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
| Weekly trend | Bearish | Below weekly WMA50 and WMA200 |

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
"""

AAPL_EXAMPLE = r"""# Example: Gold-Standard AAPL Equity Signal Brief

This is the reference output format for US equity reports. Every equity report must match this structure,
density, and tone. Numbers are illustrative — do NOT reuse in live reports.
Run a fresh yfinance fetch for every live report.

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
- **SMA200 reclaimed:** First close above the 200-day moving average since February 2026. Historically, reclaims after extended consolidations precede multi-week trending moves. (Past performance is not indicative of future results.)
- **Analyst upgrade cycle:** Goldman Sachs raised price target to $250; Morgan Stanley reiterated Overweight with $245 target. Consensus upgrades increase index-fund rebalancing pressure to the upside.

**Bear**
- **EU regulatory drag:** Digital Markets Act compliance costs estimated at $1.2B annually — margin headwind not yet fully priced. New App Store fee restrictions effective Q3 2026.
- **China softness persists:** Greater China revenue -8% YoY for second consecutive quarter. No catalyst for reversal identified; local competition gaining share.
- **Valuation ceiling:** Forward PE 27.4x sits at the 85th percentile of AAPL's 5-year range. Multiple expansion limited at current rates; any earnings miss risks sharp de-rating.

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
"""


# ─────────────────────────────────────────────────────────────────────────────
# INSTALLER LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def get_args():
    parser = argparse.ArgumentParser(description="MATS Skill Installer v2")
    parser.add_argument("--update", action="store_true",
                        help="Overwrite existing installation")
    parser.add_argument("--verify", action="store_true",
                        help="Check installation without writing files")
    return parser.parse_args()


def verify_installation(skill_root):
    expected = [
        skill_root / "SKILL.md",
        skill_root / "references" / "equity.md",
        skill_root / "references" / "crypto.md",
        skill_root / "references" / "disclaimers.md",
        skill_root / "examples" / "btc_full_report.md",
        skill_root / "examples" / "aapl_report.md",
    ]
    all_ok = True
    for path in expected:
        if path.exists():
            print(f"  ✓  {path.relative_to(Path.home())}")
        else:
            print(f"  ✗  {path.relative_to(Path.home())} — MISSING")
            all_ok = False
    return all_ok


def install(args):
    skill_root = Path.home() / ".claude" / "skills" / "mats"
    workspace  = Path.home() / "claude-workspace" / "mats"

    print("MATS Skill Installer v2")
    print("=" * 40)

    # Pre-flight
    print("\nPre-flight checks:")
    check_python_version()
    check_claude_code()

    # Verify-only mode
    if args.verify:
        print("\nInstallation check:")
        ok = verify_installation(skill_root)
        print("\nDependency check:")
        deps_ok = verify_dependencies()
        status = "OK" if (ok and deps_ok) else "ISSUES FOUND"
        print(f"\nStatus: {status}")
        return

    # Check for existing installation
    if skill_root.exists() and not args.update:
        print(f"\nExisting installation found at {skill_root}")
        print("Run with --update to overwrite, or use --verify to check.")
        sys.exit(0)

    # Install dependencies
    print("\nDependencies:")
    install_dependencies()

    # Create directories
    print("\nCreating directories:")
    for path in [skill_root, skill_root / "references", skill_root / "examples"]:
        path.mkdir(parents=True, exist_ok=True)
        print(f"  {path.relative_to(Path.home())}")

    # Write files
    files = {
        skill_root / "SKILL.md":                          SKILL_MD,
        skill_root / "references" / "equity.md":          EQUITY_MD,
        skill_root / "references" / "crypto.md":          CRYPTO_MD,
        skill_root / "references" / "disclaimers.md":     DISCLAIMERS_MD,
        skill_root / "examples"   / "btc_full_report.md": BTC_EXAMPLE,
        skill_root / "examples"   / "aapl_report.md":     AAPL_EXAMPLE,
    }

    print("\nWriting skill files:")
    for path, content in files.items():
        path.write_text(content.strip() + "\n", encoding="utf-8")
        print(f"  ✓  {path.relative_to(Path.home())}")

    # Symlink
    print("\nWorkspace symlink:")
    workspace.parent.mkdir(parents=True, exist_ok=True)
    if workspace.exists() or workspace.is_symlink():
        workspace.unlink()
    workspace.symlink_to(skill_root)
    print(f"  ~/claude-workspace/mats → {skill_root}")

    # Final verification
    print("\nVerifying installation:")
    verify_installation(skill_root)

    print("\n" + "=" * 40)
    print("Installation complete.")
    print(f"\nRestart Claude Code, then test:")
    print("  /mats BTC        (crypto)")
    print("  /mats AAPL       (US equity)")
    print("  /mats 700        (HK equity — auto-pads to 0700.HK)")
    print("\nNote: /crypto command (Phase 1) remains untouched.")


if __name__ == "__main__":
    args = get_args()
    install(args)
