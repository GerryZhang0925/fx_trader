"""EURUSD H1 range fade: train <2021, lockbox 2021-2025 once. No grid."""

from __future__ import annotations

import pandas as pd

from paths import KIT_DIR, boot

boot()

from account.backtest.run_portfolio import _daily_pnl, _load_pair_params, _portfolio_params  # noqa: E402
from account.engine import run_backtest  # noqa: E402
from account.metrics import compute_metrics  # noqa: E402
from account.settings import engine_from_config, kit_data_dir, kit_params_dir, load_config  # noqa: E402
from feed.loader import load_csv  # noqa: E402
from feed.pairs import pip_size  # noqa: E402
from strategy.cores.donchian import DonchianStrategy  # noqa: E402
from strategy.cores.donchian.backtest.eval_regime import CORE  # noqa: E402
from strategy.cores.donchian.backtest.optimize_donchian import TEST_END, TRAIN_END  # noqa: E402
from strategy.cores.eurusd_h1_range import EurusdH1RangeStrategy  # noqa: E402

ROOT = KIT_DIR
SYMBOL = "EURUSD"
RISK_PCT = 1.0
DD_CAP = 15.0


def _run(prepared, cfg, symbol, risk, mask):
    frame = prepared.loc[mask]
    engine = engine_from_config(cfg, pip_size=pip_size(symbol), risk_pct=risk)
    eq, trades = run_backtest(frame, engine)
    return eq, trades, compute_metrics(eq, trades, engine.initial_equity)


def _print_m(label: str, m) -> None:
    print(
        f"  {label:28} n={m.trades:4} PF={m.profit_factor:.3f} avgR={m.avg_r:.3f} "
        f"year={m.yearly_return_mean:.2%} CAGR={m.cagr:.2%} DD={m.max_drawdown_pct:.2f}% "
        f"Sharpe={m.sharpe:.2f}",
        flush=True,
    )


def _book(pnls: dict[str, pd.Series], trades_list: list[pd.DataFrame], initial: float):
    pnl_sum = pd.concat(pnls, axis=1).fillna(0.0).sum(axis=1)
    eq = (initial + pnl_sum.cumsum()).rename("equity")
    tds = [t for t in trades_list if t is not None and not t.empty]
    trades = pd.concat(tds, ignore_index=True) if tds else pd.DataFrame()
    if not trades.empty and "exit_time" in trades.columns:
        trades = trades.sort_values("exit_time")
    return compute_metrics(eq, trades, initial), pnl_sum


def main() -> int:
    cfg = load_config()
    data_dir = kit_data_dir(cfg)
    path = data_dir / f"{SYMBOL.lower()}_h1.csv"
    if not path.exists():
        print(f"missing {path}")
        return 1
    h1 = load_csv(path)
    sat = EurusdH1RangeStrategy().prepare(h1)
    train = sat.index < TRAIN_END
    lockbox = (sat.index >= TRAIN_END) & (sat.index < TEST_END)
    print(f"{SYMBOL} H1 range fade  risk={RISK_PCT}%  bars={len(sat)}", flush=True)
    sat_lock_eq = None
    sat_lock_trades = None
    for name, mask in (("train<2021", train), ("lockbox 2021-2025", lockbox)):
        eq, trades, m = _run(sat, cfg, SYMBOL, RISK_PCT, mask)
        _print_m(name, m)
        if not trades.empty:
            print(f"    exits {trades['exit_reason'].value_counts().to_dict()}", flush=True)
        if name.startswith("lockbox"):
            sat_lock_eq, sat_lock_trades = eq, trades
    print("lockbox is a single measurement. Do not retune.", flush=True)

    if sat_lock_eq is None:
        return 0
    print("\n## Add-on vs frozen H4 book (lockbox 2021-2025)\n", flush=True)
    initial = float(cfg.get("initial_equity", 100000))
    h4_risk = float((cfg.get("portfolio") or {}).get("risk_pct_per_pair", 5.0))
    fallback = _portfolio_params(cfg)
    params_dir = kit_params_dir(cfg)
    h4_pnls: dict[str, pd.Series] = {}
    h4_trades: list[pd.DataFrame] = []
    for symbol in CORE:
        params, _ = _load_pair_params(symbol, params_dir, fallback)
        h4 = load_csv(data_dir / f"{symbol.lower()}_h4.csv")
        prepared = DonchianStrategy(params).prepare(h4)
        pair_lock = (prepared.index >= TRAIN_END) & (prepared.index < TEST_END)
        eq, trades, m = _run(prepared, cfg, symbol, h4_risk, pair_lock)
        _print_m(f"H4 {symbol} 5%", m)
        h4_pnls[symbol] = _daily_pnl(eq)
        if not trades.empty:
            h4_trades.append(trades.assign(symbol=symbol))
    h4_m, h4_pnl = _book(h4_pnls, h4_trades, initial)
    _print_m("H4 book 5%x3", h4_m)

    sat_pnl = _daily_pnl(sat_lock_eq)
    combined_m, _ = _book({**h4_pnls, SYMBOL: sat_pnl}, h4_trades + [sat_lock_trades], initial)
    _print_m("H4 + EURUSD 1%", combined_m)

    aligned = pd.concat({"h4": h4_pnl, "sat": sat_pnl}, axis=1).dropna()
    corr = float(aligned["h4"].corr(aligned["sat"])) if len(aligned) > 3 else float("nan")
    print(f"  daily pnl corr H4 vs satellite: {corr:.3f}", flush=True)

    worse = (
        combined_m.yearly_return_mean < h4_m.yearly_return_mean
        or combined_m.cagr < h4_m.cagr
        or combined_m.max_drawdown_pct > h4_m.max_drawdown_pct
        or combined_m.max_drawdown_pct > DD_CAP
        or (corr == corr and corr >= 0.7)
    )
    print(
        "DROP satellite"
        if worse
        else "add-on did not worsen H4 yearly/CAGR/DD and DD<=15; keep 1% for ops review",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
