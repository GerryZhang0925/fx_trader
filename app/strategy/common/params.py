"""Pair JSON + last-bar snapshot. Price analysis only; no lots.

Donchian is the adopted live core (`strategy.cores.donchian`). Other catalog cores are for experiments.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from strategy.catalog import DEFAULT_CORE, build_strategy, core_name
from strategy.cores.donchian import DonchianParams, DonchianStrategy
from .pips import pip_size

JST = "Asia/Tokyo"


def _ts_utc(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        return t.tz_localize("UTC")
    return t.tz_convert("UTC")


def _fmt(ts, tz: str = "UTC") -> str:
    return str(_ts_utc(ts).tz_convert(tz))


def _side(sig: int) -> str:
    if sig > 0:
        return "long"
    if sig < 0:
        return "short"
    return "flat"


def _field(row: pd.Series, key: str) -> float | None:
    if key not in row.index:
        return None
    val = row[key]
    return float(val) if pd.notna(val) else None


def _params_dict(params: Any) -> dict:
    if params is None:
        return {}
    if is_dataclass(params) and not isinstance(params, type):
        raw = asdict(params)
        return {k: v for k, v in raw.items() if not isinstance(v, dict)}
    return {}


def portfolio_params(cfg: dict) -> DonchianParams:
    port = cfg.get("portfolio", {})
    merged = {**cfg.get("donchian", {}), **(port.get("donchian") or {})}
    return DonchianParams.from_dict(merged)


def load_pair_params(
    symbol: str, params_dir: Path | None, fallback: DonchianParams
) -> tuple[DonchianParams, dict]:
    extra: dict = {}
    if params_dir is None:
        return fallback, extra
    path = Path(params_dir) / f"{symbol.lower()}_donchian.json"
    if not path.exists():
        return fallback, extra
    data = json.loads(path.read_text(encoding="utf-8"))
    extra = {
        "train_profit_factor": (data.get("train") or {}).get("profit_factor"),
        "test_profit_factor": (data.get("test") or {}).get("profit_factor"),
    }
    return DonchianParams.from_dict(data.get("params") or {}), extra


def analyze(h4: pd.DataFrame, params: DonchianParams) -> pd.DataFrame:
    return DonchianStrategy(params).prepare(h4)


def prepare_core(
    symbol: str,
    h4: pd.DataFrame,
    *,
    core: str,
    cfg: dict,
    params_dir: Path | None,
    fallback: DonchianParams,
) -> tuple[pd.DataFrame, Any]:
    name = core_name(cfg, core)
    if name == "donchian":
        params, _extra = load_pair_params(symbol, params_dir, fallback)
        return DonchianStrategy(params).prepare(h4), params
    strat = build_strategy(name, cfg)
    return strat.prepare(h4), strat.params


def snapshot_pair(
    symbol: str,
    prepared: pd.DataFrame,
    params: Any = None,
    *,
    lookback: int = 8,
    core: str = DEFAULT_CORE,
) -> dict:
    last = prepared.iloc[-1]
    bar = _ts_utc(prepared.index[-1])
    sig = int(last["signal"]) if pd.notna(last.get("signal")) else 0
    direction = 1 if sig > 0 else (-1 if sig < 0 else 0)
    close = float(last["close"])
    stop_dist = _field(last, "stop_dist")
    partial_r = float(getattr(params, "partial_r", 1.0) or 1.0)
    partial_frac = float(getattr(params, "partial_frac", 0.0) or 0.0)
    trail = getattr(params, "atr_mult", None)
    if trail is None:
        trail = _field(last, "trail_mult")
    stop_at_close = None
    partial_at_close = None
    if direction != 0 and stop_dist and stop_dist > 0:
        stop_at_close = close - direction * stop_dist
        partial_at_close = close + direction * stop_dist * partial_r

    fired = prepared[prepared["signal"] != 0].tail(lookback)
    recent = []
    for ts, row in fired.iterrows():
        recent.append(
            {
                "bar_open_utc": _fmt(ts),
                "bar_open_jst": _fmt(ts, JST),
                "side": _side(int(row["signal"])),
                "close": float(row["close"]),
                "reason": str(row.get("reason") or ""),
                "stop_dist": _field(row, "stop_dist"),
            }
        )

    return {
        "symbol": symbol,
        "core": core,
        "pip_size": pip_size(symbol),
        "bar_open_utc": _fmt(bar),
        "bar_open_jst": _fmt(bar, JST),
        "next_fill": "next_H4_open_after_this_closed_bar",
        "close": close,
        "signal": sig,
        "side": _side(sig),
        "reason": str(last.get("reason") or ""),
        "stop_dist": stop_dist,
        "stop_price_if_filled_at_close": stop_at_close,
        "partial_1r_if_filled_at_close": partial_at_close,
        "partial_frac": partial_frac,
        "partial_r": partial_r,
        "trail_atr_mult": float(trail) if trail is not None else None,
        "adx": _field(last, "adx"),
        "ema_trend": _field(last, "ema_trend"),
        "donch_hi": _field(last, "donch_hi"),
        "donch_lo": _field(last, "donch_lo"),
        "bias": int(last["bias"]) if "bias" in last.index and pd.notna(last.get("bias")) else 0,
        "params": _params_dict(params),
        "recent_signals": recent,
    }
