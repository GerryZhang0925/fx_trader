---
name: fx-research-protocol
description: >-
  Freeze one FX research hypothesis, measure train then a single lockbox,
  and apply the add-on gate versus the live H4 Donchian book. Use when
  proposing a new core, overlay, M15/H1 satellite, EURUSD specialization,
  grid search, walk-forward, or "improve PF" request.
---

# FX research protocol (this kit)

New ideas do not raise live returns by default. Most overlays already failed the
book gate. This skill prevents repeating F1 (using 2021–2025 as a selection filter).

> Educational method — not financial advice. Past backtests do not guarantee live results.

## Live engine (do not touch while researching)

- H4 Donchian 3-pair book: USDCAD / USDJPY / GBPUSD
- Per-pair JSON params stay frozen. Risk 5% per pair stays frozen.
- Live default core remains `donchian`. Research cores stay `cores.<name>: false`.

## One hypothesis at a time

1. Write the full spec **before** code: instrument, TF, regime, closed-bar trigger, stop, exit, session, cost, risk.
2. Name and rule must match (no "divergence" that is actually RSI 30/70).
3. Do not run A and B in parallel. Do not start at M15 if H1 CSV already exists.
4. Do not copy TradingView / talib skeletons. Use `strategy.common.indicators`, next-bar engine, DST overlap helper.

## Splits

| Split | Use |
|---|---|
| Index < 2021-01-01 | Look at mechanics, trade count, train PF. Do **not** hunt avg R ≈ 0.05. |
| 2021-01-01 ≤ t < 2026-01-01 | **Lockbox, one shot.** Report PF. Do not require PF ≥ 1.2. If PF < 1, **DROP**. |
| After seeing lockbox | No RSI length, ADX, trail, 0.5% risk, or M15 of the same rule. |

Choosing the *next* spec to "fix" lockbox failure modes (e.g. add pivots because WR was 22%) is F1-adjacent. Prefer a **different trigger family**, not a tighter version of the loser.

2021–2025 was already used for Donchian pair picks **and** EURUSD satellites. A pass on that window is weak evidence, not a size-up.

## Add-on gate (required if lockbox PF ≥ 1)

Same engine, independent daily PnL paths:

- H4 3-pair at 5% vs H4 3-pair + satellite at **1%**, one position.
- **DROP** if combined yearly return, CAGR, or max DD worse than H4-only, or combined DD > 15%, or daily PnL corr ≥ 0.7.

Standalone PF / yearly % is not adoption.

## Arithmetic sanity

Do not design `n × risk × avg R = 20%`. Avg R is measured. H4 realized avg R is about 0.05–0.07. Claims of 0.8–1.2 R with hundreds of trades/year are internally false.

## Already closed (do not revive)

- EURUSD H4 Donchian (test PF ~1.01)
- EURUSD H1 RSI 30/70 fade (lockbox PF 1.55 but add-on DD 15.4%)
- EURUSD H1 false-break reject (lockbox PF 0.82)
- H1 Donchian / HalfTrend stack as a second trend book
- GBPUSD on two cores at once
- Pine as source of truth
- Donchian F2: do not size from IS Sharpe after the 792-cell search; new pair grids use `--compact`
- Donchian F3: do not put test return in the USDJPY objective; keep the live pin; do not bake-off on 2026 holdout

## Code layout

`strategy/cores/<name>/` with `strategy.py` (`prepare` → `signal` / `stop_dist`), README freeze, `backtest/eval.py`. Register in `catalog.py`, YAML default **false**.

Eval: `python -m strategy.cores.<name>.backtest.eval` with `PYTHONPATH=app`.
