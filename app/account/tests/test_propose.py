from __future__ import annotations

from account.propose import propose


def test_propose_adds_size_on_signal():
    snap = {
        "symbol": "USDCAD",
        "pip_size": 0.0001,
        "signal": 1,
        "side": "long",
        "close": 1.35,
        "stop_dist": 0.005,
    }
    cfg = {
        "initial_equity": 100000.0,
        "cost": {"spread_pips": 1.0, "slippage_pips": 0.2, "lot_size": 100000.0},
        "portfolio": {"risk_pct_per_pair": 5.0},
    }
    out = propose(snap, cfg)
    assert out["lots"] > 0
    assert out["units"] > 0
    assert out["risk_pct"] == 5.0
    assert out["fill_price_if_next_open_equals_close"] > out["close"]
    assert "order" not in out


def test_propose_flat_has_no_size():
    out = propose({"symbol": "USDJPY", "signal": 0, "close": 150.0, "stop_dist": None, "pip_size": 0.01}, {"portfolio": {"risk_pct_per_pair": 5.0}})
    assert out["lots"] is None
    assert out["signal"] == 0
