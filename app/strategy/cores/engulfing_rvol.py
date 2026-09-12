"""Body engulfing + relative tick volume + room to next swing. Optional ADX range gate."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from strategy.common.indicators import adx, atr, ema, sma, swing_points


@dataclass
class EngulfingParams:
    rvol_len: int = 20
    rvol_min: float = 1.2
    swing_len: int = 5
    min_room_r: float = 1.5
    take_profit_r: float = 2.0
    adx_len: int = 14
    adx_range_max: float = 20.0
    stop_buffer_atr: float = 0.1
    trend_ema: int = 200
    require_range: bool = False
    atr_len: int = 14


class EngulfingRvolStrategy:
    name = "engulfing"

    def __init__(self, params: EngulfingParams | None = None, **kwargs):
        if params is None:
            allow = EngulfingParams.__dataclass_fields__.keys()
            params = EngulfingParams(**{k: v for k, v in kwargs.items() if k in allow and v is not None})
        self.params = params

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        out = df.copy()
        body_top = out[["open", "close"]].max(axis=1)
        body_bot = out[["open", "close"]].min(axis=1)
        prev_top = body_top.shift(1)
        prev_bot = body_bot.shift(1)
        bull_body = out["close"] > out["open"]
        bear_body = out["close"] < out["open"]
        prev_bear = out["close"].shift(1) < out["open"].shift(1)
        prev_bull = out["close"].shift(1) > out["open"].shift(1)
        bull_eng = bull_body & prev_bear & (body_bot <= prev_bot) & (body_top >= prev_top)
        bear_eng = bear_body & prev_bull & (body_top >= prev_top) & (body_bot <= prev_bot)

        vol_ma = sma(out["volume"].replace(0, pd.NA).fillna(out["volume"].median()), p.rvol_len)
        out["rvol"] = out["volume"] / vol_ma.replace(0, pd.NA)
        rvol_ok = out["rvol"] >= p.rvol_min

        out["atr"] = atr(out, p.atr_len)
        sh, sl = swing_points(out, p.swing_len)
        out["swing_high"] = sh
        out["swing_low"] = sl
        stop_long = (out["low"].rolling(2).min() - out["atr"] * p.stop_buffer_atr)
        stop_short = (out["high"].rolling(2).max() + out["atr"] * p.stop_buffer_atr)
        dist_long = (out["close"] - stop_long).clip(lower=out["atr"] * 0.5)
        dist_short = (stop_short - out["close"]).clip(lower=out["atr"] * 0.5)
        room_long = (out["swing_high"] - out["close"]) / dist_long
        room_short = (out["close"] - out["swing_low"]) / dist_short
        room_long_ok = room_long >= p.min_room_r
        room_short_ok = room_short >= p.min_room_r

        out["adx"] = adx(out, p.adx_len)
        ranging = out["adx"] <= p.adx_range_max
        gate = ranging if p.require_range else True

        out["ema_trend"] = ema(out["close"], p.trend_ema)
        long_c = bull_eng & rvol_ok & room_long_ok & (out["close"] > out["ema_trend"])
        short_c = bear_eng & rvol_ok & room_short_ok & (out["close"] < out["ema_trend"])
        if p.require_range:
            long_c = long_c & gate
            short_c = short_c & gate

        out["signal"] = 0
        out.loc[long_c, "signal"] = 1
        out.loc[short_c, "signal"] = -1
        out["stop_dist"] = out["atr"]
        out.loc[long_c, "stop_dist"] = dist_long[long_c]
        out.loc[short_c, "stop_dist"] = dist_short[short_c]
        out["trail_mult"] = pd.NA
        out["tp_r"] = p.take_profit_r
        out["tp_price"] = pd.NA
        out.loc[long_c, "tp_price"] = out.loc[long_c, "swing_high"]
        out.loc[short_c, "tp_price"] = out.loc[short_c, "swing_low"]
        out["reason"] = ""
        out.loc[long_c, "reason"] = "engulf_long"
        out.loc[short_c, "reason"] = "engulf_short"
        out["exit_signal"] = False
        out["bias"] = 0
        out.loc[out["close"] > out["ema_trend"], "bias"] = 1
        out.loc[out["close"] < out["ema_trend"], "bias"] = -1
        out["ranging"] = ranging
        return out
