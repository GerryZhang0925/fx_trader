"""Donchian breakout with EMA/ADX/ATR filters, swing stop, and 1R partial + ATR trail."""

from __future__ import annotations

from dataclasses import dataclass, fields

import pandas as pd

from .indicators import adx, atr, donchian_prev, ema, swing_points


@dataclass
class DonchianParams:
    length: int = 55
    ema_len: int = 200
    atr_len: int = 14
    atr_mult: float = 2.5
    swing_len: int = 5
    stop_buffer_atr: float = 0.5
    adx_len: int = 14
    adx_min: float = 20.0
    atr_median_len: int = 50
    use_adx_filter: bool = True
    use_atr_filter: bool = True
    partial_frac: float = 0.5
    partial_r: float = 1.0
    exit_on_opposite_break: bool = True
    exit_on_ema_flip: bool = False
    take_profit_r: float | None = None
    remainder_tp_r: float | None = None
    be_after_partial: bool = False
    trail_after_partial: bool = False
    target_mode: str = "none"
    vol_size_scale: bool = False

    @classmethod
    def from_dict(cls, data: dict | None) -> "DonchianParams":
        allowed = {f.name for f in fields(cls)}
        raw = {k: v for k, v in (data or {}).items() if k in allowed and v is not None}
        return cls(**raw)


class DonchianStrategy:
    name = "donchian"

    def __init__(self, params: DonchianParams | None = None, **kwargs):
        if params is None:
            params = DonchianParams.from_dict(kwargs)
        self.params = params

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        out = df.copy()
        out["ema_trend"] = ema(out["close"], p.ema_len)
        upper, lower = donchian_prev(out, p.length)
        out["donch_hi"] = upper
        out["donch_lo"] = lower
        out["atr"] = atr(out, p.atr_len)
        out["adx"] = adx(out, p.adx_len)
        sh, sl = swing_points(out, p.swing_len)
        out["swing_high"] = sh
        out["swing_low"] = sl

        stop_long = sl - out["atr"] * p.stop_buffer_atr
        stop_short = sh + out["atr"] * p.stop_buffer_atr
        dist_long = (out["close"] - stop_long).clip(lower=out["atr"] * 0.35)
        dist_short = (stop_short - out["close"]).clip(lower=out["atr"] * 0.35)

        long_c = (out["close"] > out["donch_hi"]) & (out["close"] > out["ema_trend"])
        short_c = (out["close"] < out["donch_lo"]) & (out["close"] < out["ema_trend"])
        if p.use_adx_filter:
            trend_ok = out["adx"] >= p.adx_min
            long_c = long_c & trend_ok
            short_c = short_c & trend_ok
        if p.use_atr_filter:
            atr_med = out["atr"].rolling(p.atr_median_len, min_periods=p.atr_median_len).median()
            vol_ok = out["atr"] > atr_med
            long_c = long_c & vol_ok
            short_c = short_c & vol_ok

        out["signal"] = 0
        out.loc[long_c, "signal"] = 1
        out.loc[short_c, "signal"] = -1
        out["stop_dist"] = out["atr"] * p.atr_mult
        out.loc[long_c, "stop_dist"] = dist_long[long_c]
        out.loc[short_c, "stop_dist"] = dist_short[short_c]
        out["trail_mult"] = p.atr_mult
        tp_r = p.remainder_tp_r if p.remainder_tp_r else p.take_profit_r
        out["tp_r"] = tp_r if tp_r else pd.NA
        out["tp_price"] = pd.NA
        if p.target_mode == "measured_move":
            width = (out["donch_hi"] - out["donch_lo"]).clip(lower=out["atr"] * 0.5)
            out.loc[long_c, "tp_price"] = out["close"][long_c] + width[long_c]
            out.loc[short_c, "tp_price"] = out["close"][short_c] - width[short_c]
            out["tp_r"] = pd.NA
        out["partial_frac"] = p.partial_frac
        out["partial_r"] = p.partial_r
        out["be_after_partial"] = p.be_after_partial
        out["trail_after_partial"] = p.trail_after_partial
        if p.vol_size_scale:
            atr_med = out["atr"].rolling(p.atr_median_len, min_periods=p.atr_median_len).median()
            out["risk_mult"] = 0.5
            out.loc[out["atr"] >= atr_med, "risk_mult"] = 1.0
        else:
            out["risk_mult"] = 1.0
        out["reason"] = ""
        out.loc[long_c, "reason"] = "donchian_long"
        out.loc[short_c, "reason"] = "donchian_short"
        out["exit_signal"] = False
        out["exit_long"] = False
        out["exit_short"] = False
        if p.exit_on_ema_flip:
            out["exit_long"] = out["close"] < out["ema_trend"]
            out["exit_short"] = out["close"] > out["ema_trend"]
        out["bias"] = 0
        out.loc[out["close"] > out["ema_trend"], "bias"] = 1
        out.loc[out["close"] < out["ema_trend"], "bias"] = -1
        return out
