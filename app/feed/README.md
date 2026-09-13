# Feed

Dukascopy H1 download, H4 resample, gap fill. Weekend (Sat/Sun UTC) is skipped.

```bash
python -m feed.download --start 2015-01-01
# 既定は検討比較した7本（採用 USDCAD / USDJPY / GBPUSD に加え EURUSD / AUDUSD / NZDUSD / USDCHF）。
# 1本だけなら --symbol USDCAD
```

CSV lives in kit `data/`, not in this folder.

## Config

`config.yaml`: lag, retry, overlap.

## Tests / backtest

Resample and weekend-gap tests only. No PnL.

## Do not

Import strategy or account. No broker.
