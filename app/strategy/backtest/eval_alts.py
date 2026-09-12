"""Full-sample ema_atr / engulfing / confluence vs adopted Donchian on 11y H4."""

from __future__ import annotations

import json

import pandas as pd

from paths import boot

boot()

from account.backtest.run_portfolio import _daily_pnl, _load_pair_params, _portfolio_params  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from account.settings import load_config  # noqa: E402
from feed.loader import load_csv  # noqa: E402
from strategy.cores.donchian.backtest.eval_regime import CORE, ROOT, _metrics  # noqa: E402
from strategy.cores.donchian.backtest.optimize_donchian import TEST_END, TRAIN_END  # noqa: E402
from strategy.cores.confluence import ConfluenceStrategy  # noqa: E402
from strategy.cores.donchian import DonchianStrategy  # noqa: E402
from strategy.cores.ema_atr import EmaAtrStrategy  # noqa: E402
from strategy.cores.engulfing_rvol import EngulfingRvolStrategy  # noqa: E402

CORES = ("donchian", "ema_atr", "engulfing", "confluence")


def _build(name: str, params):
    if name == "donchian":
        return DonchianStrategy(params)
    if name == "ema_atr":
        return EmaAtrStrategy()
    if name == "engulfing":
        return EngulfingRvolStrategy()
    return ConfluenceStrategy()


def main() -> int:
    cfg = load_config()
    risk = float((cfg.get("portfolio") or {}).get("risk_pct_per_pair", 5.0))
    initial = float(cfg.get("initial_equity", 100000))
    fallback = _portfolio_params(cfg)
    data_dir = ROOT / "data"
    params_dir = ROOT / "params"
    frames = {}
    for symbol in CORE:
        params, _ = _load_pair_params(symbol, params_dir, fallback)
        h4 = load_csv(data_dir / f"{symbol.lower()}_h4.csv")
        print(f"prepare {symbol}", flush=True)
        frames[symbol] = {name: _build(name, params).prepare(h4) for name in CORES}

    rows = []
    books = {name: {"pnl": {}, "trades": []} for name in CORES}
    print("\n## Per pair test 2021-2025\n", flush=True)
    for symbol in CORE:
        for name in CORES:
            base = frames[symbol][name]
            train_mask = base.index < TRAIN_END
            test_mask = (base.index >= TRAIN_END) & (base.index < TEST_END)
            for split, mask in (("train", train_mask), ("test", test_mask), ("full", None)):
                eq, trades, m = _metrics(base, cfg, symbol, risk, mask)
                rows.append(
                    {
                        "core": name,
                        "symbol": symbol,
                        "split": split,
                        "trades": m.trades,
                        "profit_factor": m.profit_factor,
                        "avg_r": m.avg_r,
                        "yearly_mean": m.yearly_return_mean,
                        "max_drawdown_pct": m.max_drawdown_pct,
                        "sharpe": m.sharpe,
                    }
                )
                if split == "full":
                    books[name]["pnl"][symbol] = _daily_pnl(eq)
                    if not trades.empty:
                        books[name]["trades"].append(trades.assign(symbol=symbol))
            tes = next(r for r in rows[-3:] if r["split"] == "test")
            print(f"  {symbol:7} {name:12} test n={tes['trades']:4} PF={tes['profit_factor']:.3f}", flush=True)

    print("\n## Book full sample\n", flush=True)
    book_rows = []
    for name in CORES:
        pnl_sum = pd.concat(books[name]["pnl"], axis=1).fillna(0.0).sum(axis=1)
        eq = (initial + pnl_sum.cumsum()).rename("equity")
        tds = books[name]["trades"]
        trades = pd.concat(tds, ignore_index=True) if tds else pd.DataFrame()
        if not trades.empty and "exit_time" in trades.columns:
            trades = trades.sort_values("exit_time")
        m = compute_metrics(eq, trades, initial)
        rec = {
            "core": name,
            "trades": m.trades,
            "profit_factor": m.profit_factor,
            "yearly_mean": m.yearly_return_mean,
            "cagr": m.cagr,
            "max_drawdown_pct": m.max_drawdown_pct,
            "sharpe": m.sharpe,
        }
        book_rows.append(rec)
        print(
            f"  {name:12} n={m.trades:4} PF={m.profit_factor:.3f} year={m.yearly_return_mean:.2%} "
            f"CAGR={m.cagr:.2%} DD={m.max_drawdown_pct:.2f}%",
            flush=True,
        )

    pair_df = pd.DataFrame(rows)
    book_df = pd.DataFrame(book_rows)
    out = ROOT / "reports"
    pair_df.to_csv(out / "alts_pairs.csv", index=False)
    book_df.to_csv(out / "alts_books.csv", index=False)
    (out / "alts.json").write_text(
        json.dumps({"pairs": pair_df.to_dict(orient="records"), "books": book_df.to_dict(orient="records")}, indent=2, default=str),
        encoding="utf-8",
    )
    lines = [
        "# Full-sample alternate cores vs adopted Donchian",
        "",
        "Same 5% risk, engine, costs. Train <2021 / test 2021–2025. Do not replace Donchian unless test PF and book beat it.",
        "",
        "## Test PF",
        "",
        pair_df[pair_df["split"] == "test"][["core", "symbol", "trades", "profit_factor", "avg_r", "max_drawdown_pct"]].to_string(index=False),
        "",
        "## Book",
        "",
        book_df.to_string(index=False),
        "",
        "Checklist, not a guarantee.",
        "",
    ]
    (out / "alts.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out / 'alts.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
