"""Compatibility shim. Implementation: python/method/eval_upside.py"""
from method.eval_upside import *  # noqa: F403
from method.eval_upside import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
