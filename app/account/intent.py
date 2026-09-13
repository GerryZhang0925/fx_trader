"""Map a new signal onto a held sleeve position. Strategy declares the policy; this executes it."""

from __future__ import annotations

from typing import Literal

from .books import StackingPolicy

Action = Literal["enter", "hold", "ignore", "reverse", "flatten"]


def desired_action(policy: StackingPolicy, held_direction: int, signal: int) -> Action:
    """held_direction/signal are -1, 0, +1. Account translates the action to venue tickets."""
    sig = int(signal)
    held = int(held_direction)
    if sig == 0:
        return "hold" if held != 0 else "ignore"
    if held == 0:
        return "enter"
    if sig == held:
        if policy.same_direction == "replace":
            return "reverse"
        if policy.same_direction == "add":
            return "enter"
        return "ignore"
    if policy.opposite == "flatten":
        return "flatten"
    if policy.opposite == "hedge":
        return "enter"
    return "reverse"
