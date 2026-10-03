"""Hand ranges as weights over the 1326 two-card combos."""

from __future__ import annotations

from .cards import COMBOS, COMBO_CLASS, class_combos
from .preflop_tables import HAND_ORDER

N_COMBOS = 1326

# class -> rank position (0 = best) and cumulative combo share at its start
_CLASS_START = [0.0] * 169
_acc = 0
for _c in HAND_ORDER:
    _CLASS_START[_c] = _acc / N_COMBOS
    _acc += class_combos(_c)
_CLASS_SHARE = [class_combos(c) / N_COMBOS for c in range(169)]


def uniform() -> list[float]:
    return [1.0] * N_COMBOS


def class_weights_top(top: float, floor: float = 0.0) -> list[float]:
    """Per-class weight for the top `top` share of hands (partial at the edge)."""
    top = max(0.0, min(1.0, top))
    w = [floor] * 169
    for c in range(169):
        start = _CLASS_START[c]
        share = _CLASS_SHARE[c]
        if start + share <= top:
            w[c] = 1.0
        elif start < top:
            w[c] = max(floor, (top - start) / share)
    return w


def top_range(top: float, floor: float = 0.0) -> list[float]:
    cw = class_weights_top(top, floor)
    return [cw[k] for k in COMBO_CLASS]


def band_range(top: float, exclude_top: float, exclude_weight: float, floor: float = 0.0) -> list[float]:
    """Top `top` share with the strongest `exclude_top` share down-weighted."""
    cw = class_weights_top(top, floor)
    ex = class_weights_top(exclude_top)
    out = []
    for k in COMBO_CLASS:
        w = cw[k]
        if ex[k] > 0:
            w *= 1 - ex[k] * (1 - exclude_weight)
        out.append(w)
    return out


def remove_dead(weights: list[float], dead) -> list[float]:
    dead = set(dead)
    return [0.0 if (a in dead or b in dead) else w for w, (a, b) in zip(weights, COMBOS)]


def total(weights: list[float]) -> float:
    return sum(weights)
