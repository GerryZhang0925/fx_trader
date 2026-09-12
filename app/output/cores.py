"""Runtime ON/OFF overlay for strategy cores. YAML defaults + reports/cores.json."""

from __future__ import annotations

import json
from pathlib import Path

from strategy.catalog import STRATEGIES, cores_map


def cores_file(out_dir: Path) -> Path:
    return Path(out_dir) / "cores.json"


def read_overlay(out_dir: Path | None) -> dict:
    if out_dir is None:
        return {}
    path = cores_file(out_dir)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def load_enabled(out_dir: Path | None, cfg: dict | None = None) -> dict[str, bool]:
    return cores_map(cfg, read_overlay(out_dir))


def save_enabled(out_dir: Path, flags: dict) -> dict[str, bool]:
    normalized = {name: bool(flags.get(name, False)) for name in STRATEGIES}
    path = cores_file(out_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, indent=2) + "\n", encoding="utf-8")
    return normalized


def set_core(out_dir: Path, cfg: dict | None, name: str, enabled: bool) -> dict[str, bool]:
    if name not in STRATEGIES:
        known = ", ".join(sorted(STRATEGIES))
        raise ValueError(f"unknown core {name!r}; choose {known}")
    flags = load_enabled(out_dir, cfg)
    flags[name] = bool(enabled)
    return save_enabled(out_dir, flags)
