# FX Trader（研究用シグナル）

H4 ドンチャンのトレンドフォローを自前実装した研究キットです。TradingView 用 Pine と、同じルールの Python バックテストが入っています。

**これは売買助言ではありません。** 下記の成績は 2015–2026 の Dukascopy H4 バックテスト（チェックリスト）であり、将来のリターンや DD を保証しません。公開インジケータ（INTELA、Kill Zone Sniper 等）のコピーではありません。

## 採用手法

**ペア別パラメータの H4 ドンチャンブレイク**を、USDCAD / USDJPY / GBPUSD の固定ブックとして同時に回す。

ルール（全ペア共通）:

- 前日窓のドンチャン上限／下限ブレイク＋200EMA 方向フィルタ＋ADX フィルタ
- スイング損切り（ATR 0.5 バッファ）
- 1R で 50% 利確、残りはエントリー直後から ATR トレイル
- 逆方向ブレイクで反転クローズ
- 1 トレードあたり資金の **5.5%** リスク
- 1 日最大 2 トレード。連続 3 負け、またはその日 −2R で当日停止
- 約定はシグナル確定バーの **次バー始値**。スプレッド 1 pip ＋スリッページ 0.2 pip

ペア別パラメータ:

| ペア | Donchian | ATR トレイル | ADX 最小 | ATR 中央値フィルタ |
|---|---|---|---|---|
| USDCAD | 55 | 3.0 | 22 | オン |
| USDJPY | 25 | 1.5 | 15 | オフ |
| GBPUSD | 60 | 3.0 | 24 | オン |

USDJPY だけ学習期 PF 最大ではなく、学習＋検証リターン最大かつ検証 PF ≥ 1.2 のセットを採用している（`params/usdjpy_donchian.json` は `pinned: true`）。

採用しないもの: 2R/3R 固定利確、BE、遅延トレール、測度ターゲット、10 点コンフィデンスによるロット調整、エンガルフィング衛星、Kill Zone でドンチャンを間引く。いずれも同一エンジンでバックテストし、コア収益または PF が悪化した。

## 実装箇所

| 役割 | 場所 |
|---|---|
| 採用ブックの候補・リスク | `app/account/config.yaml` → `portfolio.candidates` / `risk_pct_per_pair: 5.5` / `fixed_book: true` |
| ペア別パラメータ | `params/usdcad_donchian.json`, `params/usdjpy_donchian.json`, `params/gbpusd_donchian.json` |
| シグナル（ドンチャン） | `app/strategy/donchian.py` |
| サイン出力のみ（発注なし） | `app/run.py`（根から `python run_signals.py`。常時監視） |
| H4 追記・ギャップ埋め | `app/feed/live.py` |
| 次バー約定・部分利確・ATR トレイル・サイズ提案 | `app/account/engine.py` / `propose.py` |
| 日次停止・サイズ | `app/account/risk.py` |
| コンソール / Telegram / ローカル HTML | `app/output/` |
| 3 通貨合成バックテスト | `app/account/backtest/run_portfolio.py`（根から `python run_portfolio.py`） |
| TradingView（単体。合成ブックではない） | `pine/01_donchian_h4.pine` |
| 直近の合成レポート | `reports/portfolio.md` / `reports/portfolio.json` |

`02`〜`05` の Pine と `engulfing` / `killzone` / `ema_atr` / `confluence` 戦略は比較・研究用で、採用ブックには含まれない。

## 対象通貨ペア

採用: **USDCAD, USDJPY, GBPUSD**（`portfolio.candidates`）。検証 PF がおおむね 1.2 以上で、戦略 PnL の相関も低い。

## 採用しない通貨ペア

探索対象は EURUSD / GBPUSD / USDJPY / AUDUSD / USDCAD / NZDUSD。次の 3 本はブックに入れない。

| ペア | 理由 |
|---|---|
| EURUSD | 学習 PF 1.55 に対し検証 PF **1.01**。OOS でエッジが消えた。単体 4% でも年率はチェックリストの 10–20% に届かず、リスクを上げると DD が 20% を超える。 |
| AUDUSD | 学習 PF 1.09、検証 PF **1.07**。トレードも少なく、Donchian に乗らない。 |
| NZDUSD | 学習 PF 2.12 だが検証 PF **1.06**。インサンプル偏り。 |

`optimize_pairs.py` を再実行しても、USDJPY の pinned JSON は `--force` なしでは上書きしない。

## バックテストで確認した成績

データ: Dukascopy H1 BID を H4 にリサンプル。期間 **2015-01-01 ～ 2026-08-31（11.66 年）**。初期資金 100,000。3 パスを日次 PnL で合算した独立パス近似（同一 100k ブック）。チェックリストであり保証ではない。

### 合成ブック（採用設定）

| 指標 | 値 |
|---|---|
| トレード数 | **1004** |
| 勝率 | 43.9% |
| 平均 R | 0.07 |
| 年率平均 | **23.14%** |
| CAGR | **22.03%** |
| 最大 DD（合成） | **13.38%** |
| Profit Factor | 1.44 |
| Sharpe（日次×√252） | 1.07 |
| Sortino | 1.90 |
| Calmar | 1.65 |
| 純損益 | +919,519（+919.5%） |

チェックリスト（合成）: 年数 / PF ≥ 1.3 / 合成 DD ≤ 15% / Sharpe ≥ 0.6 は PASS。トレード数は 10 年 500–600 の目安を上回る（回数を減らすと利益も減るため、間引きは採用していない）。

単体の最大 DD は合成より大きい（GBP 約 34%、JPY 約 27%、CAD 約 26%）。ブックとして見る前提。

### ペア別（リスク 5.5%）

| ペア | トレード | 勝率 | PF（通期） | 検証 PF | 単体最大 DD |
|---|---|---|---|---|---|
| USDCAD | 187 | 50.8% | 1.69 | 1.24 | 25.9% |
| USDJPY | 653 | 42.0% | 1.41 | 1.85 | 26.8% |
| GBPUSD | 164 | 43.9% | 1.26 | 1.28 | 33.8% |

再計測: `python run_portfolio.py`。詳細は `reports/portfolio.md`。

TradingView のストラテジーテスターは 1 銘柄ずつ・資金も別なので、3 回の結果を足してもこの合成数字にはならない。

## 構成

```
fx_trader/
  pine/                 TradingView に貼る strategy
  app/                  上位アプリ。feed → strategy → account → output
    run.py
    feed/               データ取得
    strategy/           価格分析・最適化
    account/            建値・サイズ・PnL バックテスト
    output/             コンソール / Telegram / ローカル HTML
  python/               旧 import 用の互換シム
  params/               ペア別 Donchian JSON
  data/                 CSV（コミットしない）
  reports/              実行結果（signals.md, www/index.html）
```

## TradingView（ペア単体）

1. チャートを `USDCAD` / `USDJPY` / `GBPUSD` のいずれか、時間足 **H4**、タイムゾーンは UTC 推奨。
2. `pine/01_donchian_h4.pine` を貼り、上表のペア別パラメータと Risk % **5.5** を入力する（ファイル初期値は EURUSD 用なので上書きする）。
3. 初期資金 100000、手数料 0、スプレッド有効（目安 1 pip）。
4. `02`〜`05` は採用手法のテストには使わない。

こちらから TradingView アカウント上の 10 年テストは実行できない。FX の出来高はティック出来高であり、Rvol は実需給ではない。

## Python バックテスト

```bash
cd fx_trader
pip install -r python/requirements.txt

# 採用ブック
python download_data.py --start 2015-01-01 --symbols EURUSD,GBPUSD,USDJPY,AUDUSD,USDCAD,NZDUSD
python run_portfolio.py

# サインのみ（ブローカーへ発注しない）。既定は常時起動: H4 確定後に Dukascopy を取り込み、穴があれば埋めて CSV を更新し、コンソールへ提案を出す。失敗時は待ってリトライ。土日（UTC）は FX 休場のため取得しない。
python run_signals.py
python run_signals.py --once          # 1 回更新して終了
python run_signals.py --offline       # ダウンロードせず既存 CSV だけ
python run_signals.py --offline --serve   # あわせて http://127.0.0.1:8765

# 配管確認（合成データ。成績評価には使わない）
python run_backtest.py --strategy donchian --synthetic

python -m pytest -q
```

ペア別最適化は `optimize_pairs.py`（学習 <2021、検証 2021–2025）。`run_portfolio.py` は JSON があればペアごとに読み、なければ `portfolio.donchian`。同一パラメータ比較は `python run_portfolio.py --shared`。候補やリスクは `app/account/config.yaml`、または `--pairs` / `--risk`。

レポート JSON は `id` / `type` / `api_version` / `data` の封筒。Webhook は `webhook.url` または `FX_TRADER_WEBHOOK_URL`（署名は `FX_TRADER_WEBHOOK_SECRET`。旧 `EURUSD_WEBHOOK_*` も読む）。Telegram は `TELEGRAM_BOT_TOKEN` と `app/output/config.yaml` の `chat_id`（未設定なら送らない）。ローカルページは `reports/www/index.html`。

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
- ブローカー API や自動発注（`run_signals.py` はサイン表示のみ）
- 目標達成のための過剰最適化
