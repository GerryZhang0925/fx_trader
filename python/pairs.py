"""Compatibility shim. Implementation: app/feed/pairs.py"""
import _boot_app  # noqa: F401
from feed.pairs import *  # noqa: F403
from feed.pairs import CANDIDATES, KEEP_BOTH, PAIRS, RECOMMENDED, pip_size  # noqa: F401
