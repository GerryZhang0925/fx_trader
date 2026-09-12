# strategy/common

コア横断の価格ヘルパー。シグナルもロットもここで決めない。

| ファイル | 役割 |
|---|---|
| `indicators.py` | EMA / ATR / Donchian / ADX / FVG / session |
| `bars.py` | H4 リサンプル（strategy が feed を import しないため） |
| `pips.py` | pip サイズ |
| `params.py` | ペア JSON 読み込みとライブ用スナップショット |
