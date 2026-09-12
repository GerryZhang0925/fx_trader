---
name: risk-management-review
description: Review a portfolio, trading strategy, or single-position risk — volatility, drawdown, VaR/CVaR (ES), Sharpe/Sortino/Calmar/UPI, Kelly & volatility-targeted sizing, concentration & leverage caps, and stress tests. Outputs a verdict, risk dashboard, sizing review, stress-test table, and concrete recommendations. Use to vet a trade size, audit a portfolio, or institutionalize a risk policy.
version: 1.0.0
---

# Risk Management Review

A disciplined, repeatable methodology for reviewing the **risk** of a portfolio,
trading strategy, or single position — before sizing it, while running it, or
when stress hits. It answers four questions, in order:

1. **What is the loss distribution?** (volatility, skew, fat tails, drawdown profile)
2. **How big should the position(s) be?** (Kelly, fractional Kelly, vol-targeting, Optimal f)
3. **What is the right risk-adjusted return metric?** (Sharpe / Sortino / Calmar / UPI — not raw return)
4. **How does the portfolio fail?** (concentration, correlation, regime, leverage, liquidity, tail)

The output is a blunt **verdict banner**, a numeric **risk dashboard**, a
**sizing review**, a **stress-test table**, and concrete **recommendations** —
backed by formulas the user can re-run.

> **Honest scope and limits.** I reason over what you provide (returns series,
> positions/weights, leverage, scenario inputs). **Without numbers, output is
> qualitative.** Risk metrics describe history and assumed distributions — they
> do **not** predict the next regime shift. **Not financial advice; size below
> your pain threshold.**

---

## When to Activate

Activate when the user:

- Asks **"is this position too big?"** or *"how much should I risk on this trade?"*
- Shares a **returns series** and asks for risk metrics (Sharpe, Sortino, MDD, VaR, ES).
- Wants a **portfolio risk review** ("am I diversified?", "what's my real downside?").
- Mentions any of: *Kelly · fractional Kelly · vol targeting · drawdown · MDD ·
  VaR · CVaR · Expected Shortfall · Sharpe · Sortino · Calmar · Ulcer Index ·
  risk-of-ruin · position sizing · leverage cap · concentration · stress test ·
  reverse stress test · risk parity · Optimal f.*
- Wants to **institutionalize a risk policy** (single-name cap, factor cap,
  drawdown stop, leverage cap) for a fund / personal book / trading desk.

---

## Step 1: Intake & Scope

Pin down **what** is being reviewed and **what inputs** you have before computing
anything. A risk number without scope is theatre.

1. **What is being reviewed?**
   - **(A) Single position** — one symbol / one trade. Sizing is the dominant
     question.
   - **(B) Strategy** — a rule-set with a returns series (live or backtest).
     Risk-adjusted return + drawdown + tail are dominant.
   - **(C) Multi-asset portfolio** — multiple positions, possibly leveraged.
     Concentration + correlation + stress are dominant.
2. **What inputs are available?**
   - **Returns series** (daily / weekly / monthly): needed for σ, σ_d, MDD, UI,
     VaR, ES, Sharpe, Sortino, Calmar, UPI.
   - **Positions / weights** (per name): needed for concentration, top-N share,
     sector/factor exposure.
   - **Leverage** (gross and net): needed for risk-of-ruin and margin checks.
   - **Pairwise correlations** (or factor exposures): needed for "ρ → 1" stress.
   - **Scenario inputs** (vol shock, rate shock, liquidity haircut): for stress
     tests.
3. **Capital, benchmark, risk policy.**
   - **NAV** (so percentages map to dollars).
   - **Benchmark** (SPY / 60-40 / risk-free): so we can compute Information Ratio
     when relevant.
   - **Existing risk policy** (single-name cap, factor cap, leverage cap, max
     drawdown stop) — if absent, **flag it** as a Step-8 red flag.
4. **Horizon and regime.**
   - Holding period (intraday / daily / monthly).
   - Realized regime over the returns window (bull / bear / low-vol / crisis) —
     a 2017-only sample is not a risk model.

Do not proceed to a verdict until you know **what is being reviewed**, **what
inputs exist**, and **what the existing risk policy (if any) is**.

---

## Step 2: Loss Distribution & Metrics

Compute (or explain how to compute) every metric below. Use the formulas
verbatim — the user should be able to re-run them.

### Volatility & dispersion

- **Standard deviation** `σ = sqrt( mean( (r_t − r̄)² ) )` — total dispersion;
  **symmetric** (treats upside = downside).
- **Downside deviation** `σ_d = sqrt( mean( min(r_t − MAR, 0)² ) )` — only
  returns below the **minimum acceptable return** (often 0 or the risk-free
  rate) count. Used by Sortino.

### Drawdown family

- **Max drawdown** `MDD = max_t (peak_t − value_t) / peak_t` — the single
  number every retail trader should know.
- **Average drawdown** — mean of all drawdown episodes (each counted from peak
  to recovery).
- **Drawdown duration** — *peak → trough → recovery* in calendar time. A long
  flat -20% is often more painful than a fast -30% that recovers in a month;
  **track duration, not just depth**.
- **Ulcer Index** (Peter Martin, 1987):
  `UI = sqrt( mean( drawdown_t² ) )` over the period.
  Captures *depth × time underwater* in one number — penalises sustained
  underwater periods.

### Tail risk

- **VaR_α** — the loss that is **not** exceeded with confidence α. *"95% daily
  VaR = $X"* means the worst 5% of days lose **at least** $X. Computable via
  historical sim, parametric (normal), or Monte Carlo. **VaR is NOT
  subadditive** — combining two portfolios' VaRs can give the wrong answer.
- **CVaR / Expected Shortfall** `ES_α = E[ loss | loss ≥ VaR_α ]` — the
  **average** loss in the worst (1 − α) of cases. **Coherent** (subadditive,
  monotonic, translation-invariant, positive-homogeneous). **Basel III moved
  banks from VaR to ES_97.5** — prefer ES for portfolio decisions.
- **Risk of ruin** — probability the equity curve hits a fatal threshold. Closed
  form exists for IID Bernoulli trades; otherwise simulate.
- **Tail / kurtosis check** — empirical returns are **fat-tailed**, **not
  normal**, almost always. Parametric-normal VaR therefore **systematically
  understates** tail loss. If you must use it, call out the assumption and
  cross-check against historical/ES.

Output these as a **dashboard table** (Step 9), not prose.

---

## Step 3: Risk-Adjusted Return

Never quote raw return. Always pair it with one of these — and pick the one
that matches the strategy shape.

| Metric | Formula | When it fits | What it hides |
|---|---|---|---|
| **Sharpe** | `(R − R_f) / σ` | Roughly symmetric returns; broad comparability. | Punishes upside vol; gamed by autocorrelation & illiquidity smoothing. |
| **Sortino** | `(R − MAR) / σ_d` | Asymmetric payoffs (options, trend following). | MAR choice (0 vs R_f) changes the number; still a single-number summary. |
| **Calmar** | `annualised return / |MDD|` | "Can I survive the worst stretch?" framing. | Single-event metric — one big DD dominates. |
| **Ulcer Performance Index (UPI / Martin ratio)** | `(R − R_f) / UI` | "Did I sleep at night?" — penalises underwater **time**. | Less standard than Sharpe; needs a long enough window. |
| **Information Ratio** | `active return / tracking error` | Benchmark-relative strategies. | Tells you nothing about absolute drawdown. |

### Patterns that should make you suspicious

- **Sharpe > 3 on a non-HFT strategy** → likely over-fit, illiquidity smoothing,
  or hidden tail (short-vol). Treat as **red flag**, not a feature.
- **Autocorrelated daily returns** — inflates Sharpe artificially; check via the
  autocorrelation of `r_t` (a daily ρ of 0.2+ is suspicious for liquid markets).
- **Sortino << Sharpe** → the **upside** is the source of "return" (e.g. selling
  vol / picking up nickels in front of a steam roller). Drawdowns are larger
  than the symmetric vol implies.
- **Calmar high but UPI low** → the strategy avoided one giant DD but spends
  long stretches underwater (a slow bleed); investors will redeem.

> **Multiple-testing.** If the strategy was selected from many candidates,
> Sharpe overstates skill. Cross-link the Viprasol **`trading-strategy-review`**
> skill to compute **Deflated Sharpe** (Bailey & López de Prado) and Probability
> of Backtest Overfitting before trusting the headline number.

---

## Step 4: Position Sizing Review

What method is being used? Apply the right formula; flag missing or arbitrary
sizing as a Step-8 red flag.

### Kelly criterion

- **Discrete bet** with edge `e` and net odds `b`: `f* = e / b`.
- **Continuous returns** (the practical form):
  ```
  f* = (μ − r) / σ²
  ```
  where μ = expected return, r = risk-free rate, σ² = return variance.
- **Why Kelly maximises long-run growth** — and **why pure Kelly is too
  aggressive in practice**: parameter-estimation error (μ and σ are *estimated*,
  not known) → systematic over-sizing → catastrophic drawdowns when reality
  rhymes differently than the sample. Kelly also assumes IID stationary
  returns; real markets shift regime.
- **Half-Kelly / quarter-Kelly is the practitioner default.** Halving f*
  approximately halves volatility while keeping most of the geometric growth.

### Volatility targeting

- Choose a target **portfolio** vol (e.g. 10–15% annualised). Size each position
  so its risk contribution matches the budget:
  ```
  notional_i = (target_vol × NAV) / σ_i
  ```
- Used by every CTA, risk-parity manager, and most multi-strat books — it turns
  regime-vol changes into stable risk contributions instead of stable dollars.

### Risk parity (limits)

- Equal **risk contribution**, not equal weight: `w_i × σ_i × ρ_{ip} = const`.
  Works when correlations are stable; **fails badly in crisis** when everything
  correlates → 1.

### Optimal f (Vince)

- Maximises geometric growth on the **actual P&L distribution** (not an assumed
  Gaussian). Closer to "empirical Kelly" — better than naive Kelly when payoffs
  are highly non-binary (options strategies, lumpy event trades).

### Output of this step

State the **current** sizing method (or "gut-feel — none documented" if so),
the **recommended** sizing, and the **constraint that should bind** (the lower
of half-Kelly, vol-target sizing, and the single-name cap from Step 5). Show
the numbers.

---

## Step 5: Concentration, Correlation & Leverage

Sizing is necessary but not sufficient — a properly-sized but concentrated
portfolio still blows up.

- **Single-position cap** — practitioner default: **5–10% of NAV per single
  position**. Tighter (1–3%) for illiquid names. **>10–15% on one name = flag.**
- **Sector / factor concentration** — sum exposures to any one factor (tech,
  oil, US-rates duration, EM-FX, momentum) and apply a hard cap. A "diversified"
  book of 8 tech names is one position.
- **Top-N concentration** — **top-3 holdings > 40% of NAV = flag**, regardless
  of vol; reads as "if any one of these breaks, the book breaks."
- **Pairwise correlation stress** — assume **ρ → 1** in crisis for all
  risk-on assets and recompute portfolio vol. If realized vol explodes, the
  book is a *single bet* dressed up as diversification.
- **Leverage** — gross (sum of absolute exposures) vs net (long − short).
  Practitioner reads:
  - gross > 2× equity = **elevated** (intraday stops mandatory),
  - gross > 3× without stops = **flag**,
  - gross > 4× = **institutional / margin-call territory** (one bad day kills the
    fund).
- **Liquidity** — position size as a **% of average daily volume (ADV)**. >1
  ADV = "can't exit in one day at quoted prices"; price-of-exit is part of the
  risk model.

---

## Step 6: Stress-Test Catalog

Apply **at least 3 historical** scenarios and **2 hypotheticals** plus a
**reverse stress test**. Report **portfolio P&L per scenario**, in dollars and
as a percent of NAV.

### Historical replays (apply each book to the move)

- **1987-Oct ("Black Monday")** — SPX -22% in a day.
- **2008-Sep–Nov ("GFC")** — SPX peak-to-trough ≈ -45%, credit spreads ×3,
  funding markets frozen, gold up, treasuries up.
- **2020-Mar ("COVID crash")** — SPX -34% in 22 trading days, IG spreads ×3,
  HY ×4, oil briefly negative, VIX > 80, correlations → 1.
- **2022 bond rout** — bonds and equities **down together**; 60-40 had its worst
  year since the 1930s.
- **2023-Mar ("SVB")** — regional-bank stress, 2-yr UST fastest move in
  decades, repricing of duration.

### Hypotheticals

- **+1σ vol shock** — multiply realised σ by ~1.7× (one standard deviation up
  on a vol-of-vol basis); does the leverage cap still hold?
- **-10% equity / +200bp rates instant** — concurrent shock to both legs.
- **Correlation → 1** — every "diversifier" moves with risk; recompute portfolio
  vol on a correlation matrix of ones.
- **50% liquidity haircut** — every exit price halves the bid; how big is the
  gap between mark and exit?

### Reverse stress test

Ask the inverse question: **what move kills the book?** Solve for the
combination of equity shock + vol shock + correlation shock + liquidity shock
that drives the portfolio to a fatal drawdown (e.g. -50%). If the answer is
"3% intraday on SPX", the book is too levered. If the answer is "1987 + 2008
+ 2020 all at once and twice as big", it is robust.

---

## Step 7: Risk-of-Ruin

Make the asymmetry explicit. **Drawdown recovery is multiplicative, not
additive.**

```
required gain to recover from a drawdown of d  =  1 / (1 − d) − 1

  -25%  →  +33.3%
  -50%  →  +100%
  -75%  →  +300%
  -80%  →  +400%
  -90%  →  +900%
```

> **Asymmetry kills compounders.** A strategy that compounds at 15% for ten
> years and gives back 80% in year eleven is a worse outcome than one that
> compounds at 6% with no -80% event.

Risk-of-ruin is high whenever sizing or leverage make a fatal drawdown a
plausible **path**, not a tail. Triggers to call this out explicitly:

- Single position > 20% of NAV with σ_i > 50% annualised.
- Pure-Kelly (not fractional) sizing.
- Gross leverage > 3× without **intraday** stops.
- A stress-test row in Step 6 produces > -40% portfolio P&L.

Compute, when given the inputs, the probability of breaching a drawdown
threshold (e.g. -50%) over the holding horizon — via the closed-form ruin
formula for IID trades or a quick Monte Carlo.

---

## Step 8: Red-Flag Quick Scan

Any one of these moves the verdict toward 🟠 / ⛔.

- **Sharpe > 3** on a non-HFT strategy → over-fit or hidden tail.
- **Single position > 10–15%** of NAV.
- **Top-3 positions > 40%** of NAV.
- **MDD < 5% on 6+ months of live data** → fat-tail risk hidden (likely a
  short-vol / sell-tail payoff).
- **Leverage gross > 3× without intraday stops.**
- **Undefined max loss / no stop / no position cap** in the strategy doc.
- **"Sizing by gut-feel"** — no Kelly, vol target, or fixed-fractional rule
  documented.
- **Correlation → 1 in stress ignored** — book is implicitly one factor.
- **Sortino << Sharpe** — upside is the source of "return"; downside fat-tail
  hidden.
- **Parametric-normal VaR on fat-tailed returns** — VaR systematically
  understates; pair with ES_97.5 and historical sim.
- **No drawdown duration tracked** — only depth. Long flat losses get under
  investors' skin.

---

## Step 9: Output Format — the Risk Report

Lead with a verdict banner, then the dashboards, the sizing review, the
stress-test table, the risk-of-ruin call-out (when relevant), the
recommendations, and the disclaimer.

### Verdict banner (pick one)

- ✅ **WITHIN RISK POLICY** — caps respected, sizing methodical, stress tests
  within tolerance, no red flags.
- 🟡 **CAUTION** — within caps but one or two yellow flags (concentration creep,
  high but not fatal leverage, missing reverse stress test, Sortino noticeably
  below Sharpe).
- 🟠 **OVER-RISK** — at least one hard cap breached (single-name > 15%, top-3 >
  40%, gross > 3× without stops, MDD path > 30% in stress). Reduce before
  doing anything else.
- ⛔ **LIKELY-RUIN PATH** — sizing or leverage make a fatal drawdown a
  *plausible path*, not a tail (pure Kelly + 3×, all-in one factor, stress row
  > -40%). Cut size now.

Follow the banner with **one sentence** explaining why.

### Risk dashboard

| Metric | Value | Notes |
|---|---|---|
| Annualised σ | … | total dispersion |
| Downside deviation σ_d | … | MAR used = … |
| Max drawdown | … | peak → trough … |
| MDD duration | … days | peak → recovery |
| Ulcer Index | … | depth × time underwater |
| Sharpe | … | R_f used = … |
| Sortino | … | MAR used = … |
| Calmar | … | annualised return / |MDD| |
| UPI (Martin ratio) | … | (R − R_f) / UI |
| VaR_95 (daily, historical) | … | …% of NAV |
| ES_97.5 (daily) | … | …% of NAV |

### Position dashboard

| Item | Value | Cap | Status |
|---|---|---|---|
| Single-name max | …% NAV | 10% | ✅/🟠 |
| Top-3 share | …% NAV | 40% | ✅/🟠 |
| Dominant factor | …% NAV | 25% | ✅/🟠 |
| Gross leverage | …× | 2× | ✅/🟠 |
| Net leverage | …× | — | — |
| Largest position vs ADV | …× | 1× | ✅/🟠 |

### Sizing review

State the **current** method (or "none — gut-feel"), the **Kelly / half-Kelly /
vol-target** recommended sizes (with formulas and plugged-in numbers), the
**binding cap**, and the **recommended size in dollars and % NAV**.

### Stress-test table

| Scenario | Assumed shock | Portfolio P&L | Post-stress NAV |
|---|---|---|---|
| 1987-Oct replay | SPX -22% in a day | … | … |
| 2008-Sep–Nov replay | SPX -45% / spreads ×3 | … | … |
| 2020-Mar replay | SPX -34% in 22 days / ρ → 1 | … | … |
| +1σ vol shock | σ × 1.7 | … | … |
| -10% equity / +200bp rates | concurrent | … | … |
| **Reverse stress** | move that drives -50% NAV | … | … |

### Risk-of-ruin call-out (when triggered)

State the *path*, the recovery math (`+X% needed to recover -Y%`), and the
probability of breaching the user's drawdown threshold over the horizon if a
closed-form or quick Monte Carlo gives it.

### Recommendations

Concrete and numbered. Examples:

1. Cut single-name X from 18% → 8% (single-name cap).
2. Replace 3× ETF with the underlying to remove embedded leverage.
3. Add a tail hedge: SPX 5-delta puts, 1% of NAV per month.
4. Cap gross leverage at 2× with an intraday -2% NAV hard stop.
5. Switch sizing from gut-feel to vol-target 12% annualised with a half-Kelly
   override per position.

### Disclaimer (always include)

> **Educational risk-management guidance — not financial, legal, or investment
> advice, and not a guarantee of safety.** I reason only over the data you
> provide; without numbers, output is qualitative. Risk metrics describe
> **history and assumed distributions**; they do **not** predict the next
> regime shift. **Risk-of-ruin is real — size below your pain threshold.**
> Markets do things that have never happened before. Consult a qualified risk
> or investment professional for live decisions.

---

## Related Viprasol Skills

- **`trading-strategy-review`** — backtest failure-modes (look-ahead,
  overfitting, survivorship, slippage) and Deflated Sharpe / PBO. Pair with
  this skill before trusting a headline Sharpe.
- **`options-strategy-analyzer`** — Greeks, payoff diagrams, and closed-form
  max-loss / max-profit / break-even for defined-risk option structures. Use
  before plugging an options strategy's σ and DD into this review.

*Not affiliated with or endorsed by Anthropic.*
