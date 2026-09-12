"""Append-only run log (JSONL). Display lives in web.py. Never raises to callers."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from paths import KIT_DIR

LOG_NAME = "status.jsonl"
MODULES = ("app", "feed", "strategy", "account")
STATES = ("started", "ok", "error")
_MAX_BYTES = 512_000
_KEEP_LINES = 2000


def default_dir() -> Path:
    return KIT_DIR / "reports"


def log_path(out_dir: Path | None = None) -> Path:
    return (out_dir or default_dir()) / LOG_NAME


def record(
    module: str,
    action: str,
    state: str,
    message: str = "",
    *,
    out_dir: Path | None = None,
    extra: dict | None = None,
    refresh: bool = True,
) -> dict:
    """Write one status line, then refresh reports/www/index.html."""
    dest = Path(out_dir) if out_dir is not None else default_dir()
    event = {
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "module": str(module or "app"),
        "action": str(action or "run"),
        "state": state if state in STATES else "ok",
        "message": str(message or "")[:500],
    }
    if extra:
        event["extra"] = extra
    try:
        dest.mkdir(parents=True, exist_ok=True)
        path = dest / LOG_NAME
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, default=str) + "\n")
        _trim(path)
        if refresh:
            from .web import refresh_site

            refresh_site(dest)
    except Exception:
        return event
    return event


def read_events(out_dir: Path | None = None, *, limit: int = 500) -> list[dict]:
    path = log_path(out_dir)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events: list[dict] = []
    for line in lines[-max(1, limit) :]:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            events.append(row)
    return events


def load_dashboard(out_dir: Path | None = None, *, log_limit: int = 80) -> dict:
    events = read_events(out_dir, limit=500)
    by_module: dict[str, dict | None] = {name: None for name in MODULES}
    last_ok = None
    last_error = None
    for event in events:
        name = event.get("module")
        if name in by_module:
            by_module[name] = event
        if event.get("state") == "ok":
            last_ok = event
        elif event.get("state") == "error":
            last_error = event
    recent = list(reversed(events[-log_limit:]))
    return {
        "modules": by_module,
        "last_ok": last_ok,
        "last_error": last_error,
        "events": recent,
    }


@contextmanager
def tracked(
    module: str,
    action: str,
    *,
    out_dir: Path | None = None,
    message: str = "",
) -> Iterator[Path]:
    dest = Path(out_dir) if out_dir is not None else default_dir()
    record(module, action, "started", message, out_dir=dest)
    try:
        yield dest
    except Exception as exc:
        record(module, action, "error", f"{type(exc).__name__}: {exc}"[:500], out_dir=dest)
        raise
    else:
        record(module, action, "ok", message, out_dir=dest)


def _trim(path: Path) -> None:
    try:
        if path.stat().st_size <= _MAX_BYTES:
            return
        lines = path.read_text(encoding="utf-8").splitlines()
        path.write_text("\n".join(lines[-_KEEP_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        return
