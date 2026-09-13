"""Per-trade risk and daily circuit breakers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class RiskConfig:
    risk_pct: float = 1.0
    max_trades_per_day: int = 2
    max_consecutive_losses: int = 3
    max_daily_loss_r: float = 2.0
    lot_size: float = 100_000.0


@dataclass
class RiskState:
    trades_today: int = 0
    consecutive_losses: int = 0
    daily_r: float = 0.0
    day: date | None = None
    halted_today: bool = False

    def on_new_day(self, d: date) -> None:
        if self.day != d:
            self.day = d
            self.trades_today = 0
            self.daily_r = 0.0
            self.consecutive_losses = 0
            self.halted_today = False

    def can_enter(self, cfg: RiskConfig) -> bool:
        if self.halted_today:
            return False
        if self.trades_today >= cfg.max_trades_per_day:
            return False
        if self.daily_r <= -cfg.max_daily_loss_r:
            return False
        return True

    def register_entry(self) -> None:
        self.trades_today += 1

    def register_exit(self, r_multiple: float, cfg: RiskConfig) -> None:
        self.daily_r += r_multiple
        if r_multiple < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        if (
            self.consecutive_losses >= cfg.max_consecutive_losses
            or self.daily_r <= -cfg.max_daily_loss_r
        ):
            self.halted_today = True


def position_units(equity: float, risk_pct: float, stop_dist: float) -> float:
    """Quote-currency PnL ≈ units * price_change (research engine).
    Venue-account currency conversion is `account.money.units_for_risk` — not used here.
    """
    if stop_dist <= 0 or equity <= 0:
        return 0.0
    risk_amount = equity * (risk_pct / 100.0)
    return risk_amount / stop_dist


def lots_from_units(units: float, lot_size: float) -> float:
    if lot_size <= 0:
        return 0.0
    return units / lot_size


def kelly_fraction(win_rate: float, payoff_ratio: float) -> float:
    """Discrete Kelly: f* = (p*(b+1)-1)/b. 0 if no edge."""
    if payoff_ratio <= 0 or win_rate <= 0:
        return 0.0
    f = (win_rate * (payoff_ratio + 1.0) - 1.0) / payoff_ratio
    return float(max(0.0, f))


def kelly_growth(mu: float, sigma: float, rf: float = 0.0) -> float:
    """Continuous Kelly f* = (μ − r) / σ² on the same frequency as μ and σ."""
    var = sigma * sigma
    if var <= 0:
        return 0.0
    return float(max(0.0, (mu - rf) / var))


def realized_payoff_ratio(trades) -> tuple[float, float]:
    """Return (win_rate, avg_win/avg_loss) from a trades DataFrame with pnl."""
    if trades is None or len(trades) == 0:
        return 0.0, 0.0
    pnl = trades["pnl"]
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    p = float(len(wins) / len(pnl))
    if wins.empty or losses.empty:
        return p, 0.0
    b = float(wins.mean() / (-losses.mean()))
    return p, b
