from __future__ import annotations

from feed.loader import make_synthetic, resample_ohlcv


def test_h1_to_h4_keeps_ohlc_contract():
    h1 = make_synthetic(n=48, freq="1h", seed=1)
    h4 = resample_ohlcv(h1, "4h")
    assert list(h4.columns) == ["open", "high", "low", "close", "volume"]
    assert len(h4) == 12
    assert h4["high"].iloc[0] >= h4["open"].iloc[0]
    assert h4["low"].iloc[0] <= h4["close"].iloc[0]
