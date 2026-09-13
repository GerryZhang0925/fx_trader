---
name: technical-research
description: >-
  Index of technical-analysis and kit research skills for fx_trader. Use when
  proposing indicators, regimes, MTF, satellites, overlays, or a new core.
  Pair with fx-research-protocol (Explore vs Frozen improve).
---

# Technical research (this kit)

Playbooks in `.cursor/skills/` do **not** raise returns by themselves. Pair with
`fx-research-protocol`: **Explore** for a new core; **Frozen improve** only after
that core's fundamentals are pinned.

Do not copy public TradingView scripts. Keep next-bar fills and costs.

## Do this first

| Goal | Skill |
|---|---|
| New core / hybrid / DL / "find another engine" | `fx-research-protocol` **Explore** |
| Overlay or PF tweak on a **pinned** core | `fx-research-protocol` **Frozen improve** |
| Spreads, H1 vs M15, DST, Dukascopy | `fx-microstructure` |
| Risk % / Kelly / concurrent book | `fx-position-sizing` |
| USD overlap, pair map | `fx-usd-factor` |
| Look-ahead, PBO, DSR | `trading-strategy-review` |
| DD, ruin | `risk-management-review` |

## Indicator skills (Explore: allowed)

Use these to **build** a new core. Do not refuse RSI, ATR, Donchian features, range,
MTF, or structure because they failed as **Donchian overlays**.

| Topic | Skill |
|---|---|
| Regime / vol | `market-regime-detection` |
| H1 / MTF | `multi-timeframe-analysis` |
| Continuation | `breakout-trading`, `flag-pennant`, `momentum-trading` |
| Pullback | `pullback-trading`, `optimal-trade-entry`, `fibonacci-trading` |
| Range / MR | `range-trading`, `mean-reversion`, `bollinger-bands` |
| Structure | `fair-value-gaps`, `liquidity-zones`, `order-blocks` |
| Sessions | `kill-zones` (DST helper, not fixed UTC) |
| Exits | `trailing-stop`, `partial-profit-taking` |
| Book / USD | `correlation-risk`, `market-correlation-trading`, `fx-usd-factor` |

## Donchian H4 overlays (Frozen improve only)

History vs the **pinned** H4 3-pair. Do not use this table to block a new core.

| Experiment | Note as Donchian overlay |
|---|---|
| `not_squeeze` | Pair PF held, book DD worse |
| H1 side filter | No-op or worse |
| RVOL continuation | PF up, book DD worse |
| Pullback alt | Test PF often < 1 |
| EURUSD H1 RSI fade / false-break | Failed as satellites on this book |
| FVG | PF up, book DD up |
| H4 kill-zone overlap | Dropped |
| 1R 50% + ATR trail | Beat 2R/3R **on Donchian only** |
| 10-point confluence size | Failed on Donchian |

## How to test

**Explore:** next-bar + costs; standalone metrics; iterate until the user freezes the spec.

**Frozen improve:** one frozen delta; train mechanics then one lockbox; add-on vs **that** book (live Donchian: 1% sleeve, DD 15%, no worse yearly/CAGR/DD).
