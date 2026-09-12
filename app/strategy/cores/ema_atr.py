"""20/50 EMA cross with 200-EMA regime filter and ATR trail."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from strategy.common.indicators import atr, ema


@dataclass
class EmaAtrParams:
    fast: int = 20
    slow: int = 50
    trend: int = 200
    atr_len: int = 14
    atr_mult: float = 2.5
    take_profit_r: float | None = 2.0


class EmaAtrStrategy:
    name = "ema_atr"

    def __init__(self, params: EmaAtrParams | None = None, **kwargs):
        if params is None:
            params = EmaAtrParams(**{k: v for k, v in kwargs.items() if v is not None})
        self.params = params

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        out = df.copy()
        out["ema_fast"] = ema(out["close"], p.fast)
        out["ema_slow"] = ema(out["close"], p.slow)
        out["ema_trend"] = ema(out["close"], p.trend)
        out["atr"] = atr(out, p.atr_len)
        out["stop_dist"] = out["atr"] * p.atr_mult
        bull_cross = (out["ema_fast"] > out["ema_slow"]) & (
            out["ema_fast"].shift(1) <= out["ema_slow"].shift(1)
        )
        bear_cross = (out["ema_fast"] < out["ema_slow"]) & (
            out["ema_fast"].shift(1) >= out["ema_slow"].shift(1)
        )
        long_c = bull_cross & (out["close"] > out["ema_trend"])
        short_c = bear_cross & (out["close"] < out["ema_trend"])
        out["signal"] = 0
        out.loc[long_c, "signal"] = 1
        out.loc[short_c, "signal"] = -1
        out["trail_mult"] = p.atr_mult
        out["tp_r"] = p.take_profit_r if p.take_profit_r else pd.NA
        out["tp_price"] = pd.NA
        out["reason"] = ""
        out.loc[long_c, "reason"] = "ema_golden"
        out.loc[short_c, "reason"] = "ema_death"
        out["exit_signal"] = False
        out.loc[bear_cross, "exit_signal"] = True
        out.loc[bull_cross, "exit_signal"] = True
        # Do not flatten the same bar we enter on the cross
        out.loc[long_c | short_c, "exit_signal"] = False
        out["bias"] = 0
        out.loc[out["close"] > out["ema_trend"], "bias"] = 1
        out.loc[out["close"] < out["ema_trend"], "bias"] = -1
        return out
