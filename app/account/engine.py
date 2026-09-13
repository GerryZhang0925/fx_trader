"""Next-bar fill engine with spread, slippage, ATR trail, partial 1R, and daily halt."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .risk import RiskConfig, RiskState, position_units, lots_from_units


@dataclass
class CostConfig:
    spread_pips: float = 1.0
    slippage_pips: float = 0.2
    commission_per_lot: float = 0.0
    pip_size: float = 0.0001
    lot_size: float = 100_000.0

    @property
    def half_spread(self) -> float:
        return (self.spread_pips * self.pip_size) / 2.0

    @property
    def slip(self) -> float:
        return self.slippage_pips * self.pip_size


@dataclass
class EngineConfig:
    initial_equity: float = 100_000.0
    risk: RiskConfig = field(default_factory=RiskConfig)
    cost: CostConfig = field(default_factory=CostConfig)


@dataclass
class Position:
    direction: int
    entry_i: int
    entry_price: float
    units: float
    initial_units: float
    stop: float
    stop_dist: float
    risk_amount: float
    trail_mult: float
    tp_price: float
    partial_frac: float
    partial_r: float
    partial_taken: bool
    realized_pnl: float
    reason: str
    be_after_partial: bool
    trail_after_partial: bool
    max_hold_bars: int


@dataclass
class PendingEntry:
    direction: int
    stop_dist: float
    trail_mult: float
    tp_r: float
    tp_price: float
    partial_frac: float
    partial_r: float
    reason: str
    be_after_partial: bool
    trail_after_partial: bool
    risk_mult: float
    max_hold_bars: int


def _fill_price(direction: int, raw: float, cost: CostConfig, is_entry: bool) -> float:
    adverse = cost.half_spread + cost.slip
    if is_entry:
        return raw + adverse if direction > 0 else raw - adverse
    return raw - adverse if direction > 0 else raw + adverse


def _commission(units: float, cost: CostConfig) -> float:
    lots = abs(lots_from_units(units, cost.lot_size))
    return lots * cost.commission_per_lot


def _nan(x: float) -> bool:
    return x != x  # NaN


def _close_full(
    pos: Position,
    ts,
    exit_px: float,
    why: str,
    equity: float,
    cfg: EngineConfig,
    trades: list,
    risk_state: RiskState,
    index,
) -> float:
    pnl = pos.realized_pnl + pos.direction * pos.units * (exit_px - pos.entry_price)
    pnl -= _commission(pos.units, cfg.cost)
    r_mult = pnl / pos.risk_amount if pos.risk_amount else 0.0
    equity += pos.direction * pos.units * (exit_px - pos.entry_price)
    equity -= _commission(pos.units, cfg.cost)
    trades.append(
        {
            "entry_time": index[pos.entry_i],
            "exit_time": ts,
            "direction": pos.direction,
            "entry": pos.entry_price,
            "exit": exit_px,
            "pnl": pnl,
            "r": r_mult,
            "reason": pos.reason,
            "exit_reason": why,
        }
    )
    risk_state.register_exit(r_mult, cfg.risk)
    return equity


def _take_partial(pos: Position, exit_px: float, cfg: EngineConfig) -> float:
    qty = pos.initial_units * pos.partial_frac
    qty = min(qty, pos.units)
    if qty <= 0:
        pos.partial_taken = True
        return 0.0
    pnl = pos.direction * qty * (exit_px - pos.entry_price)
    fee = _commission(qty, cfg.cost)
    pos.units -= qty
    pos.realized_pnl += pnl - fee
    pos.partial_taken = True
    return pnl - fee


def run_backtest(df: pd.DataFrame, cfg: EngineConfig) -> tuple[pd.Series, pd.DataFrame]:
    """Evaluate `signal` at bar close; fill at the next bar open. No lookahead."""
    required = {"open", "high", "low", "close", "signal", "stop_dist"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame missing {missing}")

    n = len(df)
    index = df.index
    o = df["open"].to_numpy(dtype=float, copy=False)
    h = df["high"].to_numpy(dtype=float, copy=False)
    l = df["low"].to_numpy(dtype=float, copy=False)
    c = df["close"].to_numpy(dtype=float, copy=False)
    sig = pd.to_numeric(df["signal"], errors="coerce").fillna(0).to_numpy(dtype=np.int8)
    stop_dist_a = pd.to_numeric(df["stop_dist"], errors="coerce").to_numpy(dtype=float)
    atr_a = (
        pd.to_numeric(df["atr"], errors="coerce").to_numpy(dtype=float)
        if "atr" in df.columns
        else stop_dist_a / 2.5
    )
    trail_a = (
        pd.to_numeric(df["trail_mult"], errors="coerce").to_numpy(dtype=float)
        if "trail_mult" in df.columns
        else np.full(n, np.nan)
    )
    tp_r_a = (
        pd.to_numeric(df["tp_r"], errors="coerce").to_numpy(dtype=float)
        if "tp_r" in df.columns
        else np.full(n, np.nan)
    )
    tp_px_a = (
        pd.to_numeric(df["tp_price"], errors="coerce").to_numpy(dtype=float)
        if "tp_price" in df.columns
        else np.full(n, np.nan)
    )
    partial_frac_a = (
        pd.to_numeric(df["partial_frac"], errors="coerce").to_numpy(dtype=float)
        if "partial_frac" in df.columns
        else np.zeros(n)
    )
    partial_r_a = (
        pd.to_numeric(df["partial_r"], errors="coerce").to_numpy(dtype=float)
        if "partial_r" in df.columns
        else np.full(n, np.nan)
    )
    be_a = (
        df["be_after_partial"].fillna(False).to_numpy(dtype=bool)
        if "be_after_partial" in df.columns
        else np.zeros(n, dtype=bool)
    )
    trail_after_a = (
        df["trail_after_partial"].fillna(False).to_numpy(dtype=bool)
        if "trail_after_partial" in df.columns
        else np.zeros(n, dtype=bool)
    )
    risk_mult_a = (
        pd.to_numeric(df["risk_mult"], errors="coerce").fillna(1.0).to_numpy(dtype=float)
        if "risk_mult" in df.columns
        else np.ones(n, dtype=float)
    )
    max_hold_a = (
        pd.to_numeric(df["max_hold_bars"], errors="coerce").fillna(0).to_numpy(dtype=np.int32)
        if "max_hold_bars" in df.columns
        else np.zeros(n, dtype=np.int32)
    )
    reasons = df["reason"].astype(str).to_numpy() if "reason" in df.columns else np.full(n, "")
    exit_sig = (
        df["exit_signal"].fillna(False).to_numpy(dtype=bool)
        if "exit_signal" in df.columns
        else np.zeros(n, dtype=bool)
    )
    exit_long = (
        df["exit_long"].fillna(False).to_numpy(dtype=bool)
        if "exit_long" in df.columns
        else np.zeros(n, dtype=bool)
    )
    exit_short = (
        df["exit_short"].fillna(False).to_numpy(dtype=bool)
        if "exit_short" in df.columns
        else np.zeros(n, dtype=bool)
    )
    dates = pd.DatetimeIndex(index).tz_convert("UTC").date if index.tz is not None else pd.DatetimeIndex(index).date

    equity = cfg.initial_equity
    eq_arr = np.empty(n, dtype=float)
    trades: list[dict] = []
    pos: Position | None = None
    pending: PendingEntry | None = None
    flatten_next = False
    risk_state = RiskState()

    for i in range(n):
        risk_state.on_new_day(dates[i])

        if pos is not None and flatten_next:
            exit_px = _fill_price(pos.direction, o[i], cfg.cost, is_entry=False)
            equity = _close_full(pos, index[i], exit_px, "signal_exit", equity, cfg, trades, risk_state, index)
            pos = None
            flatten_next = False

        if pending is not None and pos is None:
            if risk_state.can_enter(cfg.risk) and pending.stop_dist > 0:
                fill = _fill_price(pending.direction, o[i], cfg.cost, is_entry=True)
                scale = pending.risk_mult if pending.risk_mult > 0 else 1.0
                units = position_units(equity, cfg.risk.risk_pct * scale, pending.stop_dist)
                if units > 0:
                    stop = fill - pending.direction * pending.stop_dist
                    tp = pending.tp_price
                    if _nan(tp) and pending.tp_r > 0:
                        tp = fill + pending.direction * pending.stop_dist * pending.tp_r
                    pos = Position(
                        direction=int(pending.direction),
                        entry_i=i,
                        entry_price=fill,
                        units=units,
                        initial_units=units,
                        stop=float(stop),
                        stop_dist=pending.stop_dist,
                        risk_amount=equity * (cfg.risk.risk_pct / 100.0) * scale,
                        trail_mult=pending.trail_mult,
                        tp_price=tp,
                        partial_frac=pending.partial_frac if pending.partial_frac > 0 else 0.0,
                        partial_r=pending.partial_r,
                        partial_taken=False,
                        realized_pnl=0.0,
                        reason=pending.reason,
                        be_after_partial=pending.be_after_partial,
                        trail_after_partial=pending.trail_after_partial,
                        max_hold_bars=pending.max_hold_bars,
                    )
                    equity -= _commission(units, cfg.cost)
                    risk_state.register_entry()
            pending = None

        if pos is not None:
            stop_hit = (l[i] <= pos.stop) if pos.direction > 0 else (h[i] >= pos.stop)
            full_tp = (not _nan(pos.tp_price)) and (
                (h[i] >= pos.tp_price) if pos.direction > 0 else (l[i] <= pos.tp_price)
            )
            partial_px = pos.entry_price + pos.direction * pos.stop_dist * pos.partial_r
            want_partial = (
                (not pos.partial_taken)
                and pos.partial_frac > 0
                and pos.partial_r > 0
                and ((h[i] >= partial_px) if pos.direction > 0 else (l[i] <= partial_px))
            )

            if stop_hit:
                raw = pos.stop
                if pos.direction > 0 and o[i] < pos.stop:
                    raw = o[i]
                elif pos.direction < 0 and o[i] > pos.stop:
                    raw = o[i]
                exit_px = _fill_price(pos.direction, raw, cfg.cost, is_entry=False)
                why = "stop_vs_tp" if (full_tp or want_partial) else "stop"
                equity = _close_full(pos, index[i], exit_px, why, equity, cfg, trades, risk_state, index)
                pos = None
            elif full_tp and not want_partial:
                raw = pos.tp_price
                if pos.direction > 0 and o[i] > pos.tp_price:
                    raw = o[i]
                elif pos.direction < 0 and o[i] < pos.tp_price:
                    raw = o[i]
                exit_px = _fill_price(pos.direction, raw, cfg.cost, is_entry=False)
                equity = _close_full(pos, index[i], exit_px, "take_profit", equity, cfg, trades, risk_state, index)
                pos = None
            else:
                if want_partial:
                    raw = partial_px
                    if pos.direction > 0 and o[i] > partial_px:
                        raw = o[i]
                    elif pos.direction < 0 and o[i] < partial_px:
                        raw = o[i]
                    exit_px = _fill_price(pos.direction, raw, cfg.cost, is_entry=False)
                    equity += _take_partial(pos, exit_px, cfg)
                    if pos.units <= 0:
                        r_mult = pos.realized_pnl / pos.risk_amount if pos.risk_amount else 0.0
                        trades.append(
                            {
                                "entry_time": index[pos.entry_i],
                                "exit_time": index[i],
                                "direction": pos.direction,
                                "entry": pos.entry_price,
                                "exit": exit_px,
                                "pnl": pos.realized_pnl,
                                "r": r_mult,
                                "reason": pos.reason,
                                "exit_reason": "partial_full",
                            }
                        )
                        risk_state.register_exit(r_mult, cfg.risk)
                        pos = None
                    else:
                        if pos.be_after_partial:
                            pos.stop = pos.entry_price
                        full_tp = (not _nan(pos.tp_price)) and (
                            (h[i] >= pos.tp_price) if pos.direction > 0 else (l[i] <= pos.tp_price)
                        )
                        if full_tp:
                            raw = pos.tp_price
                            if pos.direction > 0 and o[i] > pos.tp_price:
                                raw = o[i]
                            elif pos.direction < 0 and o[i] < pos.tp_price:
                                raw = o[i]
                            tp_exit = _fill_price(pos.direction, raw, cfg.cost, is_entry=False)
                            equity = _close_full(
                                pos, index[i], tp_exit, "take_profit", equity, cfg, trades, risk_state, index
                            )
                            pos = None
                if pos is not None and pos.trail_mult > 0 and atr_a[i] > 0:
                    if (not pos.trail_after_partial) or pos.partial_taken:
                        dist = atr_a[i] * pos.trail_mult
                        if pos.direction > 0:
                            pos.stop = max(pos.stop, h[i] - dist)
                        else:
                            pos.stop = min(pos.stop, l[i] + dist)

        if pos is None:
            if sig[i] != 0 and risk_state.can_enter(cfg.risk) and stop_dist_a[i] > 0:
                pending = PendingEntry(
                    direction=int(sig[i]),
                    stop_dist=float(stop_dist_a[i]),
                    trail_mult=0.0 if _nan(trail_a[i]) else float(trail_a[i]),
                    tp_r=0.0 if _nan(tp_r_a[i]) else float(tp_r_a[i]),
                    tp_price=float(tp_px_a[i]) if not _nan(tp_px_a[i]) else float("nan"),
                    partial_frac=0.0 if _nan(partial_frac_a[i]) else float(partial_frac_a[i]),
                    partial_r=0.0 if _nan(partial_r_a[i]) else float(partial_r_a[i]),
                    reason=str(reasons[i]),
                    be_after_partial=bool(be_a[i]),
                    trail_after_partial=bool(trail_after_a[i]),
                    risk_mult=float(risk_mult_a[i]) if risk_mult_a[i] > 0 else 1.0,
                    max_hold_bars=int(max_hold_a[i]) if max_hold_a[i] > 0 else 0,
                )
        elif sig[i] != 0 and sig[i] != pos.direction:
            flatten_next = True
            if stop_dist_a[i] > 0:
                pending = PendingEntry(
                    direction=int(sig[i]),
                    stop_dist=float(stop_dist_a[i]),
                    trail_mult=0.0 if _nan(trail_a[i]) else float(trail_a[i]),
                    tp_r=0.0 if _nan(tp_r_a[i]) else float(tp_r_a[i]),
                    tp_price=float(tp_px_a[i]) if not _nan(tp_px_a[i]) else float("nan"),
                    partial_frac=0.0 if _nan(partial_frac_a[i]) else float(partial_frac_a[i]),
                    partial_r=0.0 if _nan(partial_r_a[i]) else float(partial_r_a[i]),
                    reason="reverse",
                    be_after_partial=bool(be_a[i]),
                    trail_after_partial=bool(trail_after_a[i]),
                    risk_mult=float(risk_mult_a[i]) if risk_mult_a[i] > 0 else 1.0,
                    max_hold_bars=int(max_hold_a[i]) if max_hold_a[i] > 0 else 0,
                )
        elif exit_sig[i] or (pos.direction > 0 and exit_long[i]) or (pos.direction < 0 and exit_short[i]):
            flatten_next = True
        elif pos.max_hold_bars > 0 and (i - pos.entry_i) >= pos.max_hold_bars:
            flatten_next = True

        mtm = 0.0 if pos is None else pos.direction * pos.units * (c[i] - pos.entry_price) + pos.realized_pnl
        eq_arr[i] = equity + mtm

    if pos is not None:
        exit_px = _fill_price(pos.direction, c[-1], cfg.cost, is_entry=False)
        equity = _close_full(pos, index[-1], exit_px, "eod", equity, cfg, trades, risk_state, index)
        eq_arr[-1] = equity

    eq = pd.Series(eq_arr, index=index, name="equity")
    return eq, pd.DataFrame(trades)
