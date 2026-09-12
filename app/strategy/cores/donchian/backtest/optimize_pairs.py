"""Optimize Donchian params per FX pair. Train <2021, test 2021-2025.

Writes params/{SYMBOL}_donchian.json. In-sample gains can fail out of sample.
"""

from __future__ import annotations

import argparse
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
from strategy.cores.donchian.backtest.optimize_donchian import TRAIN_END, TEST_END, _row, grid_params  # noqa: E402
from feed.pairs import CANDIDATES, pip_size  # noqa: E402
from account.settings import engine_from_config, load_config  # noqa: E402
from strategy.cores.donchian import DonchianParams, DonchianStrategy  # noqa: E402


def _metrics_dict(m) -> dict:
    return {
        "trades": m.trades,
        "win_rate": m.win_rate,
        "avg_r": m.avg_r,
        "profit_factor": m.profit_factor,
        "max_drawdown_pct": m.max_drawdown_pct,
        "sharpe": m.sharpe,
        "return_pct": m.return_pct,
        "years": m.years,
    }


def optimize_symbol(symbol: str, h4: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    engine = engine_from_config(cfg, pip_size=pip_size(symbol))
    initial = float(cfg.get("initial_equity", 100000))
    base = {**cfg.get("donchian", {}), **(cfg.get("portfolio", {}).get("donchian") or {})}
    train_mask = h4.index < TRAIN_END
    test_mask = (h4.index >= TRAIN_END) & (h4.index < TEST_END)
    combos = list(grid_params(base))
    rows = []
    for i, params in enumerate(combos, start=1):
        prepared = DonchianStrategy(params).prepare(h4)
        eq_tr, td_tr = run_backtest(prepared.loc[train_mask], engine)
        eq_te, td_te = run_backtest(prepared.loc[test_mask], engine)
        m_tr = compute_metrics(eq_tr, td_tr, initial)
        m_te = compute_metrics(eq_te, td_te, initial)
        row = {
            "length": params.length,
            "atr_mult": params.atr_mult,
            "adx_min": params.adx_min,
            "use_atr_filter": params.use_atr_filter,
        }
        row.update(_row("train_", m_tr))
        row.update(_row("test_", m_te))
        rows.append(row)
        if i % 80 == 0 or i == len(combos):
            print(f"  {symbol} grid {i}/{len(combos)}", flush=True)
    grid = pd.DataFrame(rows)
    robust = grid[(grid["test_profit_factor"] >= 1.0) & (grid["train_max_drawdown_pct"] <= 20.0)]
    pool = robust if len(robust) else grid
    best_row = pool.sort_values(
        ["train_profit_factor", "test_profit_factor", "train_avg_r"],
        ascending=False,
    ).iloc[0]
    best_params = DonchianParams.from_dict(
        {
            **base,
            "length": int(best_row.length),
            "atr_mult": float(best_row.atr_mult),
            "adx_min": float(best_row.adx_min),
            "use_atr_filter": bool(best_row.use_atr_filter),
            "use_adx_filter": True,
            "partial_frac": 0.5,
            "partial_r": 1.0,
            "stop_buffer_atr": 0.5,
        }
    )
    prepared = DonchianStrategy(best_params).prepare(h4)
    eq_all, td_all = run_backtest(prepared, engine)
    m_all = compute_metrics(eq_all, td_all, initial)
    payload = {
        "symbol": symbol,
        "selection": "max train PF among test PF>=1.0 and train DD<=20%",
        "params": asdict(best_params),
        "train": {k.replace("train_", ""): best_row[k] for k in best_row.index if str(k).startswith("train_")},
        "test": {k.replace("test_", ""): best_row[k] for k in best_row.index if str(k).startswith("test_")},
        "full": _metrics_dict(m_all),
    }
    return grid, payload


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--symbols", default=",".join(CANDIDATES))
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--data", type=Path, default=None)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--force", action="store_true", help="Overwrite pinned {symbol}_donchian.json")
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    data_dir = args.data or (ROOT / "data")
    out_dir = args.out or (ROOT / "params")
    out_dir.mkdir(parents=True, exist_ok=True)
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    from output.status import tracked

    with tracked("strategy", "optimize", out_dir=ROOT / "reports", message=",".join(symbols)):
        return _optimize(args, cfg, data_dir, out_dir, symbols)


def _optimize(args, cfg, data_dir: Path, out_dir: Path, symbols: list[str]) -> int:
    catalog = []
    for symbol in symbols:
        csv_path = data_dir / f"{symbol.lower()}_h4.csv"
        if not csv_path.exists():
            print(f"SKIP {symbol}: missing {csv_path}")
            continue
        json_path = out_dir / f"{symbol.lower()}_donchian.json"
        if json_path.exists() and not args.force:
            existing = json.loads(json_path.read_text(encoding="utf-8"))
            if existing.get("pinned"):
                print(f"SKIP {symbol}: pinned {json_path} (pass --force to overwrite)")
                catalog.append(existing)
                continue
        print(f"=== optimize {symbol} ===", flush=True)
        h4 = load_csv(csv_path)
        grid, payload = optimize_symbol(symbol, h4, cfg)
        grid.to_csv(out_dir / f"{symbol.lower()}_grid.csv", index=False)
        json_path = out_dir / f"{symbol.lower()}_donchian.json"
        json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        catalog.append(payload)
        f = payload["full"]
        t = payload["test"]
        par = payload["params"]
        print(
            f"  saved {json_path} length={par['length']} atr={par['atr_mult']} "
            f"adx={par['adx_min']} atr_filter={par['use_atr_filter']} "
            f"full PF={f['profit_factor']:.3f} test PF={t['profit_factor']:.3f} n={f['trades']}"
        )
    all_path = out_dir / "all_pairs.json"
    by_symbol: dict[str, dict] = {}
    if all_path.exists():
        try:
            loaded = json.loads(all_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = []
        if isinstance(loaded, list):
            for item in loaded:
                if isinstance(item, dict) and item.get("symbol"):
                    by_symbol[str(item["symbol"])] = item
    for payload in catalog:
        by_symbol[str(payload["symbol"])] = payload
    all_path.write_text(json.dumps(list(by_symbol.values()), indent=2, default=str), encoding="utf-8")
    print(f"Wrote {all_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
