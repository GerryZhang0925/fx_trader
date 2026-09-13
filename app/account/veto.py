"""Night watch veto list. Alerts only. Does not gate Donchian signals or place orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

_NY = ZoneInfo("America/New_York")
_LONDON = ZoneInfo("Europe/London")
_UTC = timezone.utc


@dataclass(frozen=True)
class VetoConfig:
    spread_pips: float = 2.0
    indicator_minutes: int = 60
    max_daily_loss_r: float = 2.0
    max_consecutive_losses: int = 3
    nfp_hour: int = 8
    nfp_minute: int = 30
    fomc_hour: int = 14
    fomc_minute: int = 0


@dataclass(frozen=True)
class VetoResult:
    reject: bool
    reasons: tuple[str, ...]
    codes: tuple[str, ...]
    in_overlap: bool
    signature: str
    notify: bool


def veto_from_cfg(cfg: dict | None) -> VetoConfig:
    risk = (cfg or {}).get("risk") or {}
    raw = (cfg or {}).get("veto") or {}
    return VetoConfig(
        spread_pips=float(raw.get("spread_pips", 2.0)),
        indicator_minutes=int(raw.get("indicator_minutes", 60)),
        max_daily_loss_r=float(raw.get("max_daily_loss_r", risk.get("max_daily_loss_r", 2.0))),
        max_consecutive_losses=int(
            raw.get("max_consecutive_losses", risk.get("max_consecutive_losses", 3))
        ),
    )


def in_london_ny_overlap_at(now: datetime) -> bool:
    """DST overlap: London 08–16 and NY 08–17 local. Not 13:00–17:00 UTC."""
    utc = _as_utc(now)
    london = utc.astimezone(_LONDON)
    ny = utc.astimezone(_NY)
    lm = london.hour * 60 + london.minute
    nm = ny.hour * 60 + ny.minute
    return (8 * 60 <= lm < 16 * 60) and (8 * 60 <= nm < 17 * 60)


def _as_utc(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=_UTC)
    return now.astimezone(_UTC)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    shift = (weekday - first.weekday()) % 7
    return date(year, month, 1 + shift + (n - 1) * 7)


def _ny_event(year: int, month: int, weekday: int, n: int, hour: int, minute: int) -> datetime:
    day = _nth_weekday(year, month, weekday, n)
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=_NY)


def _within_minutes(now: datetime, event: datetime, minutes: int) -> bool:
    delta = abs((_as_utc(now) - event.astimezone(_UTC)).total_seconds())
    return delta <= minutes * 60


def _nearby_nfp_fomc(now: datetime, cfg: VetoConfig) -> tuple[bool, bool]:
    utc = _as_utc(now)
    ny = utc.astimezone(_NY)
    nfp = False
    fomc = False
    for month_delta in (-1, 0, 1):
        y, m = ny.year, ny.month + month_delta
        if m < 1:
            y, m = y - 1, 12
        elif m > 12:
            y, m = y + 1, 1
        nfp_at = _ny_event(y, m, 4, 1, cfg.nfp_hour, cfg.nfp_minute)
        fomc_at = _ny_event(y, m, 2, 3, cfg.fomc_hour, cfg.fomc_minute)
        nfp = nfp or _within_minutes(utc, nfp_at, cfg.indicator_minutes)
        fomc = fomc or _within_minutes(utc, fomc_at, cfg.indicator_minutes)
    return nfp, fomc


def book_near_halt(
    *,
    venue_halted: bool = False,
    daily_r: float | None = None,
    consecutive_losses: int | None = None,
    cfg: VetoConfig | None = None,
) -> bool:
    """H4 book only. Satellites are not live. daily_r is R, not percent."""
    p = cfg or VetoConfig()
    if venue_halted:
        return True
    if daily_r is not None and daily_r <= -p.max_daily_loss_r:
        return True
    if consecutive_losses is not None and consecutive_losses >= p.max_consecutive_losses:
        return True
    return False


def evaluate(
    now: datetime,
    *,
    spread_pips: float | None = None,
    venue_halted: bool = False,
    daily_r: float | None = None,
    consecutive_losses: int | None = None,
    cfg: VetoConfig | None = None,
) -> VetoResult:
    """Reject-list snapshot. Does not change signals. BID CSV has no live spread."""
    p = cfg or VetoConfig()
    overlap = in_london_ny_overlap_at(now)
    nfp, fomc = _nearby_nfp_fomc(now, p)
    codes: list[str] = []
    reasons: list[str] = []
    if nfp:
        codes.append("nfp")
        reasons.append(f"NFP proxy within {p.indicator_minutes}m (first Friday 08:30 NY)")
    if fomc:
        codes.append("fomc")
        reasons.append(f"FOMC proxy within {p.indicator_minutes}m (third Wednesday 14:00 NY)")
    if spread_pips is not None and spread_pips > p.spread_pips:
        codes.append("spread")
        reasons.append(f"spread {spread_pips:.2f} pip > {p.spread_pips:.2f}")
    if book_near_halt(
        venue_halted=venue_halted, daily_r=daily_r, consecutive_losses=consecutive_losses, cfg=p
    ):
        codes.append("book")
        extra = []
        if venue_halted:
            extra.append("venue halted")
        if daily_r is not None:
            extra.append(f"daily_r={daily_r:.2f}")
        if consecutive_losses is not None:
            extra.append(f"losses={consecutive_losses}")
        reasons.append("H4 book halt (" + ", ".join(extra) + ")")

    watch = [c for c in codes if c in ("nfp", "fomc") or overlap]
    signature = "|".join(watch) if watch else ""
    return VetoResult(
        reject=bool(codes),
        reasons=tuple(reasons),
        codes=tuple(codes),
        in_overlap=overlap,
        signature=signature,
        notify=bool(watch),
    )


def format_alert(result: VetoResult, now: datetime) -> str:
    utc = _as_utc(now).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "VETO (watch only, no orders)",
        utc,
        "H4 Donchian 3-pair. Not a new entry.",
    ]
    lines.extend(f"- {row}" for row in result.reasons)
    return "\n".join(lines)


@dataclass
class VetoDedup:
    last: str = field(default="")

    def should_send(self, result: VetoResult) -> bool:
        if not result.notify or not result.signature:
            return False
        if result.signature == self.last:
            return False
        self.last = result.signature
        return True


def main(argv: list[str] | None = None) -> int:
    import argparse

    from account.books import load_venues
    from account.settings import load_config
    from output.status import tracked

    p = argparse.ArgumentParser(
        description="H4 Donchian night-watch veto list. Alerts only. No orders."
    )
    p.add_argument("--spread", type=float, default=None, help="Current spread in pips if known")
    p.add_argument("--daily-r", type=float, default=None, dest="daily_r")
    p.add_argument("--losses", type=int, default=None, help="H4 book consecutive losses")
    args = p.parse_args(argv)
    cfg = load_config()
    now = datetime.now(timezone.utc)
    halted = any(v.halted for v in load_venues(cfg).values())
    result = evaluate(
        now,
        spread_pips=args.spread,
        venue_halted=halted,
        daily_r=args.daily_r,
        consecutive_losses=args.losses,
        cfg=veto_from_cfg(cfg),
    )
    with tracked("account", "veto", message=result.signature or "clear"):
        if result.reasons:
            print(format_alert(result, now), flush=True)
        else:
            print(f"VETO clear  {now:%Y-%m-%d %H:%M UTC}", flush=True)
        print(
            f"overlap={result.in_overlap} notify={result.notify} codes={list(result.codes)}",
            flush=True,
        )
        print("Watch only. Does not gate Donchian signals. No orders.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
