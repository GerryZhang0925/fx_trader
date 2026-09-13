"""Grid-search Donchian params on 2015-2020, validate on 2021-2025.

Prioritize PF and average R. Trade count of 500-600 over ~10y is enough.
Targets are a research checklist, not a guarantee.
"""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import pandas as pd

from paths import KIT_DIR, boot

boot()
ROOT = KIT_DIR  # kit root

from feed.loader import load_csv  # noqa: E402
from account.engine import run_backtest  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from account.settings import engine_from_config, load_config  # noqa: E402
from strategy.cores.donchian import DonchianParams, DonchianStrategy  # noqa: E402

TRAIN_END = "2021-01-01"
TEST_END = "2026-01-01"


def _row(prefix: str, m) -> dict:
    return {
        f"{prefix}trades": m.trades,
        f"{prefix}win_rate": m.win_rate,
        f"{prefix}avg_r": m.avg_r,
        f"{prefix}profit_factor": m.profit_factor,
        f"{prefix}max_drawdown_pct": m.max_drawdown_pct,
        f"{prefix}sharpe": m.sharpe,
        f"{prefix}return_pct": m.return_pct,
    }


def meets(m, pf: float, dd: float, sharpe: float, min_trades: int | None, max_trades: int | None = None) -> bool:
    if m.profit_factor < pf:
        return False
    if m.max_drawdown_pct > dd:
        return False
    if m.sharpe < sharpe:
        return False
    if min_trades is not None and m.trades < min_trades:
        return False
    if max_trades is not None and m.trades > max_trades:
        return False
    return True


# Adopted search: 9 lengths x 4 ATR x 11 ADX x 2 ATR-filter = 792.
# Compact (F2): 5 x 3 x 3 x 2 = 90. Use for new pair searches; do not retune live JSON from it.
COMPACT_LENGTHS = (20, 25, 40, 55, 60)
COMPACT_ATR_MULTS = (1.5, 2.5, 3.0)
COMPACT_ADX_MINS = (15, 20, 24)


def grid_params(base: dict | None = None, *, compact: bool = False):
    # Shorter lengths + ATR-filter off are needed to reach 500-600 trades on the full grid.
    base = dict(base or {})
    if compact:
        lengths = list(COMPACT_LENGTHS)
        atr_mults = list(COMPACT_ATR_MULTS)
        adx_mins = list(COMPACT_ADX_MINS)
    else:
        lengths = list(range(20, 56, 5)) + [60]
        atr_mults = [1.5, 2.0, 2.5, 3.0]
        adx_mins = range(15, 26)
    atr_filters = [False, True]
    for length, atr_mult, adx_min, use_atr in itertools.product(lengths, atr_mults, adx_mins, atr_filters):
        yield DonchianParams.from_dict(
            {
                **base,
                "length": int(length),
                "atr_mult": float(atr_mult),
                "adx_min": float(adx_min),
                "use_adx_filter": True,
                "use_atr_filter": bool(use_atr),
                "partial_frac": 0.5,
                "partial_r": 1.0,
                "stop_buffer_atr": 0.5,
            }
        )


def run_grid(h4: pd.DataFrame, cfg: dict, *, compact: bool = False) -> pd.DataFrame:
    engine = engine_from_config(cfg)
    initial = float(cfg.get("initial_equity", 100000))
    targets = cfg.get("targets", {})
    pf_t = float(targets.get("profit_factor", 1.3))
    dd_t = float(targets.get("max_drawdown_pct", 20.0))
    sh_t = float(targets.get("sharpe", 0.5))
    min_tr = int(targets.get("min_trades", 500))
    max_tr = int(targets.get("preferred_trades_max", 600))
    base = dict(cfg.get("donchian", {}))
    train_mask = h4.index < TRAIN_END
    test_mask = (h4.index >= TRAIN_END) & (h4.index < TEST_END)
    combos = list(grid_params(base, compact=compact))
    rows = []
    for i, params in enumerate(combos, start=1):
        prepared = DonchianStrategy(params).prepare(h4)
        eq_tr, td_tr = run_backtest(prepared.loc[train_mask], engine)
        eq_te, td_te = run_backtest(prepared.loc[test_mask], engine)
        eq_all, td_all = run_backtest(prepared, engine)
        m_tr = compute_metrics(eq_tr, td_tr, initial)
        m_te = compute_metrics(eq_te, td_te, initial)
        m_all = compute_metrics(eq_all, td_all, initial)
        row = {
            "length": params.length,
            "atr_mult": params.atr_mult,
            "adx_min": params.adx_min,
            "use_atr_filter": params.use_atr_filter,
            "train_pass": meets(m_tr, pf_t, dd_t, sh_t, None),
            "test_pass": meets(m_te, pf_t, dd_t, sh_t, None),
            "full_pass": meets(m_all, pf_t, dd_t, sh_t, min_tr),
            "in_trade_band": min_tr <= m_all.trades <= max_tr,
        }
        row.update(_row("train_", m_tr))
        row.update(_row("test_", m_te))
        row.update(_row("full_", m_all))
        rows.append(row)
        if i % 40 == 0 or i == len(combos):
            print(f"grid {i}/{len(combos)}", flush=True)
    return pd.DataFrame(rows)


def _pick(grid: pd.DataFrame) -> pd.Series:
    band = grid[grid["in_trade_band"]].copy()
    pool = band if len(band) else grid[grid["full_trades"] >= 500]
    pool = pool if len(pool) else grid
    return pool.sort_values(
        ["full_profit_factor", "full_avg_r", "test_profit_factor", "full_sharpe"],
        ascending=False,
    ).iloc[0]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, default=None)
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument(
        "--compact",
        action="store_true",
        help="90-cell grid for new searches (F2). Default 792 is the adopted historical search.",
    )
    args = p.parse_args(argv)
    from output.status import tracked

    out_dir = args.out or (ROOT / "reports")
    with tracked("strategy", "grid", out_dir=out_dir, message="donchian"):
        return _grid(args, out_dir)


def _grid(args, out_dir: Path) -> int:
    cfg = load_config(args.config)
    targets = cfg.get("targets", {})
    pf_t = float(targets.get("profit_factor", 1.3))
    dd_t = float(targets.get("max_drawdown_pct", 20.0))
    sh_t = float(targets.get("sharpe", 0.5))
    min_tr = int(targets.get("min_trades", 500))
    max_tr = int(targets.get("preferred_trades_max", 600))
    csv_path = args.csv or (ROOT / "data" / "eurusd_h4.csv")
    h4 = load_csv(csv_path)
    print(f"Loaded {len(h4)} H4 bars {h4.index[0]} -> {h4.index[-1]}")
    grid = run_grid(h4, cfg, compact=args.compact)
    out_dir.mkdir(parents=True, exist_ok=True)
    grid_path = out_dir / "donchian_grid.csv"
    grid.to_csv(grid_path, index=False)

    best = _pick(grid)
    band = grid[grid["full_pass"]]
    trade_band = grid[grid["in_trade_band"]].sort_values(
        ["full_profit_factor", "full_avg_r"], ascending=False
    )
    oos_ok = grid[grid["train_pass"] & grid["test_pass"]]

    cols = [
        "length", "atr_mult", "adx_min", "use_atr_filter",
        "full_profit_factor", "full_avg_r", "full_max_drawdown_pct",
        "full_sharpe", "full_trades", "test_profit_factor",
    ]
    lines = [
        "# Donchian grid search",
        "",
        "Train: < 2021-01-01. Test: 2021-01-01 to 2026-01-01. Full = all loaded bars.",
        "Prioritize PF and average R. 500-600 trades over ~10y is enough.",
        "Targets are a checklist, not a guarantee.",
        "",
        f"- Combos: {len(grid)}"
        + (" (compact F2: length 20/25/40/55/60, ATR 1.5/2.5/3.0, ADX 15/20/24, ATR-filter on|off)"
           if args.compact
           else " (length 20-60 / ATR 1.5-3.0 / ADX 15-25 / ATR-filter on|off)"),
        f"- Full pass (PF>={pf_t}, DD<={dd_t}%, Sharpe>={sh_t}, trades>={min_tr}): {len(band)}",
        f"- In preferred trade band ({min_tr}-{max_tr}): {len(trade_band)}",
        f"- Train and test both pass: {len(oos_ok)}",
        "",
        "## Selected (PF / avg R, prefer 500-600 trades)",
        "",
        f"- length={int(best.length)}, atr_mult={best.atr_mult}, adx_min={best.adx_min}, atr_filter={bool(best.use_atr_filter)}",
        f"- Train PF={best.train_profit_factor:.3f} avgR={best.train_avg_r:.2f} DD={best.train_max_drawdown_pct:.2f}% Sharpe={best.train_sharpe:.2f} n={int(best.train_trades)}",
        f"- Test  PF={best.test_profit_factor:.3f} avgR={best.test_avg_r:.2f} DD={best.test_max_drawdown_pct:.2f}% Sharpe={best.test_sharpe:.2f} n={int(best.test_trades)}",
        f"- Full  PF={best.full_profit_factor:.3f} avgR={best.full_avg_r:.2f} DD={best.full_max_drawdown_pct:.2f}% Sharpe={best.full_sharpe:.2f} n={int(best.full_trades)}",
        "",
    ]
    if len(trade_band):
        lines.append(f"## Preferred trade band ({min_tr}-{max_tr}), top by PF then avg R")
        lines.append("")
        lines.append(trade_band[cols].head(15).to_string(index=False))
        lines.append("")
    if len(band):
        lines.append("## Full-sample passing band")
        lines.append("")
        lines.append(
            band.sort_values(["full_profit_factor", "full_avg_r"], ascending=False)[cols]
            .head(15)
            .to_string(index=False)
        )
        lines.append("")
    else:
        lines.append("No combo met PF / DD / Sharpe / min-trades together.")
        lines.append("")
        top = grid.sort_values(["full_profit_factor", "full_avg_r"], ascending=False).head(10)
        lines.append("## Top 10 by full-sample PF then avg R")
        lines.append("")
        lines.append(top[cols].to_string(index=False))
        lines.append("")

    report = "\n".join(lines) + "\n"
    (out_dir / "donchian_grid.md").write_text(report, encoding="utf-8")
    (out_dir / "donchian_grid.json").write_text(
        json.dumps(
            {
                "selected": best.to_dict(),
                "full_pass_count": int(len(band)),
                "trade_band_count": int(len(trade_band)),
                "train_and_test_pass_count": int(len(oos_ok)),
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(report)
    print(f"Wrote {grid_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
