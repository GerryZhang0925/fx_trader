# Strategy

Price-only analysis. Donchian (adopted) plus research strategies. No lots, no fills.

Live: `analyze(symbol, h4)` → `signal` / `stop_dist` / `reason`. Pair JSON from kit `params/`.

## Config

`config.yaml`: Donchian and research defaults. USDJPY pinned JSON is not overwritten without `--force`.

## Tests / backtest

`backtest/`: `optimize_pairs.py`, `walkforward.py`, eval scripts. PnL scoring calls `account` from those CLIs only.

## Do not

Size positions or print to Telegram.
