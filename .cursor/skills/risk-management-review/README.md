# Risk Management Review — Agent Skill

> Before you size the trade: compute the loss distribution, run the stress
> tests, name the binding cap, and get a blunt verdict — Kelly / vol-targeting,
> VaR / ES, Sharpe / Sortino / Calmar / UPI, concentration and leverage caps,
> and risk-of-ruin asymmetry included.

[![GitHub stars](https://img.shields.io/github/stars/Viprasol-Tech/risk-management-review?style=social)](https://github.com/Viprasol-Tech/risk-management-review)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Compatible-blueviolet)](https://github.com/Viprasol-Tech/risk-management-review)
[![Metrics](https://img.shields.io/badge/Risk%20Metrics-11-green)](skill.md)
[![Covers](https://img.shields.io/badge/Kelly%20%2B%20Vol--Target%20%2B%20VaR%2FES-blue)](skill.md)
[![Version](https://img.shields.io/badge/version-1.0.0-informational)](CHANGELOG.md)

**Works with:** Claude Code · OpenAI Codex · Cursor · GitHub Copilot · Gemini
CLI · 26+ tools that support portable agent skills.

---

## Quick Install

Clone the skill into your agent's skills directory:

```bash
# Claude Code
git clone https://github.com/Viprasol-Tech/risk-management-review \
  ~/.claude/skills/risk-management-review

# OpenAI Codex
git clone https://github.com/Viprasol-Tech/risk-management-review \
  ~/.codex/skills/risk-management-review

# Cursor / Gemini CLI / other tools — clone anywhere your tool loads skills from, e.g.
git clone https://github.com/Viprasol-Tech/risk-management-review \
  ~/.config/skills/risk-management-review
```

The skill is a single self-contained `skill.md` (plus examples) — no
dependencies, no install step, nothing to build.

## Try It

Paste your inputs and ask:

```
Vet this position size — long XYZ, μ=12% annualised, σ=35%, R_f=5%,
NAV=$100k, leverage 1.5×. Is it too big?
```

The skill will scope the review, apply Kelly (`f* = (μ − r) / σ²`) and
half-Kelly, run the vol-target sizing, check it against the single-name cap,
flag risk-of-ruin if relevant, and return a verdict banner
(✅ / 🟡 / 🟠 / ⛔) with concrete sizing recommendations.

---

## Why This Exists

Most trading losses aren't a bad call on direction — they're a **bad call on
size**, on **leverage**, or on **how a "diversified" book behaves when
correlations go to 1**. A 50% drawdown requires +100% to recover; 80% needs
+400%; **asymmetry kills compounders**. Pure Kelly is almost always over-sized
in practice; parametric-normal VaR systematically understates fat tails; Sharpe
above 3 on a non-HFT strategy is usually over-fit, not edge. The defense is a
*consistent*, formulas-on-the-table risk review — compute the loss
distribution, size with half-Kelly or a vol target, cap single-name and
factor exposure, and stress-test what could actually kill the book. This
skill encodes that review so your agent runs it the same way every time.

## What It Does

1. **Scopes** the review — single position, strategy, or multi-asset
   portfolio — and pins down which inputs (returns series, weights, leverage,
   correlations, scenarios) are available.
2. **Computes** the loss distribution — σ, σ_d, MDD + duration, Ulcer Index,
   VaR_95, ES_97.5 — with explicit formulas and the fat-tail caveat.
3. **Picks** the right risk-adjusted return metric — Sharpe vs Sortino vs Calmar
   vs UPI vs Information Ratio — and flags gameable patterns (Sharpe > 3,
   autocorrelation, Sortino << Sharpe).
4. **Reviews position sizing** — applies Kelly `f* = (μ − r) / σ²` and the
   half-Kelly default, vol-targeting `notional_i = target_vol × NAV / σ_i`, and
   Optimal f; flags missing or gut-feel sizing.
5. **Checks concentration, correlation & leverage** — single-name cap, top-3
   share, factor/sector caps, pairwise ρ → 1 stress, gross/net leverage, and %
   of ADV.
6. **Runs the stress catalog** — 1987, 2008, 2020-Mar, 2022 bond rout, 2023-Mar
   SVB, plus +1σ vol shock, -10% equity / +200bp rates, correlation → 1,
   liquidity haircut, and a **reverse stress test** ("what move kills the
   book?").
7. **Calls out risk-of-ruin** with the recovery-asymmetry math when sizing or
   leverage make a fatal drawdown a plausible path.
8. **Outputs a verdict** (✅ Within risk policy / 🟡 Caution / 🟠 Over-risk /
   ⛔ Likely-ruin path), a risk dashboard, a position dashboard, a sizing
   review, a stress-test table, and a concrete recommendations list.

## Features

- **Full risk dashboard** — σ, σ_d, MDD, MDD duration, Ulcer Index, Sharpe,
  Sortino, Calmar, UPI, VaR_95, ES_97.5 — one table the user can re-run.
- **Sizing engine** — Kelly, half-Kelly default, vol-targeting, Optimal f, with
  the binding-cap rule (lower of half-Kelly, vol-target, and single-name cap).
- **Concentration + leverage caps** — 10% single-name, 40% top-3, gross > 3×
  without stops = flag.
- **Stress-test catalog** — three historical replays + two hypotheticals + a
  reverse stress test, mandatory.
- **Risk-of-ruin asymmetry baked in** — `-50% → +100%`, `-80% → +400%`, with
  the recovery formula on the table.
- **Red-flag scan** — Sharpe > 3, single-name > 15%, MDD < 5% over 6+ months
  (hidden tail), parametric-normal VaR on fat tails, no drawdown duration.

### Risk-adjusted return cheat-sheet

| Metric | Formula | Best for |
|---|---|---|
| **Sharpe** | `(R − R_f) / σ` | Roughly symmetric returns; broad comparability |
| **Sortino** | `(R − MAR) / σ_d` | Asymmetric payoffs (options, trend following) |
| **Calmar** | `annualised return / |MDD|` | "Can I survive the worst stretch?" |
| **UPI** | `(R − R_f) / UI` | "Did I sleep at night?" — penalises underwater **time** |
| **Information Ratio** | `active return / tracking error` | Benchmark-relative strategies |

*Pick the metric that matches the strategy's payoff shape — never quote raw return alone.*

See full worked reports in **[examples/](examples/)**:
- [Single-position sizing](examples/single-position-sizing.md) — long XYZ
  μ=12% σ=35%, full Kelly ≈ 57%, half-Kelly ≈ 29%, single-name cap binds at
  10% → 🟠 OVER-RISK.
- [Multi-asset portfolio review](examples/multi-asset-portfolio-review.md) —
  35% TQQQ / 25% BTC / 20% NVDA / 15% SVXY / 5% cash; top-3 = 80%, embedded 3×
  leverage, short-vol tail, reverse stress fails at SPY -8% → ⛔ LIKELY-RUIN
  PATH.

---

## Not Financial Advice

This skill provides **educational risk-management guidance only** — not
financial, legal, or investment advice, and **not a guarantee of safety**. It
reasons only over the information you provide; without numbers, output is
qualitative. Risk metrics describe **history and assumed distributions**; they
do **not** predict the next regime shift. Markets do things that have never
happened before — **size below your pain threshold**, and consult a qualified
risk or investment professional for live decisions. **Not affiliated with or
endorsed by Anthropic.**

---

## Contact — Viprasol Tech Private Limited
- 🌐 Website: [viprasol.com](https://viprasol.com)
- ✉️ Email: [support@viprasol.com](mailto:support@viprasol.com)
- 💬 Telegram: [t.me/viprasol_help](https://t.me/viprasol_help) · 📱 WhatsApp: +91 96336 52112
- 🐙 GitHub: [@Viprasol-Tech](https://github.com/Viprasol-Tech) · 💼 [LinkedIn](https://www.linkedin.com/in/viprasol/) · 𝕏 [@viprasol](https://twitter.com/viprasol)

> *Viprasol Tech — fintech software, AI agents, algorithmic trading systems, and B2B SaaS.*

## License
[MIT](LICENSE) © 2025 Viprasol Tech Private Limited
