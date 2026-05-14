# Equity Reference — MATS v2

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

HK stock note: yfinance .info coverage is materially sparser for HKEX listings. Expect more None values — trigger web fallback accordingly. Prices returned in HKD.

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

---

## China A-Share (AkShare)

Data source: AkShare via East Money (东方财富).
Replaces yfinance for .SZ, .SS, .SH symbols and 6-digit numeric inputs starting with 0, 3, or 6.

### AkShare field reference

| Field | AkShare key (info_dict) |
|---|---|
| Market cap | 总市值 |
| Trailing PE | 市盈率TTM |
| Dynamic PE | 市盈率(动) |
| EPS TTM | 每股收益TTM |
| PB ratio | 市净率 |
| Dividend yield | 股息率TTM |
| Sector | 行业 |
| Beta | Beta |

### Web search fallback queries (China A-share)

| Field | Query |
|---|---|
| Analyst target | `{TICKER} 目标价 分析师 {year}` |
| Earnings beat/miss | `{TICKER} 业绩 超预期 不及预期 {quarter} {year}` |
| Insider activity | `{TICKER} 大股东 减持 增持 {year}` |
| ROE | `{TICKER} 净资产收益率 ROE {year}` |

### Trusted news sources (China A-share)

Sina Finance (finance.sina.com.cn)
East Money (eastmoney.com)
Caixin (caixin.com) — English available
Reuters China (reuters.com/world/china)
