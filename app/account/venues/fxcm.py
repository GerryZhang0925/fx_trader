"""FXCM REST demo — read-only. Socket.IO sid + GET snapshot. No orders."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from urllib import error, parse, request

DEMO_HOST = "https://api-demo.fxcm.com"
TOKEN_ENV = ("FXCM_API_TOKEN", "FXCM_ACCESS_TOKEN")
ACCOUNT_ENV = "FXCM_ACCOUNT_ID"


class FxcmError(RuntimeError):
    def __init__(self, status: int, detail: str):
        self.status = int(status)
        super().__init__(f"FXCM HTTP {status}: {detail}")


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
    row = ((cfg or {}).get("venues") or {}).get("fxcm_demo") or {}
    return str(row.get("account_id") or "").strip()


def to_fxcm_symbol(symbol: str) -> str:
    s = str(symbol).replace("_", "").replace("/", "").upper()
    if len(s) != 6:
        raise ValueError(f"need a 6-letter FX symbol, got {symbol}")
    return f"{s[:3]}/{s[3:]}"


def from_fxcm_symbol(symbol: str) -> str:
    return str(symbol).replace("/", "").replace("_", "").upper()


def bearer(socket_id: str, token: str) -> str:
    return f"Bearer {socket_id}{token}"


def parse_engineio_sid(body: str) -> str:
    """Engine.IO v3 polling packet: ``97:0{"sid":"..."}``."""
    text = (body or "").strip()
    idx = text.find("{")
    if idx < 0:
        raise FxcmError(0, "socket handshake had no JSON")
    end = text.find("}", idx)
    payload = text[idx : end + 1] if end > idx else text[idx:]
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise FxcmError(0, f"socket handshake JSON: {exc}") from None
    sid = str(data.get("sid") or "").strip()
    if not sid:
        raise FxcmError(0, "socket handshake missing sid")
    return sid


def _num(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _account_rows(data: dict) -> list[dict]:
    rows = data.get("accounts") or data.get("Account") or []
    return [row for row in rows if isinstance(row, dict) and not row.get("isTotal")]


def _position_rows(data: dict) -> list[dict]:
    rows = data.get("open_positions") or data.get("OpenPosition") or []
    return [row for row in rows if isinstance(row, dict) and not row.get("isTotal")]


@dataclass
class FxcmDemo:
    """GET-only client for api-demo.fxcm.com. REST after a Socket.IO sid."""

    token: str
    account_id: str | None = None
    timeout: float = 15.0
    host: str = DEMO_HOST
    get_json: object | None = None
    open_socket: object | None = None
    sid: str | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.token = str(self.token or "").strip()
        if not self.token:
            raise ValueError(
                "missing FXCM_API_TOKEN (Trading Station → User Account → Token Management)"
            )
        host = str(self.host or DEMO_HOST).rstrip("/")
        if host != DEMO_HOST:
            raise ValueError("fxcm_demo only connects to api-demo.fxcm.com")
        self.host = host
        aid = str(self.account_id or "").strip()
        self.account_id = aid or None

    def _headers(self, sid: str) -> dict[str, str]:
        return {
            "Authorization": bearer(sid, self.token),
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "request",
            "Cookie": f"io={sid}",
        }

    def _urlopen(self, req: request.Request) -> tuple[int, str]:
        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                return int(resp.status), resp.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise FxcmError(exc.code, _redact(body, self.token)[:400]) from None
        except error.URLError as exc:
            raise FxcmError(0, _redact(str(exc.reason), self.token)) from None

    def handshake(self) -> str:
        opener = self.open_socket
        if opener is not None:
            sid = str(opener()).strip()
            if not sid:
                raise FxcmError(0, "open_socket returned no sid")
            self.sid = sid
            return sid
        q = parse.urlencode(
            {"access_token": self.token, "EIO": "3", "transport": "polling"}
        )
        get_req = request.Request(
            f"{self.host}/socket.io/?{q}",
            headers={"User-Agent": "request", "Accept": "*/*"},
            method="GET",
        )
        _, body = self._urlopen(get_req)
        sid = parse_engineio_sid(body)
        post_q = parse.urlencode(
            {
                "access_token": self.token,
                "EIO": "3",
                "transport": "polling",
                "sid": sid,
            }
        )
        post_req = request.Request(
            f"{self.host}/socket.io/?{post_q}",
            data=b"40",
            headers={
                "User-Agent": "request",
                "Content-Type": "text/plain;charset=UTF-8",
                "Cookie": f"io={sid}",
            },
            method="POST",
        )
        try:
            self._urlopen(post_req)
        except FxcmError:
            # Sid from GET is enough on some demo nodes.
            pass
        self.sid = sid
        return sid

    def _http_get(self, path: str) -> dict:
        sid = self.sid or self.handshake()
        url = f"{self.host}{path}"
        req = request.Request(url, headers=self._headers(sid), method="GET")
        _, body = self._urlopen(req)
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise FxcmError(200, f"not JSON: {exc}") from None
        if not isinstance(data, dict):
            raise FxcmError(200, "snapshot was not an object")
        executed = (data.get("response") or {}).get("executed")
        if executed is False:
            err = (data.get("response") or {}).get("error") or "executed=false"
            raise FxcmError(200, _redact(str(err), self.token)[:400])
        return data

    def fetch(self, path: str) -> dict:
        getter = self.get_json or self._http_get
        return getter(path)  # type: ignore[operator]

    def snapshot(self) -> dict:
        if self.get_json is None and not self.sid:
            self.handshake()
        return self.fetch("/trading/get_model/?models=Account&models=OpenPosition")

    def ping(self) -> dict:
        data = self.snapshot()
        accounts = _account_rows(data)
        if not accounts:
            raise FxcmError(200, "token returned no demo accounts")
        ids = [str(a.get("accountId") or a.get("accountName") or "") for a in accounts]
        ids = [i for i in ids if i]
        aid = self.account_id or ids[0]
        acc = next(
            (
                a
                for a in accounts
                if str(a.get("accountId") or "") == aid
                or str(a.get("accountName") or "") == aid
            ),
            None,
        )
        if acc is None:
            raise FxcmError(403, f"account {aid} is not in the token's account list")
        positions = []
        for row in _position_rows(data):
            row_aid = str(row.get("accountId") or row.get("accountName") or "")
            if row_aid and row_aid not in {str(acc.get("accountId") or ""), str(acc.get("accountName") or "")}:
                continue
            amount_k = _num(row.get("amountK"))
            sign = 1.0 if row.get("isBuy") else -1.0
            positions.append(
                {
                    "instrument": str(row.get("currency") or ""),
                    "symbol": from_fxcm_symbol(str(row.get("currency") or "")),
                    "units": sign * amount_k * 1000.0,
                    "unrealized_pl": _num(row.get("grossPL")),
                    "trade_id": str(row.get("tradeId") or ""),
                }
            )
        return {
            "ok": True,
            "host": self.host,
            "account_id": str(acc.get("accountId") or aid),
            "alias": str(acc.get("accountName") or ""),
            "currency": "",
            "balance": _num(acc.get("balance")),
            "nav": _num(acc.get("equity")),
            "unrealized_pl": _num(acc.get("grossPL")),
            "margin_available": _num(acc.get("usableMargin")),
            "open_position_count": len(positions),
            "positions": positions,
            "account_ids": ids,
            "hedging": str(acc.get("hedging") or ""),
        }


def connect_from_env(cfg: dict | None = None, *, environ: dict | None = None, get_json=None, open_socket=None) -> FxcmDemo:
    env = environ if environ is not None else os.environ
    return FxcmDemo(
        token=token_from_env(env),
        account_id=account_id_from(cfg, env),
        get_json=get_json,
        open_socket=open_socket,
    )


def _print_ping(info: dict) -> None:
    print(
        f"FXCM demo ok  host={info['host']}\n"
        f"  account={info['account_id']} alias={info['alias'] or '-'}\n"
        f"  NAV={info['nav']:.2f} balance={info['balance']:.2f} "
        f"uPL={info['unrealized_pl']:.2f}\n"
        f"  margin_available={info['margin_available']:.2f} "
        f"open_positions={info['open_position_count']}"
        + (f" hedging={info['hedging']}" if info.get("hedging") else ""),
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
        description="Ping FXCM demo REST (socket sid + GET accounts). No orders."
    )
    p.add_argument("--account", default=None, help="Override FXCM_ACCOUNT_ID")
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
        with tracked("account", "fxcm_ping", message=client.account_id or "demo"):
            info = client.ping()
    except FxcmError as exc:
        print(exc, flush=True)
        return 1
    _print_ping(info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
