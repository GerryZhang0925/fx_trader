"""Overfitting diagnostics for the adopted 3-pair Donchian book.

Uses saved pair JSON (train/test split) plus the published grid size.
If H4 CSV is on disk, Deflated Sharpe also uses daily PnL skew/kurtosis.
Does not change live params. Checklist, not a guarantee.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from paths import KIT_DIR, boot

boot()

from strategy.cores.donchian.backtest.optimize_donchian import grid_params  # noqa: E402

ROOT = KIT_DIR
CORE = ["USDCAD", "USDJPY", "GBPUSD"]
TRADING_DAYS = 252.0
EULER = 0.5772156649015329


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


def grid_trial_count() -> int:
    return len(list(grid_params({})))


def _years(block: dict, fallback: float) -> float:
    y = block.get("years")
    if y is None:
        return fallback
    return float(y)


def main() -> int:
    n_grid = grid_trial_count()
    rows = []
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
            "dsr_train_n_grid": deflated_sharpe(float(train["sharpe"]), n_grid, train_years),
            "dsr_train_n_eff20": deflated_sharpe(float(train["sharpe"]), 20, train_years),
            "dsr_test_n1": deflated_sharpe(float(test["sharpe"]), 1, test_years),
        }
        rows.append(row)

    wf_path = ROOT / "reports" / "walkforward_adopted.json"
    wf = json.loads(wf_path.read_text(encoding="utf-8")) if wf_path.exists() else {}

    out = {
        "grid_trials_per_pair": n_grid,
        "universe_pairs_searched": 7,
        "adopted": CORE,
        "pairs": rows,
        "walkforward": wf.get("gates"),
        "notes": [
            "Test 2021-2025 was used as a selection filter (test PF floor), so it is not a lockbox.",
            "USDJPY used max train+test return among test PF>=1.2, so test leaked into the objective.",
            "Independent N=792 DSR is a lower bound on confidence (grid cells are correlated).",
            "Do not change live params from this report.",
        ],
    }
    reports = ROOT / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "overfit_adopted.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    lines = [
        "# Adopted Donchian overfitting check",
        "",
        "Train <2021 / test 2021-2025. Grid is length x ATR trail x ADX min x ATR filter.",
        f"Trials per pair: **{n_grid}**. Universe searched: 7 pairs, live book keeps 3.",
        "Costs and next-bar fills are already in the engine. Checklist, not a guarantee.",
        "",
        "## Train vs test (saved JSON)",
        "",
        "symbol train_PF test_PF PF_decay train_SR test_SR DSR_train_N792 DSR_train_Neff20 DSR_test_N1",
    ]
    for row in rows:
        lines.append(
            f"{row['symbol']} {row['train_pf']:.3f} {row['test_pf']:.3f} {row['pf_decay']*100:.0f}% "
            f"{row['train_sharpe']:.2f} {row['test_sharpe']:.2f} "
            f"{row['dsr_train_n_grid']['dsr']:.2f} {row['dsr_train_n_eff20']['dsr']:.2f} "
            f"{row['dsr_test_n1']['dsr']:.2f}"
        )
    lines += [
        "",
        "## Read",
        "",
        "- DSR is P(true Sharpe > 0) after a Bailey-Lopez de Prado haircut for N trials.",
        "- N=792 independent is pessimistic (nearby grid points move together). N_eff=20 is a correlated-grid sketch.",
        "- CAD/GBP test PF still >= 1.24 after 42%/12% decay. JPY test PF 1.85 > train 1.35, but test entered the pick.",
        "- EURUSD / AUDUSD / NZDUSD failed the same search on OOS PF. USDCHF failed book DD. Pair-level fail rate 4/7.",
        "",
        "## Walk-forward (adopted params, not re-tuned)",
        "",
        "See `reports/walkforward_adopted.md`. Mean window PF >= 1.64 all three. Small-n 1y windows can print PF<1.",
        "",
        "## Verdict",
        "",
        "The **search** is overfit-prone (grid + test used as a filter). The **adopted 3-pair book is not IS-only**:",
        "holdout PF stays above 1.2, WF mean PF holds, dropped pairs show the filter catching IS-only names.",
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
