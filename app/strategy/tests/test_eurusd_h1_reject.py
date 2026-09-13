from __future__ import annotations

import pandas as pd

from account.engine import EngineConfig, run_backtest
from account.risk import RiskConfig
from feed.loader import make_synthetic
from strategy.cores.eurusd_h1_breakout_reject import EurusdH1RejectStrategy


def test_reject_needs_prior_close_break_then_return():
    n = 80
    idx = pd.date_range("2024-01-15 08:00", periods=n, freq="1h", tz="UTC")
    close = pd.Series(1.1000, index=idx)
    close.iloc[40] = 1.1030
    close.iloc[41] = 1.1005
    high = close + 0.0002
    high.iloc[40] = 1.1032
    low = close - 0.0002
    low.iloc[40] = 1.0998
    df = pd.DataFrame(
        {"open": close, "high": high, "low": low, "close": close, "volume": 1.0},
        index=idx,
    )
    out = EurusdH1RejectStrategy().prepare(df)
    assert out.loc[idx[41], "signal"] in (-1, 0)


def test_reject_prepares_h1_and_backtests():
    h1 = make_synthetic(n=2500, freq="1h", seed=12, vol=0.0008)
    prepared = EurusdH1RejectStrategy().prepare(h1)
    need = {"signal", "stop_dist", "h4_adx", "in_overlap", "max_hold_bars", "donch_hi"}
    assert need.issubset(prepared.columns)
    shorts = prepared["signal"] == -1
    longs = prepared["signal"] == 1
    if shorts.any():
        assert prepared.loc[shorts, "in_overlap"].all()
        assert (prepared.loc[shorts, "close"] > prepared.loc[shorts, "ema_center"]).all()
    if longs.any():
        assert prepared.loc[longs, "in_overlap"].all()
        assert (prepared.loc[longs, "close"] < prepared.loc[longs, "ema_center"]).all()
    cfg = EngineConfig(risk=RiskConfig(max_trades_per_day=20, max_consecutive_losses=20))
    eq, _ = run_backtest(prepared, cfg)
    assert len(eq) == len(h1)
    assert eq.iloc[-1] > 0
