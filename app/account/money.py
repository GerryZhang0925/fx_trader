"""Quote PnL and risk into a venue account currency. Research engine does not use this yet."""

from __future__ import annotations

from feed.pairs import quote_currency

# fx[PAIR] is the conventional quote: USDJPY=150 means 1 USD = 150 JPY.
_USD_DIRECT = {"EUR": "EURUSD", "GBP": "GBPUSD", "AUD": "AUDUSD", "NZD": "NZDUSD"}
_USD_INDIRECT = {"JPY": "USDJPY", "CAD": "USDCAD", "CHF": "USDCHF"}


def usd_per_unit(ccy: str, fx: dict[str, float]) -> float:
    """How many USD one unit of `ccy` is worth."""
    code = str(ccy).upper()
    if code == "USD":
        return 1.0
    if code in _USD_DIRECT:
        pair = _USD_DIRECT[code]
        if pair not in fx:
            raise KeyError(f"need {pair} to convert {code}")
        return float(fx[pair])
    if code in _USD_INDIRECT:
        pair = _USD_INDIRECT[code]
        if pair not in fx:
            raise KeyError(f"need {pair} to convert {code}")
        rate = float(fx[pair])
        if rate <= 0:
            raise ValueError(f"{pair} rate must be > 0")
        return 1.0 / rate
    raise KeyError(f"unsupported currency {code}")


def convert(amount: float, src: str, dst: str, fx: dict[str, float]) -> float:
    src_u = str(src).upper()
    dst_u = str(dst).upper()
    if src_u == dst_u:
        return float(amount)
    return float(amount) * usd_per_unit(src_u, fx) / usd_per_unit(dst_u, fx)


def quote_to_account(amount_quote: float, symbol: str, account_ccy: str, fx: dict[str, float]) -> float:
    return convert(amount_quote, quote_currency(symbol), account_ccy, fx)


def units_for_risk(
    risk_account: float,
    stop_dist: float,
    symbol: str,
    account_ccy: str,
    fx: dict[str, float],
) -> float:
    """Units so a full stop ≈ risk_account in the venue account currency."""
    if stop_dist <= 0 or risk_account <= 0:
        return 0.0
    stop_account = quote_to_account(stop_dist, symbol, account_ccy, fx)
    if stop_account <= 0:
        return 0.0
    return float(risk_account) / stop_account
