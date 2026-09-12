from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import CostConfig, EngineConfig, run_backtest
from risk import RiskConfig, position_units


def _ohlcv(n: int, start="2020-01-01", freq="4h", price=1.10) -> pd.DataFrame:
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    close = pd.Series(price, index=idx, dtype=float)
    return pd.DataFrame(
        {
            "open": close,
            "high": close + 0.001,
            "low": close - 0.001,
            "close": close,
            "volume": 1000.0,
        },
        index=idx,
    )


def test_fill_is_next_bar_open():
    df = _ohlcv(6)
    df["signal"] = 0
    df["stop_dist"] = 0.002
    df["atr"] = 0.0008
    df.iloc[1, df.columns.get_loc("signal")] = 1
    df.iloc[2, df.columns.get_loc("open")] = 1.1234
    df.iloc[2, df.columns.get_loc("high")] = 1.13
    df.iloc[2, df.columns.get_loc("low")] = 1.12
    df.iloc[2, df.columns.get_loc("close")] = 1.125
    cfg = EngineConfig(
        initial_equity=100_000,
        risk=RiskConfig(risk_pct=1.0, max_trades_per_day=5, max_consecutive_losses=10),
        cost=CostConfig(spread_pips=0.0, slippage_pips=0.0),
    )
    _, trades = run_backtest(df, cfg)
    assert len(trades) >= 1
    assert trades.iloc[0]["entry_time"] == df.index[2]
    assert abs(trades.iloc[0]["entry"] - 1.1234) < 1e-9


def test_same_bar_stop_uses_stop_not_close():
    df = _ohlcv(5, price=1.20)
    df["signal"] = 0
    df["stop_dist"] = 0.001
    df["atr"] = 0.0004
    df.iloc[0, df.columns.get_loc("signal")] = 1
    df.iloc[1, df.columns.get_loc("open")] = 1.20
    df.iloc[1, df.columns.get_loc("high")] = 1.201
    df.iloc[1, df.columns.get_loc("low")] = 1.198
    df.iloc[1, df.columns.get_loc("close")] = 1.2005
    cfg = EngineConfig(
        cost=CostConfig(spread_pips=0.0, slippage_pips=0.0),
        risk=RiskConfig(max_trades_per_day=5, max_consecutive_losses=10),
    )
    _, trades = run_backtest(df, cfg)
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "stop"
    assert trades.iloc[0]["exit"] <= 1.20 - 0.001 + 1e-9


def test_daily_halt_after_three_losses():
    n = 20
    df = _ohlcv(n, freq="1h", price=1.10)
    df["signal"] = 0
    df["stop_dist"] = 0.0005
    df["atr"] = 0.0002
    # Signal every other bar so fills can occur; each trade stops out immediately.
    for i in range(0, 12, 1):
        df.iloc[i, df.columns.get_loc("signal")] = 1
        df.iloc[i, df.columns.get_loc("low")] = 1.09
    cfg = EngineConfig(
        cost=CostConfig(spread_pips=0.0, slippage_pips=0.0),
        risk=RiskConfig(risk_pct=1.0, max_trades_per_day=10, max_consecutive_losses=3),
    )
    _, trades = run_backtest(df, cfg)
    assert len(trades) == 3


from run_portfolio import parse_symbols, risk_pct_for


def test_risk_pct_for_reads_config_and_overrides():
    port = {"risk_pct_per_pair": 4.0, "risk_pct_by_pair": {"USDJPY": 3.0}}
    assert risk_pct_for("USDCAD", port) == 4.0
    assert risk_pct_for("USDJPY", port) == 3.0
    assert risk_pct_for("USDJPY", port, override=5.0) == 5.0
    assert parse_symbols(None, {"candidates": ["usdcad", "usdjpy"]}) == ["USDCAD", "USDJPY"]
    assert parse_symbols("gbpusd, usdcad", {}) == ["GBPUSD", "USDCAD"]


def test_donchian_ignores_current_bar_high():
    df = _ohlcv(80, price=1.10)
    df["high"] = 1.101
    df["low"] = 1.099
    df["close"] = 1.100
    df["open"] = 1.100
    df.iloc[-1, df.columns.get_loc("high")] = 1.20
    df.iloc[-1, df.columns.get_loc("close")] = 1.19
    from strategies.donchian import DonchianParams, DonchianStrategy

    out = DonchianStrategy(
        DonchianParams(use_adx_filter=False, use_atr_filter=False, partial_frac=0.0)
    ).prepare(df)
    assert out["donch_hi"].iloc[-1] < 1.15
    assert out["signal"].iloc[-1] == 1


def test_partial_one_r_closes_half():
    df = _ohlcv(8, price=1.10)
    df["signal"] = 0
    df["stop_dist"] = 0.010
    df["atr"] = 0.004
    df["trail_mult"] = 10.0
    df["partial_frac"] = 0.5
    df["partial_r"] = 1.0
    df.iloc[0, df.columns.get_loc("signal")] = 1
    # Fill at bar 1 open 1.10, 1R = 1.11. Hit 1R on bar 2, then hold.
    df.iloc[1, df.columns.get_loc("open")] = 1.10
    df.iloc[1, df.columns.get_loc("high")] = 1.101
    df.iloc[1, df.columns.get_loc("low")] = 1.099
    df.iloc[2, df.columns.get_loc("open")] = 1.105
    df.iloc[2, df.columns.get_loc("high")] = 1.12
    df.iloc[2, df.columns.get_loc("low")] = 1.104
    df.iloc[2, df.columns.get_loc("close")] = 1.11
    cfg = EngineConfig(
        cost=CostConfig(spread_pips=0.0, slippage_pips=0.0),
        risk=RiskConfig(max_trades_per_day=5, max_consecutive_losses=10),
    )
    eq, trades = run_backtest(df, cfg)
    assert not trades.empty
    # Still in remainder or closed later; equity should have risen after 1R partial.
    assert eq.iloc[2] > cfg.initial_equity


def test_breakeven_after_partial():
    df = _ohlcv(8, price=1.10)
    df["signal"] = 0
    df["stop_dist"] = 0.010
    df["atr"] = 0.004
    df["trail_mult"] = 0.0
    df["partial_frac"] = 0.5
    df["partial_r"] = 1.0
    df["be_after_partial"] = True
    df.iloc[0, df.columns.get_loc("signal")] = 1
    df.iloc[1, df.columns.get_loc("open")] = 1.10
    df.iloc[1, df.columns.get_loc("high")] = 1.101
    df.iloc[1, df.columns.get_loc("low")] = 1.099
    df.iloc[2, df.columns.get_loc("open")] = 1.105
    df.iloc[2, df.columns.get_loc("high")] = 1.12
    df.iloc[2, df.columns.get_loc("low")] = 1.104
    df.iloc[2, df.columns.get_loc("close")] = 1.11
    # After 1R, stop should sit at entry so a dip to 1.10 exits remainder at BE.
    df.iloc[3, df.columns.get_loc("open")] = 1.108
    df.iloc[3, df.columns.get_loc("high")] = 1.109
    df.iloc[3, df.columns.get_loc("low")] = 1.099
    df.iloc[3, df.columns.get_loc("close")] = 1.100
    cfg = EngineConfig(
        cost=CostConfig(spread_pips=0.0, slippage_pips=0.0),
        risk=RiskConfig(max_trades_per_day=5, max_consecutive_losses=10),
    )
    _, trades = run_backtest(df, cfg)
    assert len(trades) == 1
    assert trades.iloc[0]["r"] > 0.4


def test_kelly_fraction_example():
    from risk import kelly_fraction

    assert abs(kelly_fraction(0.40, 2.0) - 0.10) < 1e-9
    assert kelly_fraction(0.40, 0.5) == 0.0


def test_kelly_growth_continuous():
    from risk import kelly_growth

    # μ=0.001 daily, σ=0.01 → f* = 0.001/0.0001 = 10 (raw; half-Kelly would be 5)
    assert abs(kelly_growth(0.001, 0.01) - 10.0) < 1e-9
    assert kelly_growth(-0.001, 0.01) == 0.0


def test_daily_sharpe_and_sortino():
    from metrics import compute_metrics

    idx = pd.date_range("2020-01-01", periods=80, freq="4h", tz="UTC")
    growth = 100_000 * (1.001 ** np.arange(80))
    growth[40:48] *= 0.98  # brief dip so Calmar is defined
    eq = pd.Series(growth, index=idx)
    trades = pd.DataFrame({"pnl": [10.0, -5.0], "r": [0.2, -0.1]})
    m = compute_metrics(eq, trades, 100_000)
    assert m.sharpe > 0
    assert m.sortino > 0
    assert m.cagr > 0
    assert m.calmar > 0


def test_webhook_signature_and_skip():
    from reporting import envelope, notify, sign_payload

    secret = "test-secret"
    body = b'{"ok":true}'
    sig = sign_payload(secret, "2026-01-01T00:00:00Z", "id-1", body)
    assert len(sig) == 64
    assert notify({}, envelope({"x": 1})) is None
    seen = {}

    def poster(url, headers, raw):
        seen["url"] = url
        seen["sig"] = headers.get("X-Webhook-Signature")
        seen["id"] = headers.get("X-Idempotency-Key")
        return 204

    env = envelope({"hello": 1})
    result = notify({"webhook": {"url": "https://example.invalid/hook", "secret": secret}}, env, poster=poster)
    assert result["ok"] is True
    assert seen["url"].startswith("https://")
    assert seen["sig"].startswith("sha256=")
    assert seen["id"] == env["id"]
