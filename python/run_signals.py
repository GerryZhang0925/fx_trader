"""Compatibility shim. Implementation: app/run.py"""
import _boot_app  # noqa: F401
from run import main

if __name__ == "__main__":
    raise SystemExit(main())
