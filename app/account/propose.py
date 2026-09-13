"""Estimated next-bar fill and size from a strategy snapshot. Not an order."""

from __future__ import annotations

from .books import load_venues, sleeve_for
from .engine import CostConfig
from .risk import lots_from_units, position_units
from .settings import engine_from_config


def risk_pct_for(symbol: str, port: dict, override: float | None = None) -> float:
    if override is not None:
        return float(override)
    by_pair = port.get("risk_pct_by_pair") or {}
    if symbol in by_pair and by_pair[symbol] is not None:
        return float(by_pair[symbol])
    return float(port.get("risk_pct_per_pair", 5.0))


def _fill_if_open_equals_close(direction: int, close: float, cost: CostConfig) -> float:
    adverse = cost.half_spread + cost.slip
    if direction > 0:
        return close + adverse
    if direction < 0:
        return close - adverse
    return close


def propose(snapshot: dict, cfg: dict, *, risk_pct: float | None = None) -> dict:
    """Attach account overlay. Does not send or place anything."""
    port = cfg.get("portfolio", {})
    symbol = str(snapshot.get("symbol") or "")
    core = str(snapshot.get("core") or "donchian")
    sleeve = sleeve_for(cfg, core=core, symbol=symbol)
    venues = load_venues(cfg)
    venue = venues.get(sleeve.venue_id) or next(iter(venues.values()))
    if risk_pct is not None:
        pct = float(risk_pct)
    elif cfg.get("sleeves"):
        pct = float(sleeve.risk_pct)
    else:
        pct = float(risk_pct_for(symbol, port))
    engine = engine_from_config(cfg, pip_size=snapshot.get("pip_size"), risk_pct=pct)
    direction = int(snapshot.get("signal") or 0)
    close = snapshot.get("close")
    stop_dist = snapshot.get("stop_dist")
    equity = float(engine.initial_equity)
    fill = None
    units = None
    lots = None
    risk_amount = None
    if direction != 0 and close is not None and stop_dist and stop_dist > 0:
        fill = _fill_if_open_equals_close(direction, float(close), engine.cost)
        units = position_units(equity, pct, float(stop_dist))
        lots = lots_from_units(units, engine.cost.lot_size)
        risk_amount = equity * (pct / 100.0)
    out = dict(snapshot)
    out.update(
        {
            "risk_pct": pct,
            "equity": equity,
            "fill_price_if_next_open_equals_close": fill,
            "units": units,
            "lots": lots,
            "risk_amount": risk_amount,
            "spread_pips": float(engine.cost.spread_pips),
            "slippage_pips": float(engine.cost.slippage_pips),
            "venue_id": venue.id,
            "venue_kind": venue.kind,
            "connector": venue.connector,
            "account_currency": venue.currency,
            "sleeve_id": sleeve.id,
            "stacking": {
                "same_direction": sleeve.stacking.same_direction,
                "opposite": sleeve.stacking.opposite,
            },
        }
    )
    return out
