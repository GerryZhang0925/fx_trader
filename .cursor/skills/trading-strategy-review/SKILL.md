---
name: trading-strategy-review
description: Review trading strategies and backtests for the failure modes that blow up live — look-ahead bias, overfitting, survivorship bias, unrealistic fills, and risk-of-ruin. Grounded in backtest-overfitting research (PBO, Deflated Sharpe). Outputs severity-rated findings with fixes. Use to vet a strategy, audit a backtest, or pre-deployment risk-check.
version: 1.0.0
---

# Trading Strategy & Backtest Review

A methodology for reviewing a trading strategy, a backtest, or strategy code (Python,
Pine, or any language) for the failure modes that make a backtest look great in a chart
and lose money in production. The output is a **severity-rated findings report** with a
concrete fix for each problem.

This skill is grounded in the established backtest-overfitting literature, primarily the
work of **David H. Bailey and Marcos López de Prado** — *"The Probability of Backtest
Overfitting"* (PBO), *"The Deflated Sharpe Ratio"*, *"Pseudo-Mathematics and Financial
Charlatanism"*, and *"The Seven Sins of Quantitative Investing."* The central insight of
that literature: if you try enough strategy configurations, **a spectacular in-sample
backtest is the expected outcome even when the strategy has zero real edge.** Most of the
checklist below exists to detect exactly that.

> **Not financial advice.** This skill performs an *educational, methodological review of
> a strategy or backtest*. It is not investment advice, not a recommendation to trade, and
> not a guarantee of any outcome. Past backtest performance — even after every fix here —
> does **not** guarantee live results. The user is solely responsible for their own
> trading and risk decisions.

---

## When to Activate

Activate this skill when the user:

- Shares a trading strategy idea, ruleset, or signal and asks whether it is sound.
- Shares **backtest code** (Python/pandas/`backtrader`/`vectorbt`/`zipline`, Pine Script,
  or any language) and asks for a review.
- Shares **backtest results** — an equity curve, a metrics table (Sharpe, CAGR, max
  drawdown, win rate), or a screenshot from TradingView / a backtesting platform.
- Asks for a "pre-deployment check," "is this overfit?", "why might this fail live?", or a
  risk review before putting real capital behind a strategy.

If the user only shares *results* with no code, you can still run Steps 1, 2, 4 and 5 and
the metrics sanity check; flag that code-level confirmation is needed for several findings.

---

## Step 1: Scope & Context

Before reviewing, establish context. Ask for anything missing — these answers change the
severity of nearly every finding. If the user cannot answer, note the gap as an `Info`
finding and assume the worst reasonable case.

| Question | Why it matters |
|---|---|
| **Asset class & instrument** (equities, futures, FX, crypto, options) | Drives cost model, liquidity, borrow/funding, session boundaries. |
| **Timeframe / bar size** (tick, 1m, 1h, daily) | Sets the realistic Sharpe ceiling and how dangerous look-ahead is. |
| **Backtest window & in-sample period** | Short windows + one regime = fragile. |
| **Number of parameters** in the strategy | More knobs → more overfitting capacity. |
| **Number of strategies / configs tried** (the "trials") | The single biggest driver of false discovery; needed for Deflated Sharpe / PBO. |
| **Out-of-sample / walk-forward done?** | If everything is in-sample, results are unverified. |
| **Live or paper track record?** | Live > paper > backtest in evidentiary weight. |
| **Capital, position size, leverage** | Determines risk-of-ruin and market-impact realism. |
| **Costs modeled?** (commission, slippage, spread, borrow, funding) | Frictionless backtests are the most common silent killer. |

---

## Step 2: Severity Model

Rate every finding with this scale. The driving question is always: *"Does this change the
decision to trade, or just the precision of the estimate?"*

| Severity | Definition | Examples |
|---|---|---|
| **Critical** | Invalidates the results entirely, or exposes the account to ruin. The backtest cannot be trusted and/or the strategy can blow up. | Look-ahead bias in the signal; zero transaction costs on a high-turnover strategy; no risk limit / unbounded position sizing; survivorship-biased universe; results are 100% in-sample with hundreds of trials. |
| **High** | Materially inflates performance or materially understates risk; likely flips the strategy from "edge" to "no edge" once corrected. | Optimistic fills (mid/close, no slippage); over-parameterization without OOS; ignoring borrow/funding; regime dependence on a single bull market. |
| **Medium** | Biases results in a meaningful but recoverable way; needs correction before sizing real money. | Curve-fit stop/target levels; survivorship in a secondary filter; small trade count weakening significance; timezone/session edge cases. |
| **Low** | Minor realism or robustness gap; unlikely to flip the conclusion but should be fixed. | Rounding/contract-size handling; minor parameter sensitivity; cost estimate slightly optimistic. |
| **Info** | Context, missing information, or good practice to confirm — not a defect per se. | "Number of trials not disclosed"; "confirm data is point-in-time"; "consider regime-tagging the equity curve." |

A single **Critical** finding means *do not deploy* until fixed, regardless of how good the
metrics look.

---

## Step 3: Failure-Mode Checklist

Walk every item. For each, you have: **what it is → how to detect it → why it inflates
performance → the fix.** Cover at minimum the 16 modes below.

### 3.1 Look-ahead bias *(usually Critical)*
- **What:** The strategy uses information at bar *t* that was not actually available until
  *t+1* or later — future prices, end-of-bar values used intrabar, same-bar close used to
  decide a same-bar entry, full-series statistics (mean, z-score, scaler) computed over
  data that includes the future.
- **Detect:** Signals that index the future (`close[t+1]`, `df['close'].shift(-1)`,
  `.shift(-n)` feeding a feature); indicators computed on the *entire* series then used at
  earlier bars; `fillna(method='bfill')`; a `StandardScaler`/`MinMaxScaler` fit on the
  whole dataset before the train/test split; using a bar's high/low to decide entries that
  also assume the favorable extreme was filled; resampling that leaks the closing bar.
- **Why it inflates:** Trading with tomorrow's information is the most powerful "edge" there
  is — and it is entirely fake. It typically produces unrealistically smooth equity curves
  and Sharpe ratios that are physically impossible.
- **Fix:** Use **point-in-time data** and a **frozen, as-of view** of every input. Lag all
  signals by one bar relative to execution. Fit any normalizer/scaler **inside** the
  walk-forward fold on training data only. Decide on bar *t*'s **closed** values, execute at
  bar *t+1*'s open (or next available price).

  ```python
  # BAD — decides and fills on the same bar's close (look-ahead)
  signal = (df['close'] > df['sma']).astype(int)
  df['ret'] = signal * df['close'].pct_change()      # uses same-bar close

  # GOOD — decide on closed bar t, execute next bar
  signal = (df['close'] > df['sma']).astype(int)
  df['position'] = signal.shift(1)                    # act on prior bar's signal
  df['ret'] = df['position'] * df['close'].pct_change()
  ```

### 3.2 Survivorship bias *(High–Critical)*
- **What:** The universe only contains instruments that survived to today — delisted,
  bankrupt, merged, or relegated names are missing.
- **Detect:** Universe pulled from a *current* index membership / current ticker list;
  equities backtest with no delisting returns; crypto backtest excluding dead coins; using
  "today's S&P 500" over a 20-year history.
- **Why it inflates:** You systematically exclude the losers. Buy-and-hold and especially
  mean-reversion strategies look far better than reality because the names that went to zero
  were never in the test.
- **Fix:** Use a **point-in-time, survivorship-free universe** with historical constituents
  and delisting/bankruptcy returns. Reconstruct index membership as of each date.

### 3.3 Data-snooping / overfitting (too many params, in-sample tuning) *(Critical)*
- **What:** Parameters were chosen by maximizing performance on the same data used to report
  it; or the strategy has so many free parameters it can fit noise.
- **Detect:** Grid/optimizer over many parameters reporting only the *best* result; no
  held-out data; parameter count high relative to trade count; "we tried a few and kept the
  best."
- **Why it inflates:** With enough knobs and enough trials, you can fit historical noise
  perfectly. Per Bailey–López de Prado, the **expected maximum** in-sample Sharpe across N
  independent trials grows roughly like √(2·ln N) even when true Sharpe is zero — so a great
  backtest is the *default* outcome of a search, not evidence of edge.
- **Fix:** **Out-of-sample holdout + walk-forward** analysis. Minimize parameters
  (parsimony). Report the **Deflated Sharpe Ratio** and **PBO** (below). Pre-register the
  rule before testing where possible.

### 3.4 Multiple testing / p-hacking *(Critical)*
- **What:** Many configurations, indicators, or universes were tried; only the winner is
  reported. The reported Sharpe is a **maximum over trials**, not a single draw.
- **Detect:** "Selected the best of K"; many indicators/lookbacks scanned; the count of
  trials is undisclosed or large.
- **Why it inflates:** The more you try, the higher the best in-sample result purely by
  chance. A nominal Sharpe of 2.0 over 1,000 trials may be statistically indistinguishable
  from luck.
- **Fix:** **Deflated Sharpe Ratio (DSR)** — adjust the observed Sharpe for the number of
  trials, the variance of trial Sharpes, and the non-normality (skew/kurtosis) of returns;
  DSR is the probability the true Sharpe > 0 after that haircut. **Probability of Backtest
  Overfitting (PBO)** via Combinatorially Symmetric Cross-Validation (CSCV): the fraction of
  splits where the in-sample-best config underperforms the median out-of-sample. **PBO > 0.5
  means the selection process is overfit.** Always report **how many trials** were run.

### 3.5 Unrealistic fills *(High–Critical)*
- **What:** Orders assumed to fill at prices you could not actually get — mid, close,
  best-case high/low of the bar, or instantly with no queue.
- **Detect:** Backtest fills at the signal bar's `close`; limit orders assumed filled
  whenever price merely *touched* the level; market-on-open with no gap handling; no spread.
- **Why it inflates:** Best-case fills quietly add returns every single trade; the effect is
  largest for high-frequency / high-turnover strategies.
- **Fix:** Model the **bid/ask spread**; fill market orders at the **next bar's open** (or
  worse); for limit orders, require the price to **trade through** the level, not just touch
  it, and account for queue position. Add conservative slippage (below).

### 3.6 Slippage & commission omitted/under-modeled *(High–Critical)*
- **What:** No (or token) per-trade costs.
- **Detect:** Cost = 0; commission set but slippage = 0; costs not scaled by turnover.
- **Why it inflates:** A strategy with a 5 bps gross edge and 200% monthly turnover is
  *guaranteed* to lose after realistic costs, yet looks profitable frictionless.
- **Fix:** Apply realistic **commission + spread + slippage** per fill, scaled by turnover.
  A useful sanity check: compute the **break-even cost** (the per-trade cost at which the
  strategy's edge disappears) and ask whether real-world costs exceed it.

  ```python
  COST_BPS = 5  # round-trip commission + half-spread + slippage, in basis points
  df['turnover'] = df['position'].diff().abs()
  df['net_ret'] = df['gross_ret'] - df['turnover'] * (COST_BPS / 1e4)
  ```

### 3.7 Market impact & liquidity ignored *(High)*
- **What:** Assumes you can trade any size at the quoted price with no impact.
- **Detect:** Position sizes large vs. average daily volume (ADV); thin instruments; no cap
  on participation rate.
- **Why it inflates:** Real orders move the price against you; the backtest captures alpha
  that evaporates at size.
- **Fix:** Cap order size to a fraction of ADV (e.g. ≤1–5% participation), add a
  size-dependent **impact cost** model (e.g. square-root impact), and stress-test at the
  capital you actually intend to deploy.

### 3.8 Regime dependence *(High)*
- **What:** The strategy only works in one market regime (one long bull market, one
  low-vol period, one rate environment) present in the backtest.
- **Detect:** Backtest spans a single regime; equity curve is one smooth uptrend; no
  drawdowns through 2008/2020/2022-type stress.
- **Why it inflates:** It is a bet on the regime continuing, not a durable edge.
- **Fix:** Test across **multiple regimes** (bull/bear/high-vol/low-vol/rate cycles), tag
  performance by regime, and run **out-of-sample on a different regime** than the one tuned
  on.

### 3.9 No out-of-sample / walk-forward validation *(Critical)*
- **What:** All reported performance is in-sample.
- **Detect:** No train/test split; no holdout; no walk-forward.
- **Why it inflates:** In-sample performance is an upper bound, not an estimate of the
  future.
- **Fix:** **Walk-forward analysis** — repeatedly tune on a rolling/anchored window and
  evaluate on the immediately following untouched window; concatenate the out-of-sample
  segments to get an honest equity curve. Keep a **final lockbox** holdout never used for
  tuning.

### 3.10 Position sizing & risk-of-ruin *(Critical)*
- **What:** Sizing is ad hoc, fixed-fractional too large, or unbounded; no account-level
  risk limit.
- **Detect:** "All-in" sizing; no max position; bet size that risks a large fraction of
  capital per trade; ignoring the probability of a terminal drawdown.
- **Why it inflates / endangers:** Even a positive-edge strategy bankrupts with too-large
  bets due to the variance drag and path dependence; risk-of-ruin can be high even when
  expectancy is positive.
- **Fix:** **Volatility targeting** (size to a target portfolio vol) and/or a **fractional
  Kelly** stake (e.g. ¼–½ Kelly, never full Kelly), with hard per-trade and per-account risk
  caps. Estimate **risk-of-ruin** explicitly given edge, variance, and bet size.

### 3.11 Leverage & path dependence *(High–Critical)*
- **What:** Leverage applied to the *return series* without modeling margin, intraday path,
  or forced liquidation.
- **Detect:** Returns simply multiplied by a leverage factor; no margin call / liquidation
  logic; ignoring volatility drag of leveraged compounding.
- **Why it inflates:** A 3× return series ignores that an intraday spike can liquidate you
  before the favorable close; leveraged compounding suffers volatility decay.
- **Fix:** Model **margin requirements, intraday path, and liquidation**; account for
  **volatility drag**; cap leverage; backtest on the **actual path**, not just close-to-close.

### 3.12 Funding & borrow costs ignored *(High for shorts/crypto/leverage)*
- **What:** Short rebate/borrow fees, hard-to-borrow constraints, perpetual-swap **funding
  rates**, and carry are omitted.
- **Detect:** Short strategy with no borrow cost; crypto perp strategy with no funding;
  long-short with no financing.
- **Why it inflates:** Borrow/funding can exceed the gross edge, especially on shorts and
  crypto perps where funding flips sign and is paid continuously.
- **Fix:** Apply **borrow fees** (and hard-to-borrow availability) on shorts and **funding
  rates** on perps; include financing on leveraged/long-short books.

### 3.13 Timezone / session-boundary bugs *(Medium–High)*
- **What:** Bars aligned to the wrong timezone, daylight-saving shifts, or session
  open/close handled incorrectly; mixing exchange time and UTC.
- **Detect:** Naive timestamps; DST not handled; daily bars rolled at the wrong hour;
  overnight gaps treated as intraday moves; 24/7 crypto vs. session-based equities mismatch.
- **Why it inflates:** Misaligned bars can accidentally introduce look-ahead or attribute
  the overnight gap to an intraday signal.
- **Fix:** Use **timezone-aware** timestamps, define sessions explicitly per instrument,
  handle DST, and verify bar boundaries against the exchange calendar.

### 3.14 Repainting indicators (Pine / charting) *(Critical on the affected signal)*
- **What:** An indicator changes its historical values after the fact — `security()`
  pulling higher-timeframe data without offset/lookahead guards, signals confirmed only on
  the **closing** bar but evaluated intrabar in the backtest, `request.security(...,
  lookahead=barmerge.lookahead_on)`.
- **Detect:** Pine `request.security` with `lookahead_on`; signals that reference the
  current (unclosed) bar; alerts that fire then disappear; backtest results that change on
  reload.
- **Why it inflates:** Repainting bakes future information into historical signals — the
  on-chart backtest is fiction.
- **Fix:** Use `lookahead=barmerge.lookahead_off` and reference **confirmed/closed** values
  (`[1]` offset for HTF data); only act on **bar-close confirmed** signals
  (`barstate.isconfirmed`); compare strategy-tester results to bar-close-only alerts.

### 3.15 Curve-fit stop-loss / take-profit levels *(Medium–High)*
- **What:** Stop and target levels (or trailing parameters) tuned to maximize the same
  backtest.
- **Detect:** Oddly specific levels (e.g. "stop at 2.37×ATR, target 4.81×ATR"); stops/targets
  swept in the same optimization as entries.
- **Why it inflates:** Exits become additional fitted parameters that snugly avoid the
  specific historical losers.
- **Fix:** Derive exits from **risk logic** (volatility/ATR-based, fixed-R multiples) chosen
  *a priori*; validate stop/target robustness **out-of-sample**; prefer few, round,
  rule-based levels over swept ones.

### 3.16 Too few trades / weak statistical significance *(Medium–High)*
- **What:** The track record rests on too few trades to distinguish skill from luck.
- **Detect:** < ~30 trades (often < 100 for a real claim); a handful of trades dominate P&L;
  concentrated in one period.
- **Why it inflates:** Small samples have huge sampling error; one or two lucky trades can
  manufacture a great Sharpe.
- **Fix:** Require a **meaningful trade count**, test across periods, and report **confidence
  intervals** on the metrics; treat the Sharpe as an estimate with error bars, not a point.

---

## Step 4: Red-Flags Quick Scan

Instant danger signs. Any hit warrants a finding and a closer look at the related checklist
item.

- **Sharpe > 3 on daily data** (or > ~2 for a simple retail strategy) — almost always
  look-ahead, cost omission, or overfitting.
- **Equity curve is "too smooth"** / near-straight diagonal with tiny drawdowns — classic
  look-ahead or in-sample fitting signature.
- **No transaction costs / slippage** anywhere in the code.
- **Indicator or signal references the future** — `close[future]`, `shift(-n)`,
  `lookahead_on`, full-series `fit()` before split.
- **Parameters tuned on the whole series** with no holdout.
- **< 30 trades**, or P&L dominated by 1–2 trades.
- **Win rate ~100%** or suspiciously high with no losing streak.
- **Many configs tried, only the best reported** (undisclosed trial count).
- **Universe is "today's" index / current tickers** over a long history (survivorship).
- **Leverage applied by multiplying returns**, no margin/liquidation logic.
- **Shorts/perps with no borrow/funding cost.**
- **Backtest results change on reload** (repainting).
- **Reported max drawdown is implausibly small** relative to the strategy's volatility.

---

## Step 5: Output Format

Produce the review in this structure.

### 5.1 Findings summary table

| ID | Issue | Severity | Where |
|----|-------|----------|-------|
| F1 | Look-ahead: signal uses same-bar close | Critical | `strategy.py:42` |
| F2 | No transaction costs modeled | Critical | `backtest.py` (no cost term) |
| F3 | Params tuned on full series, no OOS | High | optimizer block |
| … | … | … | … |

### 5.2 Per-finding detail

For each finding:

- **ID & title** (e.g. *F1 — Look-ahead bias in entry signal*).
- **Severity** and one-line rationale.
- **Impact:** what it does to the reported numbers (e.g. "inflates Sharpe; equity curve is
  not achievable").
- **How to verify:** the exact check the user can run to confirm (e.g. "lag the signal by one
  bar and re-run — if returns collapse, this was the source").
- **Fix:** concrete remedy, with a short **before/after** code snippet where useful.

### 5.3 Metrics sanity check

Recompute or critically assess the headline metrics; define each so the user can audit them:

- **Sharpe ratio** = (annualized mean excess return) ÷ (annualized return volatility).
  Daily-to-annual scaling uses √252 (√365 or √(24·365) for crypto). Flag any Sharpe that is
  implausible for the asset/timeframe.
- **Sortino ratio** = like Sharpe but the denominator is **downside** deviation only
  (volatility of negative returns), rewarding strategies that are only "volatile" to the
  upside.
- **Max drawdown** = the largest peak-to-trough decline in the equity curve; check it is
  measured on the **net** (post-cost) curve and is plausible vs. the strategy's volatility.
- **Deflated Sharpe Ratio (DSR)** = the probability the true Sharpe > 0 after correcting the
  observed Sharpe for the **number of trials**, the **dispersion** of trial Sharpes, and
  **skew/kurtosis** of returns. Ask for the trial count so DSR can be assessed.
- **Probability of Backtest Overfitting (PBO)** = via CSCV, the fraction of splits where the
  in-sample-best configuration ranks below median out-of-sample; **> 0.5 ⇒ overfit.**
- **Trade count & exposure:** number of trades (significance), average holding period,
  **time in market** (exposure) — low exposure with a high Sharpe can still mean tiny,
  fragile edges.
- **Turnover & break-even cost:** confirm net-of-cost results and that real costs are below
  the break-even cost.

Where you cannot recompute (no return series provided), say so explicitly and state what the
user must supply.

### 5.4 Verdict

A short, honest bottom line: *which* findings (if any) are **Critical** and therefore block
deployment, what must be re-run (e.g. "add costs + lag signals + walk-forward, then
re-evaluate"), and whether the remaining edge is plausible.

### 5.5 Disclaimer (always include)

> **Educational review — not financial advice.** This is a methodological critique of a
> strategy/backtest, not investment advice and not a recommendation to trade. Even after
> every fix, **past backtest performance does not guarantee live results.** Markets change,
> costs and liquidity vary, and all trading carries risk of loss. You are solely responsible
> for your own trading and risk decisions.

---

## Tools that operationalize these fixes

These Viprasol open-source tools implement parts of this methodology and pair naturally with
this review:

- **[`bar-by-bar`](https://github.com/Viprasol-Tech/bar-by-bar)** — an agentic backtester
  with a built-in **look-ahead guard** that structurally prevents the Step 3.1 / 3.9 class of
  bugs (point-in-time iteration, no future leakage).
- **[`edgehunt`](https://github.com/Viprasol-Tech/edgehunt)** — a prediction-market
  edge/arbitrage engine for finding and pricing real edges, useful when validating whether a
  measured edge survives realistic costs (Step 3.6 / 3.7).

Use this skill to *find* the failure modes; use those tools to *enforce* the fixes.
