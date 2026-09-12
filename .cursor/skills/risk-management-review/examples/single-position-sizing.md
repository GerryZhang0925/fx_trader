# Example — Single-position sizing: long XYZ, μ=12%, σ=35%

> Illustrative walkthrough. Numbers are fabricated for teaching. This is
> educational risk-management guidance, **not financial advice**.

## The request (what the user provided)

> "I want to take a long single-stock position in XYZ. I think it'll do **12%
> annualised** with **35% annualised vol**. Risk-free rate is **5%**. My NAV is
> **$100,000** and my broker margin lets me lever up to **1.5×**. How big
> should this position be?"

**Inputs**

| Field | Value |
|---|---|
| Expected return μ | 12% annualised |
| Volatility σ | 35% annualised |
| Risk-free rate `R_f` | 5% |
| NAV | $100,000 |
| Max leverage available | 1.5× |
| Single-position cap (practitioner default) | 10% NAV |
| Target portfolio vol (assumed for vol-targeting) | 15% annualised |

---

## Step 1 — Scope

- **What:** a **single position** (case A) — sizing is the dominant question.
- **Inputs:** point estimates of μ, σ, `R_f`; NAV; leverage cap. No returns
  series → metrics (Sharpe / Sortino / MDD / VaR / ES) cannot be computed for
  the position; sizing is analytic.
- **Existing risk policy:** none stated → **flag** (Step-8 red flag: gut-feel
  sizing).
- **Caveat:** μ and σ are **estimates**. Kelly sized on point estimates
  systematically over-sizes; we will halve.

---

## Step 4 — Position sizing review

### Full Kelly

```
f* = (μ − R_f) / σ²
   = (0.12 − 0.05) / 0.35²
   = 0.07 / 0.1225
   ≈ 0.5714
   ≈ 57.1% of NAV
```

**$57,140** notional on a $100,000 NAV.

### Half-Kelly (practitioner default)

```
f_½ ≈ 0.5714 / 2 ≈ 0.2857
   ≈ 28.6% of NAV
```

**$28,570** notional. Halves the volatility contribution of this position while
keeping most of the long-run geometric growth.

### Volatility-targeted size

Target portfolio σ = 15% annualised. For a single-position bookmark:

```
notional = (target_vol × NAV) / σ_position
         = (0.15 × 100,000) / 0.35
         = 15,000 / 0.35
         ≈ $42,857
         ≈ 42.9% of NAV
```

### Single-name cap (practitioner default 10% NAV)

```
cap = 0.10 × 100,000 = $10,000
```

### The binding cap

Pick the **lower** of half-Kelly, vol-target, and single-name cap:

| Method | Recommended notional | % NAV |
|---|---|---|
| Full Kelly | $57,140 | 57.1% |
| Half-Kelly | $28,570 | 28.6% |
| Vol-target (15% port vol) | $42,857 | 42.9% |
| **Single-name cap (10%)** | **$10,000** | **10.0%** |

→ **Recommended size: $10,000 (10% of NAV).** The single-name cap **binds**;
half-Kelly is also above the cap. The 1.5× margin headroom is **irrelevant** —
this position should not use any leverage.

---

## Step 5 — Concentration & leverage check

- Single-position cap **10%** → recommended size respects it.
- Factor exposure: a 35%-vol single equity is dominated by one factor
  (idiosyncratic + sector); do not stack other positions in the same factor.
- Leverage: **none required** for the recommended size. Even at full Kelly
  ($57k), the position fits inside the 1.5× margin — but margin **availability
  is not a sizing reason**.

---

## Step 7 — Risk-of-ruin call-out

Full Kelly at 57% NAV in a 35%-vol single equity creates a **plausible
ruin path**, not a tail. A one-year worst-case for a single 35%-vol stock can
easily be **-50% to -70%** (well within one standard deviation of historical
drawdowns for individual equities). At 57% sizing, a -50% stock move = **-28.6%
NAV** in one position; a -70% stock move = **-40% NAV**. Recovery math:

```
required gain to recover from a drawdown d  =  1 / (1 − d) − 1

  -28.6% NAV  →  +40.0% needed to recover
  -40.0% NAV  →  +66.7% needed to recover
```

At the **recommended 10% sizing**, the same stock moves produce -5% NAV (-7%
worst case) — survivable and well inside the user's plausible recovery range.

---

## Step 8 — Red-flag scan

- 🟠 **Sizing by gut-feel** — no documented sizing rule until this review.
- 🟠 **Full-Kelly result > 50% NAV** — the textbook Kelly answer is
  immediately disqualified by the single-name cap; this is the rule, not the
  exception.
- 🟢 **Recommended size 10%** respects the practitioner single-name cap and
  is below every other sizing method.

---

## Step 9 — Verdict

### 🟠 OVER-RISK *(if the user takes the full-Kelly or vol-target size)* / ✅ WITHIN RISK POLICY *(at the recommended 10%)*

The unconstrained sizing methods (full Kelly 57%, half-Kelly 29%, vol-target
43%) **all breach the 10% single-name cap**. The cap is the binding
constraint. **Size at $10,000 (10% NAV), unlevered.**

### Recommendations

1. **Size the position at $10,000 (10% of NAV), unlevered.**
2. **Do not use the 1.5× margin** for this position — margin availability is
   not a sizing reason; the cap binds first.
3. **Document a sizing rule** going forward: *"the lower of (a) half-Kelly,
   (b) vol-target at 15% portfolio vol, (c) 10% single-name cap"*. This
   replaces gut-feel.
4. **Re-derive μ and σ from an out-of-sample window** before re-running
   Kelly — point estimates are biased, especially μ.
5. **Set an explicit drawdown stop** on this position (e.g. -25% from entry)
   so the position-level risk is bounded even if σ proves too low.

### Cross-link

- **`trading-strategy-review`** — if μ and σ came from a backtest, run
  Deflated Sharpe / PBO to gauge how much of "12% / 35%" is over-fit.
- **`options-strategy-analyzer`** — if the long-XYZ thesis can be expressed
  as a defined-risk call spread, you cap loss and may free single-name cap
  for other names.

---

## Disclaimer

**Educational risk-management guidance — not financial, legal, or investment
advice, and not a guarantee of safety.** Numbers above are illustrative;
inputs (μ, σ, NAV, caps) are user-supplied and unverified here. Risk metrics
describe **history and assumed distributions**; they do **not** predict the
next regime shift. **Size below your pain threshold.** Markets do things that
have never happened before. Consult a qualified risk or investment
professional for live decisions.
