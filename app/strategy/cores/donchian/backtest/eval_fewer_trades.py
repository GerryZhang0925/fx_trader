"""Fewer trades vs more profit: grid Pareto + full-sample portfolio books."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from paths import KIT_DIR, boot

boot()
ROOT = KIT_DIR  # kit root

from feed.loader import load_csv  # noqa: E402
from account.engine import run_backtest  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from feed.pairs import CANDIDATES, pip_size  # noqa: E402
from account.settings import engine_from_config, load_config  # noqa: E402
from account.backtest.run_portfolio import _daily_pnl  # noqa: E402
from strategy.cores.donchian import DonchianParams, DonchianStrategy  # noqa: E402

PARAMS = ROOT / "params"
DATA = ROOT / "data"
OUT = ROOT / "reports"


def _grid(symbol: str) -> pd.DataFrame:
    g = pd.read_csv(PARAMS / f"{symbol.lower()}_grid.csv")
    g["tot_return"] = g["train_return_pct"] + g["test_return_pct"]
    g["tot_trades"] = g["train_trades"] + g["test_trades"]
    return g


def _match(g: pd.DataFrame, p: dict) -> pd.Series:
    return g[
        (g.length == p["length"])
        & (g.atr_mult == p["atr_mult"])
        & (g.adx_min == p["adx_min"])
        & (g.use_atr_filter == p["use_atr_filter"])
    ].iloc[0]


def _params_from_row(row: pd.Series, base: dict) -> DonchianParams:
    return DonchianParams.from_dict(
        {
            **base,
            "length": int(row.length),
            "atr_mult": float(row.atr_mult),
            "adx_min": float(row.adx_min),
            "use_atr_filter": bool(row.use_atr_filter),
            "use_adx_filter": True,
        }
    )


def _backtest(symbol: str, params: DonchianParams, cfg: dict, risk_pct: float):
    h4 = load_csv(DATA / f"{symbol.lower()}_h4.csv")
    prepared = DonchianStrategy(params).prepare(h4)
    engine = engine_from_config(cfg, pip_size=pip_size(symbol), risk_pct=risk_pct)
    eq, trades = run_backtest(prepared, engine)
    metrics = compute_metrics(eq, trades, cfg.get("initial_equity", 100000))
    return eq, trades, metrics


def _book(label: str, specs: list[tuple[str, DonchianParams]], cfg: dict, risk_pct: float, initial: float) -> dict:
    pair_rows = []
    pnl = {}
    trade_frames = []
    for symbol, params in specs:
        print(
            f"  {label} {symbol} L={params.length} ATR={params.atr_mult} "
            f"ADX={params.adx_min} filt={params.use_atr_filter} risk={risk_pct}%",
            flush=True,
        )
        eq, trades, m = _backtest(symbol, params, cfg, risk_pct)
        pnl[symbol] = _daily_pnl(eq)
        pair_rows.append(
            {
                "symbol": symbol,
                "length": params.length,
                "atr_mult": params.atr_mult,
                "adx_min": params.adx_min,
                "use_atr_filter": params.use_atr_filter,
                "trades": m.trades,
                "profit_factor": m.profit_factor,
                "avg_r": m.avg_r,
                "max_drawdown_pct": m.max_drawdown_pct,
                "sharpe": m.sharpe,
                "return_pct": m.return_pct,
            }
        )
        if not trades.empty:
            trade_frames.append(trades.assign(symbol=symbol))
    rows = pd.DataFrame(pair_rows)
    selected = list(rows["symbol"])
    pnl_sum = pd.concat([pnl[s] for s in selected], axis=1).fillna(0.0).sum(axis=1)
    port_eq = (initial + pnl_sum.cumsum()).rename("equity")
    port_trades = pd.concat(trade_frames, ignore_index=True) if trade_frames else pd.DataFrame()
    if not port_trades.empty:
        port_trades = port_trades.sort_values("exit_time")
    pm = compute_metrics(port_eq, port_trades, initial)
    return {
        "label": label,
        "risk_pct": risk_pct,
        "selected": selected,
        "pairs": pair_rows,
        "trades": pm.trades,
        "profit_factor": pm.profit_factor,
        "max_drawdown_pct": pm.max_drawdown_pct,
        "sharpe": pm.sharpe,
        "return_pct": pm.return_pct,
        "avg_r": pm.avg_r,
        "win_rate": pm.win_rate,
    }


def main() -> int:
    cfg = load_config(None)
    base = {**cfg.get("donchian", {}), **(cfg.get("portfolio", {}).get("donchian") or {})}
    catalog = {p["symbol"]: p for p in json.loads((PARAMS / "all_pairs.json").read_text(encoding="utf-8"))}
    initial = float(cfg.get("initial_equity", 100000))

    print("## Grid: can fewer trades beat current train+test return?\n")
    pareto_rows = []
    picks = {}
    for symbol in CANDIDATES:
        g = _grid(symbol)
        cur = _match(g, catalog[symbol]["params"])
        robust = g[(g.test_profit_factor >= 1.0) & (g.train_max_drawdown_pct <= 20)]
        fewer = robust[robust.tot_trades < cur.tot_trades]
        win = fewer[fewer.tot_return >= cur.tot_return + 0.5]
        best_fewer = fewer.sort_values(["tot_return", "test_return_pct"], ascending=False).iloc[0] if len(fewer) else None
        best_win = win.sort_values(["tot_return", "test_return_pct"], ascending=False).iloc[0] if len(win) else None
        best_cap = robust[robust.tot_trades <= cur.tot_trades].sort_values(
            ["tot_return", "test_return_pct"], ascending=False
        ).iloc[0]
        strict = g[
            (g.test_profit_factor >= 1.2)
            & (g.train_profit_factor >= 1.2)
            & (g.train_max_drawdown_pct <= 20)
        ]
        sparse_strict = None
        if len(strict):
            cap = strict.tot_trades.median()
            pool = strict[strict.tot_trades <= cap]
            sparse_strict = pool.sort_values(["tot_return", "test_avg_r"], ascending=False).iloc[0]
        print(f"{symbol} current n={int(cur.tot_trades)} ret={cur.tot_return:.2f} tePF={cur.test_profit_factor:.3f}")
        if best_win is not None:
            print(
                f"  WIN fewer+more$ L={int(best_win.length)} ATR={best_win.atr_mult} ADX={best_win.adx_min} "
                f"filt={bool(best_win.use_atr_filter)} n={int(best_win.tot_trades)} ret={best_win.tot_return:.2f} "
                f"tePF={best_win.test_profit_factor:.3f}"
            )
        else:
            print("  no combo with fewer trades AND +0.5pt higher train+test return")
        if best_fewer is not None:
            print(
                f"  best-fewer     L={int(best_fewer.length)} ATR={best_fewer.atr_mult} ADX={best_fewer.adx_min} "
                f"n={int(best_fewer.tot_trades)} ret={best_fewer.tot_return:.2f} tePF={best_fewer.test_profit_factor:.3f}"
            )
        if sparse_strict is not None:
            print(
                f"  sparse PF>=1.2 L={int(sparse_strict.length)} ATR={sparse_strict.atr_mult} "
                f"ADX={sparse_strict.adx_min} filt={bool(sparse_strict.use_atr_filter)} "
                f"n={int(sparse_strict.tot_trades)} ret={sparse_strict.tot_return:.2f} tePF={sparse_strict.test_profit_factor:.3f}"
            )
        pareto_rows.append(
            {
                "symbol": symbol,
                "current_n": int(cur.tot_trades),
                "current_ret": float(cur.tot_return),
                "current_test_pf": float(cur.test_profit_factor),
                "fewer_and_better": best_win is not None,
                "best_fewer_n": int(best_fewer.tot_trades) if best_fewer is not None else None,
                "best_fewer_ret": float(best_fewer.tot_return) if best_fewer is not None else None,
                "best_capped_n": int(best_cap.tot_trades),
                "best_capped_ret": float(best_cap.tot_return),
            }
        )
        picks[symbol] = {
            "current": _params_from_row(cur, base),
            "capped": _params_from_row(best_cap, base),
            "sparse": _params_from_row(sparse_strict, base) if sparse_strict is not None else None,
            "fewer": _params_from_row(best_fewer, base) if best_fewer is not None else None,
        }

    print("\n## Full-sample books\n")
    books = []
    # Current 5-pair (AUD dropped by PF<1.2 in previous run; include same universe)
    core = ["USDCAD", "USDJPY", "GBPUSD"]
    wide = core + ["EURUSD", "NZDUSD"]
    books.append(_book("current_wide_0.5", [(s, picks[s]["current"]) for s in wide], cfg, 0.5, initial))
    books.append(_book("current_core_0.5", [(s, picks[s]["current"]) for s in core], cfg, 0.5, initial))
    books.append(_book("current_core_1.0", [(s, picks[s]["current"]) for s in core], cfg, 1.0, initial))
    # EUR OOS-robust + core
    eur_sparse = picks["EURUSD"]["sparse"]
    if eur_sparse is not None:
        books.append(
            _book(
                "core_plus_eur_sparse_0.5",
                [(s, picks[s]["current"]) for s in core] + [("EURUSD", eur_sparse)],
                cfg,
                0.5,
                initial,
            )
        )
    # Sparse-strict params on pairs that have them
    sparse_specs = []
    for s in ["USDCAD", "USDJPY", "GBPUSD", "EURUSD"]:
        if picks[s]["sparse"] is not None:
            sparse_specs.append((s, picks[s]["sparse"]))
    books.append(_book("sparse_strict_0.5", sparse_specs, cfg, 0.5, initial))
    books.append(_book("sparse_strict_1.0", sparse_specs, cfg, 1.0, initial))

    summary = pd.DataFrame(
        [
            {
                "book": b["label"],
                "pairs": ",".join(b["selected"]),
                "risk": b["risk_pct"],
                "trades": b["trades"],
                "return_pct": round(b["return_pct"], 2),
                "profit_factor": round(b["profit_factor"], 3),
                "max_dd": round(b["max_drawdown_pct"], 2),
                "sharpe": round(b["sharpe"], 3),
                "avg_r": round(b["avg_r"], 3),
            }
            for b in books
        ]
    )
    print("\n## Book comparison\n")
    print(summary.to_string(index=False))
    OUT.mkdir(parents=True, exist_ok=True)
    summary.to_csv(OUT / "fewer_trades_books.csv", index=False)
    (OUT / "fewer_trades_books.json").write_text(json.dumps(books, indent=2, default=str), encoding="utf-8")
    pd.DataFrame(pareto_rows).to_csv(OUT / "fewer_trades_pareto.csv", index=False)
    print(f"\nWrote {OUT / 'fewer_trades_books.md'}".replace("fewer_trades_books.md", "fewer_trades_books.csv"))
    lines = [
        "# Fewer trades vs more profit",
        "",
        "Trade count is not a profit lever by itself. USDJPY earns more with more trades;",
        "USDCAD/NZDUSD earn more by skipping weak trades. Portfolio profit rises when risk",
        "is concentrated on the robust pairs, not when every pair is thinned.",
        "",
        "## Books",
        "",
        summary.to_string(index=False),
        "",
        "Targets are a checklist, not a guarantee.",
        "",
    ]
    (OUT / "fewer_trades.md").write_text("\n".join(lines), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
