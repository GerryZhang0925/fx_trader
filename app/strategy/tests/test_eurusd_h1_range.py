from __future__ import annotations

import pandas as pd

from account.engine import EngineConfig, run_backtest
from account.risk import RiskConfig
from feed.loader import make_synthetic
from strategy.common.indicators import in_london_ny_overlap, rsi
from strategy.cores.eurusd_h1_range import EurusdH1RangeStrategy


def test_rsi_rises_in_uptrend():
    close = pd.Series([1.0 + 0.001 * i for i in range(80)])
    values = rsi(close, 14).dropna()
    assert values.between(0, 100).all()
    assert float(values.iloc[-1]) > 70


def test_london_ny_overlap_uses_dst():
    winter_in = pd.DatetimeIndex(["2024-01-15 14:00:00"], tz="UTC")
    winter_out = pd.DatetimeIndex(["2024-01-15 10:00:00"], tz="UTC")
    summer_after_london = pd.DatetimeIndex(["2024-07-15 15:30:00"], tz="UTC")
    assert bool(in_london_ny_overlap(winter_in).iloc[0])
    assert not bool(in_london_ny_overlap(winter_out).iloc[0])
    assert not bool(in_london_ny_overlap(summer_after_london).iloc[0])


def test_range_fade_prepares_h1_and_backtests():
    h1 = make_synthetic(n=2500, freq="1h", seed=8, vol=0.0008)
    prepared = EurusdH1RangeStrategy().prepare(h1)
    assert {"signal", "stop_dist", "h4_adx", "in_overlap", "max_hold_bars", "tp_price"}.issubset(
        prepared.columns
    )
    longs = prepared["signal"] == 1
    shorts = prepared["signal"] == -1
    if longs.any():
        assert (prepared.loc[longs, "close"] < prepared.loc[longs, "ema_center"]).all()
        assert prepared.loc[longs, "in_overlap"].all()
    if shorts.any():
        assert (prepared.loc[shorts, "close"] > prepared.loc[shorts, "ema_center"]).all()
        assert prepared.loc[shorts, "in_overlap"].all()
    cfg = EngineConfig(risk=RiskConfig(max_trades_per_day=20, max_consecutive_losses=20))
    eq, _ = run_backtest(prepared, cfg)
    assert len(eq) == len(h1)
    assert eq.iloc[-1] > 0
