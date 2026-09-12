# Signal app

Closed-bar Donchian proposals for USDCAD / USDJPY / GBPUSD.

`run.py` calls **feed → strategy → account → output**. It does not place orders.

```bash
python run.py              # watch H4 closes
python run.py --offline    # CSV only
python run.py --once
python run.py --offline --serve   # also http://127.0.0.1:18080 (status + proposals)
```

## Config

`config.yaml`: pair list, lookback, lag, which outputs. Account risk and strategy lengths live in the child modules.

## Tests / backtest

- `tests/` — pipeline wiring
- `backtest/` — offline end-to-end on synthetic or CSV

## Do not

Talk to a broker, size from this folder (that is `account/`), or fetch prices here (that is `feed/`).
