from __future__ import annotations

import pytest

from account.venues.oanda import (
    OandaPractice,
    PRACTICE_HOST,
    connect_from_env,
    from_oanda_instrument,
    to_oanda_instrument,
)


def test_instrument_round_trip():
    assert to_oanda_instrument("USDJPY") == "USD_JPY"
    assert from_oanda_instrument("USD_JPY") == "USDJPY"


def test_practice_host_only():
    with pytest.raises(ValueError, match="api-fxpractice"):
        OandaPractice(token="tok", host="https://api-fxtrade.oanda.com")


def test_missing_token():
    with pytest.raises(ValueError, match="OANDA_API_TOKEN"):
        connect_from_env(environ={})


def test_ping_reads_summary_and_positions():
    calls: list[str] = []

    def fake(path: str) -> dict:
        calls.append(path)
        if path == "/v3/accounts":
            return {"accounts": [{"id": "101-001-1"}]}
        if path.endswith("/summary"):
            return {
                "account": {
                    "id": "101-001-1",
                    "alias": "practice",
                    "currency": "USD",
                    "balance": "100000.0",
                    "NAV": "100010.5",
                    "unrealizedPL": "10.5",
                    "marginAvailable": "99000.0",
                    "openPositionCount": 1,
                }
            }
        if path.endswith("/openPositions"):
            return {
                "positions": [
                    {
                        "instrument": "USD_JPY",
                        "long": {"units": "0"},
                        "short": {"units": "-1000"},
                        "unrealizedPL": "10.5",
                    }
                ]
            }
        raise AssertionError(path)

    client = OandaPractice(token="secret-token", get_json=fake)
    info = client.ping()
    assert info["ok"] is True
    assert info["host"] == PRACTICE_HOST
    assert info["currency"] == "USD"
    assert info["nav"] == 100010.5
    assert info["positions"][0]["symbol"] == "USDJPY"
    assert info["positions"][0]["units"] == -1000.0
    assert "/v3/accounts" in calls


def test_unknown_account_id_rejected():
    def fake(path: str) -> dict:
        if path == "/v3/accounts":
            return {"accounts": [{"id": "101-001-1"}]}
        raise AssertionError(path)

    client = OandaPractice(token="tok", account_id="999", get_json=fake)
    with pytest.raises(Exception, match="not in the token"):
        client.ping()


def test_http_error_redacts_token():
    from account.venues.oanda import _redact

    assert "secret-token" not in _redact("Authorization Bearer secret-token", "secret-token")
