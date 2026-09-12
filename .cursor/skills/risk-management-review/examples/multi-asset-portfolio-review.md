# Example — Multi-asset portfolio review: TQQQ / BTC / NVDA / SVXY / cash

> Illustrative walkthrough. Numbers are fabricated for teaching. This is
> educational risk-management guidance, **not financial advice**.

## The request (what the user provided)

> "Here's my portfolio. Is it diversified? How risky is it really?"

| Position | Weight | What it is |
|---|---|---|
| **TQQQ** | 35% | 3× leveraged long Nasdaq-100 ETF |
| **BTC** | 25% | Spot bitcoin |
| **NVDA** | 20% | Single mega-cap tech stock |
| **SVXY** | 15% | Short-VIX-futures ETF (sells volatility) |
| **Cash / T-bills** | 5% | Risk-free |
| **NAV** | $250,000 | |
| **Stated leverage** | "None — just the ETF" | (in practice, TQQQ embeds 3×) |

The user has **no documented risk policy**, **no single-name cap**, **no
factor cap**, and **no stop**.

---

## Step 1 — Scope

- **What:** a **multi-asset portfolio** (case C). Concentration + correlation
  + stress are dominant.
- **Inputs:** weights + NAV. No returns series provided → metrics below are
  **illustrative** based on long-window historical proxies for each holding,
  rolled up at the stated weights. Recompute against the user's actual
  returns before quoting.
- **Existing risk policy:** none → **flag** (Step-8 red flag).

---

## Step 2 — Loss distribution & metrics (illustrative)

Using historical proxies (TQQQ since 2010, BTC since 2014, NVDA since 2010,
SVXY since 2011, daily returns at the stated weights — illustrative only):

| Metric | Value (illustrative) | Notes |
|---|---|---|
| Annualised σ | **~45%** | high; dominated by TQQQ + BTC |
| Downside deviation σ_d | ~32% | MAR = 0 |
| Max drawdown (historical roll-up) | **~-65%** | 2022 + 2018 vol-pop blend |
| MDD duration | ~14 months peak → recovery | sustained underwater |
| Ulcer Index | ~22 | high — depth × time underwater |
| Sharpe | ~0.7 | unimpressive given the risk |
| Sortino | ~0.6 | < Sharpe ⇒ upside is the "return" source |
| Calmar | ~0.25 | annualised return / |MDD| ≈ 0.16 / 0.65 |
| UPI (Martin) | ~0.20 | underwater time penalised |
| VaR_95 (daily, historical) | **~4.5%** of NAV | ≈ -$11,250 worst-5% day |
| ES_97.5 (daily) | **~6.5%** of NAV | ≈ -$16,250 average tail day |

> Sortino < Sharpe and a 65% MDD vs Sharpe 0.7 both confirm: the **return is
> coming from the upside fat tail; the downside fat tail is fully exposed.**

---

## Step 3 — Risk-adjusted return

- **Sharpe 0.7** — mediocre.
- **Sortino 0.6 < Sharpe** — classic short-vol / leveraged-long signature; the
  "good" volatility (upside) is doing all the lifting.
- **Calmar 0.25** — for every 1% of expected annual return you accept 4% of
  drawdown.
- **UPI 0.20** — investors would spend over a year underwater per crisis.

None of these justify the **65% historical MDD** in a portfolio with no
documented risk policy.

---

## Step 4 — Sizing review

There is no sizing rule — positions are large round percentages chosen by
conviction. No Kelly, no vol target, no fixed-fractional discipline. **Flag.**

---

## Step 5 — Concentration, correlation & leverage

| Item | Value | Cap | Status |
|---|---|---|---|
| Single-name max | **35% (TQQQ)** | 10% | ⛔ |
| Top-3 share | **35 + 25 + 20 = 80%** | 40% | ⛔ |
| Dominant factor (US equity beta) | **TQQQ 35% + NVDA 20% + SVXY 15% ≈ 70%** | 25% | ⛔ |
| Stated gross leverage | "1×" | 2× | — |
| **Effective gross leverage** (TQQQ embeds 3×; SVXY is short-vol levered) | **≈ 1.85×** *(0.35×3 + 0.25 + 0.20 + 0.15×~2 + 0.05 ≈ 1.85)* | 2× without stops | 🟠 |
| Liquidity vs ADV | well under 1× ADV | 1× | ✅ |

### Correlation reality

All four risk positions (TQQQ, BTC, NVDA, SVXY) are **levered long-risk
expressions**. In normal regimes their pairwise ρ ranges ~0.4–0.7. **In a
crisis (March 2020, late-2018 vol-pop, May 2022) all four pairwise ρ → 0.9+
toward 1.0 simultaneously.** That is the correlation-creep failure mode — the
portfolio looks diversified across "tech / crypto / leveraged ETF / vol" but
is **one factor**: short-gamma, long-risk, long-tech-beta.

---

## Step 6 — Stress tests

Applied to the current weights and the embedded 3× / short-vol leverage:

| Scenario | Shock | Portfolio P&L | Post-stress NAV |
|---|---|---|---|
| **2020-Mar replay** | SPX -34% / VIX → 80 / ρ → 1 | **≈ -65%** | ~$87,500 |
| **2008-Sep–Nov replay** | SPX -45% / spreads ×3 (SVXY didn't exist; proxy via VIX spike) | **≈ -70%** | ~$75,000 |
| **1987-Oct replay** | SPX -22% in a day (intraday gamma + 3× ETF reset path) | **≈ -50%** (single-day, before any unwind) | ~$125,000 |
| **+1σ vol shock** + ρ → 1 | σ × 1.7 across risk legs | **≈ -25% intraday** | ~$187,500 |
| **-10% equity / +200bp rates** | concurrent | ≈ -20% | ~$200,000 |
| **50% liquidity haircut** on TQQQ + SVXY exit | exit at half the bid | exit cost ≈ -8% of NAV on top of mark | ~$230,000 minus the mark loss |
| **Reverse stress** — what move kills the book? | **SPX -8% intraday with VIX > 40** is sufficient: TQQQ ≈ -24% (3×), SVXY drops ~30%+ on a vol-pop, NVDA ≈ -10–12% on beta; combined ≈ **-21% NAV in a single session** *before* any further damage from gamma in SVXY. The 1987 / 2020 / 2018 paths all kill it. | | |

The portfolio fails the **reverse stress test** at a move (SPX -8% intraday +
VIX > 40) that the market has produced **multiple times** in the user's
investing lifetime.

---

## Step 7 — Risk-of-ruin

A 60% drawdown is **inside the realised historical envelope** for this book.
The recovery math:

```
required gain to recover -60%  =  1 / (1 − 0.60) − 1  =  1 / 0.40 − 1  =  +150%
required gain to recover -65%  =  1 / (1 − 0.65) − 1  =  1 / 0.35 − 1  ≈  +186%
required gain to recover -70%  =  1 / (1 − 0.70) − 1  =  1 / 0.30 − 1  ≈  +233%
```

That is, the 2020-Mar replay (-65% drawdown) requires the **portfolio to
nearly triple from the trough** to get back to its old high — historically
that has taken **multi-year** runs in the same kind of regime that just took
it down.

Triggers met: ⛔ single-name > 20%, dominant factor > 25%, stress row > -40%,
no intraday stops on the levered ETF. **This is a likely-ruin path, not a
tail.**

---

## Step 8 — Red-flag scan

- ⛔ **Single position > 10–15%** (TQQQ 35%, BTC 25%, NVDA 20%).
- ⛔ **Top-3 > 40%** (80%).
- ⛔ **Dominant factor > 25%** (US-equity-beta + vol ≈ 70%).
- 🟠 **Embedded leverage** (TQQQ 3×) **without intraday stops**.
- 🟠 **Sortino < Sharpe** — upside fat tail is the return source.
- 🟠 **No documented risk policy / no sizing rule / no stop.**
- 🟠 **Short-vol exposure (SVXY)** — asymmetric, blew up in Feb 2018
  (XIV terminated, SVXY -90% in two days).
- 🟠 **Correlation → 1 in stress ignored.**

---

## Step 9 — Verdict

### ⛔ LIKELY-RUIN PATH

The portfolio is a leveraged short-vol bet on US tech and bitcoin dressed up
as four positions. Stress tests, reverse stress test, and the recovery
asymmetry agree: a single ordinary crisis (SPX -8% intraday + VIX > 40)
produces a **-20%+ NAV** day before any further damage, and a 2020-Mar
replay produces a **-65% NAV** drawdown requiring **+186%** to recover.

### Recommendations

1. **Cut every single name to ≤ 10% of NAV.** TQQQ 35 → 10, BTC 25 → 10,
   NVDA 20 → 10, SVXY 15 → 0.
2. **Replace TQQQ with QQQ** at the same dollar size — remove the embedded
   3× leverage (which carries gamma decay even without stops being hit).
3. **Eliminate SVXY entirely.** Short-vol is an *asymmetric* trade
   (limited upside, unbounded downside) that does not belong in an
   undocumented-policy retail book. The Feb 2018 XIV termination is the
   precedent.
4. **Add a real diversifier**: 20–30% short-duration US Treasuries / T-bills,
   5–10% gold. Both have historically lower realised correlation in
   crisis-tech regimes than any of the current holdings.
5. **Cap dominant-factor exposure at 25% of NAV.** Tech-beta names (NVDA,
   QQQ, BTC as a risk-asset proxy) all count toward the same factor.
6. **Adopt a written sizing rule:** *"the lower of half-Kelly, vol-target at
   12% portfolio vol, and a 10% single-name cap"*; **and a portfolio drawdown
   stop** at -15% from the rolling 90-day high (cut risk by half), -25%
   (de-risk to T-bills, reassess).
7. **Run the stress catalog quarterly** against the *actual* book — not the
   intended one.

### Cross-link

- **`trading-strategy-review`** — for any of the underlying strategies, run
  Deflated Sharpe / PBO before sizing them.
- **`options-strategy-analyzer`** — if the user wants tech-beta exposure with
  bounded loss, a long call spread on QQQ replaces TQQQ + an explicit
  drawdown stop.

---

## Disclaimer

**Educational risk-management guidance — not financial, legal, or investment
advice, and not a guarantee of safety.** Numbers above are illustrative
historical-proxy roll-ups, not a backtest of the user's actual returns. Risk
metrics describe **history and assumed distributions**; they do **not**
predict the next regime shift. **Risk-of-ruin is real — size below your pain
threshold.** Markets do things that have never happened before. Consult a
qualified risk or investment professional for live decisions.
