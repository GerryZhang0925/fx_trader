"""Compare fewer-trade / higher-profit Donchian picks from existing grids."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from paths import KIT_DIR, boot

boot()
ROOT = KIT_DIR  # kit root
sys.path.insert(0, str(ROOT))

from feed.pairs import CANDIDATES  # noqa: E402

PARAMS = ROOT / "params"


def _load_grid(symbol: str) -> pd.DataFrame:
    g = pd.read_csv(PARAMS / f"{symbol.lower()}_grid.csv")
    g["tot_return"] = g["train_return_pct"] + g["test_return_pct"]
    g["tot_trades"] = g["train_trades"] + g["test_trades"]
    return g


def _match(g: pd.DataFrame, params: dict) -> pd.Series:
    m = g[
        (g.length == params["length"])
        & (g.atr_mult == params["atr_mult"])
        & (g.adx_min == params["adx_min"])
        & (g.use_atr_filter == params["use_atr_filter"])
    ]
    return m.iloc[0]


def _fmt(row: pd.Series, label: str) -> str:
    return (
        f"  {label:18} L={int(row.length):2} ATR={row.atr_mult:.1f} ADX={row.adx_min:.0f} "
        f"filt={bool(row.use_atr_filter)!s:5} "
        f"n={int(row.tot_trades):3} "
        f"trPF={row.train_profit_factor:.3f} tePF={row.test_profit_factor:.3f} "
        f"ret={row.tot_return:.2f} (tr {row.train_return_pct:.2f}/te {row.test_return_pct:.2f}) "
        f"avgR tr={row.train_avg_r:.3f} te={row.test_avg_r:.3f}"
    )


def _pick(df: pd.DataFrame, cols: list[str]) -> pd.Series | None:
    if df.empty:
        return None
    return df.sort_values(cols, ascending=False).iloc[0]


def main() -> int:
    catalog = {p["symbol"]: p for p in json.loads((PARAMS / "all_pairs.json").read_text(encoding="utf-8"))}
    quality = []
    for symbol in CANDIDATES:
        g = _load_grid(symbol)
        robust = g[(g["test_profit_factor"] >= 1.0) & (g["train_max_drawdown_pct"] <= 20)]
        strict = g[
            (g["test_profit_factor"] >= 1.2)
            & (g["train_profit_factor"] >= 1.2)
            & (g["train_max_drawdown_pct"] <= 20)
        ]
        current = _match(g, catalog[symbol]["params"])
        max_ret = _pick(robust, ["tot_return", "test_return_pct", "train_avg_r"])
        max_ret_strict = _pick(strict, ["tot_return", "test_return_pct", "train_avg_r"])
        max_test = _pick(robust, ["test_return_pct", "test_avg_r"])
        max_avgr = _pick(robust[robust["train_trades"] >= 50], ["train_avg_r", "test_avg_r"])

        print("=" * 88)
        print(f"{symbol}  robust={len(robust)}  strict(PF>=1.2 both)={len(strict)}")
        print(_fmt(current, "CURRENT max-PF"))
        if max_ret is not None:
            print(_fmt(max_ret, "MAX tot-return"))
        if max_ret_strict is not None:
            print(_fmt(max_ret_strict, "MAX ret PF>=1.2"))
        else:
            print("  MAX ret PF>=1.2   (none)")
        if max_test is not None:
            print(_fmt(max_test, "MAX test-return"))
        if max_avgr is not None:
            print(_fmt(max_avgr, "MAX train avgR"))
        print(
            f"  corr n vs totRet={robust.tot_trades.corr(robust.tot_return):.3f}  "
            f"n vs trainAvgR={robust.train_trades.corr(robust.train_avg_r):.3f}  "
            f"totRet vs trainAvgR={robust.tot_return.corr(robust.train_avg_r):.3f}"
        )
        q = robust.copy()
        q["trade_bin"] = pd.qcut(q.tot_trades, 4, duplicates="drop")
        print(
            q.groupby("trade_bin", observed=True)[["tot_return", "train_avg_r", "test_profit_factor", "tot_trades"]]
            .mean()
            .round(3)
            .to_string()
        )
        chosen = max_ret_strict if max_ret_strict is not None else max_ret
        if chosen is not None:
            quality.append(
                {
                    "symbol": symbol,
                    "length": int(chosen.length),
                    "atr_mult": float(chosen.atr_mult),
                    "adx_min": float(chosen.adx_min),
                    "use_atr_filter": bool(chosen.use_atr_filter),
                    "tot_trades": int(chosen.tot_trades),
                    "tot_return": float(chosen.tot_return),
                    "test_profit_factor": float(chosen.test_profit_factor),
                    "train_profit_factor": float(chosen.train_profit_factor),
                    "has_strict": max_ret_strict is not None,
                    "current_tot_return": float(current.tot_return),
                    "current_tot_trades": int(current.tot_trades),
                    "current_test_pf": float(current.test_profit_factor),
                }
            )
    print("\n## Quality vs current (1% risk, train+test return, not compounded together)")
    qdf = pd.DataFrame(quality)
    print(qdf.to_string(index=False))
    print(
        f"\nsum current ret={qdf.current_tot_return.sum():.2f} n={qdf.current_tot_trades.sum()}  "
        f"quality ret={qdf.tot_return.sum():.2f} n={qdf.tot_trades.sum()}"
    )
    (PARAMS / "quality_picks.json").write_text(qdf.to_json(orient="records", indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
