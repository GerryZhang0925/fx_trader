# Signal app

Closed-bar Donchian proposals for USDCAD / USDJPY / GBPUSD.

`run.py` calls **feed → strategy → account → output**. It does not place orders.

```bash
python run_signals.py              # watch H4 closes
python run_signals.py --offline    # CSV only
python run_signals.py --once
python run_signals.py --offline --serve   # also http://127.0.0.1:8765
```

## Config

`config.yaml`: pair list, lookback, lag, which outputs. Account risk and strategy lengths live in the child modules.

## Tests / backtest

- `tests/` — pipeline wiring
- `backtest/` — offline end-to-end on synthetic or CSV

## Do not

Talk to a broker, size from this folder (that is `account/`), or fetch prices here (that is `feed/`).
