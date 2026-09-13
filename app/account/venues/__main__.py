"""python -m account.venues — FXCM demo read-only ping. No orders."""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    p = argparse.ArgumentParser(
        add_help=True,
        description="Ping the FXCM demo venue (GET only). No orders.",
    )
    p.add_argument(
        "venue",
        nargs="?",
        choices=("fxcm",),
        help="Only fxcm is in the book. Default: fxcm",
    )
    args, rest = p.parse_known_args(argv)
    if args.venue not in (None, "fxcm"):
        print("venue is fxcm only (oanda_practice is off)", flush=True)
        return 2
    from account.venues.fxcm import main as fxcm_main

    return fxcm_main(rest)


if __name__ == "__main__":
    raise SystemExit(main())
