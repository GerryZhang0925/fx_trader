# Donchian core（採用）

H4 確定バーのドンチャンブレイク。ライブの唯一のコア。シグナルのみ。ロットも発注もしない。成績はチェックリストであり保証ではない。

実装: `strategy.py`。import: `from strategy.cores.donchian import DonchianStrategy`。

## ライブブック

固定 3 本。`app/account/config.yaml` の `portfolio.candidates` / `fixed_book: true` / `risk_pct_per_pair: 5.0`。

| ペア | Donchian 長さ | ATR トレイル | ADX 最小 | ATR 中央値フィルタ | パラメータ JSON |
|---|---|---|---|---|---|
| USDCAD | 55 | 3.0 | 22 | オン | `params/usdcad_donchian.json` |
| USDJPY | 25 | 1.5 | 15 | オフ | `params/usdjpy_donchian.json`（`pinned: true`） |
| GBPUSD | 60 | 3.0 | 24 | オン | `params/gbpusd_donchian.json` |

USDJPY だけ学習 PF 最大ではなく、学習+検証リターン最大かつ検証 PF ≥ 1.2 のセット。

## ルール（全ペア共通）

- 前日窓のドンチャン上限／下限を終値が越える。200EMA の側にあること。ADX フィルタ（USDJPY 以外は ATR 中央値も）
- スイング損切り（ATR 0.5 バッファ）
- 1R で 50% 利確。残りはエントリー直後から ATR トレイル
- 逆方向ブレイクで反転クローズ
- 1 トレードあたり資金の **5.0%**
- 1 日最大 2 トレード。連続 3 負け、またはその日 −2R で当日停止
- 約定はシグナル確定バーの **次バー始値**。スプレッド 1 pip ＋スリッページ 0.2 pip
- レポートのエクイティ MTM / 最大 DD は終値のみ

学習 &lt;2021、検証 2021–2025。データは Dukascopy H1 BID を H4 にリサンプル（2015-01-01 ～ 2026-08-31）。

## 合成成績（5.0%、11.66 年、独立パス 100k）

| 指標 | 値 |
|---|---|
| トレード | 1004 |
| 年率平均 | 21.29% |
| CAGR | 20.39% |
| 最大 DD（終値 MTM） | 12.48% |
| PF | 1.45 |
| Sharpe | 1.07 |

ペア別検証 PF はおおよそ 1.24 / 1.85 / 1.28。再計測は `python -m account.backtest`。詳細は `reports/portfolio.md`。

## オーバーレイの採用ゲート

同じエンジン・コスト・次バー約定。ライブに載せるのは次をすべて満たすときだけ。

1. 3 ペアとも検証 PF がコア未満にならない
2. 3 本ブックの年率・CAGR・最大 DD が悪化しない
3. コアと同一の no-op ではない

検証 PF &lt; 1.0、または学習期だけ良くて検証が落ちるものは棄てる。回数を大きく減らす間引きは、収益も減るので採用していない。

## 試した手法とドロップ理由

レポートは `reports/`。評価スクリプトは `backtest/`（このフォルダ内）。

### ペア探索（4 本目は入れない）

| 対象 | 結果 | 理由 |
|---|---|---|
| EURUSD | DROP | 検証 PF **1.01**。OOS でエッジが消える |
| AUDUSD | DROP | 検証 PF **1.07**。グリッドでも検証 PF ≥ 1.2 のセルなし |
| NZDUSD | DROP | 学習 PF 2.12 だが検証 PF **1.06**。AUD との日次価格相関 0.84 |
| USDCHF | DROP | 検証 PF 1.36 のセルはあるが、5.5%×4 本で合成 DD **16.6%**（15% キャップ超）。サイズ梯子でも DD が先に悪化 |

### エグジット・サイズ（コア変更）

| 手法 | 結果 | 理由 |
|---|---|---|
| 2R / 3R 固定利確、BE、遅延トレール、測度ターゲット | DROP | 1R 50% + 直後 ATR トレイルよりコア収益または PF が悪化 |
| 10 点コンフィデンス / A+ でロット増 | DROP | グレード別平均 R が上がらない。サイズはリスク%のみ |
| コアリスク 5.5% | 5.0% に下げた | ウィック余裕。年率 23.1%→21.3%、DD 13.4%→12.5% |

### オーバーレイ（コアの入りをフィルタ）

ゲートは学習 &lt;2021 / 検証 2021–2025、リスク 5.0%。ベースブックは年率 21.29% / CAGR 20.39% / DD 12.48% / 1004 本。

| 実験 | 主なバリアント | 結果 | ドロップ理由 |
|---|---|---|---|
| レジーム | EMA50 斜面、BB 幅、ATR 比、トレンド複合、チョップ除外 | DROP | `not_squeeze` だけ検証 PF は全ペアで持ったが、年率 19.57%、DD 13.94%。他は検証 PF が落ちる |
| H1 整列 | H1 EMA50 斜面 / 50・200 サイド / Donchian 位置 | DROP | `h1_ema50_side` は 1004 本ともコアと同一（no-op）。斜面は DD 12.75%。200EMA と Donchian 三分位は検証 PF が落ちる |
| ブレイク継続 | 0.1ATR バッファ、実体、RVOL、フラッグ圧縮、6 バーリテスト | DROP | `rvol` は検証 PF が 3 ペアとも改善したが DD 13.31%。リテストは PF&lt;1 で DD 68%。フラッグは 371 本まで間引き |
| プルバック代替 | EMA21 リクレイム、OTE 62–79%、Fib 61.8%（点数合算なし） | DROP | 単独戦略として検証 PF がだいたい &lt;1.0。ブックは年率マイナス・DD 100% 超 |
| 構造 | FVG、BOS、スイープ、オーダーブロック代理 | DROP | FVG は検証 PF 改善だが DD 14.18%。スイープは本数が潰れる。OB は検証 PF が落ちる |
| H4 Kill Zone | ロンドン / NY 重なり、重なり除外。M5 なし | DROP | 重なり必須も除外も年率が落ちる。M5 間引きは以前に棄却済み |
| イベント停止 | NFP 第1金曜・FOMC 第3水曜のプロキシ（公式カレンダーなし） | DROP | 止めると検証 PF がコア未満。公式フィードは未導入 |
| 相関スキップ | 60 日終値リターン相関 &gt; 0.70 で弱いペアを翌休 | DROP | 一度も発火しない（CAD–JPY 最大約 0.69）。3 本はもともと低相関 |
| 代替コア 11 年 | ema_atr / engulfing / confluence | DROP | ドンチャン以外はブック年率・DD で負ける（ema_atr 年率 14.7% / DD 37%、engulfing マイナス、confluence 年率 8.2% / DD 34%） |

### ウォークフォワード（ゲートとして残す）

採用パラメータの 3 年学習 / 1 年検証 / 1 年ステップ。平均窓 PF は 3 ペアとも ≥ 1.64。1 年窓は本数が少なく PF&lt;1 の年がある（CAD 2022、GBP 2019/2023/2025）。ライブ変更の前に `reports/walkforward_adopted.md` を出す。1 年・約 15 本の窓だけでパラメータは変えない。

## 再実行

```bash
$env:PYTHONPATH="app"
python -m account.backtest
python -m strategy.cores.donchian.backtest
python -m strategy.cores.donchian.backtest.eval_regime
python -m strategy.cores.donchian.backtest.eval_walkforward
```

Pine の単体確認は `pine/01_donchian_h4.pine`（合成ブックではない）。
