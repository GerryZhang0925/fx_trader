---
name: fx-research-protocol
description: >-
  Two modes: explore a new core freely, or improve a frozen core under
  lockbox/add-on rules. Use when proposing a new core, overlay, satellite,
  DL/hybrid features, grid, walk-forward, or "improve PF".
---

# FX research protocol (this kit)

> Educational method — not financial advice. Past backtests do not guarantee live results.

Pick a mode first. **Do not apply frozen-core gates to a new core.**

| Mode | When | What the skill may constrain |
|---|---|---|
| **Explore** | New core, new family, hybrid/DL, new TF/pair, revival of a dropped idea as its own core | Honesty of fills/costs/look-ahead. Not the live Donchian scoreboard. |
| **Frozen improve** | That core's trigger, TF, pairs, stop/exit family, and risk% are already locked | One-shot lockbox, no post-look tweak, add-on vs **that** book, F1–F3 for Donchian |

Default when the user is "looking for another core": **Explore**. Frozen improve starts only after they freeze that core's fundamentals (README spec + YAML/JSON pin).

## Live Donchian (both modes)

Do not rewrite live JSON or 5% risk to "make room" for research. Default live core stays `donchian`. New cores: `strategy/cores/<name>/`, catalog, YAML **false** until adopted.

## Explore (new core)

The live H4 3-pair (PF 1.45, DD 12.48%) is **one frozen book**, not a ceiling. Do not refuse an idea because it might not raise that book's yearly return, because an overlay already DROPped vs that book, or because the family is "the same indicators."

Allowed: RSI/ATR/Donchian features + linear or DL; H1/M15; EURUSD/AUD/NZD; grids; several candidates. Past DROP rows are **prior measurements**, not a ban.

Measure honestly (not a creativity cap):

- Closed-bar signal, next-bar fill, documented spread/slip. No look-ahead (no full-series scaler, no same-bar fill).
- Name matches the rule. Use `strategy.common.indicators` and `account.engine`; do not copy TV/talib skeletons.
- Score **standalone** PF, trades, DD, yearly. Do **not** require beating the Donchian book or passing the add-on gate. Do **not** DROP the whole family because one lockbox PF < 1.
- Splits are for reporting, not a veto: say which window was train vs held out. 2021–2025 was used for Donchian selection, so a pass there is weaker evidence — still report it; do not refuse to run.
- Arithmetic: do not invent avg R. Measure it. Donchian's ~0.05–0.07 R is that core, not a law for every core.

When the user **freezes** this core (spec in README, params pinned, "this is the rule"), switch to Frozen improve. Until then, iterate.

## Frozen improve (locked core only)

Applies to overlays, exits, filters, and sizing on **that** pinned spec — including live Donchian.

1. Write the delta spec before code. One change at a time. Do not retune the frozen lengths/trail/ADX to chase the delta.
2. Train window: look at mechanics only. One lockbox shot. After seeing it, do not add RSI length / ADX / trail / 0.5% / M15 of the **same** rule.
3. Choosing the next spec to "fix" lockbox failure modes is F1-adjacent. Prefer a new Explore core, not a tighter loser.
4. **Add-on gate** only here: independent daily PnL of the frozen book vs book + delta sleeve. DROP the delta if combined yearly/CAGR/max DD worsen, combined DD > the book's cap (live Donchian: 15%), or daily PnL corr ≥ 0.7. Standalone PF of the overlay is not adoption onto a frozen book.
5. Live Donchian extras (do not export these to Explore):
   - Do not size from IS Sharpe after the 792-cell search; new **Donchian pair** grids use `--compact`.
   - Do not put test return in the USDJPY objective; keep the live pin; no 2026 holdout bake-off of the pin.
   - Failed **Donchian overlays** stay failed as Donchian overlays (EURUSD H4 Donchian as 4th pair, H1 RSI fade as Donchian satellite, false-break as Donchian satellite, H1 Donchian/HalfTrend stack on the same USD book, GBPUSD on two Donchian cores, Pine as source of truth). They may be restarted as Explore cores with their own spec.

## Code layout

`strategy/cores/<name>/` with `strategy.py` (`prepare` → `signal` / `stop_dist`), README, `backtest/eval.py`. Register in `catalog.py`, YAML default **false**.

Eval: `python -m strategy.cores.<name>.backtest.eval` with `PYTHONPATH=app`.
