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

## Frozen live book

- 5.0% equity risk **per pair** on USDCAD, USDJPY, GBPUSD.
- `portfolio_max_dd: 15`. Fourth pair at 5% already pushed DD ~16.6% and was dropped.
- Config `half_kelly_pct` / `quarter_kelly_pct` are **not** a license to size up the 11y 21% figure (that mix is train+test).

## Satellites

| Rule | Value |
|---|---|
| Risk per satellite trade | 1.0% (cap 1.5%) |
| Concurrent satellite positions | 1 |
| Do not cut H4 5% to "make room" | H4 is the return engine |
| After lockbox | Do not retry at 0.5% to sneak under DD 15% |

2% + 3% + 5% "equal risk cores" stacks open risk past the DD cap. Vol targeting does not replace a hard simultaneous-risk limit.

## Concurrent and stress

- Sum open risk across cores and pairs. USD shock: assume ρ → 1 on USD legs.
- Add-on eval: independent paths, daily PnL sum, combined DD ≤ 15% **and** not worse than H4-only.
- Daily halt (`max_trades_per_day`, 3 losses, −2R) applies per engine run. Shared book halt is not fully modeled — treat it as extra live conservatism.

## Kelly

Full Kelly overstates because μ/σ are estimated and non-stationary. If used at all: quarter to half Kelly, then the **min** of that and the 5%/1% caps. Never size from in-sample Sharpe after 792-cell search (Donchian F2).

## Arithmetic check

`trades/year × risk × avg R` must match claimed yearly return order-of-magnitude. H4: ~86 trades/year × 5% × ~0.06 R ≈ 20% ballpark. Thousands of trades × 2% × 0.8 R cannot be 20%.
