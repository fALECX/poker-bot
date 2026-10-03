"""Per-decision time budget derived from the remaining chess clock."""

from __future__ import annotations

import time

RESERVE_MS = 3000
MIN_MS = 2.0
MAX_MS = 250.0


def budget_ms(clock_ms: float, hand: int, num_hands: int, importance: float = 1.0) -> float:
    """Milliseconds this decision may spend on simulation."""
    acts_left = (num_hands - hand) * 1.8 + 5
    base = (clock_ms - RESERVE_MS) / max(acts_left, 1.0)
    if clock_ms < 8000:
        base = min(base, 20.0)
    return max(MIN_MS, min(MAX_MS, base * importance))


class Deadline:
    __slots__ = ("end",)

    def __init__(self, ms: float):
        self.end = time.perf_counter() + ms / 1000.0

    def expired(self) -> bool:
        return time.perf_counter() >= self.end

    def left_ms(self) -> float:
        return (self.end - time.perf_counter()) * 1000.0
