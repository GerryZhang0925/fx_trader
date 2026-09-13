"""OANDA fxTrade Practice (demo) — read-only. No orders."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib import error, request

PRACTICE_HOST = "https://api-fxpractice.oanda.com"
TOKEN_ENV = ("OANDA_API_TOKEN", "OANDA_ACCESS_TOKEN")
ACCOUNT_ENV = "OANDA_ACCOUNT_ID"


class OandaError(RuntimeError):
    def __init__(self, status: int, detail: str):
        self.status = int(status)
        super().__init__(f"OANDA HTTP {status}: {detail}")


def _redact(text: str, token: str) -> str:
    if not token:
        return text
    return text.replace(token, "***")


def token_from_env(environ: dict | None = None) -> str:
    env = environ if environ is not None else os.environ
    for key in TOKEN_ENV:
        raw = str(env.get(key) or "").strip()
        if raw:
            return raw
    return ""


def account_id_from(cfg: dict | None = None, environ: dict | None = None) -> str:
    env = environ if environ is not None else os.environ
    raw = str(env.get(ACCOUNT_ENV) or "").strip()
    if raw:
        return raw
    row = ((cfg or {}).get("venues") or {}).get("oanda_practice") or {}
    return str(row.get("account_id") or "").strip()


def to_oanda_instrument(symbol: str) -> str:
    s = str(symbol).replace("_", "").replace("/", "").upper()
    if len(s) != 6:
        raise ValueError(f"need a 6-letter FX symbol, got {symbol}")
    return f"{s[:3]}_{s[3:]}"


def from_oanda_instrument(instrument: str) -> str:
    return str(instrument).replace("_", "").upper()


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class OandaPractice:
    """GET-only client for api-fxpractice.oanda.com."""

    token: str
    account_id: str | None = None
    timeout: float = 15.0
    host: str = PRACTICE_HOST
    get_json: object | None = None

    def __post_init__(self) -> None:
        self.token = str(self.token or "").strip()
        if not self.token:
            raise ValueError(
                "missing OANDA_API_TOKEN (Personal Access Token from the practice portal)"
            )
        host = str(self.host or PRACTICE_HOST).rstrip("/")
        if host != PRACTICE_HOST:
            raise ValueError("oanda_practice only connects to api-fxpractice.oanda.com")
        self.host = host
        aid = str(self.account_id or "").strip()
        self.account_id = aid or None

    def _http_get(self, path: str) -> dict:
        url = f"{self.host}{path}"
        req = request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept-Datetime-Format": "RFC3339",
            },
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OandaError(exc.code, _redact(body, self.token)[:400]) from None
        except error.URLError as exc:
            raise OandaError(0, _redact(str(exc.reason), self.token)) from None

    def fetch(self, path: str) -> dict:
        getter = self.get_json or self._http_get
        return getter(path)  # type: ignore[operator]

    def list_accounts(self) -> list[dict]:
        data = self.fetch("/v3/accounts")
        rows = data.get("accounts") or []
        return [row for row in rows if isinstance(row, dict)]

    def summary(self, account_id: str) -> dict:
        data = self.fetch(f"/v3/accounts/{account_id}/summary")
        acc = data.get("account") or {}
        return acc if isinstance(acc, dict) else {}

    def open_positions(self, account_id: str) -> list[dict]:
        data = self.fetch(f"/v3/accounts/{account_id}/openPositions")
        rows = data.get("positions") or []
        out = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            long_u = _num((row.get("long") or {}).get("units"))
            short_u = _num((row.get("short") or {}).get("units"))
            out.append(
                {
                    "instrument": str(row.get("instrument") or ""),
                    "symbol": from_oanda_instrument(str(row.get("instrument") or "")),
                    "units": long_u + short_u,
                    "unrealized_pl": _num(row.get("unrealizedPL")),
                }
            )
        return out

    def ping(self) -> dict:
        accounts = self.list_accounts()
        ids = [str(a.get("id") or "") for a in accounts if a.get("id")]
        if not ids:
            raise OandaError(200, "token returned no practice accounts")
        aid = self.account_id or ids[0]
        if aid not in ids:
            raise OandaError(403, f"account {aid} is not in the token's account list")
        acc = self.summary(aid)
        positions = self.open_positions(aid)
        return {
            "ok": True,
            "host": self.host,
            "account_id": aid,
            "alias": str(acc.get("alias") or ""),
            "currency": str(acc.get("currency") or ""),
            "balance": _num(acc.get("balance")),
            "nav": _num(acc.get("NAV")),
            "unrealized_pl": _num(acc.get("unrealizedPL")),
            "margin_available": _num(acc.get("marginAvailable")),
            "open_position_count": int(acc.get("openPositionCount") or len(positions)),
            "positions": positions,
            "account_ids": ids,
        }


def connect_from_env(cfg: dict | None = None, *, environ: dict | None = None, get_json=None) -> OandaPractice:
    env = environ if environ is not None else os.environ
    return OandaPractice(
        token=token_from_env(env),
        account_id=account_id_from(cfg, env),
        get_json=get_json,
    )


def _print_ping(info: dict) -> None:
    print(
        f"OANDA practice ok  host={info['host']}\n"
        f"  account={info['account_id']} alias={info['alias'] or '-'}\n"
        f"  currency={info['currency']} NAV={info['nav']:.2f} "
        f"balance={info['balance']:.2f} uPL={info['unrealized_pl']:.2f}\n"
        f"  margin_available={info['margin_available']:.2f} "
        f"open_positions={info['open_position_count']}",
        flush=True,
    )
    for pos in info.get("positions") or []:
        print(
            f"  {pos['symbol']} units={pos['units']} uPL={pos['unrealized_pl']}",
            flush=True,
        )
    extra = [i for i in info.get("account_ids") or [] if i != info["account_id"]]
    if extra:
        print("  other accounts: " + ", ".join(extra), flush=True)
    print("Read-only ping. No orders.", flush=True)


def main(argv: list[str] | None = None) -> int:
    import argparse

    from account.settings import load_config
    from output.status import tracked

    p = argparse.ArgumentParser(
        description="Ping OANDA fxTrade Practice (GET accounts/summary). No orders."
    )
    p.add_argument("--account", default=None, help="Override OANDA_ACCOUNT_ID")
    p.add_argument("--timeout", type=float, default=15.0)
    args = p.parse_args(argv)
    cfg = load_config()
    try:
        client = connect_from_env(cfg)
    except ValueError as exc:
        print(exc, flush=True)
        return 2
    if args.account:
        client.account_id = str(args.account).strip()
    client.timeout = float(args.timeout)
    try:
        with tracked("account", "oanda_ping", message=client.account_id or "practice"):
            info = client.ping()
    except OandaError as exc:
        print(exc, flush=True)
        return 1
    _print_ping(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

