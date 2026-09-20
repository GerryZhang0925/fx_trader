from __future__ import annotations

import pytest

from account.venues.fxcm import (
    DEMO_HOST,
    FxcmDemo,
    bearer,
    connect_from_env,
    from_fxcm_symbol,
    parse_engineio_sid,
    to_fxcm_symbol,
)


def test_symbol_round_trip():
    assert to_fxcm_symbol("USDJPY") == "USD/JPY"
    assert from_fxcm_symbol("USD/JPY") == "USDJPY"


def test_bearer_is_sid_then_token():
    assert bearer("sock", "tok") == "Bearer socktok"


def test_parse_engineio_sid():
    body = '97:0{"sid":"HHGqC3Gao2ENa5tNAAEu","upgrades":["websocket"],"pingInterval":25000}'
    assert parse_engineio_sid(body) == "HHGqC3Gao2ENa5tNAAEu"


def test_demo_host_only():
    with pytest.raises(ValueError, match="api-demo"):
        FxcmDemo(token="tok", host="https://api.fxcm.com")


def test_missing_token():
    with pytest.raises(ValueError, match="FXCM_API_TOKEN"):
        connect_from_env(environ={})


def test_cli_reports_rest_deprecated():
    from account.venues.fxcm import REST_DEPRECATED, main

    assert main([]) == 2
    assert "deprecated" in REST_DEPRECATED.lower()


def test_ping_reads_accounts_and_positions():
    calls: list[str] = []

    def fake(path: str) -> dict:
        calls.append(path)
        return {
            "response": {"executed": True},
            "accounts": [
                {
                    "accountId": "1027808",
                    "accountName": "01027808",
                    "balance": 50000.0,
                    "equity": 50010.5,
                    "grossPL": 10.5,
                    "usableMargin": 49000.0,
                    "hedging": "N",
                    "isTotal": False,
                }
            ],
            "open_positions": [
                {
                    "accountId": "1027808",
                    "currency": "USD/JPY",
                    "isBuy": False,
                    "amountK": 1,
                    "grossPL": 10.5,
                    "tradeId": "1",
                    "isTotal": False,
                }
            ],
        }

    client = FxcmDemo(token="secret-token", open_socket=lambda: "sid123", get_json=fake)
    info = client.ping()
    assert info["ok"] is True
    assert info["host"] == DEMO_HOST
    assert info["nav"] == 50010.5
    assert info["positions"][0]["symbol"] == "USDJPY"
    assert info["positions"][0]["units"] == -1000.0
    assert any("get_model" in p for p in calls)


def test_unknown_account_id_rejected():
    def fake(path: str) -> dict:
        return {
            "response": {"executed": True},
            "accounts": [{"accountId": "1027808", "accountName": "01027808"}],
            "open_positions": [],
        }

    client = FxcmDemo(
        token="tok", account_id="999", open_socket=lambda: "sid", get_json=fake
    )
    with pytest.raises(Exception, match="not in the token"):
        client.ping()


def test_http_error_redacts_token():
    from account.venues.fxcm import _redact

    assert "secret-token" not in _redact("Authorization Bearer secret-token", "secret-token")
