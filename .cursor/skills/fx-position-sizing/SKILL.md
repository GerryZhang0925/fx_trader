---
name: fx-position-sizing
description: >-
  Position and book sizing for fx_trader. Use when setting risk %, adding a
  satellite, Kelly/half-Kelly, concurrent exposure, or cutting H4 to fund
  a new core.
---

# FX position sizing (this kit)

Sizing is a risk cap, not a way to manufacture 20% annual return.

> Educational — not financial advice. Size below the pain threshold.

Modes follow `fx-research-protocol`. Explore may pick any research risk%. Frozen
improve vs live Donchian does not cut the 5% book to fund an overlay.

## Frozen live Donchian (do not change while researching)

- 5.0% equity risk **per pair** on USDCAD, USDJPY, GBPUSD.
- `portfolio_max_dd: 15`. Fourth Donchian pair at 5% pushed DD ~16.6% (history for this book).
- Config `half_kelly_pct` / `quarter_kelly_pct` are **not** a license to size up the 11y 21% figure (train+test mix).

## Explore (new core)

Standalone backtests may use 1%, 2%, 5%, or another stated risk. Do not refuse a
core because 1% would not lift the Donchian yearly number. State risk in the README.
When/if the core is frozen and combined with live Donchian, then use Frozen improve caps.

## Frozen improve — satellites on a pinned book

| Rule | Value (live Donchian) |
|---|---|
| Risk per satellite trade | 1.0% (cap 1.5%) |
| Concurrent satellite positions | 1 |
| Do not cut H4 5% to "make room" | Live book stays 5% |
| After lockbox | Do not retry at 0.5% to sneak under DD 15% |

2% + 3% + 5% "equal risk cores" on the **same** pinned book stacks open risk. Vol targeting does not replace a hard simultaneous-risk limit.

## Concurrent and stress

- Sum open risk across cores and pairs. USD shock: assume ρ → 1 on USD legs.
- Frozen improve add-on: independent paths, daily PnL sum, combined DD ≤ 15% **and** not worse than the pinned book alone.
- Daily halt (`max_trades_per_day`, 3 losses, −2R) applies per engine run. Shared book halt is not fully modeled.

## Kelly

Full Kelly overstates because μ/σ are estimated and non-stationary. If used at all: quarter to half Kelly, then the **min** of that and the stated caps. Never size live Donchian from in-sample Sharpe after the 792-cell search (F2).

## Arithmetic check

`trades/year × risk × avg R` must match claimed yearly return order-of-magnitude. Live H4 Donchian: ~86 trades/year × 5% × ~0.06 R ≈ 20% ballpark. Invented 0.8 R on hundreds of H4 trades/year is internally false **for that core**. Measure avg R on the core under test.
