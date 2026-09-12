"""Compatibility shim. Implementation: python/method/analyze_quality.py"""
from method.analyze_quality import *  # noqa: F403
from method.analyze_quality import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
