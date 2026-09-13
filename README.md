# FX Trader（研究用シグナル）

H4 の確定バーで動く FX 研究キットです。戦略コアは並列に回せます。いまの採用ライブブックはドンチャンです。TradingView 用 Pine と、同じエンジンの Python バックテストが入っています。

**これは売買助言ではありません。** 下記の成績は 2015–2026 の Dukascopy H4 バックテスト（チェックリスト）であり、将来のリターンや DD を保証しません。公開インジケータ（INTELA、Kill Zone Sniper 等）のコピーではありません。

## 採用手法

**ペア別パラメータの H4 ドンチャンブレイク**を、USDCAD / USDJPY / GBPUSD の固定ブックとして同時に回す。

ルール（全ペア共通）:

- 前日窓のドンチャン上限／下限ブレイク＋200EMA 方向フィルタ＋ADX フィルタ
- スイング損切り（ATR 0.5 バッファ）
- 1R で 50% 利確、残りはエントリー直後から ATR トレイル
- 逆方向ブレイクで反転クローズ
- 1 トレードあたり資金の **5.0%** リスク
- 1 日最大 2 トレード。連続 3 負け、またはその日 −2R で当日停止
- 約定はシグナル確定バーの **次バー始値**。スプレッド 1 pip ＋スリッページ 0.2 pip

ペア別パラメータ:

| ペア | Donchian | ATR トレイル | ADX 最小 | ATR 中央値フィルタ |
|---|---|---|---|---|
| USDCAD | 55 | 3.0 | 22 | オン |
| USDJPY | 25 | 1.5 | 15 | オフ |
| GBPUSD | 60 | 3.0 | 24 | オン |

USDJPY のライブ JSON は学習＋検証リターン最大かつ検証 PF ≥ 1.2 で選んだセットを pin したまま（`params/usdjpy_donchian.json` は `pinned: true`）。F3 以降の最適化は学習期 PF のみ（検証 PF は下限）。`--force` なしでは上書きしない。

採用しないもの: 2R/3R 固定利確、BE、遅延トレール、測度ターゲット、10 点コンフィデンスによるロット調整、エンガルフィング衛星、Kill Zone でドンチャンを間引く。いずれも同一エンジンでバックテストし、コア収益または PF が悪化した。

## 実装箇所

| 役割 | 場所 |
|---|---|
| 採用ブックの候補・リスク | `app/account/config.yaml` → `portfolio.candidates` / `risk_pct_per_pair: 5.0` / `fixed_book: true` |
| ペア別パラメータ | `params/usdcad_donchian.json`, `params/usdjpy_donchian.json`, `params/gbpusd_donchian.json` |
| 採用コア（ドンチャン） | `app/strategy/cores/donchian/`（試した手法とドロップ理由も README） |
| 共通ヘルパー | `app/strategy/common/` |
| シグナル（発注なし） | `app/run.py`。`cores:` が true のコアを並列実行 |
| コア ON/OFF | `app/strategy/config.yaml` の `cores:`。ダッシュボードは `reports/cores.json` |
| H4 追記・ギャップ埋め | `app/feed/live.py` |
| 次バー約定・部分利確・ATR トレイル・サイズ提案 | `app/account/engine.py` / `propose.py`（研究採点は凍結） |
| 会場口座・スリーブ・証拠金通貨 | `app/account/books.py` / `money.py` / `intent.py`。説明は `app/account/README.md` |
| 日次停止・サイズ | `app/account/risk.py` |
| コンソール / Telegram / ローカル HTML | `app/output/` |
| 3 通貨合成バックテスト | `app/account/backtest/run_portfolio.py`（`python -m account.backtest`） |
| TradingView（単体。合成ブックではない） | `pine/01_donchian_h4.pine` |
| 直近の合成レポート | `reports/portfolio.md` / `reports/portfolio.json` |

`02`〜`05` の Pine と `engulfing` / `killzone` / `ema_atr` / `confluence` 戦略は比較・研究用で、採用ブックには含まれない。

## 対象通貨ペア

採用: **USDCAD, USDJPY, GBPUSD**（`portfolio.candidates`）。検証 PF がおおむね 1.2 以上で、戦略 PnL の相関も低い。

## 採用しない通貨ペア

探索対象は EURUSD / GBPUSD / USDJPY / AUDUSD / USDCAD / NZDUSD / USDCHF。次の 4 本はブックに入れない。

| ペア | 理由 |
|---|---|
| EURUSD | 学習 PF 1.55 に対し検証 PF **1.01**。OOS でエッジが消えた。単体 4% でも年率はチェックリストの 10–20% に届かず、リスクを上げると DD が 20% を超える。 |
| AUDUSD | 学習 PF 1.09、検証 PF **1.07**。トレードも少なく、Donchian に乗らない。 |
| NZDUSD | 学習 PF 2.12 だが検証 PF **1.06**。インサンプル偏り。 |
| USDCHF | 学習 PF 最大だと検証 PF 1.08。USDJPY と同じ「検証 PF≥1.2 のうち学習+検証リターン最大」では検証 PF **1.36**（length 35 / ATR 1.5 / ADX 20 / ATR フィルタ）。採用3本に 5.5% で足すと合成 DD が 13.4%→**16.6%** で 15% キャップを超える。 |

`python -m strategy.backtest` を再実行しても、USDJPY の pinned JSON は `--force` なしでは上書きしない。

## バックテストで確認した成績

データ: Dukascopy H1 BID を H4 にリサンプル。期間 **2015-01-01 ～ 2026-08-31（11.66 年）**。初期資金 100,000。3 パスを日次 PnL で合算した独立パス近似（同一 100k ブック）。チェックリストであり保証ではない。

### 合成ブック（採用設定）

| 指標 | 値 |
|---|---|
| トレード数 | **1004** |
| 勝率 | 43.9% |
| 平均 R | 0.07 |
| 年率平均 | **21.29%** |
| CAGR | **20.39%** |
| 最大 DD（合成） | **12.48%** |
| Profit Factor | 1.45 |
| Sharpe（日次×√252） | 1.07 |
| Sortino | 1.90 |
| Calmar | 1.63 |
| 純損益 | +771,230（+771.2%） |

チェックリスト（合成）: 年数 / PF ≥ 1.3 / 合成 DD ≤ 15% / Sharpe ≥ 0.6 は PASS。トレード数は 10 年 500–600 の目安を上回る（回数を減らすと利益も減るため、間引きは採用していない）。上表の年率 21% は学習期と検証期の混在であり、毎年そうなる見通しではない（下記の考察）。

単体の最大 DD は合成より大きい（GBP 約 31%、JPY 約 25%、CAD 約 24%）。ブックとして見る前提。

### ペア別（リスク 5.0%）

| ペア | トレード | 勝率 | PF（通期） | 検証 PF | 単体最大 DD |
|---|---|---|---|---|---|
| USDCAD | 187 | 50.8% | 1.69 | 1.24 | 23.7% |
| USDJPY | 653 | 42.0% | 1.42 | 1.85 | 24.7% |
| GBPUSD | 164 | 43.9% | 1.27 | 1.28 | 31.3% |

再計測: `python -m account.backtest`。詳細は `reports/portfolio.md`。

TradingView のストラテジーテスターは 1 銘柄ずつ・資金も別なので、3 回の結果を足してもこの合成数字にはならない。

## オーバーフィットに関する考察

オーバーフィットしているのは **採用 3 本そのものというより、パラメータを選んだ探索** です。ペアあたり 792 セル、検証 2021–2025 を選定フィルタに使い、USDJPY では検証リターンまで目的関数に入っていた。試行を増やせば学習期の見かけの Sharpe は上がるので、その数字や 11 年年率 21% を「これから毎年実現する期待値」にはできません。未使用の 2026-01〜08（約 0.66 年）ではブック年率は約 7%、PF 1.20、DD 11.8% でした。これも 8 か月・少数本の 1 回測りであり、7% が新しい見通しというわけではありません。

一方で、採用 3 本が学習期だけの偽物、とまでは言い切れません。3 本の検証 PF は 1.2 超、同じ探索で EURUSD / AUDUSD / NZDUSD / USDCHF の 4 本は落ち、ウォークフォワードの平均窓 PF も持ちます。エッジがゼロという意味ではありません。ルックアヘッド（次バー始値）とコスト（1 pip + 0.2 slip）はこの欠陥ではありません。

**いまから長さ・ATR・ADX を学習し直すと、何を最適化しているか分からなくなります。** 短い窓、見たあとの検証期、学習 Sharpe でピンを動かすのは成績の修正ではなく、同じデータの再漁です。USDJPY の学習期最大（20 / 1.5 / 25 / フィルタオン）はライブピン（25 / 1.5 / 15 / オフ）と違うが、ピンは維持する。2026 ホールドアウトでの焼き比べもしない。5% リスクも、21% や学習 Sharpe からは上げない。

過去の探索を消して 21% に近づける方法はありません。状況を良くするのは次だけです。

1. **期待を変える。** 計画に使うのは 11 年年率 21% ではなく、凍結ルールのこれからの期間の実績。
2. **本当に未使用の時間を積む。** 2021–2025 も 2026-01〜08 も、もう選定か評価に使っている。本体は凍結したルールをデモ／ライブで前に進めること。セル収益を残して公式 PBO を出すのは診断であり、年率は増えない。
3. **足すなら別ファミリだけ。** 同じ USD トレンドの二階建てや、落ちた EURUSD H1 平均回帰の再試行はしない。仕様を先に書き、学習と lockbox を一度だけ測り、H4 3 本＋衛星 1% の合成 DD が 15% を超えず悪化もしないこと。

診断の数値と F1–F5 は `app/strategy/cores/donchian/README.md` と `reports/overfit_adopted.md`。再計算は `python -m strategy.cores.donchian.backtest.eval_overfit`。新規ペア探索だけ `--compact`（90 セル）。これは手法の点検であり、売買助言ではありません。

## 構成

```
fx_trader/
  run.py                上位アプリ入口（発注なし）
  pine/                 TradingView
  app/
    run.py              feed → strategy → account → output
    feed/               データ取得（download / live）
    strategy/           価格分析。採用コアは strategy/cores/<name>/（評価は cores/<name>/backtest/）
    account/            建値・サイズ・会場口座とスリーブ。成績バックテストは account/backtest/
    output/             コンソール / Telegram / ローカル HTML
  params/               ペア別 Donchian JSON
  data/                 CSV（コミットしない）
  reports/              実行結果
```

## TradingView（ペア単体）

1. チャートを `USDCAD` / `USDJPY` / `GBPUSD` のいずれか、時間足 **H4**、タイムゾーンは UTC 推奨。
2. `pine/01_donchian_h4.pine` を貼り、上表のペア別パラメータと Risk % **5.0** を入力する（ファイル初期値は EURUSD 用なので上書きする）。
3. 初期資金 100000、手数料 0、スプレッド有効（目安 1 pip）。
4. `02`〜`05` は採用手法のテストには使わない。

こちらから TradingView アカウント上の 10 年テストは実行できない。FX の出来高はティック出来高であり、Rvol は実需給ではない。

## Python バックテスト

```bash
cd fx_trader
pip install -r requirements.txt

# 採用ブック（モジュール CLI。PYTHONPATH=app か pip install -e .）
python -m feed.download --start 2015-01-01
python -m account.backtest

# サインのみ（ブローカーへ発注しない）。既定は常時起動。
python run.py
python run.py --once
python run.py --offline
python run.py --offline --serve   # http://127.0.0.1:18080  (run status + proposals)

# 配管確認（合成データ。成績評価には使わない）
python -m account.backtest.run_backtest --strategy donchian --synthetic

# OANDA Practice 接続テスト（参照のみ。発注しない）
# export OANDA_API_TOKEN=...
# python -m account.venues

python -m pytest -q
```

Windows で `-m` が `feed` を見つけないときは、先に `$env:PYTHONPATH="app"` するか `pip install -e .` してください。

ペア別最適化は `python -m strategy.backtest` または `python -m strategy.cores.donchian.backtest`（学習 <2021、検証 2021–2025）。ポートフォリオは JSON があればペアごとに読み、なければ `portfolio.donchian`。同一パラメータ比較は `python -m account.backtest --shared`。候補やリスクは `app/account/config.yaml`、または `--pairs` / `--risk`。

レポート JSON は `id` / `type` / `api_version` / `data` の封筒。Webhook は `webhook.url` または `FX_TRADER_WEBHOOK_URL`（署名は `FX_TRADER_WEBHOOK_SECRET`。旧 `EURUSD_WEBHOOK_*` も読む）。Telegram は `TELEGRAM_BOT_TOKEN` と `app/output/config.yaml` の `chat_id`（未設定なら送らない）。ローカルページは `reports/www/index.html`（実行状況と直近ログ + 提案）。記録は `reports/status.jsonl`。`python run.py --offline --serve` のあと http://127.0.0.1:18080 を開く。

## CI

PR では **feed → strategy → account → output** の単体テストのあと、最後に `app/tests` の一連テストが走ります。`CI / gate` が成功したときだけマージできるように、GitHub の `main` で次を有効にしてください。

- Require a pull request before merging
- Require status checks to pass: **CI / gate**
- Do not allow bypassing the above settings

エージェントスキルは `fx_trader/.cursor/skills/`。一覧はそこの `README.md`。

チェックリスト（未達なら FAIL）:

- 期間 5 年以上（理想 10 年）
- Profit Factor ≥ 1.3
- 最大 DD ≤ 20％（採用ブックの合成キャップは設定上 15%）
- シャープ ≥ 0.5（グリッド探索の抽出ライン）
- トレード数 500〜600（10 年の目安。PF と平均 R を優先）

## やらないこと

- 公開 Pine の再配布
- ブローカー API や自動発注（`run.py` はサイン表示のみ。会場コネクタは default off）
- 目標達成のための過剰最適化（採用 JSON の再グリッド、短い窓や学習 Sharpe でのピン変更、11 年年率 21% からのサイズアップ）
