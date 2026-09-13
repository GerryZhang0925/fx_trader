# Account

Equity, spread, daily halt, next-bar research PnL — and the **book** (venue accounts + sleeves).
`run.py` still does not place orders.

Live overlay: `propose(snapshot, cfg)` adds size and book ids. Research PnL: `python -m account.backtest`.

Adopted risk: **5.0% per pair** on USDCAD / USDJPY / GBPUSD (sleeve `donchian_h4`).

> Educational method — not financial advice. Not a broker spec.

## Layers (inside this module)

Pipeline stays **feed → strategy → account → output**. Account is one module with three jobs. Do not add a fifth top-level broker app.

| 層 | 役割 | コード | いまやること |
|---|---|---|---|
| 研究 PnL | 確定バーで判断、次バー始値＋半スプレッド＋0.2 slip。サイズは従来どおり `units = risk / stop_dist` | `engine.py` `risk.py` `metrics.py` `backtest/` | **採点式は凍らせる**（採用レポートと一致させる） |
| ブック | 会場口座・スリーブ・スタッキング・証拠金通貨・ロット刻み | `books.py` `money.py` `intent.py` | 提案に id を載せる。コネクタはまだ呼ばない |
| 会場アダプタ | デモ／リアルの参照と発注 | `venues/oanda.py`（Practice は **GET のみ**） | `run.py` からは呼ばない。`python -m account.venues` で接続テスト |

## 会場口座とスリーブ

- **種別** `paper` / `demo` / `live` … 約定の現実度。ペーパーもシグナル値での即建てではなく、研究エンジンと同じ次バー。
- **コネクタ** … ツール（MT5 等）。デモはツールごとに口座が1つになりやすい。リアルは複数社があり得る。
- **会場口座** … そのコネクタ上の1ログイン。証拠金通貨（USD デモと JPY リアルなど）、ロット、倍率はここ。
- **スリーブ** … 会場口座の中の資金切り分け。コネクタをまたがない。採用ドンチャンは `donchian_h4`。

複数会場の合成 DD は、一方の通貨に換算してから合算する。デモ 10 万ドルとリアル 1,000 万円の 5% を生で足さない。

## ストラテジーとの境界

ストラテジーは `signal` / `stop_dist` とスタッキング方針だけ。ロット・刻み・レバ・口座通貨は読まない。

採用ドンチャンの方針（`intent.desired_action` / エンジンと一致）:

- スリーブ×ペアあたり1本
- 同方向の再シグナルは **ignore**
- 逆方向は次バーで閉じてから逆建て **reverse**

口座はこれをチケットへ翻訳する（ネット口座はネットがひっくり返る、ヘッジ口座は枚数が増え得る）。別スリーブが同じペアを持つのはストラテジーの「足す」ではなくブックが拒否する（GBP 二コア禁止と同じ）。

`money.units_for_risk` は証拠金通貨への正しい換算（USDJPY の損益は円、など）。**研究エンジンはまだこれを使わない。** 採用 11 年の数字を変えないため。会場パスを足すときに使う。

## デモでタイミングを確認する

これから先の H4 について、エンジンの `entry_time`（次バー始値）とデモのチケット時刻を突合する。業者テスターで 2015–2026 を流して PF 1.45 を再現することは目標にしない。

拒否リスト（指標・スプレッド・ブック停止）は会場口座の `halted`。新エントリーは作らない。Telegram は通知だけ。

## OANDA fxTrade Practice

デモ会場 `oanda_practice`（`kind: demo`, `connector: oanda_practice`）。ホストは `https://api-fxpractice.oanda.com` のみ。発注エンドポイントは実装していない。

```bash
export OANDA_API_TOKEN="..."          # practice portal の Personal Access Token
export OANDA_ACCOUNT_ID="..."         # 口座が複数あるとき
export PYTHONPATH=app
python -m account.venues              # 残高・建玉の GET。注文しない
```

トークンは環境変数だけ。YAML に書かない。採用ドンチャンのスリーブは `paper_research` のまま。Practice で 11 年バックテストはしない。

## Config

`config.yaml`: `initial_equity`, `cost`, `risk`, `portfolio`, `venues`, `sleeves`.

## Tests / backtest

PnL backtests stay in `backtest/`. Book/currency/stacking tests in `tests/`. Checklist targets are not guarantees.

## Do not

Download prices or send messages. No broker from `run.py`. Do not size the adopted book from IS Sharpe. Do not round lots **up** past intended risk.
