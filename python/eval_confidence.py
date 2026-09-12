"""Compatibility shim. Implementation: python/method/eval_confidence.py"""
from method.eval_confidence import *  # noqa: F403
from method.eval_confidence import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
