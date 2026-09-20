# Python 3.7 ForexConnect probe. Prints one JSON object. No orders.
from __future__ import print_function

import json
import os
import sys


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _attr(row, *names):
    for name in names:
        if hasattr(row, name):
            val = getattr(row, name)
            if val is not None and val != "":
                return val
    return None


def _same_account(left, right):
    a, b = str(left or "").strip(), str(right or "").strip()
    if a == b:
        return True
    core_a, core_b = a.lstrip("0"), b.lstrip("0")
    return bool(core_a) and core_a == core_b


def _symbol(inst):
    return str(inst or "").replace("/", "").replace("_", "").upper()


def _rows(fx, name):
    const = getattr(fx, name)
    if hasattr(fx, "get_table_reader"):
        return list(fx.get_table_reader(const) or [])
    table = fx.table_manager.get_table(const)
    return list(table or [])


def main():
    try:
        from forexconnect import ForexConnect
    except ImportError:
        print("forexconnect is not installed on this interpreter", file=sys.stderr)
        return 2

    user = (os.environ.get("FXCM_USER") or os.environ.get("FXCM_LOGIN") or os.environ.get("FXCM_USERNAME") or "").strip()
    password = (os.environ.get("FXCM_PASSWORD") or "").strip()
    url = (os.environ.get("FXCM_URL") or "https://www.fxcorporate.com/Hosts.jsp").strip()
    connection = (os.environ.get("FXCM_CONNECTION") or "Demo").strip()
    wanted = (os.environ.get("FXCM_ACCOUNT_ID") or "").strip()
    if not user or not password:
        print("missing FXCM_USER and FXCM_PASSWORD", file=sys.stderr)
        return 2
    if connection.lower() != "demo":
        print("ForexConnect ping is Demo only", file=sys.stderr)
        return 2

    fx = ForexConnect()
    try:
        fx.login(user, password, url, "Demo", "", "")
        accounts = _rows(fx, "ACCOUNTS")
        if not accounts:
            print("login returned no demo accounts", file=sys.stderr)
            return 1
        ids = []
        acc = None
        for row in accounts:
            aid = str(_attr(row, "account_id", "AccountID") or "")
            if aid:
                ids.append(aid)
            if wanted and (
                _same_account(aid, wanted)
                or _same_account(str(_attr(row, "account_name", "AccountName") or ""), wanted)
            ):
                acc = row
        if wanted and acc is None:
            print("account %s is not in the login's account list" % wanted, file=sys.stderr)
            return 1
        if acc is None:
            acc = accounts[0]
        aid = str(_attr(acc, "account_id", "AccountID") or wanted)
        balance = _num(_attr(acc, "balance", "Balance"))
        used = _num(_attr(acc, "used_margin", "UsedMargin"))
        nav = _num(_attr(acc, "equity", "m2m_equity", "M2MEquity"))
        u_pl = _num(_attr(acc, "gross_pl", "pl", "day_pl", "GrossPL", "DayPL"))
        if not nav:
            nav = balance + u_pl
        usable = _attr(acc, "usable_margin", "UsableMargin")
        margin_available = _num(usable) if usable is not None else balance - used
        positions = []
        for row in _rows(fx, "TRADES"):
            row_aid = str(_attr(row, "account_id", "AccountID") or "")
            if row_aid and not _same_account(row_aid, aid):
                continue
            inst = str(_attr(row, "instrument", "Instrument") or "")
            amount = _num(_attr(row, "amount", "Amount"))
            side = str(_attr(row, "buy_sell", "BuySell") or "").upper()
            if side in ("S", "SELL"):
                amount = -abs(amount)
            elif side in ("B", "BUY"):
                amount = abs(amount)
            positions.append(
                {
                    "instrument": inst,
                    "symbol": _symbol(inst),
                    "units": amount,
                    "unrealized_pl": _num(_attr(row, "pl", "gross_pl", "PL", "GrossPL")),
                    "trade_id": str(_attr(row, "trade_id", "TradeID") or ""),
                }
            )
        payload = {
            "ok": True,
            "host": url,
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
        print(json.dumps(payload))
        return 0
    except Exception as exc:
        secret = password
        text = str(exc)
        if secret:
            text = text.replace(secret, "***")
        print(text, file=sys.stderr)
        return 1
    finally:
        try:
            fx.logout()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
