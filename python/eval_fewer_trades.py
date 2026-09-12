"""Compatibility shim. Implementation: python/method/eval_fewer_trades.py"""
from method.eval_fewer_trades import *  # noqa: F403
from method.eval_fewer_trades import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
