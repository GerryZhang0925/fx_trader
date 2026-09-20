"""FXCM ForexConnect demo ping. Login + account/trades tables only. No orders."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from account.venues.fxcm import account_id_from, from_fxcm_symbol, _print_ping

USER_ENV = ("FXCM_USER", "FXCM_LOGIN", "FXCM_USERNAME")
PASSWORD_ENV = "FXCM_PASSWORD"
URL_ENV = "FXCM_URL"
CONNECTION_ENV = "FXCM_CONNECTION"
PYTHON_ENV = "FXCM_FC_PYTHON"
DEFAULT_URL = "https://www.fxcorporate.com/Hosts.jsp"
ALLOWED_URLS = frozenset(
    {
        "http://www.fxcorporate.com/Hosts.jsp",
        "https://www.fxcorporate.com/Hosts.jsp",
    }
)
MISSING_CREDS = (
    "missing FXCM_USER and FXCM_PASSWORD "
    "(Trading Station demo login, not a REST token)"
)
MISSING_SDK = (
    "forexconnect is not installed. PyPI wheels are Python 3.5-3.7 on Windows; "
    "this kit is Python 3.11+. Set FXCM_FC_PYTHON to a 3.7 interpreter that "
    "has `pip install forexconnect`, or install Python 3.7 and retry. "
    "run.py still places no orders."
)
PROBE = Path(__file__).with_name("fxcm_fc_probe.py")


class FxcmFcError(RuntimeError):
    pass


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _attr(row, *names, default=None):
    for name in names:
        if hasattr(row, name):
            val = getattr(row, name)
            if val is not None and val != "":
                return val
        if isinstance(row, dict) and name in row and row[name] not in (None, ""):
            return row[name]
    return default


def _redact(text: str, secret: str) -> str:
    if not secret:
        return text
    return text.replace(secret, "***")


def user_from_env(environ: dict | None = None) -> str:
    env = environ if environ is not None else os.environ
    for key in USER_ENV:
        raw = str(env.get(key) or "").strip()
        if raw:
            return raw
    return ""


def password_from_env(environ: dict | None = None) -> str:
    env = environ if environ is not None else os.environ
    return str(env.get(PASSWORD_ENV) or "").strip()


def normalize_url(url: str) -> str:
    raw = str(url or "").strip()
    if raw.startswith("www."):
        raw = "https://" + raw
    stripped = raw.rstrip("/")
    allowed = {u.lower() for u in ALLOWED_URLS}
    if stripped.lower() not in allowed:
        raise ValueError("ForexConnect ping only uses www.fxcorporate.com/Hosts.jsp")
    return stripped


def normalize_connection(value: str) -> str:
    raw = str(value or "Demo").strip()
    if raw.lower() != "demo":
        raise ValueError("ForexConnect ping is Demo only")
    return "Demo"


def _same_account(left: str, right: str) -> bool:
    a, b = str(left or "").strip(), str(right or "").strip()
    if a == b:
        return True
    core_a, core_b = a.lstrip("0"), b.lstrip("0")
    return bool(core_a) and core_a == core_b


def _sdk_class():
    try:
        from forexconnect import ForexConnect
    except ImportError:
        return None
    return ForexConnect


def _local_fc_python() -> str:
    candidate = Path(__file__).resolve().parents[3] / ".tools" / "py37" / "python.exe"
    return str(candidate) if candidate.is_file() else ""


def _compat_python(environ: dict | None = None) -> str:
    env = environ if environ is not None else os.environ
    explicit = str(env.get(PYTHON_ENV) or "").strip()
    if explicit:
        return explicit
    local = _local_fc_python()
    if local:
        return local
    try:
        out = subprocess.run(
            ["py", "-3.7", "-c", "import sys; print(sys.executable)"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if out.returncode == 0:
        return (out.stdout or "").strip()
    return ""


def _rows(fx, name: str) -> list:
    const = getattr(fx, name, name)
    reader = getattr(fx, "get_table_reader", None)
    if callable(reader):
        return list(reader(const) or [])
    manager = getattr(fx, "table_manager", None)
    if manager is not None:
        table = manager.get_table(const)
        return list(table or [])
    raise FxcmFcError("ForexConnect session has no account tables")


def snapshot_from_session(fx, account_id: str | None, host: str) -> dict:
    accounts = _rows(fx, "ACCOUNTS")
    if not accounts:
        raise FxcmFcError("login returned no demo accounts")
    ids = [str(_attr(a, "account_id", "AccountID") or "") for a in accounts]
    ids = [i for i in ids if i]
    wanted = str(account_id or "").strip()
    acc = None
    if wanted:
        acc = next((a for a in accounts if _same_account(str(_attr(a, "account_id", "AccountID") or ""), wanted) or _same_account(str(_attr(a, "account_name", "AccountName") or ""), wanted)), None)
        if acc is None:
            raise FxcmFcError(f"account {wanted} is not in the login's account list")
    else:
        acc = accounts[0]
    aid = str(_attr(acc, "account_id", "AccountID") or wanted)
    balance = _num(_attr(acc, "balance", "Balance"))
    used = _num(_attr(acc, "used_margin", "UsedMargin"))
    nav = _num(_attr(acc, "equity", "m2m_equity", "M2MEquity"))
    u_pl = _num(_attr(acc, "gross_pl", "pl", "day_pl", "GrossPL", "DayPL"))
    if not nav:
        nav = balance + u_pl
    usable = _attr(acc, "usable_margin", "UsableMargin", "usableMargin")
    margin_available = _num(usable) if usable is not None else balance - used
    positions = []
    for row in _rows(fx, "TRADES"):
        row_aid = str(_attr(row, "account_id", "AccountID") or "")
        if row_aid and not _same_account(row_aid, aid):
            continue
        inst = str(_attr(row, "instrument", "Instrument") or "")
        amount = _num(_attr(row, "amount", "Amount"))
        side = str(_attr(row, "buy_sell", "BuySell") or "").upper()
        if side in {"S", "SELL"}:
            amount = -abs(amount)
        elif side in {"B", "BUY"}:
            amount = abs(amount)
        positions.append(
            {
                "instrument": inst,
                "symbol": from_fxcm_symbol(inst) if inst else "",
                "units": amount,
                "unrealized_pl": _num(_attr(row, "pl", "gross_pl", "PL", "GrossPL")),
                "trade_id": str(_attr(row, "trade_id", "TradeID") or ""),
            }
        )
    return {
        "ok": True,
        "host": host,
        "account_id": aid,
        "alias": str(_attr(acc, "account_name", "AccountName") or ""),
        "currency": str(_attr(acc, "account_currency", "AccountCurrency") or ""),
        "balance": balance,
        "nav": nav,
        "unrealized_pl": u_pl,
        "margin_available": margin_available,
        "open_position_count": len(positions),
        "positions": positions,
        "account_ids": ids,
        "hedging": str(_attr(acc, "maintenance_type", "MaintenanceType") or ""),
    }


@dataclass
class FxcmForexConnect:
    """Demo login via ForexConnect. Reads accounts/trades. Never creates orders."""

    user: str
    password: str
    account_id: str | None = None
    url: str = DEFAULT_URL
    connection: str = "Demo"
    session_factory: object | None = None

    def __post_init__(self) -> None:
        self.user = str(self.user or "").strip()
        self.password = str(self.password or "").strip()
        if not self.user or not self.password:
            raise ValueError(MISSING_CREDS)
        self.url = normalize_url(self.url)
        self.connection = normalize_connection(self.connection)
        aid = str(self.account_id or "").strip()
        self.account_id = aid or None

    def ping(self) -> dict:
        factory = self.session_factory or _sdk_class()
        if factory is not None:
            return self._ping_sdk(factory)
        py = _compat_python()
        if not py:
            raise FxcmFcError(MISSING_SDK)
        return self._ping_subprocess(py)

    def _ping_sdk(self, factory) -> dict:
        fx = factory()
        entered = getattr(fx, "__enter__", None)
        session = entered() if callable(entered) else fx
        try:
            session.login(
                self.user,
                self.password,
                self.url,
                self.connection,
                "",
                "",
                lambda *_a, **_k: None,
            )
            return snapshot_from_session(session, self.account_id, self.url)
        except FxcmFcError:
            raise
        except Exception as exc:
            raise FxcmFcError(_redact(str(exc), self.password)[:400]) from None
        finally:
            try:
                logout = getattr(session, "logout", None)
                if callable(logout):
                    logout()
            except Exception:
                pass
            exited = getattr(fx, "__exit__", None)
            if callable(exited):
                try:
                    exited(None, None, None)
                except Exception:
                    pass

    def _ping_subprocess(self, python_exe: str) -> dict:
        env = os.environ.copy()
        env["FXCM_USER"] = self.user
        env["FXCM_PASSWORD"] = self.password
        env["FXCM_URL"] = self.url
        env["FXCM_CONNECTION"] = self.connection
        if self.account_id:
            env["FXCM_ACCOUNT_ID"] = self.account_id
        try:
            out = subprocess.run(
                [python_exe, str(PROBE)],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise FxcmFcError(_redact(str(exc), self.password)) from None
        err = _redact((out.stderr or out.stdout or "").strip(), self.password)
        if out.returncode != 0:
            raise FxcmFcError(err[:400] or MISSING_SDK)
        try:
            data = json.loads(out.stdout or "")
        except json.JSONDecodeError:
            raise FxcmFcError(err[:400] or "ForexConnect probe returned no JSON") from None
        if not isinstance(data, dict) or not data.get("ok"):
            raise FxcmFcError(str(data.get("error") or err or "ForexConnect probe failed")[:400])
        return data


def connect_from_env(
    cfg: dict | None = None,
    *,
    environ: dict | None = None,
    session_factory=None,
) -> FxcmForexConnect:
    env = environ if environ is not None else os.environ
    url = str(env.get(URL_ENV) or DEFAULT_URL).strip() or DEFAULT_URL
    connection = str(env.get(CONNECTION_ENV) or "Demo").strip() or "Demo"
    return FxcmForexConnect(
        user=user_from_env(env),
        password=password_from_env(env),
        account_id=account_id_from(cfg, env),
        url=url,
        connection=connection,
        session_factory=session_factory,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    from account.settings import load_config
    from output.status import tracked

    p = argparse.ArgumentParser(
        description="FXCM ForexConnect demo ping (accounts/trades). No orders."
    )
    p.add_argument("--account", default=None, help="Override FXCM_ACCOUNT_ID")
    args = p.parse_args(argv)
    cfg = load_config()
    try:
        client = connect_from_env(cfg)
    except ValueError as exc:
        print(exc, flush=True)
        return 2
    if args.account:
        client.account_id = str(args.account).strip()
    try:
        with tracked("account", "fxcm_fc_ping", message=client.account_id or "demo"):
            info = client.ping()
    except FxcmFcError as exc:
        print(exc, flush=True)
        return 1
    _print_ping(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
