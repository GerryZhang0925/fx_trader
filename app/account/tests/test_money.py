from __future__ import annotations

from account.money import convert, quote_to_account, units_for_risk


FX = {"USDJPY": 150.0, "USDCAD": 1.35, "GBPUSD": 1.30, "EURUSD": 1.10}


def test_same_currency_is_identity():
    assert convert(100.0, "JPY", "JPY", FX) == 100.0


def test_usd_jpy_round_trip():
    jpy = convert(100.0, "USD", "JPY", FX)
    assert abs(jpy - 15000.0) < 1e-9
    assert abs(convert(jpy, "JPY", "USD", FX) - 100.0) < 1e-9


def test_usdjpy_stop_risk_uses_quote_jpy():
    # $5000 risk, 50 pip (0.50 JPY) stop at 150 → units = 5000 / (0.50/150) = 1_500_000
    units = units_for_risk(5000.0, 0.50, "USDJPY", "USD", FX)
    assert abs(units - 1_500_000.0) < 1e-6
    assert abs(quote_to_account(0.50, "USDJPY", "USD", FX) - (0.50 / 150.0)) < 1e-12


def test_gbpusd_jpy_account():
    # 5% of ¥10_000_000 = 500_000 JPY, stop 0.0050 USD, GBPUSD 1.30, USDJPY 150
    # stop in JPY = 0.005 * 150 = 0.75
    units = units_for_risk(500_000.0, 0.005, "GBPUSD", "JPY", FX)
    assert abs(units - (500_000.0 / 0.75)) < 1e-6
