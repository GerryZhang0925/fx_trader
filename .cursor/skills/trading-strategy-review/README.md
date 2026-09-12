# trading-strategy-review

> An **Agent Skill** that reviews a trading strategy or backtest for the failure modes that make it look great on a chart and lose money live — and outputs **severity-rated findings with fixes.**

[![GitHub stars](https://img.shields.io/github/stars/Viprasol-Tech/trading-strategy-review?style=social)](https://github.com/Viprasol-Tech/trading-strategy-review/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-Compatible-7C3AED)](#works-with)
[![Backtest Pitfalls](https://img.shields.io/badge/Backtest%20Pitfalls-16%2B-green)](skill.md)
[![Version](https://img.shields.io/badge/version-1.0.0-blue)](CHANGELOG.md)

**Works with:** Claude Code · Codex · Cursor · Copilot · Gemini CLI · and 26+ agent tools that read portable Agent Skills.

---

## Quick Install

Clone the skill into your agent's skills directory:

```bash
# Claude Code
git clone https://github.com/Viprasol-Tech/trading-strategy-review \
  ~/.claude/skills/trading-strategy-review

# Cursor / Codex / other agents — clone anywhere on your skills path, e.g.
git clone https://github.com/Viprasol-Tech/trading-strategy-review \
  ~/.config/agent-skills/trading-strategy-review
```

The whole skill is plain markdown — there's nothing to build or install. Your agent picks it
up from `skill.md`.

## Try It

Once installed, just ask your agent:

```
Review my moving-average crossover backtest for look-ahead bias and overfitting.
```

or paste a strategy / metrics table / Pine script and say:

```
Pre-deployment risk-check this strategy before I put real money on it.
```

The agent returns a findings table, per-finding fixes, a metrics sanity check, and a verdict.

---

## Why This Exists

Almost every strategy that "works perfectly in backtest" fails for one of a small set of
well-understood reasons. The backtest-overfitting research of **Bailey & López de Prado**
(*Probability of Backtest Overfitting*, *Deflated Sharpe Ratio*, *The Seven Sins of
Quantitative Investing*) showed the uncomfortable truth: **if you try enough strategy
configurations, a spectacular in-sample backtest is the expected result even with zero real
edge.** Look-ahead bias, survivorship bias, frictionless fills, and risk-of-ruin sizing do
the rest.

This skill encodes that methodology into a repeatable review so an agent can vet a strategy
the way a careful quant would — and tell you which problems actually block deployment.

## What It Does

1. **Scopes** the strategy (asset class, timeframe, parameters, trials, costs, leverage).
2. **Scans** for 16+ failure modes — each with how to detect it in code/results and a fix.
3. **Rates** every finding **Critical → Info** so you know what blocks deployment.
4. **Sanity-checks** the headline metrics (Sharpe, Sortino, max drawdown, Deflated Sharpe,
   PBO, trade count, exposure, break-even cost).
5. **Outputs** a findings table, per-finding fixes with before/after code, and an honest
   verdict — plus a clear **not-financial-advice** disclaimer.

## Features

- **Severity model** — a Critical/High/Medium/Low/Info table; one Critical means *do not
  deploy until fixed.*
- **Failure-mode checklist** — look-ahead, survivorship, overfitting, multiple testing,
  unrealistic fills, slippage/commission, market impact, regime dependence, no OOS/walk-forward,
  position sizing & risk-of-ruin, leverage & path dependence, funding/borrow, timezone/session
  bugs, repainting (Pine), curve-fit stops/targets, too-few-trades.
- **Metrics sanity check** — recomputes and critiques the reported numbers, grounded in
  PBO and the Deflated Sharpe Ratio.
- **Red-flag quick scan** — instant danger signs with example thresholds:

| Red flag | Rough threshold | Likely cause |
|---|---|---|
| Sharpe too high for the timeframe | > 3 on daily (> ~2 retail) | Look-ahead / no costs / overfit |
| Equity curve too smooth | near-straight, tiny drawdowns | Look-ahead / in-sample fitting |
| Too few trades | < 30 (often < 100) | Not statistically significant |
| Win rate implausibly high | ~100%, no losing streak | Look-ahead / curve-fit exits |
| No transaction costs | cost term = 0 | Overstated net edge |
| Future-referencing signal | `shift(-n)`, `close[future]`, `lookahead_on` | Look-ahead / repainting |

See the full methodology in **[skill.md](skill.md)** and worked reports in **[examples/](examples/)**.

### Examples

- **[examples/ma-crossover-review.md](examples/ma-crossover-review.md)** — a Python MA-crossover
  backtest with look-ahead, no costs, and overfit parameters.
- **[examples/pine-rsi-review.md](examples/pine-rsi-review.md)** — a TradingView Pine RSI
  strategy with a repainting HTF signal and curve-fit levels.

---

## Pairs well with

- **[bar-by-bar](https://github.com/Viprasol-Tech/bar-by-bar)** — agentic backtester with a
  built-in look-ahead guard that *enforces* the fixes this skill recommends.
- **[edgehunt](https://github.com/Viprasol-Tech/edgehunt)** — prediction-market edge/arbitrage
  engine for checking whether a measured edge survives realistic costs.

> **Not financial advice.** This skill provides an educational, methodological review of a
> strategy or backtest. It is **not** investment advice, not a recommendation to trade, and not
> a guarantee of any outcome. Past backtest performance — even after every fix — does **not**
> guarantee live results. All trading carries risk of loss; you are solely responsible for your
> own decisions. This project is not affiliated with or endorsed by Anthropic, TradingView, or
> any exchange.

---

## Contact — Viprasol Tech Private Limited
- 🌐 Website: [viprasol.com](https://viprasol.com)
- ✉️ Email: [support@viprasol.com](mailto:support@viprasol.com)
- 💬 Telegram: [t.me/viprasol_help](https://t.me/viprasol_help) · 📱 WhatsApp: +91 96336 52112
- 🐙 GitHub: [@Viprasol-Tech](https://github.com/Viprasol-Tech) · 💼 [LinkedIn](https://www.linkedin.com/in/viprasol/) · 𝕏 [@viprasol](https://twitter.com/viprasol)

> *Viprasol Tech — fintech software, AI agents, algorithmic trading systems, and B2B SaaS.*

## License
[MIT](LICENSE) © 2025 Viprasol Tech Private Limited
