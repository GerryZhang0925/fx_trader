"""Backtest metrics. Sharpe/Sortino use daily returns (Rf=0, MAR=0), not bar returns."""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from .risk import kelly_fraction, kelly_growth, realized_payoff_ratio

TRADING_DAYS = 252.0


@dataclass
class Metrics:
    trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    net_pnl: float
    return_pct: float
    cagr: float
    max_drawdown_pct: float
    sharpe: float
    sortino: float
    calmar: float
    ulcer_index: float
    avg_r: float
    yearly_return_mean: float
    yearly_return_std: float
    years: float
    start: str
    end: str
    final_equity: float
    kelly_trade: float = 0.0
    kelly_growth: float = 0.0
    half_kelly_trade: float = 0.0
    half_kelly_growth: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _daily_equity(equity: pd.Series) -> pd.Series:
    s = equity.copy()
    idx = pd.DatetimeIndex(s.index)
    if idx.tz is None:
        idx = idx.tz_localize("UTC")
    else:
        idx = idx.tz_convert("UTC")
    s.index = idx
    return s.resample("1D").last().dropna()


def _cagr(final: float, initial: float, years: float) -> float:
    if years <= 0 or initial <= 0 or final <= 0:
        return 0.0
    return float((final / initial) ** (1.0 / years) - 1.0)


def _max_dd(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity - peak) / peak
    return float(-dd.min() * 100.0) if len(dd) else 0.0


def _ulcer(equity: pd.Series) -> float:
    peak = equity.cummax().replace(0, np.nan)
    dd = ((peak - equity) / peak).clip(lower=0).fillna(0.0)
    return float(np.sqrt((dd ** 2).mean()) * 100.0) if len(dd) else 0.0


def _daily_stats(equity: pd.Series) -> tuple[float, float, float]:
    """Return (sharpe, sortino, kelly_growth) from daily pct changes, Rf=MAR=0."""
    daily = _daily_equity(equity).pct_change().dropna()
    if daily.empty:
        return 0.0, 0.0, 0.0
    mu = float(daily.mean())
    sig = float(daily.std(ddof=0))
    sharpe = float(np.sqrt(TRADING_DAYS) * mu / sig) if sig > 0 else 0.0
    downside = daily.clip(upper=0.0)
    dsig = float(np.sqrt((downside ** 2).mean()))
    if dsig > 0:
        sortino = float(np.sqrt(TRADING_DAYS) * mu / dsig)
    else:
        sortino = sharpe if mu > 0 else 0.0
    growth = kelly_growth(mu, sig)
    return sharpe, sortino, growth


def compute_metrics(
    equity: pd.Series,
    trades: pd.DataFrame,
    initial_equity: float,
) -> Metrics:
    empty = Metrics(
        trades=0, wins=0, losses=0, win_rate=0, profit_factor=0,
        net_pnl=0, return_pct=0, cagr=0, max_drawdown_pct=0,
        sharpe=0, sortino=0, calmar=0, ulcer_index=0, avg_r=0,
        yearly_return_mean=0, yearly_return_std=0, years=0,
        start="", end="", final_equity=initial_equity,
    )
    if equity.empty:
        return empty
    pnl = trades["pnl"] if not trades.empty else pd.Series(dtype=float)
    wins = int((pnl > 0).sum()) if len(pnl) else 0
    losses = int((pnl < 0).sum()) if len(pnl) else 0
    gross_win = float(pnl[pnl > 0].sum()) if wins else 0.0
    gross_loss = float(-pnl[pnl < 0].sum()) if losses else 0.0
    pf = gross_win / gross_loss if gross_loss > 0 else (float("inf") if gross_win > 0 else 0.0)
    years = (equity.index[-1] - equity.index[0]).total_seconds() / (365.25 * 24 * 3600)
    years = float(max(years, 0.0))
    by_year = equity.groupby(pd.DatetimeIndex(equity.index).year)
    year_ends = by_year.last()
    rets = []
    prev = initial_equity
    for _, end_eq in year_ends.items():
        if prev > 0:
            rets.append(float(end_eq / prev - 1.0))
        prev = float(end_eq)
    yearly = pd.Series(rets)
    mdd = _max_dd(equity)
    cagr = _cagr(float(equity.iloc[-1]), initial_equity, years)
    calmar = float(cagr / (mdd / 100.0)) if mdd > 0 else 0.0
    sharpe, sortino, k_growth = _daily_stats(equity)
    p, b = realized_payoff_ratio(trades)
    k_trade = kelly_fraction(p, b)
    return Metrics(
        trades=int(len(pnl)),
        wins=wins,
        losses=losses,
        win_rate=float(wins / len(pnl)) if len(pnl) else 0.0,
        profit_factor=float(pf) if np.isfinite(pf) else 999.0,
        net_pnl=float(equity.iloc[-1] - initial_equity),
        return_pct=float((equity.iloc[-1] / initial_equity - 1.0) * 100.0),
        cagr=cagr,
        max_drawdown_pct=mdd,
        sharpe=sharpe,
        sortino=sortino,
        calmar=calmar,
        ulcer_index=_ulcer(equity),
        avg_r=float(trades["r"].mean()) if not trades.empty else 0.0,
        yearly_return_mean=float(yearly.mean()) if len(yearly) else 0.0,
        yearly_return_std=float(yearly.std(ddof=0)) if len(yearly) else 0.0,
        years=years,
        start=str(equity.index[0]),
        end=str(equity.index[-1]),
        final_equity=float(equity.iloc[-1]),
        kelly_trade=k_trade,
        kelly_growth=k_growth,
        half_kelly_trade=k_trade / 2.0,
        half_kelly_growth=k_growth / 2.0,
    )


def checklist(metrics: Metrics, targets: dict) -> dict[str, dict]:
    rows = {
        "years": {
            "value": metrics.years,
            "target": targets.get("min_years", 5),
            "pass": metrics.years >= targets.get("min_years", 5),
        },
        "profit_factor": {
            "value": metrics.profit_factor,
            "target": targets.get("profit_factor", 1.3),
            "pass": metrics.profit_factor >= targets.get("profit_factor", 1.3),
        },
        "max_drawdown_pct": {
            "value": metrics.max_drawdown_pct,
            "target": targets.get("max_drawdown_pct", 20.0),
            "pass": metrics.max_drawdown_pct <= targets.get("max_drawdown_pct", 20.0),
        },
        "sharpe": {
            "value": metrics.sharpe,
            "target": targets.get("sharpe", 1.0),
            "pass": metrics.sharpe >= targets.get("sharpe", 1.0),
        },
        "trades": {
            "value": metrics.trades,
            "target": targets.get("min_trades", 1000),
            "pass": metrics.trades >= targets.get("min_trades", 1000),
        },
    }
    return rows


def format_report(metrics: Metrics, checks: dict, name: str) -> str:
    lines = [
        f"# {name}",
        "",
        "Targets are a research checklist, not a performance guarantee.",
        "",
        f"- Period: {metrics.start} -> {metrics.end} ({metrics.years:.2f} years)",
        f"- Trades: {metrics.trades} (win rate {metrics.win_rate:.1%}, avg R {metrics.avg_r:.2f})",
        f"- Net PnL: {metrics.net_pnl:.2f} ({metrics.return_pct:.2f}%)",
        f"- CAGR: {metrics.cagr:.2%}",
        f"- Final equity: {metrics.final_equity:.2f}",
        f"- Profit factor: {metrics.profit_factor:.3f}",
        f"- Max drawdown: {metrics.max_drawdown_pct:.2f}%",
        f"- Sharpe (daily, ann.): {metrics.sharpe:.2f}",
        f"- Sortino (MAR=0): {metrics.sortino:.2f}",
        f"- Calmar: {metrics.calmar:.2f}",
        f"- Ulcer index: {metrics.ulcer_index:.2f}",
        f"- Kelly trade / half: {metrics.kelly_trade:.2%} / {metrics.half_kelly_trade:.2%}",
        f"- Kelly growth / half: {metrics.kelly_growth:.2%} / {metrics.half_kelly_growth:.2%}",
        f"- Yearly return mean/std: {metrics.yearly_return_mean:.2%} / {metrics.yearly_return_std:.2%}",
        "",
        "## Checklist",
        "",
    ]
    for key, row in checks.items():
        mark = "PASS" if row["pass"] else "FAIL"
        lines.append(f"- [{mark}] {key}: {row['value']:.4g} (target {row['target']})")
    return "\n".join(lines) + "\n"
