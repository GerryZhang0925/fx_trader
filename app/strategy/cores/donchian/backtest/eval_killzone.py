"""Kill Zone as H4-bar overlap only. M5 thinning already rejected."""

from __future__ import annotations

import pandas as pd

from paths import boot

boot()

from strategy.cores.donchian.backtest.overlay_eval import gate_signals, run_overlay  # noqa: E402
from strategy.cores.donchian.confidence import _bar_overlaps, _split  # noqa: E402

FILTERS = ("baseline", "kz_overlap", "london", "newyork", "skip_kz")


def attach_kz(symbol: str, prepared: pd.DataFrame, data_dir) -> pd.DataFrame:
    out = prepared.copy()
    idx = out.index
    out["london"] = _bar_overlaps(idx, *_split("07:00-10:00"), "UTC")
    out["newyork"] = _bar_overlaps(idx, *_split("13:00-16:00"), "UTC")
    out["kz"] = out["london"] | out["newyork"]
    return out


def apply_kz(prepared: pd.DataFrame, name: str) -> pd.DataFrame:
    sig = prepared["signal"] != 0
    if name == "baseline":
        keep = sig
    elif name == "kz_overlap":
        keep = sig & prepared["kz"]
    elif name == "london":
        keep = sig & prepared["london"]
    elif name == "newyork":
        keep = sig & prepared["newyork"]
    elif name == "skip_kz":
        keep = sig & ~prepared["kz"].fillna(False)
    else:
        raise ValueError(f"unknown killzone filter {name!r}")
    return gate_signals(prepared, keep)


def main() -> int:
    return run_overlay(
        filters=FILTERS,
        attach=attach_kz,
        apply_fn=apply_kz,
        report_stem="killzone_h4",
        title="H4 Kill Zone overlap on adopted Donchian",
        note="London 07–10 and NY 13–16 UTC on the H4 bar. No M5.",
    )


if __name__ == "__main__":
    raise SystemExit(main())
