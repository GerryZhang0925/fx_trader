"""Console markdown for proposals. No orders."""

from __future__ import annotations


def format_text(payload: dict) -> str:
    lines = [
        "# Donchian proposals (no orders)",
        "",
        "Closed H4 bar only. Fill would be the next bar open. Not advice. Not a broker.",
        f"Generated: {payload.get('time')}",
        "Daily halt reminder: max 2 trades / 3 losses / -2R that day.",
        "",
    ]
    for row in payload.get("data", {}).get("pairs", []):
        mark = "SIGNAL" if row.get("signal") else "flat"
        lines.append(f"## {row.get('symbol')}  [{mark}]  {row.get('side')}")
        lines.append(f"- bar UTC {row.get('bar_open_utc')}  /  JST {row.get('bar_open_jst')}")
        lines.append(
            f"- close={row.get('close')}  ADX={row.get('adx')}  EMA={row.get('ema_trend')}  "
            f"donch={row.get('donch_hi')} / {row.get('donch_lo')}"
        )
        if row.get("signal"):
            lines.append(f"- reason={row.get('reason')}  stop_dist={row.get('stop_dist')}")
            lines.append(
                f"- estimated fill if next open=close={row.get('fill_price_if_next_open_equals_close')}  "
                f"stop={row.get('stop_price_if_filled_at_close')}  "
                f"1R partial={row.get('partial_1r_if_filled_at_close')}"
            )
            lots = row.get("lots")
            units = row.get("units")
            lines.append(
                f"- size ~ {lots:.4f} lots ({units:.0f} units)  "
                f"risk {row.get('risk_pct')}% of {row.get('equity')}  "
                f"spread {row.get('spread_pips')} pip + slip {row.get('slippage_pips')}"
                if lots is not None and units is not None
                else f"- trail ATR x {row.get('trail_atr_mult')}  risk {row.get('risk_pct')}%"
            )
            lines.append(
                f"- trail ATR x {row.get('trail_atr_mult')}  "
                f"partial {float(row.get('partial_frac') or 0) * 100:.0f}% at {row.get('partial_r')}R"
            )
        else:
            lines.append("- no entry on this closed bar")
        recent = row.get("recent_signals") or []
        if recent:
            last_fire = recent[-1]
            lines.append(
                f"- last fire: {last_fire.get('bar_open_jst')} {last_fire.get('side')} @ {last_fire.get('close')}"
            )
        lines.append("")
    return "\n".join(lines)
