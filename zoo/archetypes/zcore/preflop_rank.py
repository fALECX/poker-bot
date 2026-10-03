"""Preflop hand ranking helpers built on the generated tables."""

from __future__ import annotations

from .cards import class_combos
from .preflop_tables import EQ_VS_RANDOM, EQ_VS_TOP, HAND_ORDER

# CLASS_PCT[c]: share of all combos ranked at or above the middle of class c
# (0.0 = best hand, 1.0 = worst), i.e. "c is a top-x% hand".
CLASS_PCT = [0.0] * 169
_acc = 0
for _c in HAND_ORDER:
    _n = class_combos(_c)
    CLASS_PCT[_c] = (_acc + _n / 2) / 1326
    _acc += _n

TOP_BUCKETS = len(EQ_VS_TOP[0])


def pct(cls: int) -> float:
    return CLASS_PCT[cls]


def eq_vs_random(cls: int, k: int) -> float:
    k = max(1, min(k, len(EQ_VS_RANDOM[cls])))
    return EQ_VS_RANDOM[cls][k - 1]


def eq_vs_top(cls: int, top: float) -> float:
    """Heads-up equity vs the top `top` share (0..1) of hands, interpolated."""
    x = max(0.02, min(top, 1.0)) * 100 / 2 - 1  # bucket coordinate
    lo = int(x)
    hi = min(lo + 1, TOP_BUCKETS - 1)
    t = x - lo
    row = EQ_VS_TOP[cls]
    return row[lo] * (1 - t) + row[hi] * t
