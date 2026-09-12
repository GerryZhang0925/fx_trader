"""Does a 10-point confidence score raise return via lot scaling?"""

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
from strategy.cores.donchian.backtest.optimize_donchian import TEST_END, TRAIN_END  # noqa: E402
from feed.pairs import pip_size  # noqa: E402
from account.settings import engine_from_config, load_config  # noqa: E402
from account.backtest.run_portfolio import _daily_pnl  # noqa: E402
from strategy.cores.donchian.confidence import apply_confidence  # noqa: E402
from strategy.cores.donchian import DonchianParams, DonchianStrategy  # noqa: E402

PARAMS = ROOT / "params"
DATA = ROOT / "data"
OUT = ROOT / "reports"
FOCUS = ["EURUSD", "USDCAD", "USDJPY", "GBPUSD"]
CORE = ["USDCAD", "USDJPY", "GBPUSD"]


def _cagr(return_pct: float, years: float) -> float:
    if years <= 0:
        return 0.0
    total = 1.0 + return_pct / 100.0
    if total <= 0:
        return -1.0
    return float(total ** (1.0 / years) - 1.0)


def _load_params(symbol: str, cfg: dict) -> DonchianParams:
    path = PARAMS / f"{symbol.lower()}_donchian.json"
    fallback = {**cfg.get("donchian", {}), **(cfg.get("portfolio", {}).get("donchian") or {})}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        return DonchianParams.from_dict(data.get("params") or fallback)
    return DonchianParams.from_dict(fallback)


def _run(prepared: pd.DataFrame, cfg: dict, symbol: str, risk_pct: float, mask=None):
    frame = prepared if mask is None else prepared.loc[mask]
    engine = engine_from_config(cfg, pip_size=pip_size(symbol), risk_pct=risk_pct)
    eq, trades = run_backtest(frame, engine)
    m = compute_metrics(eq, trades, cfg.get("initial_equity", 100000))
    return eq, trades, m


def _row(m, extra: dict) -> dict:
    return {
        **extra,
        "trades": m.trades,
        "win_rate": m.win_rate,
        "avg_r": m.avg_r,
        "profit_factor": m.profit_factor,
        "return_pct": m.return_pct,
        "yearly_mean": m.yearly_return_mean,
        "cagr": _cagr(m.return_pct, m.years),
        "max_drawdown_pct": m.max_drawdown_pct,
        "sharpe": m.sharpe,
    }


def _book(pnls: dict[str, pd.Series], trades_list: list[pd.DataFrame], cfg: dict):
    initial = float(cfg.get("initial_equity", 100000))
    pnl_sum = pd.concat(pnls, axis=1).fillna(0.0).sum(axis=1)
    eq = (initial + pnl_sum.cumsum()).rename("equity")
    trades = pd.concat([t for t in trades_list if not t.empty], ignore_index=True) if trades_list else pd.DataFrame()
    if not trades.empty and "exit_time" in trades.columns:
        trades = trades.sort_values("exit_time")
    return compute_metrics(eq, trades, initial)


def _only(scored: pd.DataFrame, grade: str) -> pd.DataFrame:
    out = scored.copy()
    out.loc[out["grade"] != grade, "signal"] = 0
    out["risk_mult"] = 1.0
    return out


def main() -> int:
    cfg = load_config(None)
    grade_rows = []
    dist_rows = []
    size_rows = []
    books = []

    scored_cache = {}
    for symbol in FOCUS:
        h4 = load_csv(DATA / f"{symbol.lower()}_h4.csv")
        prepared = DonchianStrategy(_load_params(symbol, cfg)).prepare(h4)
        scored = apply_confidence(prepared, symbol=symbol)
        scored_cache[symbol] = scored
        fired = scored[scored["signal"] != 0]
        dist = fired["grade"].value_counts().to_dict()
        dist_rows.append(
            {
                "symbol": symbol,
                "signals": int(len(fired)),
                "A+": int(dist.get("A+", 0)),
                "B": int(dist.get("B", 0)),
                "C": int(dist.get("C", 0)),
                "mean_score": float(fired["confidence"].mean()) if len(fired) else 0.0,
            }
        )
        print(
            f"{symbol} signals={len(fired)} A+={dist.get('A+',0)} B={dist.get('B',0)} "
            f"C={dist.get('C',0)} mean={fired['confidence'].mean():.2f}",
            flush=True,
        )
        train_mask = h4.index < TRAIN_END
        test_mask = (h4.index >= TRAIN_END) & (h4.index < TEST_END)
        for grade in ("A+", "B", "C"):
            sliced = _only(scored, grade)
            for split, mask in (("full", None), ("train", train_mask), ("test", test_mask)):
                _, _, m = _run(sliced, cfg, symbol, 1.0, mask)
                grade_rows.append(_row(m, {"symbol": symbol, "grade": grade, "split": split}))
            full = grade_rows[-3]
            tes = grade_rows[-1]
            print(
                f"  {grade:3} n={full['trades']:4} PF={full['profit_factor']:.3f} avgR={full['avg_r']:.3f} "
                f"ret={full['return_pct']:.1f}% testPF={tes['profit_factor']:.3f}",
                flush=True,
            )

        variants = {
            "flat_1pct": scored.assign(risk_mult=1.0),
            "scale_keep_c": scored,
            "skip_c": apply_confidence(prepared, symbol=symbol, skip_c=True),
        }
        for vname, frame in variants.items():
            _, _, m = _run(frame, cfg, symbol, 1.0)
            size_rows.append(_row(m, {"symbol": symbol, "variant": vname}))
            print(
                f"  {vname:14} n={m.trades:4} PF={m.profit_factor:.3f} ret={m.return_pct:.1f}% "
                f"year={m.yearly_return_mean:.2%} DD={m.max_drawdown_pct:.2f}%",
                flush=True,
            )

    print("\n## Core 3-pair books at 1% base\n", flush=True)
    for vname, skip in (("flat_1pct", None), ("scale_keep_c", False), ("skip_c", True)):
        pnls = {}
        tds = []
        for symbol in CORE:
            prepared = scored_cache[symbol]
            if skip is None:
                frame = prepared.assign(risk_mult=1.0)
            elif skip:
                raw = DonchianStrategy(_load_params(symbol, cfg)).prepare(
                    load_csv(DATA / f"{symbol.lower()}_h4.csv")
                )
                frame = apply_confidence(raw, symbol=symbol, skip_c=True)
            else:
                frame = prepared
            eq, trades, _ = _run(frame, cfg, symbol, 1.0)
            pnls[symbol] = _daily_pnl(eq)
            tds.append(trades.assign(symbol=symbol) if not trades.empty else trades)
        m = _book(pnls, tds, cfg)
        books.append(_row(m, {"variant": vname}))
        print(
            f"  {vname:14} n={m.trades:4} PF={m.profit_factor:.3f} ret={m.return_pct:.1f}% "
            f"year={m.yearly_return_mean:.2%} CAGR={_cagr(m.return_pct, m.years):.2%} "
            f"DD={m.max_drawdown_pct:.2f}%",
            flush=True,
        )

    OUT.mkdir(parents=True, exist_ok=True)
    dist_df = pd.DataFrame(dist_rows)
    grade_df = pd.DataFrame(grade_rows)
    size_df = pd.DataFrame(size_rows)
    book_df = pd.DataFrame(books)
    dist_df.to_csv(OUT / "confidence_dist.csv", index=False)
    grade_df.to_csv(OUT / "confidence_by_grade.csv", index=False)
    size_df.to_csv(OUT / "confidence_sizing.csv", index=False)
    book_df.to_csv(OUT / "confidence_books.csv", index=False)
    payload = {
        "distribution": dist_df.to_dict(orient="records"),
        "by_grade": grade_df.to_dict(orient="records"),
        "sizing": size_df.to_dict(orient="records"),
        "core_books": book_df.to_dict(orient="records"),
        "note": "Kill Zone scored on H4 bar overlap. Targets are a checklist, not a guarantee.",
    }
    (OUT / "confidence.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    lines = [
        "# Confidence sizing",
        "",
        dist_df.to_string(index=False),
        "",
        "## Equal-size expectancy by grade (1% risk)",
        "",
        grade_df[grade_df.split == "full"][
            ["symbol", "grade", "trades", "profit_factor", "avg_r", "return_pct"]
        ].to_string(index=False),
        "",
        "## Core books",
        "",
        book_df.to_string(index=False),
        "",
        "Targets are a checklist, not a guarantee.",
        "",
    ]
    (OUT / "confidence.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {OUT / 'confidence.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
