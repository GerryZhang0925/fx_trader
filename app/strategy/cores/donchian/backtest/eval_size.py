"""Adopted-book risk ladder. Yearly mean vs DD when per-pair risk is cut below 5.5%.

Stops already use H4 high/low. Reported max DD is close MTM, so a lower size is a
wick buffer, not a change to fill rules. Checklist, not a guarantee.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from paths import KIT_DIR, boot

boot()

from account.engine import run_backtest  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from account.settings import engine_from_config, load_config  # noqa: E402
from account.backtest.run_portfolio import _daily_pnl, _load_pair_params, _portfolio_params  # noqa: E402
from feed.loader import load_csv  # noqa: E402
from feed.pairs import pip_size  # noqa: E402
from strategy.cores.donchian import DonchianStrategy  # noqa: E402

ROOT = KIT_DIR
CORE = ["USDCAD", "USDJPY", "GBPUSD"]
UNIFORMS = [3.0, 3.5, 4.0, 4.5, 4.75, 5.0, 5.25, 5.5]
MIXED = [
    {"USDCAD": 5.5, "USDJPY": 5.5, "GBPUSD": 5.5},
    {"USDCAD": 5.0, "USDJPY": 5.0, "GBPUSD": 5.0},
    {"USDCAD": 4.75, "USDJPY": 4.75, "GBPUSD": 4.75},
    {"USDCAD": 5.5, "USDJPY": 4.5, "GBPUSD": 5.0},
    {"USDCAD": 5.5, "USDJPY": 4.0, "GBPUSD": 4.5},
    {"USDCAD": 5.5, "USDJPY": 5.0, "GBPUSD": 4.0},
    {"USDCAD": 5.0, "USDJPY": 5.5, "GBPUSD": 4.0},
    {"USDCAD": 5.0, "USDJPY": 5.0, "GBPUSD": 5.0, "USDCHF": 1.5},
    {"USDCAD": 5.0, "USDJPY": 5.0, "GBPUSD": 5.0, "USDCHF": 2.0},
    {"USDCAD": 5.0, "USDJPY": 5.0, "GBPUSD": 5.0, "USDCHF": 3.0},
    {"USDCAD": 5.0, "USDJPY": 5.0, "GBPUSD": 5.0, "USDCHF": 4.0},
    {"USDCAD": 5.0, "USDJPY": 5.0, "GBPUSD": 5.0, "USDCHF": 5.0},
    {"USDCAD": 5.5, "USDJPY": 5.5, "GBPUSD": 5.5, "USDCHF": 5.5},
    {"USDCAD": 4.75, "USDJPY": 4.75, "GBPUSD": 4.75, "USDCHF": 2.0},
    {"USDCAD": 5.5, "USDJPY": 5.0, "GBPUSD": 4.5, "USDCHF": 1.5},
]


def _label(risks: dict[str, float]) -> str:
    return " ".join(f"{s}={risks[s]:g}%" for s in sorted(risks))


def main() -> int:
    cfg = load_config()
    initial = float(cfg.get("initial_equity", 100000))
    data_dir = ROOT / "data"
    params_dir = ROOT / "params"
    fallback = _portfolio_params(cfg)
    need = sorted({s for book in MIXED for s in book} | set(CORE))
    prepared: dict[str, pd.DataFrame] = {}
    for symbol in need:
        path = data_dir / f"{symbol.lower()}_h4.csv"
        params, _ = _load_pair_params(symbol, params_dir, fallback)
        print(f"prepare {symbol} length={params.length} atr={params.atr_mult} adx={params.adx_min}", flush=True)
        prepared[symbol] = DonchianStrategy(params).prepare(load_csv(path))

    cache: dict[tuple[str, float], tuple[pd.Series, pd.DataFrame]] = {}

    def run_pair(symbol: str, risk: float):
        key = (symbol, round(float(risk), 4))
        if key not in cache:
            engine = engine_from_config(cfg, pip_size=pip_size(symbol), risk_pct=risk)
            eq, trades = run_backtest(prepared[symbol], engine)
            cache[key] = (_daily_pnl(eq), trades.assign(symbol=symbol) if not trades.empty else trades)
        return cache[key]

    def run_book(risks: dict[str, float]):
        pnls = {}
        tds = []
        for symbol, risk in risks.items():
            pnl, trades = run_pair(symbol, risk)
            pnls[symbol] = pnl
            if trades is not None and not trades.empty:
                tds.append(trades)
        pnl_sum = pd.concat(pnls, axis=1).fillna(0.0).sum(axis=1)
        eq = (initial + pnl_sum.cumsum()).rename("equity")
        trades = pd.concat(tds, ignore_index=True) if tds else pd.DataFrame()
        if not trades.empty and "exit_time" in trades.columns:
            trades = trades.sort_values("exit_time")
        m = compute_metrics(eq, trades, initial)
        return {
            "book": _label(risks),
            "pairs": ",".join(risks),
            **{f"r_{s.lower()}": risks.get(s) for s in ("USDCAD", "USDJPY", "GBPUSD", "USDCHF")},
            "trades": m.trades,
            "yearly_mean": m.yearly_return_mean,
            "yearly_std": m.yearly_return_std,
            "cagr": m.cagr,
            "max_drawdown_pct": m.max_drawdown_pct,
            "sharpe": m.sharpe,
            "calmar": m.calmar,
            "profit_factor": m.profit_factor,
            "return_pct": m.return_pct,
            "year_ge_20": m.yearly_return_mean >= 0.20,
            "dd_le_15": m.max_drawdown_pct <= 15.0,
        }

    rows = []
    print("\n## Uniform core 3-pair\n", flush=True)
    for risk in UNIFORMS:
        row = run_book({s: risk for s in CORE})
        rows.append(row)
        print(
            f"  {risk:4.2f}%  year={row['yearly_mean']:.2%} CAGR={row['cagr']:.2%} "
            f"DD={row['max_drawdown_pct']:.2f}% Sharpe={row['sharpe']:.2f} n={row['trades']}",
            flush=True,
        )

    print("\n## Mixed books\n", flush=True)
    seen = {rows[i]["book"] for i in range(len(rows))}
    for risks in MIXED:
        lab = _label(risks)
        if lab in seen:
            continue
        seen.add(lab)
        row = run_book(risks)
        rows.append(row)
        print(
            f"  {lab}  year={row['yearly_mean']:.2%} CAGR={row['cagr']:.2%} "
            f"DD={row['max_drawdown_pct']:.2f}% Sharpe={row['sharpe']:.2f}",
            flush=True,
        )

    df = pd.DataFrame(rows)
    out = ROOT / "reports"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "size_ladder.csv", index=False)

    ok = df[(df.year_ge_20) & (df.dd_le_15)].copy()
    ok["avg_core"] = ok[["r_usdcad", "r_usdjpy", "r_gbpusd"]].mean(axis=1)
    pick = None
    if len(ok):
        # Lowest average core risk that still clears 20% yearly and 15% DD.
        pick = ok.sort_values(["avg_core", "max_drawdown_pct", "yearly_mean"], ascending=[True, True, False]).iloc[0]
        print("\n## Pick (year>=20%, DD<=15%, lowest avg core risk)\n", flush=True)
        print(pick.to_string(), flush=True)
    else:
        print("\nNo book with yearly mean >=20% and DD<=15%.", flush=True)

    payload = {
        "rows": df.to_dict(orient="records"),
        "pick": pick.to_dict() if pick is not None else None,
        "note": (
            "Stops use H4 high/low. Reported max DD is close MTM. "
            "Independent-path 100k book. Checklist, not a guarantee."
        ),
    }
    (out / "size_ladder.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out / 'size_ladder.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
