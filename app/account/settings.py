"""Merged YAML + EngineConfig. Reads sibling config files as data, not Python imports."""

from __future__ import annotations

from pathlib import Path

import yaml

from paths import APP_DIR, KIT_DIR, boot

from .engine import CostConfig, EngineConfig
from .risk import RiskConfig

boot()


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = dict(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config(path: Path | None = None) -> dict:
    if path:
        return _read_yaml(Path(path))
    cfg: dict = {}
    for rel in (
        APP_DIR / "account" / "config.yaml",
        APP_DIR / "strategy" / "config.yaml",
        APP_DIR / "feed" / "config.yaml",
        APP_DIR / "output" / "config.yaml",
        APP_DIR / "config.yaml",
    ):
        cfg = _deep_merge(cfg, _read_yaml(rel))
    return cfg


def engine_from_config(
    cfg: dict, *, pip_size: float | None = None, risk_pct: float | None = None
) -> EngineConfig:
    cost = cfg.get("cost", {})
    risk = cfg.get("risk", {})
    return EngineConfig(
        initial_equity=float(cfg.get("initial_equity", 100000)),
        risk=RiskConfig(
            risk_pct=float(risk_pct if risk_pct is not None else risk.get("risk_pct", 1.0)),
            max_trades_per_day=int(risk.get("max_trades_per_day", 2)),
            max_consecutive_losses=int(risk.get("max_consecutive_losses", 3)),
            max_daily_loss_r=float(risk.get("max_daily_loss_r", 2.0)),
            lot_size=float(cost.get("lot_size", 100000)),
        ),
        cost=CostConfig(
            spread_pips=float(cost.get("spread_pips", 1.0)),
            slippage_pips=float(cost.get("slippage_pips", 0.2)),
            commission_per_lot=float(cost.get("commission_per_lot", 0.0)),
            pip_size=float(pip_size if pip_size is not None else cfg.get("pip_size", 0.0001)),
            lot_size=float(cost.get("lot_size", 100000)),
        ),
    )


def parse_symbols(raw: str | None, port: dict) -> list[str]:
    if raw:
        return [s.strip().upper() for s in raw.split(",") if s.strip()]
    pairs = port.get("candidates") or port.get("pairs")
    if not pairs:
        return ["USDCAD", "USDJPY", "GBPUSD"]
    return [s.upper() for s in pairs]


def kit_data_dir(cfg: dict | None = None) -> Path:
    rel = (cfg or {}).get("data_dir") or "data"
    path = Path(rel)
    return path if path.is_absolute() else (KIT_DIR / path)


def kit_params_dir(cfg: dict | None = None) -> Path:
    rel = (cfg or {}).get("params_dir") or "params"
    path = Path(rel)
    return path if path.is_absolute() else (KIT_DIR / path)


def kit_reports_dir(cfg: dict | None = None) -> Path:
    rel = (cfg or {}).get("reports_dir") or "reports"
    path = Path(rel)
    return path if path.is_absolute() else (KIT_DIR / path)
