# claude-mats

> **Structured trading signal briefs that tell you when NOT to trade — just as clearly as when to.**

A Claude Code skill for algo traders and systematic investors. One command generates a live, data-driven signal brief across crypto, US equities, and HK equities — with enforced symmetric bull/bear analysis, R/R calculated from real support/resistance levels, and a strict no-fabrication policy.

---

## Why MATS

Most AI trading tools are cheerleaders. MATS isn't.

| What most tools do | What MATS does |
|---|---|
| Bull-biased output | Enforced 3 bull + 3 bear drivers — symmetry is non-negotiable |
| Assumed or templated R/R | R/R calculated from live swing-detected S/R levels |
| Vague "looks bullish" calls | Explicit entry trigger, stop, target, risk%, grade (A/B/C) |
| Hallucinated or stale numbers | Every data point tied to a yfinance result or fetched URL |
| One asset class | Crypto + US equity + HK equity — auto-detected, one command |
| Always says enter | NEUTRAL bias output when there's no edge — monitor, don't enter |

---

## What It Does

Run `/mats [SYMBOL]` in Claude Code. It:

1. **Auto-detects** asset type — crypto, US equity, or HK equity
2. **Fetches live data** — 200-day daily OHLCV + 5-year weekly bars via yfinance
3. **Computes indicators** — RSI(14), MACD(12,26,9), KDJ(9,3,3), SMA20/50/200, weekly WMA50/WMA200
4. **Detects S/R zones** — swing high/low clustering on 200-day window, scored by touches + recency
5. **Calculates R/R** — from actual computed levels, not assumptions; assigns grade A/B/C
6. **Runs targeted web searches** — 4–6 searches for news, sentiment, and fundamentals
7. **Outputs a signal brief** — scannable 5-line header, indicator snapshot, symmetric 3+3 drivers, merged trade setup table with invalidation conditions

---

## Output Format

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

Followed by:
- **Market Snapshot** — 6-row indicator table + fundamentals block (equity) + trend state + sentiment
- **Key Drivers** — 3 bull + 3 bear, near-term only, no padding, no structural macro filler
- **Levels & Setup** — S1/S2/R1/R2 zones + merged trade setup table (trigger, entry, stop, risk%, T1, R/R, T2, R/R) + invalidation conditions

See [`skill/examples/`](skill/examples/) for full worked examples (BTC + AAPL).

---

## Requirements

- Python 3.8+
- Claude Code — [install here](https://claude.ai/code)
- Dependencies (auto-installed): `yfinance`, `pandas-ta`, `pandas`, `akshare`

---

## Installation

```bash
# 1. Clone the repo
git clone https://github.com/WiseManAlgo/claude-mats.git
cd claude-mats

# 2. Run the installer
python3 install_mats_skill.py
```

Restart Claude Code after installation.

### Installer options

```bash
python3 install_mats_skill.py            # fresh install
python3 install_mats_skill.py --update   # overwrite existing installation
python3 install_mats_skill.py --verify   # check installation + dependencies
```

---

## Usage

```
/mats BTC          # Bitcoin
/mats ETH          # Ethereum
/mats PEPE         # any crypto resolvable via yfinance
/mats AAPL         # US equity
/mats NVDA         # US equity
/mats 700          # HK equity — auto-pads to 0700.HK (Tencent)
/mats 9988         # HK equity (Alibaba HK)
/mats 300782       # China A-share (Maxscend Microelectronics, ChiNext)
/mats 600519       # China A-share (Kweichow Moutai, SSE)
/mats 000001       # China A-share (Ping An Bank, SZSE)
```

Natural language also works:

```
Analyze TSLA for the next couple of days
Give me a signal on ETH
Run a report on 700
```

---

## Asset Coverage

| Asset class | Example inputs | Data source | Currency |
|---|---|---|---|
| Crypto | `BTC`, `ETH`, `SOL`, `PEPE` | yfinance (`{SYMBOL}-USD`) | USD |
| US equity | `AAPL`, `NVDA`, `TSLA` | yfinance (direct ticker) | USD |
| HK equity | `700`, `0700`, `9988` | yfinance (`{SYMBOL}.HK`) | HKD |
| China A-share | `300782`, `600519`, `000001` | AkShare (East Money) | CNY ¥ |

---

## What Makes This Different

### Enforced symmetry — no cheerleading
The Symmetry Guard is non-negotiable. If the bear case has only 1 material point, that imbalance is stated explicitly. The weaker side is never padded. The stronger side is never suppressed. NEUTRAL bias is a valid and frequent output.

### R/R from real levels — not assumed
Support and resistance zones are detected algorithmically from 200 days of swing highs and lows, clustered within ±0.5%, scored by touches and recency. R/R is calculated from those actual numbers using the formula `(Target − Entry) ÷ (Entry − Stop)`. Grade A/B/C follows from the result. Nothing is assumed or templated.

### KDJ(9,3,3) — hand-implemented
KDJ is widely used in Asian markets and crypto but absent from pandas-ta and TA-Lib (which only implements the Western Stochastic variant). MATS implements it from scratch: `K = EWM(RSV, com=2)`, `D = EWM(K, com=2)`, `J = 3K − 2D`.

### Zero fabrication policy
Every numerical data point in the output is tied to a yfinance result or a specific fetched URL. Missing data is stated as `Data not available` — never inferred, never guessed. The anti-fabrication guardrail is enforced in the pre-output checklist on every run.

### HK equity — rare in the Claude ecosystem
Most Claude Code trading skills cover US equities or crypto only. MATS handles HKEX listings natively, including automatic ticker normalization (`700` → `0700.HK`) and HKD currency handling throughout the report.

---

## Key Design Decisions

**Data stack:** yfinance + AkShare + pandas-ta + hand-coded KDJ — free, public, no auth required. AkShare (East Money / 东方财富) provides China A-share OHLCV and fundamentals; yfinance covers all other asset classes.

**Weekly trend:** WMA50 + WMA200 on a 5-year weekly fetch. Guard for assets with fewer than 100 weekly bars.

**Asset detection:** Try-and-verify via yfinance — no static symbol list. Any crypto resolvable as `{SYMBOL}-USD` is supported, including newer tokens not in any hardcoded list.

**Volume trigger:** Dynamic `1.5× 20-day average volume` for equities — not hardcoded.

**Sentiment rubric:** Weighted scoring (recency × polarity × high-impact multiplier). Separate high-impact and speculative item definitions for crypto vs equity.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| RSI/MACD variance ±5–15pt | Due to smoothing differences vs other platforms. Directional signals reliable; documented in every report footnote |
| yfinance data quality | Occasional bad OHLCV points. Sanity check recommended: reject if daily range > 20% |
| HK fundamentals sparse | yfinance .info coverage weaker for HKEX. Web fallback runs automatically |
| China A-share via AkShare | Data sourced from East Money (东方财富). Analyst target unavailable from AkShare — web fallback always runs |
| Daily candles only | Intraday timeframes out of scope — use TradingView |
| No live on-chain metrics | Sourced from news commentary only |

---

## Roadmap

**v2 — Agent adapters**
- OpenAI Codex adapter
- LangChain adapter
- Core skill logic is agent-agnostic — only the Claude Code wrapper is platform-specific

**v2 — Asset expansion**
- Forex: `/mats EURUSD` via yfinance `=X` suffix
- Commodities: `/mats GC=F` via yfinance futures suffix

**v2 — Features**
- `--lite` flag: header + levels only, no news searches
- Multi-source data validation (Binance → CoinGecko fallback for crypto)
- Wilder's smoothing option for RSI/MACD to reduce platform variance

---

## Disclaimer

**This skill is for educational and research purposes only. It does not constitute financial advice, investment advice, or any form of professional recommendation. Trading crypto, equities, and other financial assets involves substantial risk of loss. Never make investment decisions based solely on these outputs. The authors accept no liability for financial losses arising from use of this skill.**

---

## License

MIT — see [LICENSE](LICENSE)
