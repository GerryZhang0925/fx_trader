# Account

Equity, spread, slippage, daily halt → estimated fill and size. Next-bar engine for research PnL.

Live: `propose(snapshot, cfg)` adds lots. Backtest: `python -m account.backtest`.

Adopted risk: **5.0% per pair** on USDCAD / USDJPY / GBPUSD.

## Config

`config.yaml`: `initial_equity`, `cost`, `risk`, `portfolio.risk_pct_per_pair`.

## Tests / backtest

PnL backtests live here. Checklist targets are not guarantees.

## Do not

Download prices or send messages. No broker.
