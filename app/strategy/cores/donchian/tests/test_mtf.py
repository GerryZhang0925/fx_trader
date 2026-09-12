from __future__ import annotations

from feed.loader import make_synthetic, resample_ohlcv
from strategy.cores.donchian.backtest.eval_mtf import apply_h1, attach_h1
from strategy.cores.donchian import DonchianStrategy


def test_h1_features_use_last_bar_in_h4_bucket():
    h1 = make_synthetic(n=800, freq="1h", seed=5, trend=0.00002)
    h4 = resample_ohlcv(h1, "4h")
    prepared = attach_h1(DonchianStrategy().prepare(h4), h1)
    assert {"h1_ema50_slope_pct", "h1_above_ema50", "h1_donch_pos"}.issubset(prepared.columns)
    later = attach_h1(DonchianStrategy().prepare(h4.iloc[:-8]), h1.iloc[:-32])
    overlap = later.index.intersection(prepared.index)[:-2]
    cols = ["h1_ema50_slope_pct", "h1_donch_pos"]
    delta = (prepared.loc[overlap, cols] - later.loc[overlap, cols]).abs().max().max()
    assert delta < 1e-12


def test_h1_filters_only_zero_signals():
    h1 = make_synthetic(n=800, freq="1h", seed=5, trend=0.00002)
    h4 = resample_ohlcv(h1, "4h")
    prepared = attach_h1(DonchianStrategy().prepare(h4), h1)
    base_n = int((prepared["signal"] != 0).sum())
    assert apply_h1(prepared, "baseline")["signal"].equals(prepared["signal"])
    for name in ("h1_slope_agree", "h1_ema50_side", "h1_ema200_side", "h1_donch_third"):
        gated = apply_h1(prepared, name)
        assert int((gated["signal"] != 0).sum()) <= base_n
        kept = gated["signal"] != 0
        assert (gated.loc[kept, "signal"] == prepared.loc[kept, "signal"]).all()
