# Strategy

Price-only analysis. Shared helpers in `common/`. Adopted cores live in `cores/<name>/`. Live default is Donchian. No lots, no fills.

Live: enabled cores in `config.yaml` `cores:` run in parallel (`analyze` → `signal` / `stop_dist`). Pair JSON from kit `params/` applies to Donchian. Dashboard toggles write `reports/cores.json`.

## Layout

| フォルダ | 役割 |
|---|---|
| `common/` | コア横断の価格ヘルパー（indicators / bars / pips / snapshot） |
| `cores/donchian/` | 採用ライブコア。ルール・試した手法・ドロップ理由は README。最適化とオーバーレイ評価は `cores/donchian/backtest/` |
| `cores/ema_atr.py` ほか | 研究用コア。11年 H4 でもドンチャンに劣る |
| `backtest/` | コア横断（`eval_alts` / `walkforward`） |
| `catalog.py` | コア登録と YAML からの構築 |

新しいコアは `cores/` にフォルダを足す（手順は `cores/README.md`）。

## Config

`config.yaml`: Donchian and research defaults. USDJPY pinned JSON is not overwritten without `--force`. New pair grids: `--compact` (90 cells). Selection sorts train PF only; test PF is a floor.

## Tests / backtest

- ドンチャン: `python -m strategy.cores.donchian.backtest`（`python -m strategy.backtest` も同じ optimize_pairs）
- コア横断: `backtest/eval_alts.py`、`backtest/walkforward.py`
- PnL 採点だけ `account` を呼ぶ

## Do not

Size positions, pick lots, or print to Telegram. Stacking (ignore same-direction / reverse opposite) is declared on the core spec; `account.intent` executes it.
