"""Overfitting diagnostics for the adopted 3-pair Donchian book.

Uses saved pair JSON plus saved per-cell grids when present.
Does not change live params. Checklist, not a guarantee.

Official CSCV PBO needs per-cell return paths; grids only have train/test
summary metrics, so PBO here is a train/test split proxy.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

from paths import KIT_DIR, boot

boot()

from feed.pairs import CANDIDATES  # noqa: E402
from strategy.cores.donchian.backtest.optimize_donchian import grid_params  # noqa: E402
from strategy.cores.donchian.backtest.select_grid import (  # noqa: E402
    cell_params,
    match_cell,
    select_row,
    select_row_legacy_jpy_return,
    pf_floor_for,
)

ROOT = KIT_DIR
CORE = ["USDCAD", "USDJPY", "GBPUSD"]
TRADING_DAYS = 252.0
EULER = 0.5772156649015329
GRID_DIMS = ("length", "atr_mult", "adx_min", "use_atr_filter")
LIVE_JPY = {"length": 25, "atr_mult": 1.5, "adx_min": 15.0, "use_atr_filter": False}


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    p = min(max(p, 1e-12), 1.0 - 1e-12)
    lo, hi = -20.0, 20.0
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        if _norm_cdf(mid) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def expected_max_z(n_trials: int) -> float:
    n = max(int(n_trials), 1)
    if n <= 1:
        return 0.0
    z1 = _norm_ppf(1.0 - 1.0 / n)
    z2 = _norm_ppf(1.0 - math.exp(-1.0) / n)
    return (1.0 - EULER) * z1 + EULER * z2


def deflated_sharpe(
    sharpe_ann: float,
    n_trials: int,
    years: float,
    skew: float = 0.0,
    kurt: float = 3.0,
) -> dict:
    """Bailey-Lopez de Prado DSR on daily Sharpe (annualized input)."""
    t_obs = max(years * TRADING_DAYS, 2.0)
    sr = float(sharpe_ann) / math.sqrt(TRADING_DAYS)
    var = (1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr) / (t_obs - 1.0)
    var = max(var, 1e-18)
    sr_star = math.sqrt(var) * expected_max_z(n_trials)
    z = (sr - sr_star) / math.sqrt(var)
    return {
        "n_trials": int(n_trials),
        "years": float(years),
        "sharpe_ann": float(sharpe_ann),
        "sr_daily": sr,
        "sr_star_daily": sr_star,
        "z": z,
        "dsr": _norm_cdf(z),
    }


def grid_trial_count(*, compact: bool = False) -> int:
    return len(list(grid_params({}, compact=compact)))


def _years(block: dict, fallback: float) -> float:
    y = block.get("years")
    if y is None:
        return fallback
    return float(y)


def _finite_corr(a: pd.Series, b: pd.Series) -> float | None:
    if len(a) < 3:
        return None
    if float(a.std(ddof=0)) < 1e-12 or float(b.std(ddof=0)) < 1e-12:
        return None
    r = float(a.corr(b))
    if not math.isfinite(r):
        return None
    return r


def n_eff_from_rho(n_levels: int, rho: float) -> float:
    n = max(int(n_levels), 1)
    rho = max(min(float(rho), 0.999), -0.999)
    if rho <= 0:
        return float(n)
    return max(1.0, n * (1.0 - rho) / (1.0 + rho))


def axis_rho(grid: pd.DataFrame, metric: str, dim: str) -> dict:
    others = [c for c in GRID_DIMS if c != dim]
    n_levels = int(grid[dim].nunique())
    rhos: list[float] = []
    if n_levels <= 2:
        left: list[float] = []
        right: list[float] = []
        for _, g in grid.groupby(list(others), dropna=False):
            ordered = g.sort_values(dim)
            if len(ordered) < 2:
                continue
            left.append(float(ordered[metric].iloc[0]))
            right.append(float(ordered[metric].iloc[-1]))
        a = pd.Series(left, dtype=float)
        b = pd.Series(right, dtype=float)
        if len(a) >= 3 and float((a - b).abs().max()) < 1e-12:
            rhos.append(1.0)
        else:
            r = _finite_corr(a, b)
            if r is not None:
                rhos.append(r)
    else:
        for _, g in grid.groupby(list(others), dropna=False):
            s = g.sort_values(dim)[metric].astype(float).reset_index(drop=True)
            if len(s) < 3:
                continue
            a = s.iloc[:-1].reset_index(drop=True)
            b = s.iloc[1:].reset_index(drop=True)
            if float((a - b).abs().max()) < 1e-12:
                rhos.append(1.0)
                continue
            r = _finite_corr(a, b)
            if r is not None:
                rhos.append(r)
    rho = float(sum(rhos) / len(rhos)) if rhos else 0.0
    return {
        "dim": dim,
        "n_levels": n_levels,
        "rho": rho,
        "n_eff": n_eff_from_rho(n_levels, rho),
        "samples": len(rhos),
    }


def effective_trials(grid: pd.DataFrame, metric: str = "train_sharpe") -> dict:
    """Independent-trial sketch from neighbor correlation of a grid metric."""
    axes = [axis_rho(grid, metric, dim) for dim in GRID_DIMS]
    product = 1.0
    for ax in axes:
        product *= float(ax["n_eff"])
    n_cells = int(len(grid))
    n_eff = min(max(product, 1.0), float(n_cells))
    return {
        "metric": metric,
        "n_cells": n_cells,
        "n_eff": n_eff,
        "axes": axes,
    }


def pbo_proxy(grid: pd.DataFrame, selected: pd.Series, *, oos: str = "test_sharpe") -> dict:
    """Train/test analogue of CSCV PBO: 1 if IS pick's OOS metric is below the median."""
    oos_vals = grid[oos].astype(float)
    picked = float(selected[oos])
    median = float(oos_vals.median())
    below = oos_vals < picked
    ties = oos_vals == picked
    rank_pct = float((below.sum() + 0.5 * ties.sum()) / max(len(oos_vals), 1))
    return {
        "oos_metric": oos,
        "selected_oos": picked,
        "median_oos": median,
        "rank_pct": rank_pct,
        "below_median": bool(picked < median),
    }


def _grid_path(symbol: str) -> Path:
    return ROOT / "params" / f"{symbol.lower()}_grid.csv"


def load_pair_grid(symbol: str) -> pd.DataFrame | None:
    path = _grid_path(symbol)
    if not path.exists():
        return None
    return pd.read_csv(path)


def _row_metrics(row: pd.Series) -> dict:
    return {
        **cell_params(row),
        "train_profit_factor": float(row["train_profit_factor"]),
        "test_profit_factor": float(row["test_profit_factor"]),
        "train_return_pct": float(row["train_return_pct"]),
        "test_return_pct": float(row["test_return_pct"]),
        "train_sharpe": float(row["train_sharpe"]),
        "test_sharpe": float(row["test_sharpe"]),
        "train_max_drawdown_pct": float(row["train_max_drawdown_pct"]),
    }


def f3_usdjpy_review(grid: pd.DataFrame) -> dict:
    pin = match_cell(grid, **LIVE_JPY)
    train_only = select_row(grid, test_pf_floor=pf_floor_for("USDJPY"))
    legacy = select_row_legacy_jpy_return(grid)
    pin_params = cell_params(pin)
    f3_params = cell_params(train_only)
    same = pin_params == f3_params
    return {
        "keep_pin": True,
        "same_as_pin": same,
        "reason": (
            "Live JSON stays frozen. Train-only pick still uses 2021-2025 as a PF floor (F1). "
            "Do not bake-off on the 2026 holdout. Future optimize_pairs sorts train-only; "
            "USDJPY remains pinned without --force."
        ),
        "pinned": _row_metrics(pin),
        "train_only": _row_metrics(train_only),
        "legacy_return_pick": _row_metrics(legacy),
        "legacy_matches_pin": cell_params(legacy) == pin_params,
    }


def main() -> int:
    n_grid = grid_trial_count()
    n_compact = grid_trial_count(compact=True)
    rows = []
    grid_rows = []
    pbo_hits = 0
    pbo_n = 0
    for symbol in CORE:
        path = ROOT / "params" / f"{symbol.lower()}_donchian.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        train = data["train"]
        test = data["test"]
        train_years = _years(train, 6.0)
        test_years = _years(test, 5.0)
        train_pf = float(train["profit_factor"])
        test_pf = float(test["profit_factor"])
        row = {
            "symbol": symbol,
            "pinned": bool(data.get("pinned")),
            "selection": data.get("selection"),
            "train_trades": int(float(train["trades"])),
            "test_trades": int(float(test["trades"])),
            "train_pf": train_pf,
            "test_pf": test_pf,
            "pf_decay": (train_pf - test_pf) / train_pf if train_pf else 0.0,
            "train_sharpe": float(train["sharpe"]),
            "test_sharpe": float(test["sharpe"]),
            "train_years": train_years,
            "dsr_train_n_grid": deflated_sharpe(float(train["sharpe"]), n_grid, train_years),
            "dsr_train_n_eff20": deflated_sharpe(float(train["sharpe"]), 20, train_years),
            "dsr_test_n1": deflated_sharpe(float(test["sharpe"]), 1, test_years),
        }
        rows.append(row)

    f3 = None
    missing_grids = []
    for symbol in CANDIDATES:
        grid = load_pair_grid(symbol)
        if grid is None:
            missing_grids.append(symbol)
            continue
        trials = effective_trials(grid)
        selected = select_row(grid, test_pf_floor=pf_floor_for(symbol))
        proxy = pbo_proxy(grid, selected)
        pbo_n += 1
        pbo_hits += int(proxy["below_median"])
        n_eff = int(round(trials["n_eff"]))
        grid_row = {
            "symbol": symbol,
            "n_cells": trials["n_cells"],
            "n_eff": trials["n_eff"],
            "axes": trials["axes"],
            "selected": {**cell_params(selected), **proxy},
            "dsr_train_n_eff": None,
        }
        core = next((r for r in rows if r["symbol"] == symbol), None)
        if core is not None:
            dsr_ne = deflated_sharpe(core["train_sharpe"], max(n_eff, 1), core["train_years"])
            core["n_eff"] = trials["n_eff"]
            core["dsr_train_n_eff"] = dsr_ne
            grid_row["dsr_train_n_eff"] = dsr_ne
        grid_rows.append(grid_row)
        if symbol == "USDJPY":
            f3 = f3_usdjpy_review(grid)

    wf_path = ROOT / "reports" / "walkforward_adopted.json"
    wf = json.loads(wf_path.read_text(encoding="utf-8")) if wf_path.exists() else {}
    pbo_rate = (pbo_hits / pbo_n) if pbo_n else None

    out = {
        "grid_trials_per_pair": n_grid,
        "grid_trials_compact": n_compact,
        "universe_pairs_searched": 7,
        "adopted": CORE,
        "pairs": rows,
        "grid_dsr": grid_rows,
        "pbo_proxy": {
            "method": (
                "Train/test split analogue of CSCV: selected cell (train PF, test PF floor) "
                "vs median test Sharpe. Not official CSCV; grids have no per-cell return paths."
            ),
            "below_median_count": pbo_hits,
            "pairs_with_grid": pbo_n,
            "rate": pbo_rate,
            "adoption_fail_rate": 4 / 7,
        },
        "f3_usdjpy": f3,
        "missing_grids": missing_grids,
        "walkforward": wf.get("gates"),
        "notes": [
            "Test 2021-2025 was used as a selection filter (test PF floor), so it is not a lockbox.",
            "USDJPY live JSON used max train+test return among test PF>=1.2; pin kept (F3).",
            "Independent N=792 DSR is a lower bound on confidence (grid cells are correlated).",
            "N_eff is AR(1) neighbor correlation of train Sharpe along each grid axis.",
            "Future pair searches should pass --compact (90 cells). Do not size on IS Sharpe.",
            "Do not change live params from this report.",
        ],
    }
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "overfit_adopted.json").write_text(
        json.dumps(out, indent=2, default=str), encoding="utf-8"
    )

    lines = [
        "# Adopted Donchian overfitting check",
        "",
        "Train <2021 / test 2021-2025. Grid is length x ATR trail x ADX min x ATR filter.",
        f"Historical search: **{n_grid}** trials/pair. Compact (F2, `--compact`): **{n_compact}**.",
        "Universe searched: 7 pairs, live book keeps 3.",
        "Costs and next-bar fills are already in the engine. Checklist, not a guarantee.",
        "",
        "## Train vs test (saved JSON)",
        "",
        "symbol train_PF test_PF PF_decay train_SR test_SR DSR_N792 DSR_Neff DSR_Neff20 DSR_test_N1",
    ]
    for row in rows:
        n_eff = row.get("n_eff")
        dsr_ne = row.get("dsr_train_n_eff")
        ne_s = f"{n_eff:.1f}" if n_eff is not None else "-"
        dsr_ne_s = f"{dsr_ne['dsr']:.2f}" if dsr_ne else "-"
        lines.append(
            f"{row['symbol']} {row['train_pf']:.3f} {row['test_pf']:.3f} {row['pf_decay']*100:.0f}% "
            f"{row['train_sharpe']:.2f} {row['test_sharpe']:.2f} "
            f"{row['dsr_train_n_grid']['dsr']:.2f} {dsr_ne_s} ({ne_s}) "
            f"{row['dsr_train_n_eff20']['dsr']:.2f} {row['dsr_test_n1']['dsr']:.2f}"
        )
    lines += [
        "",
        "## F2 Grid DSR / PBO proxy",
        "",
        "- DSR is P(true Sharpe > 0) after a Bailey-Lopez de Prado haircut for N trials.",
        "- N=792 independent is pessimistic (nearby grid points move together).",
        "- N_eff comes from lag-1 correlation of train Sharpe along length / ATR / ADX / ATR-filter.",
        "- Official CSCV PBO needs per-cell return series (not in `params/*_grid.csv`). "
        "Proxy: train-PF pick's test Sharpe vs median test Sharpe on the same split.",
        "- Adoption fail rate 4/7 (EURUSD/AUDUSD/NZDUSD test PF, USDCHF book DD) is the "
        "decision-relevant analogue. Median-beat PBO is optimistic when most of a grid is junk.",
        "- Do not size up from IS Sharpe after this search. New pair searches: `--compact`.",
        "",
        "symbol n_eff selected_test_SR median_test_SR rank_pct below_median",
    ]
    for grow in grid_rows:
        sel = grow["selected"]
        lines.append(
            f"{grow['symbol']} {grow['n_eff']:.1f} {sel['selected_oos']:.3f} "
            f"{sel['median_oos']:.3f} {sel['rank_pct']:.3f} {int(sel['below_median'])}"
        )
    if pbo_rate is not None:
        lines.append("")
        lines.append(
            f"Train/test PBO proxy: **{pbo_hits}/{pbo_n} = {pbo_rate:.2f}**. "
            f"Adoption fail rate **4/7 ~= 0.57**."
        )
    if missing_grids:
        lines.append("")
        lines.append("Missing grids (gitignored): " + ", ".join(missing_grids))
    lines += [
        "",
        "## F3 USDJPY pin revisit",
        "",
    ]
    if f3:
        pin = f3["pinned"]
        cand = f3["train_only"]
        lines += [
            "Live pin used max **train+test return** among test PF>=1.2. "
            "F3 selection is max **train PF** among test PF>=1.2 and train DD<=20% (test not in sort).",
            "",
            f"- Pin (live): length={pin['length']} ATR={pin['atr_mult']} ADX={pin['adx_min']:g} "
            f"filter={pin['use_atr_filter']} train PF={pin['train_profit_factor']:.3f} "
            f"test PF={pin['test_profit_factor']:.3f} test ret={pin['test_return_pct']:.1f}%",
            f"- Train-only: length={cand['length']} ATR={cand['atr_mult']} ADX={cand['adx_min']:g} "
            f"filter={cand['use_atr_filter']} train PF={cand['train_profit_factor']:.3f} "
            f"test PF={cand['test_profit_factor']:.3f} test ret={cand['test_return_pct']:.1f}%",
            f"- Legacy return pick matches pin: {f3['legacy_matches_pin']}. Same as pin: {f3['same_as_pin']}.",
            "",
            "**Keep the pin.** " + f3["reason"],
            "Future `optimize_pairs` uses train-only sort; USDJPY JSON stays skipped without `--force`.",
            "Do not compare pin vs train-only on 2026-01..08 (that window already measured the live book).",
            "",
        ]
    else:
        lines.append("USDJPY grid CSV not on disk; F3 candidate not recomputed.")
        lines.append("")
    lines += [
        "## Read",
        "",
        "- CAD/GBP test PF still >= 1.24 after 42%/12% decay. JPY test PF 1.85 > train 1.35, but test entered the live pick.",
        "- EURUSD / AUDUSD / NZDUSD failed the same search on OOS PF. USDCHF failed book DD. Pair-level fail rate 4/7.",
        "",
        "## Walk-forward (adopted params, not re-tuned)",
        "",
        "See `reports/walkforward_adopted.md`. Mean window PF >= 1.64 all three. Small-n 1y windows can print PF<1.",
        "",
        "## Verdict",
        "",
        "The **search** is overfit-prone (792-cell grid + test used as a filter). F2: use `--compact` "
        "and N_eff DSR from saved grids; do not size on IS Sharpe. F3: stop putting test return in the "
        "JPY objective; **live pin unchanged**.",
        "The **adopted 3-pair book is not IS-only**: holdout PF stays above 1.2, WF mean PF holds, "
        "dropped pairs show the filter catching IS-only names.",
        "**Do not change live params.** Do not size up from the 11y 21% yearly figure; that mixes IS and OOS.",
        "",
        "Educational review -- not financial advice.",
        "",
    ]
    (reports / "overfit_adopted.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
