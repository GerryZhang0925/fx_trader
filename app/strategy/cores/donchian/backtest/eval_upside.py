"""Same-entry upside: exits, fractional Kelly, DD-budget sizing, satellite.

Does not add Kill Zone / M5 confluence (those cut trade count; no M5 CSV on disk).
Targets are a checklist, not a guarantee.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from paths import KIT_DIR, boot

boot()
ROOT = KIT_DIR  # kit root

from feed.loader import load_csv  # noqa: E402
from account.engine import run_backtest  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from strategy.cores.donchian.backtest.optimize_donchian import TEST_END, TRAIN_END  # noqa: E402
from feed.pairs import pip_size  # noqa: E402
from account.risk import kelly_fraction, realized_payoff_ratio  # noqa: E402
from account.settings import engine_from_config, load_config  # noqa: E402
from account.backtest.run_portfolio import _daily_pnl  # noqa: E402
from strategy.cores.donchian import DonchianParams, DonchianStrategy  # noqa: E402
from strategy.cores.engulfing_rvol import EngulfingParams, EngulfingRvolStrategy  # noqa: E402

PARAMS = ROOT / "params"
DATA = ROOT / "data"
OUT = ROOT / "reports"

CORE = ["USDCAD", "USDJPY", "GBPUSD"]
FOCUS = ["EURUSD"] + CORE

EXIT_VARIANTS: dict[str, dict] = {
    "baseline": {},
    "tp2": {"remainder_tp_r": 2.0},
    "tp3": {"remainder_tp_r": 3.0},
    "be_trail": {"be_after_partial": True},
    "be_tp2": {"be_after_partial": True, "remainder_tp_r": 2.0},
    "trail_after": {"trail_after_partial": True},
    "trail_after_be_tp2": {
        "trail_after_partial": True,
        "be_after_partial": True,
        "remainder_tp_r": 2.0,
    },
    "measured_move": {"target_mode": "measured_move", "trail_after_partial": True},
    "vol_size_scale": {"vol_size_scale": True},
}


def _load_base(symbol: str, cfg: dict) -> DonchianParams:
    path = PARAMS / f"{symbol.lower()}_donchian.json"
    fallback = {**cfg.get("donchian", {}), **(cfg.get("portfolio", {}).get("donchian") or {})}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return DonchianParams.from_dict(data.get("params") or fallback)
    return DonchianParams.from_dict(fallback)


def _apply(base: DonchianParams, overlay: dict) -> DonchianParams:
    d = asdict(base)
    d.update(overlay)
    return DonchianParams.from_dict(d)


def _cagr(return_pct: float, years: float) -> float:
    if years <= 0:
        return 0.0
    total = 1.0 + return_pct / 100.0
    if total <= 0:
        return -1.0
    return float(total ** (1.0 / years) - 1.0)


def _metrics_row(m, extra: dict | None = None) -> dict:
    p, b = 0.0, 0.0
    row = {
        "trades": m.trades,
        "win_rate": m.win_rate,
        "avg_r": m.avg_r,
        "profit_factor": m.profit_factor,
        "max_drawdown_pct": m.max_drawdown_pct,
        "sharpe": m.sharpe,
        "return_pct": m.return_pct,
        "yearly_mean": m.yearly_return_mean,
        "cagr": _cagr(m.return_pct, m.years),
        "years": m.years,
    }
    if extra:
        row.update(extra)
    return row


def _run(prepared: pd.DataFrame, cfg: dict, symbol: str, risk_pct: float, mask=None):
    frame = prepared if mask is None else prepared.loc[mask]
    engine = engine_from_config(cfg, pip_size=pip_size(symbol), risk_pct=risk_pct)
    eq, trades = run_backtest(frame, engine)
    m = compute_metrics(eq, trades, cfg.get("initial_equity", 100000))
    return eq, trades, m


def _book(pnls: dict[str, pd.Series], trades_list: list[pd.DataFrame], cfg: dict):
    initial = float(cfg.get("initial_equity", 100000))
    pnl_sum = pd.concat(pnls, axis=1).fillna(0.0).sum(axis=1)
    eq = (initial + pnl_sum.cumsum()).rename("equity")
    trades = pd.concat([t for t in trades_list if not t.empty], ignore_index=True) if trades_list else pd.DataFrame()
    if not trades.empty and "exit_time" in trades.columns:
        trades = trades.sort_values("exit_time")
    return eq, trades, compute_metrics(eq, trades, initial)


def main() -> int:
    cfg = load_config(None)
    initial = float(cfg.get("initial_equity", 100000))
    frames = {s: load_csv(DATA / f"{s.lower()}_h4.csv") for s in FOCUS}
    bases = {s: _load_base(s, cfg) for s in FOCUS}

    print("## EURUSD + core pair exit variants (0.5% risk, same entries)\n", flush=True)
    pair_rows = []
    prepared_cache: dict[tuple[str, str], pd.DataFrame] = {}
    for symbol in FOCUS:
        h4 = frames[symbol]
        train_mask = h4.index < TRAIN_END
        test_mask = (h4.index >= TRAIN_END) & (h4.index < TEST_END)
        for name, overlay in EXIT_VARIANTS.items():
            params = _apply(bases[symbol], overlay)
            prepared = DonchianStrategy(params).prepare(h4)
            prepared_cache[(symbol, name)] = prepared
            n_sig = int((prepared["signal"] != 0).sum())
            for split, mask in (("full", None), ("train", train_mask), ("test", test_mask)):
                _, trades, m = _run(prepared, cfg, symbol, 0.5, mask)
                p, b = realized_payoff_ratio(trades)
                f_star = kelly_fraction(p, b)
                row = _metrics_row(
                    m,
                    {
                        "symbol": symbol,
                        "variant": name,
                        "split": split,
                        "signals": n_sig,
                        "payoff_b": b,
                        "kelly": f_star,
                        "half_kelly_pct": 100.0 * f_star / 2.0,
                    },
                )
                pair_rows.append(row)
            full = next(r for r in pair_rows[-3:] if r["split"] == "full")
            tes = next(r for r in pair_rows[-3:] if r["split"] == "test")
            print(
                f"  {symbol:7} {name:20} n={full['trades']:4} PF={full['profit_factor']:.3f} "
                f"ret={full['return_pct']:.1f}% DD={full['max_drawdown_pct']:.2f}% "
                f"testPF={tes['profit_factor']:.3f} kelly/2={full['half_kelly_pct']:.2f}%",
                flush=True,
            )

    pair_df = pd.DataFrame(pair_rows)

    print("\n## Core 3-pair books by exit (0.5% per pair)\n", flush=True)
    book_rows = []
    book_pnls: dict[str, dict[str, pd.Series]] = {}
    for name in EXIT_VARIANTS:
        pnls = {}
        tds = []
        for symbol in CORE:
            eq, trades, _ = _run(prepared_cache[(symbol, name)], cfg, symbol, 0.5)
            pnls[symbol] = _daily_pnl(eq)
            tds.append(trades.assign(symbol=symbol) if not trades.empty else trades)
        eq, trades, m = _book(pnls, tds, cfg)
        book_pnls[name] = pnls
        p, b = realized_payoff_ratio(trades)
        f_star = kelly_fraction(p, b)
        row = _metrics_row(
            m,
            {
                "variant": name,
                "kelly": f_star,
                "half_kelly_pct": 100.0 * f_star / 2.0,
                "payoff_b": b,
            },
        )
        book_rows.append(row)
        print(
            f"  {name:20} n={m.trades:4} PF={m.profit_factor:.3f} ret={m.return_pct:.1f}% "
            f"year={m.yearly_return_mean:.2%} DD={m.max_drawdown_pct:.2f}% "
            f"CAGR={_cagr(m.return_pct, m.years):.2%} halfK={100*f_star/2:.2f}%",
            flush=True,
        )
    book_df = pd.DataFrame(book_rows)
    best_name = book_df.sort_values(["profit_factor", "return_pct"], ascending=False).iloc[0]["variant"]
    print(f"\nBest exit by PF: {best_name}", flush=True)

    print("\n## Size to DD budget on best exit (core 3)\n", flush=True)
    size_rows = []
    for risk in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
        pnls = {}
        tds = []
        for symbol in CORE:
            eq, trades, _ = _run(prepared_cache[(symbol, best_name)], cfg, symbol, risk)
            pnls[symbol] = _daily_pnl(eq)
            tds.append(trades.assign(symbol=symbol) if not trades.empty else trades)
        _, trades, m = _book(pnls, tds, cfg)
        p, b = realized_payoff_ratio(trades)
        row = _metrics_row(
            m,
            {"risk_pct": risk, "variant": best_name, "kelly": kelly_fraction(p, b), "payoff_b": b},
        )
        size_rows.append(row)
        print(
            f"  risk {risk:.1f}%  n={m.trades:4} ret={m.return_pct:.1f}% year={m.yearly_return_mean:.2%} "
            f"CAGR={_cagr(m.return_pct, m.years):.2%} DD={m.max_drawdown_pct:.2f}% PF={m.profit_factor:.3f}",
            flush=True,
        )
    size_df = pd.DataFrame(size_rows)
    dd15 = size_df[size_df.max_drawdown_pct <= 15.0]
    dd20 = size_df[size_df.max_drawdown_pct <= 20.0]
    pick15 = dd15.sort_values("risk_pct").iloc[-1] if len(dd15) else size_df.iloc[0]
    pick20 = dd20.sort_values("risk_pct").iloc[-1] if len(dd20) else size_df.iloc[0]

    print("\n## EURUSD size ladder on best EURUSD exit\n", flush=True)
    eur_full = pair_df[(pair_df.symbol == "EURUSD") & (pair_df.split == "full")]
    eur_best = eur_full.sort_values(["profit_factor", "return_pct"], ascending=False).iloc[0]["variant"]
    eur_size = []
    for risk in (0.5, 1.0, 2.0, 3.0, 4.0, 5.0):
        _, trades, m = _run(prepared_cache[("EURUSD", eur_best)], cfg, "EURUSD", risk)
        p, b = realized_payoff_ratio(trades)
        row = _metrics_row(m, {"risk_pct": risk, "variant": eur_best, "kelly": kelly_fraction(p, b)})
        eur_size.append(row)
        print(
            f"  EUR {risk:.1f}% n={m.trades} ret={m.return_pct:.1f}% year={m.yearly_return_mean:.2%} "
            f"CAGR={_cagr(m.return_pct, m.years):.2%} DD={m.max_drawdown_pct:.2f}% PF={m.profit_factor:.3f}",
            flush=True,
        )
    eur_size_df = pd.DataFrame(eur_size)

    print("\n## Satellite: engulfing mean-reversion (range ADX) + best core Donchian\n", flush=True)
    sat_pnls = dict(book_pnls[best_name])
    sat_tds = []
    sat_pair = []
    for symbol in CORE:
        h4 = frames[symbol]
        prepared = EngulfingRvolStrategy(EngulfingParams(require_range=True)).prepare(h4)
        eq, trades, m = _run(prepared, cfg, symbol, 0.5)
        sat_pair.append(_metrics_row(m, {"symbol": symbol, "strategy": "engulfing_range"}))
        print(
            f"  engulf {symbol} n={m.trades} PF={m.profit_factor:.3f} ret={m.return_pct:.1f}% "
            f"DD={m.max_drawdown_pct:.2f}%",
            flush=True,
        )
        if m.profit_factor >= 1.0:
            sat_pnls[f"{symbol}_engulf"] = _daily_pnl(eq)
            sat_tds.append(trades.assign(symbol=f"{symbol}_engulf") if not trades.empty else trades)
    # rebuild donchian trades for combo
    core_tds = []
    for symbol in CORE:
        _, trades, _ = _run(prepared_cache[(symbol, best_name)], cfg, symbol, 0.5)
        core_tds.append(trades.assign(symbol=symbol) if not trades.empty else trades)
    combo_eq, combo_tr, combo_m = _book(sat_pnls, core_tds + sat_tds, cfg)
    print(
        f"  COMBO n={combo_m.trades} PF={combo_m.profit_factor:.3f} ret={combo_m.return_pct:.1f}% "
        f"year={combo_m.yearly_return_mean:.2%} DD={combo_m.max_drawdown_pct:.2f}%",
        flush=True,
    )

    payload = {
        "best_core_exit": best_name,
        "best_eur_exit": eur_best,
        "pair_exits": pair_df.to_dict(orient="records"),
        "core_books": book_df.to_dict(orient="records"),
        "core_size": size_df.to_dict(orient="records"),
        "eur_size": eur_size_df.to_dict(orient="records"),
        "dd15": pick15.to_dict(),
        "dd20": pick20.to_dict(),
        "satellite_pairs": sat_pair,
        "satellite_combo": _metrics_row(combo_m, {"variant": f"{best_name}+engulf_pf>=1"}),
        "note": (
            "Kill Zone / M5 not tested: no M5 CSV and those filters cut trades. "
            "Checklist targets are not guarantees."
        ),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    pair_df.to_csv(OUT / "upside_pair_exits.csv", index=False)
    book_df.to_csv(OUT / "upside_core_books.csv", index=False)
    size_df.to_csv(OUT / "upside_core_size.csv", index=False)
    (OUT / "upside.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    lines = [
        "# Upside without cutting trades",
        "",
        f"Best core exit: **{best_name}**",
        f"Best EURUSD exit: **{eur_best}**",
        "",
        "## Core 3-pair exit books (0.5% risk)",
        "",
        book_df[
            ["variant", "trades", "profit_factor", "return_pct", "yearly_mean", "cagr", "max_drawdown_pct", "sharpe", "avg_r"]
        ].to_string(index=False),
        "",
        "## Core size ladder",
        "",
        size_df[["risk_pct", "trades", "return_pct", "yearly_mean", "cagr", "max_drawdown_pct", "profit_factor"]].to_string(
            index=False
        ),
        "",
        f"Largest risk with DD<=15%: {pick15['risk_pct']}% -> yearly mean {pick15['yearly_mean']:.2%}, CAGR {pick15['cagr']:.2%}, DD {pick15['max_drawdown_pct']:.2f}%",
        f"Largest risk with DD<=20%: {pick20['risk_pct']}% -> yearly mean {pick20['yearly_mean']:.2%}, CAGR {pick20['cagr']:.2%}, DD {pick20['max_drawdown_pct']:.2f}%",
        "",
        "Kill Zone / M5 confluence was not applied: it reduces trade count and M5 history is not on disk.",
        "Targets are a checklist, not a guarantee.",
        "",
    ]
    (OUT / "upside.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUT / 'upside.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
