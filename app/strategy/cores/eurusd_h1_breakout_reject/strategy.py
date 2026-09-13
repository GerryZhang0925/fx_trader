"""EURUSD H1 false-break reject. Research satellite; live default off. No grid."""

from __future__ import annotations

from dataclasses import dataclass, fields

import pandas as pd

from strategy.common.bars import resample_ohlcv
from strategy.common.indicators import adx, atr, donchian_prev, ema, in_london_ny_overlap


@dataclass
class EurusdH1RejectParams:
    length: int = 20
    ema_center: int = 50
    atr_len: int = 14
    stop_buffer_atr: float = 0.5
    adx_len: int = 14
    h4_adx_max: float = 20.0
    max_hold_bars: int = 20

    @classmethod
    def from_dict(cls, data: dict | None) -> "EurusdH1RejectParams":
        allowed = {f.name for f in fields(cls)}
        raw = {k: v for k, v in (data or {}).items() if k in allowed and v is not None}
        return cls(**raw)


class EurusdH1RejectStrategy:
    name = "eurusd_h1_breakout_reject"

    def __init__(self, params: EurusdH1RejectParams | None = None, **kwargs):
        if params is None:
            params = EurusdH1RejectParams.from_dict(kwargs)
        self.params = params

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """H1 bars. Close-break of prior 20, next closed bar back inside. Last closed H4 ADX."""
        p = self.params
        out = df.copy()
        out["ema_center"] = ema(out["close"], p.ema_center)
        out["atr"] = atr(out, p.atr_len)
        upper, lower = donchian_prev(out, p.length)
        out["donch_hi"] = upper
        out["donch_lo"] = lower

        h4 = resample_ohlcv(out, "4h")
        h4_adx = adx(h4, p.adx_len).shift(1)
        out["h4_adx"] = h4_adx.reindex(out.index, method="ffill")
        out["in_overlap"] = in_london_ny_overlap(out.index)

        broke_up = out["close"].shift(1) > out["donch_hi"].shift(1)
        broke_dn = out["close"].shift(1) < out["donch_lo"].shift(1)
        fail_up = broke_up & (out["close"] <= out["donch_hi"].shift(1))
        fail_dn = broke_dn & (out["close"] >= out["donch_lo"].shift(1))

        stop_short = out["high"].shift(1) + out["atr"] * p.stop_buffer_atr
        stop_long = out["low"].shift(1) - out["atr"] * p.stop_buffer_atr
        dist_short = (stop_short - out["close"]).clip(lower=out["atr"] * 0.35)
        dist_long = (out["close"] - stop_long).clip(lower=out["atr"] * 0.35)

        range_ok = out["h4_adx"] < p.h4_adx_max
        long_c = (
            fail_dn
            & out["in_overlap"]
            & range_ok
            & (out["close"] < out["ema_center"])
            & (dist_long > 0)
        )
        short_c = (
            fail_up
            & out["in_overlap"]
            & range_ok
            & (out["close"] > out["ema_center"])
            & (dist_short > 0)
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
        out.loc[long_c, "reason"] = "fail_low_reject"
        out.loc[short_c, "reason"] = "fail_high_reject"
        out["exit_signal"] = False
        out["exit_long"] = False
        out["exit_short"] = False
        out["bias"] = 0
        return out
