---
name: technical-research
description: >-
  Index of technical-analysis and ICT skills for fx_trader. Use when trying
  to raise Donchian/H4 FX returns with indicators, regimes, MTF, FVG, or
  pattern overlays. Always pair with trading-strategy-review and train/test splits.
---

# Technical research (this kit)

Skills in `.cursor/skills/` are reference playbooks. They do **not** guarantee higher
returns. Test every overlay on train `<2021` / test `2021–2025` before changing defaults.

Do not copy public TradingView scripts. Keep next-bar fills and costs. Prefer overlays
that keep trade count unless the user allows fewer trades.

## Try first on this Donchian book

| Goal | Skill | Why it fits |
|---|---|---|
| Trade only when trend/vol agrees | `market-regime-detection` | Uses Donchian, ATR, BB width — same family as the core |
| H4 bias, H1/M15 timing | `multi-timeframe-analysis` | H1 CSVs exist; M5 does not |
| Breakout continuation | `breakout-trading`, `flag-pennant`, `momentum-trading` | Core is Donchian breakout |
| Pullback instead of breakout | `pullback-trading`, `optimal-trade-entry`, `fibonacci-trading` | Different entry; do not mix blindly with breakout scores |
| Range satellite | `range-trading`, `mean-reversion`, `bollinger-bands` | Prior engulfing satellite had almost no edge |
| Structure extras | `fair-value-gaps`, `liquidity-zones`, `order-blocks`, `market-structure-shift` | Original simplified versions already in Python |
| Sessions | `kill-zones` | Score on H4 overlap only unless M5 is downloaded |
| Exits | `trailing-stop`, `partial-profit-taking`, `risk-reward-ratio` | Baseline 1R+ATR trail already won vs 2R/3R |
| Book construction | `correlation-risk`, `market-correlation-trading` | CAD/JPY/GBP were chosen for low strategy corr |
| Honesty check | `trading-strategy-review` | Look-ahead, overfit, costs, too few trades |

## How to test

1. Same engine (`engine.py`), same costs, per-pair JSON params.
2. Report train PF, test PF, trades, daily Sharpe, Calmar, max DD.
3. Reject if test PF < 1.0 or if the overlay only helps in-sample.
4. Do not size up A+ confluence scores unless grade-level avg R is higher (prior 10-point sheet failed).
