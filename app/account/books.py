"""Venue accounts, sleeves, and contract spec. Not a broker client."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

FillKind = Literal["paper", "demo", "live"]
SameDirection = Literal["ignore", "add", "replace"]
Opposite = Literal["reverse", "flatten", "hedge"]


@dataclass(frozen=True)
class StackingPolicy:
    """Declared with the strategy spec. Account only executes it."""

    one_position: bool = True
    same_direction: SameDirection = "ignore"
    opposite: Opposite = "reverse"


DONCHIAN_H4 = StackingPolicy(one_position=True, same_direction="ignore", opposite="reverse")


@dataclass(frozen=True)
class VenueSpec:
    """Per venue-account contract. Strategy never reads this."""

    lot_size: float = 100_000.0
    lot_step: float = 0.01
    min_lot: float = 0.01
    pip_size: float | None = None


@dataclass(frozen=True)
class VenueAccount:
    """One login at one tool. Demo tools usually allow one account each; live may be many firms."""

    id: str
    kind: FillKind
    connector: str
    currency: str
    spec: VenueSpec = field(default_factory=VenueSpec)
    halted: bool = False


@dataclass(frozen=True)
class Sleeve:
    """Capital slice inside one venue account. Does not cross connectors."""

    id: str
    venue_id: str
    core: str
    symbols: tuple[str, ...]
    risk_pct: float
    stacking: StackingPolicy = field(default_factory=lambda: DONCHIAN_H4)


def round_lots(raw_lots: float, spec: VenueSpec) -> float:
    """Round down to lot_step. Below min_lot → 0 (skip). Never round up past intended risk."""
    if raw_lots <= 0 or spec.lot_step <= 0:
        return 0.0
    stepped = (int(raw_lots / spec.lot_step)) * spec.lot_step
    # Guard float dust.
    stepped = round(stepped / spec.lot_step) * spec.lot_step
    if stepped + 1e-12 < spec.min_lot:
        return 0.0
    return float(stepped)


def stacking_conflict(sleeves: list[Sleeve], symbol: str) -> list[str]:
    """Same symbol on two sleeves is a book refusal, not a strategy add."""
    hit = [s.id for s in sleeves if symbol.upper() in {x.upper() for x in s.symbols}]
    return hit if len(hit) > 1 else []


def default_paper_usd() -> VenueAccount:
    return VenueAccount(
        id="paper_research",
        kind="paper",
        connector="engine",
        currency="USD",
        spec=VenueSpec(),
    )


def default_donchian_sleeve() -> Sleeve:
    return Sleeve(
        id="donchian_h4",
        venue_id="paper_research",
        core="donchian",
        symbols=("USDCAD", "USDJPY", "GBPUSD"),
        risk_pct=5.0,
        stacking=DONCHIAN_H4,
    )


def load_venues(cfg: dict) -> dict[str, VenueAccount]:
    raw = cfg.get("venues")
    if not raw:
        v = default_paper_usd()
        return {v.id: v}
    out: dict[str, VenueAccount] = {}
    for vid, row in raw.items():
        spec_raw = row.get("spec") or {}
        kind_raw = str(row.get("kind", "paper")).lower()
        if kind_raw not in ("paper", "demo", "live"):
            raise ValueError(f"venue {vid}: kind must be paper|demo|live, got {kind_raw}")
        out[str(vid)] = VenueAccount(
            id=str(vid),
            kind=kind_raw,  # type: ignore[arg-type]
            connector=str(row.get("connector", "engine")),
            currency=str(row.get("currency", "USD")).upper(),
            spec=VenueSpec(
                lot_size=float(spec_raw.get("lot_size", row.get("lot_size", 100000))),
                lot_step=float(spec_raw.get("lot_step", row.get("lot_step", 0.01))),
                min_lot=float(spec_raw.get("min_lot", row.get("min_lot", 0.01))),
            ),
            halted=bool(row.get("halted", False)),
        )
    return out


def load_sleeves(cfg: dict) -> list[Sleeve]:
    raw = cfg.get("sleeves")
    if not raw:
        return [default_donchian_sleeve()]
    out: list[Sleeve] = []
    for sid, row in raw.items():
        stack = row.get("stacking") or {}
        out.append(
            Sleeve(
                id=str(sid),
                venue_id=str(row["venue"]),
                core=str(row.get("core", "donchian")),
                symbols=tuple(str(s).upper() for s in (row.get("symbols") or [])),
                risk_pct=float(row.get("risk_pct", 5.0)),
                stacking=StackingPolicy(
                    one_position=bool(stack.get("one_position", True)),
                    same_direction=str(stack.get("same_direction", "ignore")),  # type: ignore[arg-type]
                    opposite=str(stack.get("opposite", "reverse")),  # type: ignore[arg-type]
                ),
            )
        )
    return out


def sleeve_for(cfg: dict, *, core: str | None, symbol: str | None) -> Sleeve:
    sleeves = load_sleeves(cfg)
    core_name = (core or "donchian").lower()
    sym = (symbol or "").upper()
    for s in sleeves:
        if s.core.lower() != core_name:
            continue
        if not sym or not s.symbols or sym in s.symbols:
            return s
    return default_donchian_sleeve()
