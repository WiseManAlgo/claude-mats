# MATS Engine Architecture (v0.1 — design doc, no code yet)

Status: **approved for Phase 1 build** (2026-07-23, three evidence-dialogue-loop review rounds: architecture concept → this file's first draft → this file's revision after 4 gaps were found and fixed). This file is the single source of truth for "what lives where" — do not rely on memory of this discussion; read this file fresh each time the engine's shape is in question. Update it whenever a file is added, a mechanism is promoted/demoted, or a backtest result lands.

## Why this exists

Three documented incidents (signal.alarm false-negative on Futu connectivity, `adjust_bias()` misapplied MU vs AMD from memory, Step 3a TV MCP call skipped without attempt) share one root cause: deterministic, one-right-answer logic was being re-derived from 1400+ lines of prose by an LLM each run, instead of executed by a fixed program. The fix is to move what can be moved into real, versioned code — but NOT all at once (see Phase boundary below), and NOT including logic this skill itself has flagged as unvalidated (n=1/n=2 cases) — hard-coding a guess just makes it a confident, repeatable guess.

**Execution reliability ≠ rule correctness.** Turning a rule into code fixes *whether it runs the same way every time*. It does nothing for *whether the rule is right*. Keep these two axes separate throughout this doc.

## Layer split — what can and cannot leave the AI/agent layer

| Data / logic | Automatable (pure script, no AI) | Why |
|---|---|---|
| yfinance / AkShare OHLCV, fundamentals | ✅ Yes | Plain HTTP/library calls |
| Futu OpenD (connectivity, capital flow, options wall) | ✅ Yes | Plain socket API via `futu` package |
| Indicators computed from OHLC (KDJ, BOLL, ATR, EMA, RSI2, regime ADX/ER/CHOP) | ✅ Yes | Pure `pandas_ta`/numpy math |
| S/R levels, Row 0/1/2/3 engine, R/R + gates, bias adjustment | ✅ Yes | Pure math/logic given the OHLC data above |
| **TradingView MCP** (`combined_analysis` for TV's own RSI/MACD/SMA, `financial_news`) | ❌ No | MCP tool — only callable from the agent/chat layer, not from a standalone `.py` process |
| **WebSearch** (news fallback when TV MCP returns <3 articles) | ❌ No | Same reason — agent-layer tool only |
| Driver selection, sentiment scoring judgment, report prose, 白話版 wording | ❌ No, by design | Genuinely needs judgment, not a computation |

**Consequence:** the engine cannot be "one script that does everything in Step 0–4c." It computes everything that doesn't need TV MCP/WebSearch, and leaves clearly-labeled null fields for the two AI-layer-only data points (TV's RSI/MACD/SMA, news). The AI's job for those fields is copy-paste into the JSON, not computation — this must be enforced as a literal transcription step, not a "fill in what you think is right" step.

**Transcription-loophole mitigation (flagged 2026-07-23 as a named-but-unsolved risk — this closes it, not just names it again):** naming the risk in prose does not stop it — Step 8.5's own "Honest limitations" section already admits this same gap exists for its Verification Cell and was never fixed there either. Concrete mechanism instead of a promise:
- When the AI calls `combined_analysis` (TV MCP), the **raw tool-call JSON response stays visible in the transcript** — it already does, this is just never being used as a check.
- Before writing the report, run one string-match check: the RSI/MACD-histogram/SMA20/50/200 values that end up in the report's indicator table must appear verbatim (same rounding) in that raw MCP response. This is mechanical enough to do as a literal `grep`/substring check against the tool output already in context — no new tool needed, just a discipline of actually doing the check instead of trusting memory of what the MCP call returned.
- If a value in the report does NOT match the raw MCP response, that is not a rounding nuance to wave through — it means the AI substituted a self-computed or misremembered number for the source-of-truth tool output, and the report must be corrected before it goes out.
- This is a real fix, not a full solve: it still depends on the AI actually performing the check rather than skipping it (the exact "did they even attempt it" failure from the Step 3a incident). Flagging that residual honestly rather than claiming this closes the loop completely.

**Known field trap in TV MCP's `combined_analysis`, confirmed 2026-07-23 (NVDA + LITE, caught because the user checked the live TradingView site and the number didn't match):** the tool's `price_data.change_percent` field is NOT day-over-day change — it is `(close − today's open) / today's open × 100`. Verified exactly on both tickers: NVDA reported 3.039, and `(212.06 − 205.805) / 205.805 × 100 = 3.039` to 3 decimals; LITE reported 2.404, matching `(829.70 − 810.22) / 810.22 × 100 = 2.404` identically. The standard day-over-day change (what TradingView's own website displays, and what `engine/indicators.py`'s `pct_chg` computes from yfinance's prev close) was 2.301% for NVDA and −0.938% for LITE — both meaningfully different from the MCP field, in LITE's case even flipping sign. **Do not read `change_percent` from this tool as "24H change" — it isn't.** For the report's 24H%/PRICE header line, always use `engine/indicators.py`'s `pct_chg` (prev-close basis), never the MCP field of the same apparent meaning. First reaction to this discrepancy (see conversation) was to wave it off as "two data sources define 24H% differently, both valid" — that was wrong, not investigated, and got corrected only because the user pushed back with an independent check. Lesson restated for this specific case: a plausible-sounding explanation for a numeric mismatch is not a substitute for tracing the actual arithmetic.

## Phase boundary (Plan B — build order)

Not everything gets hardened into a script at once. Priority is **documented incident first, unvalidated logic last**:

**Phase 1 — BUILT AND SMOKE-TESTED 2026-07-23 (all six files exist in `engine/`, each run against live LITE data and cross-checked against this week's manual LITE report numbers):**
1. `futu_check.py` — OpenD connectivity (`get_global_state()`, bare call, no signal/alarm wrapper — see incident 2026-07-23), capital flow fetch, options wall attempt + quota-failure detection. **Extra fix found during build, not in the original design:** the `futu` SDK's own logger writes INFO-level connection noise straight to `sys.stdout` (not stderr — confirmed via source read of `ft_logger.py`), which would have silently broken JSON parsing for every caller. Silenced via the official `SysConfig.enable_console_log(False)` switch, called once at import time. Verified: output now parses cleanly with `json.load`.
2. `bias_engine.py` — `adjust_bias()` ported verbatim from SKILL.md Step 1.5. Tested against both the NEUTRAL/Risk-On/Bearish case (this week's actual LITE result, no change) and the LONG/Risk-Off/Bearish case (the original MU incident scenario) — both match.
3. `rr_gate.py` — R/R arithmetic + three family gates + entry-distance invariant. Tested against SKILL.md's own worked example (257/252/277 → 4.00 ✓) and this week's actual Row 1 LITE case (785.77/750.00/843.00 → 1.60, NO TRADE ✓).
4. `regime_vote.py` — ADX/ER/CHOP three-vote majority. ADX and CHOP matched manual calculation exactly on re-test; ER/verdict showed expected small drift because the market was still live-trading between the manual calc and this run — not a bug, a live-price artifact.
5. `indicators.py` — KDJ/BOLL/ATR/EMA/RSI2/SMA5/20/50/200. Cross-checked against this week's manual LITE numbers, matched within live-price drift tolerance.
6. `market_context.py` — SPX/HSI/CSI300 + sector ETF Risk-On/Off + Bullish/Bearish classification. Matched this week's manual LITE market-context call (sector Bearish despite 3-day uptrend, because price sits just under sector SMA20 — same edge case flagged manually, now reproduced by the script).

**Post-build hardening (2026-07-23, evidence-dialogue-loop review of the six scripts found 5 real gaps — fixed, not just noted):**
1. `rr_gate.py`'s `check_entry_distance_invariant()` existed since first build but the CLI never actually called it — "tested" claims for this file were 2/3 true, not 3/3. Fixed: CLI reworked into `rr rr ENTRY STOP TARGET FAMILY` / `rr_gate.py invariant ENTRY CURRENT_PRICE ATR14 STATUS` subcommands; all three invariant paths (TRIGGERED-within-limit, TRIGGERED-over-limit, PENDING-exempt) now individually run and verified.
2. `bias_engine.py`'s docstring claimed it "also includes the market_context fetch" — false, always was; the file only ever took three strings as input. Docstring corrected to state plainly it's a pure function and the caller must supply broad/sector from `market_context.py` separately.
3. `futu_check.py`'s options-wall SUCCESS path (real OI data returned, not the quota-failure path) has never been tested — this account's 0 options quota (see the confirmed-via-official-docs note above) makes that path untestable here. **Disclosed as an open gap, not silently ignored** — if this account's options permission ever gets granted, the success path must be smoke-tested before being trusted.
4. All prior "verification" was manual eyeballing of live-price-dependent output against numbers recalled mid-conversation — reproducible in spirit only, not bit-exact, and evaporates once the session ends. Fixed: `backtest/fixtures_LITE_2026-07-17.json` freezes real output from `indicators.py` + `regime_vote.py` against LITE's fully-closed 2026-07-17 session (immutable historical data), plus deterministic cases for `bias_engine.py` and `rr_gate.py` (no live-data dependency, so no freezing needed — always reproducible). `backtest/test_engine_fixtures.py` is a real, re-runnable regression test — not a request to remember to re-check by hand. **Run: `python3 references/backtest/test_engine_fixtures.py` → `ALL PASS`, `grep -c "^PASS:"` → `60`.**
5. `market_context.py` still has NO fixture (SPX/sector-ETF trend depends on "today," no frozen historical version built yet) — same for `futu_check.py`'s connectivity/capital-flow paths (depend on the live OpenD process being up). Both remain manually-verified-this-session only; flagged here rather than left implicit.

**Round-2 correction (2026-07-23, same-day second evidence-dialogue-loop pass — caught in the FIRST completion report, not by the user re-checking independently):** the initial report of item 4 above claimed "46/46 checks" — that number was never actually counted, just written from impression. The real count, obtained via `grep -c "^PASS:"`, is **60**. Also fixed in the same pass: `check()`'s tolerance was 0.05 (loose enough to silently pass a real 2nd-decimal regression on data that should reproduce bit-exact) — tightened to 0.005; and `isinstance(expected, float) or isinstance(expected, int)` accidentally routed booleans through the numeric-tolerance branch (Python's `bool` subclasses `int`) instead of exact equality — reordered to check `bool` first. Both the miscount and the tolerance/isinstance fixes were verified by actually running commands and pasting real output, not re-asserted from memory — including a deliberate-injection test (forced `atr14` to a wrong value, confirmed the tightened test catches it, then restored and confirmed `ALL PASS` returns). This correction is itself evidence for why `ENGINE_ARCHITECTURE.md`'s Phase 1/Phase 2 split and fixture requirement exist: even a "just report a test count" step produced a wrong, confident-sounding number on the first pass.

**Assembly — BUILT 2026-07-23, only after the round-2 fixes above were independently re-verified from scratch in the same session (fresh `grep`/exit-code checks, not re-trusting the prior report), per explicit user go-ahead.** `engine/run_report.py` wires `indicators.py` + `regime_vote.py` + `market_context.py` + `bias_engine.py` + `futu_check.py` into one JSON call:
```
python3 run_report.py TICKER ASSET_TYPE [--sector SECTOR] [--initial-bias LONG|NEUTRAL|SHORT] [--futu-code US.XXX]
```
Tested end-to-end against LITE (both with and without `--initial-bias`, to confirm the "AI hasn't decided yet" fallback path) and against a crypto ticker (to confirm the Futu-skip path) — both produced clean, `json.load`-parseable output. What it deliberately does NOT do, restated so it's never mistaken for an oversight: does not call TradingView MCP or WebSearch (agent-layer only, left null with a note); does not decide `initial_bias` on its own (judgment, not computation — caller supplies it once drivers are read, or the bias section stays null with `final_bias: null`); does not compute Phase 2 (S/R, Row 0/1/2/3) — that stays AI-executed + Verification Cell exactly as scoped above.

**Phase 2 (stays AI-executed + Verification Cell for now — provisional, n=1/n=2 validated, NOT hardened until backtested):**
- S/R Breach Filter, Polarity Flip (4.2), Unified Candidate Pool + Confluence Merge (4.3/4.4) — all self-flagged in SKILL.md as validated against exactly one case (DOCN)
- Mean-Reversion R/R gate threshold (0.5) — calibrated on n=2 (XLU)
- Row 0/1/2 entry-anchor logic (EMA10/21, pivot lookback) — literature-standard but never backtested against this skill's own historical report set

Promotion from Phase 2 → Phase 1 happens only after a mechanism passes its own backtest (see below) — not on a calendar, not on "it's been a while."

## File layout (target — created incrementally, Phase 1 first)

```
mats/
  references/
    ENGINE_ARCHITECTURE.md      <- this file
    engine/
      futu_check.py             <- Phase 1
      bias_engine.py             <- Phase 1
      rr_gate.py                  <- Phase 1
      regime_vote.py              <- Phase 1
      sr_levels.py                <- Phase 2 (stays prose-executed until backtested)
      row_engine.py                <- Phase 2 (stays prose-executed until backtested)
      indicators.py                <- Phase 1 (KDJ/BOLL/ATR/EMA — pure math; user-approved 2026-07-23 after being flagged as an undiscussed scope add in the prior review round)
      market_context.py            <- Phase 1 (SPX/HSI/CSI300 + sector ETF fetch + trend classification; same 2026-07-23 approval)
    backtest/
      BACKTEST_LOG.md              <- status table, see below
      dataset.json                  <- fixed historical ticker/date list (see below) — plain data file, not .py, so the frozen list can't accidentally get logic mixed into it
      sample_dataset.py              <- the sampling script that GENERATES dataset.json once; not re-run after freeze without an explicit new dataset version
      run_backtest.py                <- harness, one mechanism at a time
```

Each Phase 1 script: plain function(s), no classes needed, pure stdlib + yfinance/pandas_ta/futu. Input = ticker + already-fetched OHLC DataFrame (so scripts compose — `indicators.py` output feeds `sr_levels.py` input, etc., even though sr_levels.py itself stays prose-executed in Phase 1). Output = plain dict/JSON, printed to stdout so the calling agent can read it directly from Bash tool output — no file I/O required for a single report run.

## Backtest process (answers "how and when do we keep validating Phase 2 items")

**Correction to the old SKILL.md framing:** "review at ~100-report checkpoint" is NOT a backtest — it's waiting for organic accumulation of whatever tickers happen to get analyzed, with no control over sample composition. A real backtest can run **today**, against historical data, on a **fixed, designed** dataset — it does not need to wait for future `/mats` usage at all. This doc replaces that framing.

- **Trigger:** user-initiated only (e.g. `/mats backtest <mechanism_name>`). Never automatic, never on a schedule the AI decides.
- **Dataset construction (fixes the "who picks the 50 tickers" gap flagged 2026-07-23):** stratified, not ad hoc, so no mechanism's backtest is silently favored by a skewed sample —
  - Stratify by two axes: **sector** (use the 12 sector buckets already defined in SKILL.md Step 1.5's ETF mapping table — Technology, Semiconductors, Communication Services, Consumer Discretionary/Staples, Healthcare, Financials, Energy, Industrials, Materials, Real Estate, Utilities, plus one crypto bucket) × **volatility tier** (low/med/high, split by trailing-90-day ATR14-as-%-of-price into terciles across a broad universe, e.g. S&P 500 + top-50 crypto by market cap).
  - Target ~3-4 tickers per (sector × vol-tier) cell — gives the ~50-ticker total while guaranteeing no single profile dominates.
  - Date ranges: for each selected ticker, pick 2 non-overlapping 200-day windows from different calendar years (avoids the whole dataset being one shared market regime, e.g. all-2026-AI-rally).
  - `sample_dataset.py` implements this selection mechanically (deterministic given a random seed, so it's reproducible) and writes the result to `dataset.json`. Once written, **`dataset.json` is frozen** — re-running the sampler to get a "better" sample after seeing backtest results defeats the point and must not happen without an explicit new dataset version number.
- **Method (per mechanism, defined at backtest time, not generically):** compare the mechanism's output against a naive baseline (e.g. Polarity Flip vs. structural-swing-points-only) on the same dataset, and score which one's implied levels were actually respected by subsequent price action (e.g. S1 held as support within the next 3-5 sessions).
- **Pass/fail threshold:** set by the user at the time each mechanism's backtest is designed — not a fixed number in this doc, since what counts as "good enough" depends on the mechanism and its role in the report.
- **Result recording:** `backtest/BACKTEST_LOG.md` — one row per mechanism: `status (provisional / backtested-passed / backtested-failed) | n | date tested | dataset version | notes`. This is the only place backtest status lives — not memory, not this doc's prose (this doc describes the *process*, BACKTEST_LOG records *results*).
- **After backtested-failed:** the mechanism does not just sit labeled "failed" — it triggers one of two required next actions, decided by the user when the result lands: (a) revise the mechanism's logic and re-backtest against the SAME frozen dataset (never a fresh sample chosen after seeing the failure), or (b) retire the mechanism from the skill entirely. "Failed, no action" is not a valid end state for an entry in this log.

## Demotion path (Phase 1 → Phase 2, the missing half of the promotion rule)

Promotion (Phase 2 → 1) requires passing a backtest. Demotion is asymmetric and faster to trigger, because a Phase 1 script carries more trust than Phase 2 prose — a bug there is more dangerous, not less:
- **Trigger:** any live report where a Phase 1 script's output is found wrong (by the user, by a Verification Cell-style spot check, or by the script erroring/hanging in a way this doc's incident history already shows can happen — e.g. the `signal.alarm` case).
- **Immediate action:** the affected script is marked `SUSPENDED` in this file's Phase 1 list (not silently left in place) and the skill falls back to the AI-executed + Verification Cell path for that one mechanism until the script is fixed — the report must not simply keep using a known-bad script because "it's already in Phase 1."
- **Re-entry to Phase 1:** requires the fix PLUS a re-run of whatever test caught the bug (at minimum, re-check against the specific case that exposed it) — not just "looks fixed now."
- This path is asymmetric by design: getting promoted to Phase 1 requires a full backtest; getting suspended out of it requires only one demonstrated failure. That asymmetry is intentional — trust should be hard to earn and easy to lose here.

## What this doc is NOT

- Not a promise that Phase 1 scripts are bug-free once written — they still need to be tested against the LITE reports already produced this week (numbers must match) before being trusted in a live report.
- Not a memory-system entry — this file lives in the skill directory precisely so it is read fresh from disk each time, never recalled from the auto-memory system (architecture/file-structure facts are explicitly excluded from that system for exactly this staleness reason).
