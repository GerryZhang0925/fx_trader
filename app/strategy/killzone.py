"""London/NY kill zone + H1 EMA stack + sweep + FVG score (original simplified model)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .bars import resample_ohlcv
from .indicators import atr, bearish_fvg, bullish_fvg, ema, in_session, swing_points


@dataclass
class KillZoneParams:
    london: str = "07:00-10:00"
    newyork: str = "13:00-16:00"
    timezone: str = "UTC"
    h1_fast: int = 21
    h1_slow: int = 50
    h1_trend: int = 200
    swing_len: int = 5
    min_score: int = 6
    take_profit_r: float = 2.0
    atr_len: int = 14
    atr_mult: float = 1.5
    use_pdh_pdl: bool = True
    m5_fast: int = 9
    m5_slow: int = 21


def _split_session(window: str) -> tuple[str, str]:
    start, end = window.split("-")
    return start.strip(), end.strip()


class KillZoneStrategy:
    name = "killzone"

    def __init__(self, params: KillZoneParams | None = None, **kwargs):
        if params is None:
            allow = KillZoneParams.__dataclass_fields__.keys()
            params = KillZoneParams(**{k: v for k, v in kwargs.items() if k in allow and v is not None})
        self.params = params

    def prepare(self, df: pd.DataFrame, h1: pd.DataFrame | None = None) -> pd.DataFrame:
        p = self.params
        out = df.copy()
        if h1 is None:
            h1 = resample_ohlcv(out, "1h")
        h1 = h1.copy()
        h1["ema_fast"] = ema(h1["close"], p.h1_fast)
        h1["ema_slow"] = ema(h1["close"], p.h1_slow)
        h1["ema_trend"] = ema(h1["close"], p.h1_trend)
        # Completed H1 bar only (shift 1) then join to M5
        h1_bias = pd.DataFrame(
            {
                "h1_fast": h1["ema_fast"].shift(1),
                "h1_slow": h1["ema_slow"].shift(1),
                "h1_trend": h1["ema_trend"].shift(1),
            }
        )
        aligned = h1_bias.reindex(out.index, method="ffill")
        out = out.join(aligned)
        bull_stack = (out["h1_fast"] > out["h1_slow"]) & (out["h1_slow"] > out["h1_trend"])
        bear_stack = (out["h1_fast"] < out["h1_slow"]) & (out["h1_slow"] < out["h1_trend"])

        ls, le = _split_session(p.london)
        ns, ne = _split_session(p.newyork)
        london = in_session(out.index, ls, le, p.timezone)
        ny = in_session(out.index, ns, ne, p.timezone)
        in_kz = london | ny
        out["in_killzone"] = in_kz

        sh, sl = swing_points(out, p.swing_len)
        sweep_bull = (out["low"] < sl) & (out["close"] > sl)
        sweep_bear = (out["high"] > sh) & (out["close"] < sh)
        fvg_bull = bullish_fvg(out)
        fvg_bear = bearish_fvg(out)
        out["ema_fast_m5"] = ema(out["close"], p.m5_fast)
        out["ema_slow_m5"] = ema(out["close"], p.m5_slow)
        m5_bull = out["ema_fast_m5"] > out["ema_slow_m5"]
        m5_bear = out["ema_fast_m5"] < out["ema_slow_m5"]

        score_long = (
            in_kz.astype(int) * 2
            + bull_stack.astype(int) * 2
            + sweep_bull.astype(int) * 3
            + fvg_bull.astype(int) * 2
            + m5_bull.astype(int)
        )
        score_short = (
            in_kz.astype(int) * 2
            + bear_stack.astype(int) * 2
            + sweep_bear.astype(int) * 3
            + fvg_bear.astype(int) * 2
            + m5_bear.astype(int)
        )
        out["score_long"] = score_long
        out["score_short"] = score_short
        long_c = in_kz & bull_stack & sweep_bull & (score_long >= p.min_score)
        short_c = in_kz & bear_stack & sweep_bear & (score_short >= p.min_score)

        out["atr"] = atr(out, p.atr_len)
        dist_long = (out["close"] - (out["low"] - out["atr"] * 0.1)).clip(lower=out["atr"] * p.atr_mult)
        dist_short = ((out["high"] + out["atr"] * 0.1) - out["close"]).clip(lower=out["atr"] * p.atr_mult)

        day = pd.Series(out.index.tz_convert("UTC").normalize(), index=out.index)
        daily = out.groupby(day).agg(high=("high", "max"), low=("low", "min"))
        daily["pdh"] = daily["high"].shift(1)
        daily["pdl"] = daily["low"].shift(1)
        pdh = day.map(daily["pdh"])
        pdl = day.map(daily["pdl"])

        out["signal"] = 0
        out.loc[long_c, "signal"] = 1
        out.loc[short_c, "signal"] = -1
        out["stop_dist"] = out["atr"] * p.atr_mult
        out.loc[long_c, "stop_dist"] = dist_long[long_c]
        out.loc[short_c, "stop_dist"] = dist_short[short_c]
        out["trail_mult"] = pd.NA
        out["tp_r"] = p.take_profit_r
        out["tp_price"] = pd.NA
        if p.use_pdh_pdl:
            out.loc[long_c, "tp_price"] = pdh[long_c]
            out.loc[short_c, "tp_price"] = pdl[short_c]
        out["reason"] = ""
        out.loc[long_c, "reason"] = "kz_long"
        out.loc[short_c, "reason"] = "kz_short"
        out["exit_signal"] = False
        out["bias"] = 0
        out.loc[bull_stack, "bias"] = 1
        out.loc[bear_stack, "bias"] = -1
        return out
