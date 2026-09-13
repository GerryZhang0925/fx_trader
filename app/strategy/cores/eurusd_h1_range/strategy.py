"""EURUSD H1 range fade. Research satellite; live default off. No grid."""

from __future__ import annotations

from dataclasses import dataclass, fields

import pandas as pd

from strategy.common.bars import resample_ohlcv
from strategy.common.indicators import (
    adx,
    atr,
    ema,
    in_london_ny_overlap,
    rsi,
    swing_points,
)


@dataclass
class EurusdH1RangeParams:
    rsi_len: int = 14
    rsi_os: float = 30.0
    rsi_ob: float = 70.0
    ema_center: int = 50
    atr_len: int = 14
    swing_len: int = 5
    stop_buffer_atr: float = 0.5
    adx_len: int = 14
    h4_adx_max: float = 20.0
    max_hold_bars: int = 20

    @classmethod
    def from_dict(cls, data: dict | None) -> "EurusdH1RangeParams":
        allowed = {f.name for f in fields(cls)}
        raw = {k: v for k, v in (data or {}).items() if k in allowed and v is not None}
        return cls(**raw)


class EurusdH1RangeStrategy:
    name = "eurusd_h1_range"

    def __init__(self, params: EurusdH1RangeParams | None = None, **kwargs):
        if params is None:
            params = EurusdH1RangeParams.from_dict(kwargs)
        self.params = params

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Expect H1 bars. H4 ADX uses the last *closed* H4 (shift 1, then ffill)."""
        p = self.params
        out = df.copy()
        out["ema_center"] = ema(out["close"], p.ema_center)
        out["rsi"] = rsi(out["close"], p.rsi_len)
        out["atr"] = atr(out, p.atr_len)
        sh, sl = swing_points(out, p.swing_len)
        out["swing_high"] = sh
        out["swing_low"] = sl

        h4 = resample_ohlcv(out, "4h")
        h4_adx = adx(h4, p.adx_len).shift(1)
        out["h4_adx"] = h4_adx.reindex(out.index, method="ffill")
        out["in_overlap"] = in_london_ny_overlap(out.index)

        stop_long = sl - out["atr"] * p.stop_buffer_atr
        stop_short = sh + out["atr"] * p.stop_buffer_atr
        dist_long = (out["close"] - stop_long).clip(lower=out["atr"] * 0.35)
        dist_short = (stop_short - out["close"]).clip(lower=out["atr"] * 0.35)

        range_ok = out["h4_adx"] < p.h4_adx_max
        long_c = (
            (out["rsi"] < p.rsi_os)
            & out["in_overlap"]
            & range_ok
            & (out["close"] < out["ema_center"])
        )
        short_c = (
            (out["rsi"] > p.rsi_ob)
            & out["in_overlap"]
            & range_ok
            & (out["close"] > out["ema_center"])
        )

        out["signal"] = 0
        out.loc[long_c, "signal"] = 1
        out.loc[short_c, "signal"] = -1
        out["stop_dist"] = out["atr"] * 1.0
        out.loc[long_c, "stop_dist"] = dist_long[long_c]
        out.loc[short_c, "stop_dist"] = dist_short[short_c]
        out["trail_mult"] = pd.NA
        out["partial_frac"] = 0.0
        out["partial_r"] = pd.NA
        out["tp_r"] = pd.NA
        out["tp_price"] = pd.NA
        out.loc[long_c, "tp_price"] = out.loc[long_c, "ema_center"]
        out.loc[short_c, "tp_price"] = out.loc[short_c, "ema_center"]
        out["max_hold_bars"] = p.max_hold_bars
        out["risk_mult"] = 1.0
        out["reason"] = ""
        out.loc[long_c, "reason"] = "rsi_os_fade"
        out.loc[short_c, "reason"] = "rsi_ob_fade"
        out["exit_signal"] = False
        out["exit_long"] = False
        out["exit_short"] = False
        out["bias"] = 0
        return out
