"""Same-direction confluence: Donchian core, ranging engulfing, optional kill-zone timing."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .bars import resample_ohlcv
from .donchian import DonchianParams, DonchianStrategy
from .engulfing_rvol import EngulfingParams, EngulfingRvolStrategy
from .killzone import KillZoneParams, KillZoneStrategy


@dataclass
class ConfluenceParams:
    require_killzone: bool = False
    ranging_adx_max: float = 20.0
    donchian_width_pct: float = 0.012
    donchian: DonchianParams | None = None
    engulfing: EngulfingParams | None = None
    killzone: KillZoneParams | None = None


class ConfluenceStrategy:
    name = "confluence"

    def __init__(self, params: ConfluenceParams | None = None, **kwargs):
        self.params = params or ConfluenceParams()
        self._donchian = DonchianStrategy(self.params.donchian)
        eng_params = self.params.engulfing or EngulfingParams(
            adx_range_max=self.params.ranging_adx_max,
            require_range=True,
        )
        eng_params.require_range = True
        eng_params.adx_range_max = self.params.ranging_adx_max
        self._engulfing = EngulfingRvolStrategy(eng_params)
        self._killzone = KillZoneStrategy(self.params.killzone)

    def prepare(
        self,
        df: pd.DataFrame,
        m5: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        h4 = df.copy()
        core = self._donchian.prepare(h4)
        sub = self._engulfing.prepare(h4)
        width = (core["donch_hi"] - core["donch_lo"]) / core["close"]
        ranging = (sub["adx"] <= self.params.ranging_adx_max) | (
            width <= self.params.donchian_width_pct
        )

        kz_dir = pd.Series(0, index=h4.index)
        if m5 is not None and len(m5) > 50:
            kz = self._killzone.prepare(m5)
            # Map any M5 signal onto the H4 bar that contains it
            mapped = kz["signal"].copy()
            mapped.index = mapped.index.tz_convert("UTC")
            buckets = mapped.groupby(pd.Grouper(freq="4h")).apply(
                lambda s: 1 if (s == 1).any() else (-1 if (s == -1).any() else 0)
            )
            kz_dir = buckets.reindex(h4.index, method="ffill").fillna(0).astype(int)
        elif self.params.require_killzone:
            # No M5: cannot require kill zone; leave flat
            kz_dir[:] = 0

        out = h4.copy()
        out["atr"] = core["atr"]
        out["stop_dist"] = core["stop_dist"]
        out["trail_mult"] = core["trail_mult"]
        out["tp_r"] = core["tp_r"]
        out["tp_price"] = pd.NA
        out["reason"] = ""
        out["signal"] = 0
        out["bias"] = core["bias"]
        out["ranging"] = ranging
        out["kz_dir"] = kz_dir.reindex(out.index).fillna(0).astype(int)

        core_sig = core["signal"].astype(int)
        sub_sig = sub["signal"].astype(int)
        use_kz = self.params.require_killzone and m5 is not None

        for ts in out.index:
            c = int(core_sig.loc[ts])
            e = int(sub_sig.loc[ts])
            k = int(out.at[ts, "kz_dir"])
            chosen = 0
            reason = ""
            stop = core.at[ts, "stop_dist"]
            trail = core.at[ts, "trail_mult"]
            tp_r = core.at[ts, "tp_r"]
            tp_price = pd.NA
            if c != 0:
                if (not use_kz) or k == c:
                    chosen, reason = c, "core_donchian"
            elif ranging.at[ts] and e != 0 and e == int(core.at[ts, "bias"]):
                if (not use_kz) or k == e:
                    chosen, reason = e, "sub_engulfing"
                    stop = sub.at[ts, "stop_dist"]
                    trail = pd.NA
                    tp_r = sub.at[ts, "tp_r"]
                    tp_price = sub.at[ts, "tp_price"]
            if chosen != 0:
                out.at[ts, "signal"] = chosen
                out.at[ts, "reason"] = reason
                out.at[ts, "stop_dist"] = stop
                out.at[ts, "trail_mult"] = trail
                out.at[ts, "tp_r"] = tp_r
                out.at[ts, "tp_price"] = tp_price
        out["exit_signal"] = False
        return out

    def prepare_m5(self, m5: pd.DataFrame, h4: pd.DataFrame | None = None) -> pd.DataFrame:
        """M5 kill-zone entries filtered by H4 Donchian/EMA bias."""
        if h4 is None:
            h4 = resample_ohlcv(m5, "4h")
        core = self._donchian.prepare(h4)
        bias = core["bias"].reindex(m5.index, method="ffill").fillna(0).astype(int)
        kz = self._killzone.prepare(m5)
        out = kz.copy()
        aligned = (out["signal"] != 0) & (out["signal"] == bias)
        out.loc[~aligned, "signal"] = 0
        out.loc[aligned, "reason"] = "kz_h4_aligned"
        out["h4_bias"] = bias
        return out
