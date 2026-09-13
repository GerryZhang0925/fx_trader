---
name: technical-research
description: >-
  Index of technical-analysis and kit research skills for fx_trader. Use when
  proposing indicators, regimes, MTF, satellites, or overlays. Always pair with
  fx-research-protocol and trading-strategy-review.
---

# Technical research (this kit)

Playbooks in `.cursor/skills/` do **not** raise returns by themselves. Pair every
idea with `fx-research-protocol` (freeze → lockbox once → add-on gate).

Do not copy public TradingView scripts. Keep next-bar fills and costs.

## Do this first

| Goal | Skill |
|---|---|
| New core / satellite / "improve PF" | `fx-research-protocol` |
| Spreads, H1 vs M15, DST, Dukascopy | `fx-microstructure` |
| 5% vs 1%, Kelly, concurrent risk | `fx-position-sizing` |
| EURUSD, second TF, USD overlap | `fx-usd-factor` |
| Look-ahead, PBO, DSR | `trading-strategy-review` |
| DD, ruin, book caps | `risk-management-review` |

## Donchian H4 overlays (already mostly DROP)

| Goal | Skill | Note |
|---|---|---|
| Regime / vol | `market-regime-detection` | `not_squeeze` held pair PF, hurt book DD |
| H1 timing | `multi-timeframe-analysis` | H1 side filter was no-op or worse |
| Continuation | `breakout-trading`, `flag-pennant`, `momentum-trading` | RVOL helped PF, hurt DD |
| Pullback alt | `pullback-trading`, `optimal-trade-entry`, `fibonacci-trading` | Test PF often < 1 |
| Range satellite | `range-trading`, `mean-reversion`, `bollinger-bands` | EURUSD H1 RSI fade and false-break **DROP** |
| Structure | `fair-value-gaps`, `liquidity-zones`, `order-blocks` | FVG PF up, book DD up |
| Sessions | `kill-zones` | H4 overlap dropped; use DST helper not fixed UTC |
| Exits | `trailing-stop`, `partial-profit-taking` | 1R 50% + ATR trail beat 2R/3R **on Donchian only** |
| Book | `correlation-risk`, `market-correlation-trading`, `fx-usd-factor` | |

## How to test

1. Same engine, next-bar fill, documented costs. One frozen spec — no grid after looking.
2. Train <2021 for mechanics. Lockbox 2021–2025 **once**. PF < 1 → drop.
3. If lockbox PF ≥ 1, add 1% sleeve to the 5%×3 H4 book. Drop if yearly/CAGR/DD worsen or DD > 15%.
4. Do not size up confluence grades (10-point sheet failed).
