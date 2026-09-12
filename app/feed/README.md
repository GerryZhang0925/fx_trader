# Feed

Dukascopy H1 download, H4 resample, gap fill. Weekend (Sat/Sun UTC) is skipped.

```bash
python download_data.py --start 2015-01-01 --symbols EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,NZDUSD
```

CSV lives in kit `data/`, not in this folder.

## Config

`config.yaml`: lag, retry, overlap.

## Tests / backtest

Resample and weekend-gap tests only. No PnL.

## Do not

Import strategy or account. No broker.
