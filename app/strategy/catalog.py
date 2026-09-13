from __future__ import annotations

from .cores.bb_squeeze_pivot import BbSqueezePivotParams, BbSqueezePivotStrategy
from .cores.confluence import ConfluenceParams, ConfluenceStrategy
from .cores.donchian import DonchianParams, DonchianStrategy
from .cores.ema_atr import EmaAtrStrategy
from .cores.engulfing_rvol import EngulfingParams, EngulfingRvolStrategy
from .cores.eurusd_h1_breakout_reject import EurusdH1RejectParams, EurusdH1RejectStrategy
from .cores.eurusd_h1_range import EurusdH1RangeParams, EurusdH1RangeStrategy
from .cores.h1_donchian import H1DonchianStrategy, h1_donchian_params
from .cores.killzone import KillZoneParams, KillZoneStrategy
from .cores.mtf_bb_pivot import MtfBbPivotParams, MtfBbPivotStrategy

STRATEGIES = {
    "donchian": DonchianStrategy,
    "ema_atr": EmaAtrStrategy,
    "engulfing": EngulfingRvolStrategy,
    "killzone": KillZoneStrategy,
    "confluence": ConfluenceStrategy,
    "eurusd_h1_range": EurusdH1RangeStrategy,
    "eurusd_h1_breakout_reject": EurusdH1RejectStrategy,
    "bb_squeeze_pivot": BbSqueezePivotStrategy,
    "mtf_bb_pivot": MtfBbPivotStrategy,
    "h1_donchian": H1DonchianStrategy,
}

DEFAULT_CORE = "donchian"


def enabled_cores(cfg: dict | None = None, overlay: dict | None = None) -> list[str]:
    return [name for name, on in cores_map(cfg, overlay).items() if on]


def cores_map(cfg: dict | None = None, overlay: dict | None = None) -> dict[str, bool]:
    """ON/OFF for every catalog core. Missing YAML keys default donchian=on, others=off."""
    flags = {name: (name == DEFAULT_CORE) for name in STRATEGIES}
    raw = (cfg or {}).get("cores")
    if isinstance(raw, dict):
        for key, val in raw.items():
            if key in flags:
                flags[key] = bool(val)
    elif isinstance(raw, list):
        flags = {name: False for name in STRATEGIES}
        for key in raw:
            if key in flags:
                flags[key] = True
    if overlay:
        for key, val in overlay.items():
            if key in flags:
                flags[key] = bool(val)
    return flags


def core_name(cfg: dict | None = None, override: str | None = None) -> str:
    name = (override or (cfg or {}).get("core") or DEFAULT_CORE).strip().lower()
    if name not in STRATEGIES:
        known = ", ".join(sorted(STRATEGIES))
        raise ValueError(f"unknown core {name!r}; choose {known}")
    return name


def _drop_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def build_strategy(name: str, cfg: dict, **overrides):
    """Construct a named core from YAML sections. Live default is donchian."""
    name = core_name({**cfg, "core": name})
    cls = STRATEGIES[name]
    section = dict(cfg.get(name, {}))
    if name == "confluence":
        params = ConfluenceParams(
            require_killzone=bool(section.get("require_killzone", False)),
            ranging_adx_max=float(section.get("ranging_adx_max", 20.0)),
            donchian_width_pct=float(section.get("donchian_width_pct", 0.012)),
            donchian=DonchianParams.from_dict(cfg.get("donchian", {})),
            engulfing=EngulfingParams(**_drop_none(cfg.get("engulfing", {}))),
            killzone=KillZoneParams(**_drop_none(cfg.get("killzone", {}))),
        )
        return cls(params)
    if name == "eurusd_h1_range":
        return cls(EurusdH1RangeParams.from_dict({**section, **overrides}))
    if name == "eurusd_h1_breakout_reject":
        return cls(EurusdH1RejectParams.from_dict({**section, **overrides}))
    if name == "bb_squeeze_pivot":
        return cls(BbSqueezePivotParams.from_dict({**section, **overrides}))
    if name == "mtf_bb_pivot":
        return cls(MtfBbPivotParams.from_dict({**section, **overrides}))
    if name == "h1_donchian":
        return cls(h1_donchian_params({**section, **overrides}))
    section.update(overrides)
    return cls(**_drop_none(section))


__all__ = [
    "DEFAULT_CORE",
    "STRATEGIES",
    "build_strategy",
    "enabled_cores",
    "cores_map",
    "core_name",
    "ConfluenceStrategy",
    "DonchianStrategy",
    "EmaAtrStrategy",
    "EngulfingRvolStrategy",
    "KillZoneStrategy",
    "EurusdH1RangeStrategy",
    "EurusdH1RejectStrategy",
    "BbSqueezePivotStrategy",
    "MtfBbPivotStrategy",
    "H1DonchianStrategy",
]
