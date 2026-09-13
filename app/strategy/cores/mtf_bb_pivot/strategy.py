"""H1 daily BB fade (session). Explore; bounce/monthly flags off by default."""

from __future__ import annotations

from dataclasses import dataclass, fields

import pandas as pd

from strategy.common.bars import align_htf, nearer_target, resample_ohlcv
from strategy.common.indicators import (
    atr,
    bollinger,
    floor_pivots,
    in_london_ny_overlap,
    macd,
)


@dataclass
class MtfBbPivotParams:
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    daily_bb_len: int = 20
    daily_bb_k: float = 2.0
    daily_stop_k: float = 2.5
    h1_bb_len: int = 20
    h1_bb_k: float = 1.5
    atr_len: int = 14
    stop_buffer_atr: float = 0.5
    min_stop_atr: float = 0.35
    max_hold_bars: int = 48
    require_monthly: bool = False
    require_daily_bb: bool = True
    require_h4_bounce: bool = False
    require_h1_bb: bool = False
    require_overlap: bool = True
    combine_bb_bounce: str = "or"
    once_per_stretch: bool = True

    @classmethod
    def from_dict(cls, data: dict | None) -> "MtfBbPivotParams":
        allowed = {f.name for f in fields(cls)}
        raw = {k: v for k, v in (data or {}).items() if k in allowed and v is not None}
        return cls(**raw)


def _first_true_in_run(flag: pd.Series, active: pd.Series) -> pd.Series:
    """Keep the first True in each consecutive True-run of `active`."""
    run_id = active.ne(active.shift(1)).cumsum()
    return flag & flag.groupby(run_id, sort=False).cumsum().eq(1)


class MtfBbPivotStrategy:
    name = "mtf_bb_pivot"

    def __init__(self, params: MtfBbPivotParams | None = None, **kwargs):
        if params is None:
            params = MtfBbPivotParams.from_dict(kwargs)
        self.params = params

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Expect H1 bars. Monthly/daily/H4 use last closed HTF bar only."""
        p = self.params
        out = df.copy()
        mid1, up1, lo1 = bollinger(out["close"], p.h1_bb_len, p.h1_bb_k)
        out["h1_bb_mid"] = mid1
        out["h1_bb_upper"] = up1
        out["h1_bb_lower"] = lo1
        out["atr"] = atr(out, p.atr_len)
        out["in_overlap"] = in_london_ny_overlap(out.index)

        monthly = resample_ohlcv(out, "MS")
        m_line, m_sig, _ = macd(monthly["close"], p.macd_fast, p.macd_slow, p.macd_signal)
        out["m_macd"] = align_htf(m_line, out.index)
        out["m_macd_sig"] = align_htf(m_sig, out.index)
        out["m_bull"] = out["m_macd"] > out["m_macd_sig"]
        out["m_bear"] = out["m_macd"] < out["m_macd_sig"]

        daily = resample_ohlcv(out, "1D")
        d_mid, d_up, d_lo = bollinger(daily["close"], p.daily_bb_len, p.daily_bb_k)
        out["d_bb_mid"] = align_htf(d_mid, out.index)
        out["d_bb_upper"] = align_htf(d_up, out.index)
        out["d_bb_lower"] = align_htf(d_lo, out.index)
        out["d_bb_sd"] = (out["d_bb_upper"] - out["d_bb_mid"]) / p.daily_bb_k
        out["d_close"] = align_htf(daily["close"], out.index)
        out["d_os"] = out["d_close"] < out["d_bb_lower"]
        out["d_ob"] = out["d_close"] > out["d_bb_upper"]

        h4 = resample_ohlcv(out, "4h")
        _p, r1, s1, r2, s2 = floor_pivots(h4)
        h4_atr = atr(h4, p.atr_len)
        bounce_long = (h4["low"] <= s1) & (h4["close"] > s1)
        bounce_short = (h4["high"] >= r1) & (h4["close"] < r1)
        out["h4_r1"] = align_htf(r1, out.index)
        out["h4_s1"] = align_htf(s1, out.index)
        out["h4_r2"] = align_htf(r2, out.index)
        out["h4_s2"] = align_htf(s2, out.index)
        out["h4_atr"] = align_htf(h4_atr, out.index)
        out["h4_bounce_long"] = align_htf(bounce_long.astype(float), out.index) > 0
        out["h4_bounce_short"] = align_htf(bounce_short.astype(float), out.index) > 0

        yes = pd.Series(True, index=out.index)
        no = pd.Series(False, index=out.index)
        long_bb = out["d_os"] if p.require_daily_bb else no
        short_bb = out["d_ob"] if p.require_daily_bb else no
        long_bounce = out["h4_bounce_long"] if p.require_h4_bounce else no
        short_bounce = out["h4_bounce_short"] if p.require_h4_bounce else no
        if p.combine_bb_bounce == "or":
            long_setup = long_bb | long_bounce
            short_setup = short_bb | short_bounce
            if not p.require_daily_bb and not p.require_h4_bounce:
                long_setup = yes
                short_setup = yes
        else:
            long_setup = (out["d_os"] if p.require_daily_bb else yes) & (
                out["h4_bounce_long"] if p.require_h4_bounce else yes
            )
            short_setup = (out["d_ob"] if p.require_daily_bb else yes) & (
                out["h4_bounce_short"] if p.require_h4_bounce else yes
            )
        long_c = (
            long_setup
            & (out["m_bull"] if p.require_monthly else yes)
            & ((out["close"] < out["h1_bb_lower"]) if p.require_h1_bb else yes)
            & (out["in_overlap"] if p.require_overlap else yes)
        )
        short_c = (
            short_setup
            & (out["m_bear"] if p.require_monthly else yes)
            & ((out["close"] > out["h1_bb_upper"]) if p.require_h1_bb else yes)
            & (out["in_overlap"] if p.require_overlap else yes)
        )

        bounce_stop_long = out["h4_s1"] - out["h4_atr"] * p.stop_buffer_atr
        bounce_stop_short = out["h4_r1"] + out["h4_atr"] * p.stop_buffer_atr
        bb_stop_long = out["d_bb_mid"] - out["d_bb_sd"] * p.daily_stop_k
        bb_stop_short = out["d_bb_mid"] + out["d_bb_sd"] * p.daily_stop_k
        use_bounce_long = out["h4_bounce_long"] if p.require_h4_bounce else no
        use_bounce_short = out["h4_bounce_short"] if p.require_h4_bounce else no
        stop_long = bounce_stop_long.where(use_bounce_long, bb_stop_long)
        stop_short = bounce_stop_short.where(use_bounce_short, bb_stop_short)
        floor = out["atr"] * p.min_stop_atr
        dist_long = (out["close"] - stop_long).clip(lower=floor)
        dist_short = (stop_short - out["close"]).clip(lower=floor)
        tp_long = nearer_target(out["close"], 1, out["d_bb_mid"])
        tp_short = nearer_target(out["close"], -1, out["d_bb_mid"])
        long_c = long_c & dist_long.gt(0) & tp_long.notna()
        short_c = short_c & dist_short.gt(0) & tp_short.notna()
        if p.once_per_stretch and p.require_daily_bb:
            long_c = _first_true_in_run(long_c, out["d_os"])
            short_c = _first_true_in_run(short_c, out["d_ob"])

        out["signal"] = 0
        out.loc[long_c, "signal"] = 1
        out.loc[short_c, "signal"] = -1
        out["stop_dist"] = out["atr"]
        out.loc[long_c, "stop_dist"] = dist_long[long_c]
        out.loc[short_c, "stop_dist"] = dist_short[short_c]
        out["trail_mult"] = pd.NA
        out["partial_frac"] = 0.0
        out["partial_r"] = pd.NA
        out["tp_r"] = pd.NA
        out["tp_price"] = pd.NA
        out.loc[long_c, "tp_price"] = tp_long[long_c]
        out.loc[short_c, "tp_price"] = tp_short[short_c]
        out["max_hold_bars"] = p.max_hold_bars
        out["risk_mult"] = 1.0
        out["reason"] = ""
        out.loc[long_c, "reason"] = "daily_bb_fade"
        out.loc[short_c, "reason"] = "daily_bb_fade"
        out["exit_signal"] = False
        out["exit_long"] = False
        out["exit_short"] = False
        out["bias"] = 0
        out.loc[out["m_bull"], "bias"] = 1
        out.loc[out["m_bear"], "bias"] = -1
        return out
