from __future__ import annotations

import json

import pytest

from account.venues.fxcm_fc import (
    DEFAULT_URL,
    FxcmFcError,
    FxcmForexConnect,
    connect_from_env,
    snapshot_from_session,
)


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class FakeFx:
    ACCOUNTS = "accounts"
    TRADES = "trades"

    def __init__(self):
        self.logged_in = False
        self.logged_out = False
        self.login_args = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password, url, connection, session_id, pin, callback=None):
        self.logged_in = True
        self.login_args = (user, password, url, connection)

    def logout(self):
        self.logged_out = True

    def get_table_reader(self, table):
        if table == self.ACCOUNTS:
            return [
                _Row(
                    account_id="03534103",
                    account_name="Demo",
                    balance=50000.0,
                    equity=50010.5,
                    used_margin=1000.0,
                    gross_pl=10.5,
                    usable_margin=49000.0,
                )
            ]
        return [
            _Row(
                account_id="03534103",
                instrument="USD/JPY",
                amount=1000,
                buy_sell="S",
                pl=10.5,
                trade_id="1",
            )
        ]


def test_missing_creds():
    with pytest.raises(ValueError, match="FXCM_USER"):
        connect_from_env(environ={})


def test_demo_only():
    with pytest.raises(ValueError, match="Demo only"):
        FxcmForexConnect(user="u", password="p", connection="Real")


def test_hosts_jsp_only():
    with pytest.raises(ValueError, match="Hosts.jsp"):
        FxcmForexConnect(user="u", password="p", url="https://api-demo.fxcm.com")


def test_ping_reads_accounts_and_trades():
    client = FxcmForexConnect(
        user="demo-user",
        password="secret",
        session_factory=FakeFx,
    )
    info = client.ping()
    assert info["ok"] is True
    assert info["host"] == DEFAULT_URL
    assert info["account_id"] == "03534103"
    assert info["nav"] == 50010.5
    assert info["positions"][0]["symbol"] == "USDJPY"
    assert info["positions"][0]["units"] == -1000.0


def test_unknown_account_id_rejected():
    client = FxcmForexConnect(
        user="u",
        password="p",
        account_id="999",
        session_factory=FakeFx,
    )
    with pytest.raises(FxcmFcError, match="not in the login"):
        client.ping()


def test_snapshot_matches_leading_zero_account():
    fx = FakeFx()
    info = snapshot_from_session(fx, "3534103", DEFAULT_URL)
    assert info["account_id"] == "03534103"


def test_cli_missing_creds(monkeypatch, capsys):
    from account.venues.fxcm_fc import main

    for key in ("FXCM_USER", "FXCM_LOGIN", "FXCM_USERNAME", "FXCM_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    assert main([]) == 2
    assert "FXCM_USER" in capsys.readouterr().out


def test_sdk_missing_without_compat_python(monkeypatch):
    monkeypatch.setattr("account.venues.fxcm_fc._sdk_class", lambda: None)
    monkeypatch.setattr("account.venues.fxcm_fc._compat_python", lambda environ=None: "")
    client = FxcmForexConnect(user="u", password="p")
    with pytest.raises(FxcmFcError, match="forexconnect is not installed"):
        client.ping()


def test_probe_json_round_trip(monkeypatch):
    payload = {
        "ok": True,
        "host": DEFAULT_URL,
        "account_id": "03534103",
        "alias": "Demo",
        "currency": "USD",
        "balance": 1.0,
        "nav": 1.0,
        "unrealized_pl": 0.0,
        "margin_available": 1.0,
        "open_position_count": 0,
        "positions": [],
        "account_ids": ["03534103"],
        "hedging": "",
    }

    def fake_run(*args, **kwargs):
        class Result:
            returncode = 0
            stdout = json.dumps(payload)
            stderr = ""

        return Result()

    monkeypatch.setattr("account.venues.fxcm_fc._sdk_class", lambda: None)
    monkeypatch.setattr(
        "account.venues.fxcm_fc._compat_python", lambda environ=None: "python37"
    )
    monkeypatch.setattr("account.venues.fxcm_fc.subprocess.run", fake_run)
    info = FxcmForexConnect(user="u", password="p").ping()
    assert info["account_id"] == "03534103"
