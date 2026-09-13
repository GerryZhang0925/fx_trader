# Strategy cores

採用コアと候補コアは、ここに置く。ライブはいま `donchian/` だけ。研究用の棄てたコアは単一モジュール（`ema_atr.py` など）。採用したらフォルダにする。候補の EURUSD H1 レンジ衛星は `eurusd_h1_range/`（DROP）。ダマシ拒否は `eurusd_h1_breakout_reject/`（既定オフ、グリッドしない）。

新しいコアを足す手順:

1. `cores/<name>/` に `strategy.py`（`name`・`prepare` → `signal` / `stop_dist`）、`__init__.py`、`README.md` を置く。オーバーレイ評価は `cores/<name>/backtest/`。
2. `catalog.py` の `STRATEGIES` に登録する。
3. `config.yaml` の `cores.<name>` を足す（既定は `false`）。
4. 学習 &lt;2021 / 検証 2021–2025、同じエンジン・コストでドンチャン3本ブックと比較する。検証 PF がコア未満、またはブックの年率・CAGR・DD が悪化したら棄てる。

ロットや約定はこの層では扱わない。PnL は `account` が採点する。
