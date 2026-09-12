"""Pair JSON + last-bar snapshot. Price analysis only; no lots."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .donchian import DonchianParams, DonchianStrategy
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


def snapshot_pair(
    symbol: str,
    prepared: pd.DataFrame,
    params: DonchianParams,
    *,
    lookback: int = 8,
) -> dict:
    last = prepared.iloc[-1]
    bar = _ts_utc(prepared.index[-1])
    sig = int(last["signal"])
    direction = 1 if sig > 0 else (-1 if sig < 0 else 0)
    close = float(last["close"])
    stop_dist = float(last["stop_dist"]) if pd.notna(last["stop_dist"]) else None
    stop_at_close = None
    partial_at_close = None
    if direction != 0 and stop_dist and stop_dist > 0:
        stop_at_close = close - direction * stop_dist
        partial_at_close = close + direction * stop_dist * float(params.partial_r)

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
                "stop_dist": float(row["stop_dist"]) if pd.notna(row["stop_dist"]) else None,
            }
        )

    return {
        "symbol": symbol,
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
        "partial_frac": float(params.partial_frac),
        "partial_r": float(params.partial_r),
        "trail_atr_mult": float(params.atr_mult),
        "adx": float(last["adx"]) if pd.notna(last.get("adx")) else None,
        "ema_trend": float(last["ema_trend"]) if pd.notna(last.get("ema_trend")) else None,
        "donch_hi": float(last["donch_hi"]) if pd.notna(last.get("donch_hi")) else None,
        "donch_lo": float(last["donch_lo"]) if pd.notna(last.get("donch_lo")) else None,
        "bias": int(last["bias"]) if pd.notna(last.get("bias")) else 0,
        "params": {
            "length": int(params.length),
            "atr_mult": float(params.atr_mult),
            "adx_min": float(params.adx_min),
            "use_atr_filter": bool(params.use_atr_filter),
        },
        "recent_signals": recent,
    }
