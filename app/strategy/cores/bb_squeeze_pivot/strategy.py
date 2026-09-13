"""H1 4H BB squeeze + 12H pivot break. Explore core; live default off."""

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
class BbSqueezePivotParams:
    bb_len: int = 20
    bb_k: float = 2.0
    squeeze_lookback: int = 20
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr_len: int = 14
    stop_buffer_atr: float = 0.5
    min_stop_atr: float = 0.35
    max_hold_bars: int = 72
    require_squeeze: bool = True
    require_macd: bool = True
    require_overlap: bool = True

    @classmethod
    def from_dict(cls, data: dict | None) -> "BbSqueezePivotParams":
        allowed = {f.name for f in fields(cls)}
        raw = {k: v for k, v in (data or {}).items() if k in allowed and v is not None}
        return cls(**raw)


class BbSqueezePivotStrategy:
    name = "bb_squeeze_pivot"

    def __init__(self, params: BbSqueezePivotParams | None = None, **kwargs):
        if params is None:
            params = BbSqueezePivotParams.from_dict(kwargs)
        self.params = params

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Expect H1 bars. HTF uses last closed 4H / 12H only."""
        p = self.params
        out = df.copy()
        line, sig, _ = macd(out["close"], p.macd_fast, p.macd_slow, p.macd_signal)
        out["macd"] = line
        out["macd_sig"] = sig
        out["atr"] = atr(out, p.atr_len)
        out["in_overlap"] = in_london_ny_overlap(out.index)

        h4 = resample_ohlcv(out, "4h")
        mid, upper, lower = bollinger(h4["close"], p.bb_len, p.bb_k)
        width = (upper - lower) / mid.replace(0.0, pd.NA)
        roll_min = width.rolling(p.squeeze_lookback, min_periods=p.squeeze_lookback).min()
        squeeze = width <= roll_min
        h4_atr = atr(h4, p.atr_len)
        out["h4_bb_mid"] = align_htf(mid, out.index)
        out["h4_bb_upper"] = align_htf(upper, out.index)
        out["h4_bb_lower"] = align_htf(lower, out.index)
        out["h4_squeeze"] = align_htf(squeeze.astype(float), out.index) > 0
        out["h4_atr"] = align_htf(h4_atr, out.index)

        h12 = resample_ohlcv(out, "12h")
        _p, r1, s1, r2, s2 = floor_pivots(h12)
        h12_atr = atr(h12, p.atr_len)
        break_long = h12["close"] > r1
        break_short = h12["close"] < s1
        out["h12_r1"] = align_htf(r1, out.index)
        out["h12_s1"] = align_htf(s1, out.index)
        out["h12_r2"] = align_htf(r2, out.index)
        out["h12_s2"] = align_htf(s2, out.index)
        out["h12_break_long"] = align_htf(break_long.astype(float), out.index) > 0
        out["h12_break_short"] = align_htf(break_short.astype(float), out.index) > 0
        out["h12_atr"] = align_htf(h12_atr, out.index)

        yes = pd.Series(True, index=out.index)
        long_c = (
            (out["h4_squeeze"] if p.require_squeeze else yes)
            & out["h12_break_long"]
            & ((out["macd"] > out["macd_sig"]) if p.require_macd else yes)
            & (out["in_overlap"] if p.require_overlap else yes)
        )
        short_c = (
            (out["h4_squeeze"] if p.require_squeeze else yes)
            & out["h12_break_short"]
            & ((out["macd"] < out["macd_sig"]) if p.require_macd else yes)
            & (out["in_overlap"] if p.require_overlap else yes)
        )

        stop_long = out["h12_r1"] - out["h12_atr"] * p.stop_buffer_atr
        stop_short = out["h12_s1"] + out["h12_atr"] * p.stop_buffer_atr
        floor = out["atr"] * p.min_stop_atr
        dist_long = (out["close"] - stop_long).clip(lower=floor)
        dist_short = (stop_short - out["close"]).clip(lower=floor)
        tp_long = nearer_target(out["close"], 1, out["h12_r2"], out["h4_bb_upper"])
        tp_short = nearer_target(out["close"], -1, out["h12_s2"], out["h4_bb_lower"])
        long_c = long_c & dist_long.gt(0) & tp_long.notna()
        short_c = short_c & dist_short.gt(0) & tp_short.notna()

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
        out.loc[long_c, "reason"] = "squeeze_h12_break"
        out.loc[short_c, "reason"] = "squeeze_h12_break"
        out["exit_signal"] = False
        out["exit_long"] = False
        out["exit_short"] = False
        out["bias"] = 0
        return out
