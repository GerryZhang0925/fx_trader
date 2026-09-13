"""Dict shapes passed between pipeline modules. Modules return these; they do not import each other."""

from __future__ import annotations

from typing import Any, TypedDict


class SignalSnapshot(TypedDict, total=False):
    symbol: str
    pip_size: float
    bar_open_utc: str
    bar_open_jst: str
    next_fill: str
    close: float
    signal: int
    side: str
    reason: str
    stop_dist: float | None
    stop_price_if_filled_at_close: float | None
    partial_1r_if_filled_at_close: float | None
    partial_frac: float
    partial_r: float
    trail_atr_mult: float
    adx: float | None
    ema_trend: float | None
    donch_hi: float | None
    donch_lo: float | None
    bias: int
    params: dict[str, Any]
    recent_signals: list[dict[str, Any]]


class Proposal(SignalSnapshot, total=False):
    """Account overlay: estimated next-bar fill, size, and book ids. Not an order."""

    risk_pct: float
    equity: float
    fill_price_if_next_open_equals_close: float | None
    units: float | None
    lots: float | None
    risk_amount: float | None
    spread_pips: float
    slippage_pips: float
    venue_id: str
    venue_kind: str
    connector: str
    account_currency: str
    sleeve_id: str
    stacking: dict[str, Any]


class StatusEvent(TypedDict, total=False):
    """One JSONL line in reports/status.jsonl. Written by CLIs; rendered by output.web."""

    time: str
    module: str
    action: str
    state: str
    message: str
    extra: dict[str, Any]
