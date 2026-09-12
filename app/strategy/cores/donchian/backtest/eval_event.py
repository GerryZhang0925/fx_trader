"""Halt new Donchian entries around USD employment / FOMC proxy windows.

No official calendar file is in the kit. First Friday 12:00–16:00 UTC (NFP proxy)
and third Wednesday 16:00–20:00 UTC (FOMC proxy), plus the previous H4 bar.
"""

from __future__ import annotations

import pandas as pd

from paths import boot

boot()

from strategy.cores.donchian.backtest.overlay_eval import gate_signals, run_overlay  # noqa: E402
from strategy.cores.donchian.confidence import _bar_overlaps, _split  # noqa: E402

FILTERS = ("baseline", "nfp", "fomc", "nfp_fomc")


def _event_days(index: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series]:
    utc = index.tz_convert("UTC")
    nfp = (utc.weekday == 4) & (utc.day <= 7)
    fomc = (utc.weekday == 2) & (utc.day >= 15) & (utc.day <= 21)
    return pd.Series(nfp, index=index), pd.Series(fomc, index=index)


def attach_event(symbol: str, prepared: pd.DataFrame, data_dir) -> pd.DataFrame:
    out = prepared.copy()
    nfp_day, fomc_day = _event_days(out.index)
    nfp_win = _bar_overlaps(out.index, *_split("12:00-16:00"), "UTC")
    fomc_win = _bar_overlaps(out.index, *_split("16:00-20:00"), "UTC")
    nfp = nfp_day & nfp_win
    fomc = fomc_day & fomc_win
    out["halt_nfp"] = nfp | nfp.shift(1, fill_value=False)
    out["halt_fomc"] = fomc | fomc.shift(1, fill_value=False)
    out["halt_both"] = out["halt_nfp"] | out["halt_fomc"]
    return out


def apply_event(prepared: pd.DataFrame, name: str) -> pd.DataFrame:
    sig = prepared["signal"] != 0
    if name == "baseline":
        keep = sig
    elif name == "nfp":
        keep = sig & ~prepared["halt_nfp"]
    elif name == "fomc":
        keep = sig & ~prepared["halt_fomc"]
    elif name == "nfp_fomc":
        keep = sig & ~prepared["halt_both"]
    else:
        raise ValueError(f"unknown event filter {name!r}")
    return gate_signals(prepared, keep)


def main() -> int:
    return run_overlay(
        filters=FILTERS,
        attach=attach_event,
        apply_fn=apply_event,
        report_stem="event",
        title="USD event halt on adopted Donchian",
        note="Proxy calendar (first Friday NFP, third Wednesday FOMC), not an official feed. Halt event bar + previous H4.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
