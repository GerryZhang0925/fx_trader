"""Compatibility shim. Implementation: app/feed/download.py"""
import _boot_app  # noqa: F401
from feed.download import main

if __name__ == "__main__":
    raise SystemExit(main())
