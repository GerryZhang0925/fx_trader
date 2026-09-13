"""Donchian portfolio: configurable pairs and per-pair risk, then a shared-equity book.

Default book is USDCAD+USDJPY+GBPUSD at 5.0% risk each (`portfolio` in config.yaml).
Override with --pairs / --risk, or risk_pct_by_pair in YAML.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from paths import KIT_DIR, boot

boot()
ROOT = KIT_DIR  # kit root

from feed.loader import load_csv  # noqa: E402
from account.engine import run_backtest  # noqa: E402
from account.metrics import compute_metrics, format_report, checklist  # noqa: E402
from feed.pairs import CANDIDATES, KEEP_BOTH, RECOMMENDED, pip_size  # noqa: E402
from output.reporting import envelope, notify, write_json  # noqa: E402
from account.settings import engine_from_config, load_config  # noqa: E402
from strategy.cores.donchian import DonchianParams, DonchianStrategy  # noqa: E402


def _daily_close(df: pd.DataFrame) -> pd.Series:
    s = df["close"].copy()
    s.index = pd.DatetimeIndex(s.index).tz_convert("UTC")
    return s.resample("1D").last().dropna()


def _daily_pnl(equity: pd.Series) -> pd.Series:
    eq = equity.copy()
    eq.index = pd.DatetimeIndex(eq.index).tz_convert("UTC")
    return eq.resample("1D").last().dropna().diff()


def _portfolio_params(cfg: dict) -> DonchianParams:
    port = cfg.get("portfolio", {})
    merged = {**cfg.get("donchian", {}), **(port.get("donchian") or {})}
    return DonchianParams.from_dict(merged)


def _load_pair_params(symbol: str, params_dir: Path | None, fallback: DonchianParams) -> tuple[DonchianParams, dict]:
    extra = {}
    if params_dir is None:
        return fallback, extra
    path = params_dir / f"{symbol.lower()}_donchian.json"
    if not path.exists():
        return fallback, extra
    data = json.loads(path.read_text(encoding="utf-8"))
    extra = {
        "train_profit_factor": (data.get("train") or {}).get("profit_factor"),
        "test_profit_factor": (data.get("test") or {}).get("profit_factor"),
    }
    return DonchianParams.from_dict(data.get("params") or {}), extra


def select_pairs(rows: pd.DataFrame, corr: pd.DataFrame, min_pf: float, drop_below: float, max_corr: float) -> list[str]:
    ok = rows[rows["profit_factor"] >= drop_below].copy()
    preferred = ok[ok["profit_factor"] >= min_pf]
    pool = preferred if len(preferred) else ok
    names = list(pool.sort_values("profit_factor", ascending=False)["symbol"])
    selected: list[str] = []
    for name in names:
        conflict = None
        for kept in selected:
            pair = frozenset({name, kept})
            if pair in KEEP_BOTH:
                continue
            c = corr.loc[name, kept] if name in corr.index and kept in corr.columns else 0.0
            if pd.notna(c) and abs(c) >= max_corr:
                conflict = kept
                break
        if conflict is None:
            selected.append(name)
        else:
            # keep the higher-PF name already sorted, so skip the new one
            pass
    return selected


def risk_pct_for(symbol: str, port: dict, override: float | None = None) -> float:
    if override is not None:
        return float(override)
    by_pair = port.get("risk_pct_by_pair") or {}
    if symbol in by_pair and by_pair[symbol] is not None:
        return float(by_pair[symbol])
    return float(port.get("risk_pct_per_pair", 5.0))


def parse_symbols(raw: str | None, port: dict) -> list[str]:
    if raw:
        return [s.strip().upper() for s in raw.split(",") if s.strip()]
    return [s.upper() for s in port.get("candidates", CANDIDATES)]


def run_symbol(symbol: str, data_dir: Path, params: DonchianParams, cfg: dict, risk_pct: float):
    path = data_dir / f"{symbol.lower()}_h4.csv"
    h4 = load_csv(path)
    prepared = DonchianStrategy(params).prepare(h4)
    engine = engine_from_config(cfg, pip_size=pip_size(symbol), risk_pct=risk_pct)
    eq, trades = run_backtest(prepared, engine)
    metrics = compute_metrics(eq, trades, cfg.get("initial_equity", 100000))
    return h4, eq, trades, metrics


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Multi-pair Donchian portfolio research")
    p.add_argument("--config", type=Path, default=None)
    p.add_argument("--data", type=Path, default=None)
    p.add_argument("--params-dir", type=Path, default=None, help="Folder of {symbol}_donchian.json")
    p.add_argument("--shared", action="store_true", help="Ignore per-pair JSON and use portfolio.donchian")
    p.add_argument("--pairs", default=None, help="Comma list, e.g. USDCAD,USDJPY,GBPUSD")
    p.add_argument("--risk", type=float, default=None, help="Risk %% of equity per pair (overrides config)")
    p.add_argument("--select", action="store_true", help="Drop pairs by PF / correlation instead of a fixed book")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)
    cfg = load_config(args.config)
    port = cfg.get("portfolio", {})
    data_dir = args.data or (ROOT / "data")
    out_dir = args.out or (ROOT / "reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    symbols = parse_symbols(args.pairs, port)
    from output.status import tracked

    with tracked("account", "portfolio", out_dir=out_dir, message=",".join(symbols)):
        return _run_book(args, cfg, port, data_dir, out_dir, symbols)


def _run_book(args, cfg, port, data_dir: Path, out_dir: Path, symbols: list[str]) -> int:
    min_pf = float(port.get("min_pair_pf", 1.2))
    drop_below = float(port.get("exclude_below_pf", 1.0))
    max_corr = float(port.get("max_corr", 0.7))
    fixed_book = (not args.select) and bool(port.get("fixed_book", True))
    fallback = _portfolio_params(cfg)
    params_dir = None if args.shared else (args.params_dir or (ROOT / "params"))
    initial = float(cfg.get("initial_equity", 100000))

    closes = {}
    results = []
    books = {}
    used_params = {}
    used_risk = {}
    for symbol in symbols:
        path = data_dir / f"{symbol.lower()}_h4.csv"
        if not path.exists():
            print(f"SKIP {symbol}: missing {path}")
            continue
        params, extra = _load_pair_params(symbol, params_dir, fallback)
        risk_pct = risk_pct_for(symbol, port, args.risk)
        used_params[symbol] = params
        used_risk[symbol] = risk_pct
        print(
            f"Backtest {symbol} risk={risk_pct:g}% length={params.length} atr={params.atr_mult} "
            f"adx={params.adx_min} atr_filter={params.use_atr_filter}",
            flush=True,
        )
        h4, eq, trades, metrics = run_symbol(symbol, data_dir, params, cfg, risk_pct)
        closes[symbol] = _daily_close(h4)
        books[symbol] = {"equity": eq, "trades": trades, "metrics": metrics}
        results.append(
            {
                "symbol": symbol,
                "length": params.length,
                "atr_mult": params.atr_mult,
                "adx_min": params.adx_min,
                "use_atr_filter": params.use_atr_filter,
                "risk_pct": risk_pct,
                "trades": metrics.trades,
                "win_rate": metrics.win_rate,
                "avg_r": metrics.avg_r,
                "profit_factor": metrics.profit_factor,
                "train_profit_factor": extra.get("train_profit_factor"),
                "test_profit_factor": extra.get("test_profit_factor"),
                "max_drawdown_pct": metrics.max_drawdown_pct,
                "sharpe": metrics.sharpe,
                "return_pct": metrics.return_pct,
                "years": metrics.years,
            }
        )

    rows = pd.DataFrame(results)
    if rows.empty:
        raise SystemExit("No pair CSVs found. Run: python -m feed.download")

    px = pd.concat(closes, axis=1).dropna(how="any")
    price_corr = px.pct_change().dropna().corr()
    strat_pnl = {s: _daily_pnl(books[s]["equity"]) for s in books}
    strat_corr = pd.concat(strat_pnl, axis=1).dropna(how="any").corr()

    if fixed_book:
        selected = [s for s in symbols if s in books]
    else:
        selected = select_pairs(rows, price_corr, min_pf, drop_below, max_corr)
        if not selected:
            selected = list(rows.sort_values("profit_factor", ascending=False)["symbol"].head(1))

    pnl_sum = pd.concat([strat_pnl[s] for s in selected], axis=1).fillna(0.0).sum(axis=1)
    port_eq = (initial + pnl_sum.cumsum()).rename("equity")
    port_trades = pd.concat(
        [books[s]["trades"].assign(symbol=s) for s in selected if not books[s]["trades"].empty],
        ignore_index=True,
    )
    if not port_trades.empty:
        port_trades = port_trades.sort_values("exit_time")
    port_metrics = compute_metrics(port_eq, port_trades, initial)

    targets = dict(cfg.get("targets", {}))
    targets["min_trades"] = int(port.get("portfolio_min_trades", 600))
    targets["sharpe"] = float(port.get("portfolio_sharpe", 0.6))
    targets["max_drawdown_pct"] = float(port.get("portfolio_max_dd", 15.0))
    checks = checklist(port_metrics, targets)
    report = format_report(port_metrics, checks, "donchian_portfolio")

    risk_note = ", ".join(f"{s} {used_risk[s]:g}%" for s in selected)
    if fixed_book:
        sel_head = "## Selection (fixed book from portfolio.candidates / --pairs)"
    else:
        sel_head = (
            f"## Selection (drop PF < {drop_below}, prefer PF >= {min_pf}, "
            f"|corr| < {max_corr} except EUR+GBP)"
        )
    extra = [
        "",
        "## Pair universe",
        "",
        rows.sort_values("symbol").to_string(index=False),
        "",
        sel_head,
        "",
        f"Selected: {', '.join(selected)}",
        f"Risk per pair: {risk_note}",
        "",
        "## Price return correlation (daily close)",
        "",
        price_corr.round(3).to_string(),
        "",
        "## Strategy daily-PnL correlation",
        "",
        strat_corr.round(3).to_string(),
        "",
        "Independent-path approximation on a shared 100k book. "
        "Change candidates / risk_pct_per_pair in config.yaml, or pass --pairs / --risk.",
        "Targets are a checklist, not a guarantee.",
        "",
    ]
    full_report = report + "\n".join(extra)
    print(full_report)
    (out_dir / "portfolio.md").write_text(full_report, encoding="utf-8")
    rows.to_csv(out_dir / "portfolio_pairs.csv", index=False)
    price_corr.to_csv(out_dir / "portfolio_price_corr.csv")
    strat_corr.to_csv(out_dir / "portfolio_strategy_corr.csv")
    if not port_trades.empty:
        port_trades.to_csv(out_dir / "portfolio_trades.csv", index=False)
    port_eq.to_csv(out_dir / "portfolio_equity.csv", header=True)
    payload = {
        "params_mode": "shared" if args.shared else "per-pair-json-if-present",
        "params": {
            s: {
                "length": p.length,
                "atr_mult": p.atr_mult,
                "adx_min": p.adx_min,
                "use_atr_filter": p.use_atr_filter,
            }
            for s, p in used_params.items()
        },
        "risk_pct_per_pair": used_risk,
        "fixed_book": fixed_book,
        "selected": selected,
        "pairs": rows.to_dict(orient="records"),
        "portfolio": port_metrics.to_dict(),
        "checklist": checks,
        "recommended": RECOMMENDED,
    }
    wrapped = envelope(payload)
    write_json(out_dir / "portfolio.json", wrapped)
    hooked = notify(cfg, wrapped)
    if hooked:
        print(f"Webhook delivery: {hooked}")
    print(f"Wrote {out_dir / 'portfolio.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
