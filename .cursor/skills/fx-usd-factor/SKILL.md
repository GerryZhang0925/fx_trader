---
name: fx-usd-factor
description: >-
  FX USD-factor map for this kit. Use when adding pairs, a second timeframe,
  EURUSD/GBPUSD overlap, or claiming MTF diversification. Explore cores may
  use any pair; Frozen improve vs live Donchian keeps the live three.
---

# FX USD factor (this kit)

Most majors are one dollar bet with a second currency. Timeframe stacking does
not diversify if the payoff is still USD trend-following.

> Educational — not financial advice.

## USD map (signs flip with quote)

| Position | Rough USD |
|---|---|
| Long USDJPY / USDCAD / USDCHF | Long USD |
| Long EURUSD / GBPUSD / AUDUSD | Short USD |
| Short EURUSD after an upside break | Long USD |

Report this map for a new core. Do not refuse EURUSD, AUD, NZD, or H1 because they
are "the same USD" — say so in the README and measure standalone (Explore) or
combined (Frozen improve).

## Live Donchian book (Frozen improve)

USDCAD / USDJPY / GBPUSD were kept for **strategy** correlation under 0.7.

Prior Donchian pair search (not an Explore ban): EURUSD H4 test PF ~1.01; AUDUSD no
test PF ≥ 1.2 cell; NZDUSD test PF ~1.06 and AUD price corr; USDCHF book DD cap.

On **this** pinned book only:

- Do not put GBPUSD on H4 Donchian **and** a Donchian H1/M15 satellite.
- Do not call HalfTrend + Donchian "two factors" as overlays on the same USD book.
- Do not add M15+H1+H4 expected returns as if independent. Blend correlated streams.

Gates for Frozen improve on this book: `max_corr: 0.7` on **strategy daily returns**;
rolling corr and a ρ → 1 stress. Add-on: H4 3-pair vs H4 + new sleeve; DROP the
sleeve if yearly/CAGR/DD worsen or DD > 15%.

## Explore

A new core may trade any pair/TF. Score it standalone. USD overlap is a risk
comment, not a stop-work rule.
