# Strategy backtest (cross-core)

Donchian の最適化・オーバーレイ評価は `strategy/cores/donchian/backtest/` に移した。

ここにはコア横断のものだけ残す。

| スクリプト | 内容 |
|---|---|
| `eval_alts.py` | ema_atr / engulfing / confluence を 11年 H4 でドンチャンと比較 |
| `walkforward.py` | `--strategy` で任意コアのウォークフォワード |
| `__main__.py` | `python -m strategy.backtest` → 採用ドンチャンの `optimize_pairs` |

```bash
$env:PYTHONPATH="app"
python -m strategy.backtest
python -m strategy.cores.donchian.backtest
python -m strategy.cores.donchian.backtest.eval_regime
python -m strategy.backtest.eval_alts
python -m strategy.backtest.walkforward --csv data/usdcad_h4.csv
```
