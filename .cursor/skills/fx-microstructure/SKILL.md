---
name: fx-microstructure
description: >-
  FX-specific costs, pips, sessions, and fills for this kit. Use when
  choosing M15/H1/H4, spreads, slippage, Dukascopy BID, DST overlap,
  JPY pips, or next-bar execution.
---

# FX microstructure (this kit)

Spot FX is 24/5, quoted in pips, and cheap only on liquid pairs and higher TFs.
Shorter bars raise round-trip cost as a fraction of 1R.

> Educational — not a broker spec and not financial advice.

## Data in this kit

- Source: Dukascopy **H1 BID**, resampled to H4 (`label/closed=left`). Weekend UTC Sat/Sun skipped.
- M15 needs a separate M5/M15 CSV. Do not resample H1 down.
- Signals on the **closed** bar; `account.engine` fills the **next open** with half-spread + slip.
- Default cost: 1 pip + 0.2 slip. If a short-TF idea passes lockbox, re-run at 1 + 0.4 before adopting.
- Volume is tick volume. RVOL is a weak participation filter here (already failed the H4 book DD gate).

## Pips

| Symbol | pip size |
|---|---|
| Most XXXUSD / USDXXX (not JPY) | 0.0001 |
| USDJPY and JPY crosses | 0.01 |

Stop distance in price → size via `position_units`. Do not mix pip conventions.

## Timeframes

| TF | Cost drag | When to use |
|---|---|---|
| H4 | Lowest vs 1R on this book | Live Donchian engine |
| H1 | Medium | Research satellites; CSV already on disk |
| M15/M5 | Highest | Only if the **same** rule already passed H1 lockbox + add-on |

H4 1 pip is not valid for M15 GBPUSD. EURUSD is the least-bad short-TF pair on spread, not an edge by itself.

## Sessions

Do **not** freeze `13:00–17:00 UTC`. Use `in_london_ny_overlap` (London 08–16 and NY 08–17 **local**, DST via tz database).

Japan evening ≈ London open through NY overlap. "Watch some days" is a **veto list** (news, spread, book already halted), not discretionary entries.

## Fills and exits

- Close-break ≠ wick-break. State which.
- Failed-break: freeze the **broken level** from the break bar; do not expand Donchian to include the break bar then test "back inside".
- Mean-reversion: target mid / time stop. Do not copy Donchian 1R-partial + ATR trail.
- Time stop: `max_hold_bars` on the engine (flatten next open).

## Rollover / swap

This kit does not model swap. Holding over 17:00 NY can dominate a 0.05R H1 edge. If a satellite holds overnight often, say so in the README; do not treat backtest PF as net of carry.
