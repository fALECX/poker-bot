"""Cheap postflop hand features without simulation.

hand_strength(): share of all opponent holdings we currently beat (ties half),
by exact enumeration over the unseen combos (about 1000 evaluations).
draw_outs(): approximate clean outs for flush and straight draws that use at
least one of our hole cards.
"""

from __future__ import annotations

from .evaluator import POPCOUNT, STRAIGHT_HIGH, evaluate


def hand_strength(hole: list[int], board: list[int]) -> float:
    mine = evaluate(hole + board)
    dead = set(hole) | set(board)
    live = [c for c in range(52) if c not in dead]
    win = tie = total = 0
    for i in range(len(live)):
        a = live[i]
        for j in range(i + 1, len(live)):
            v = evaluate([a, live[j], *board])
            if mine > v:
                win += 1
            elif mine == v:
                tie += 1
            total += 1
    return (win + 0.5 * tie) / max(total, 1)


def _straight_ranks(mask: int) -> set[int]:
    """Ranks that would complete a straight not already made by `mask`."""
    if STRAIGHT_HIGH[mask] >= 0:
        return set()
    return {r for r in range(13) if not mask >> r & 1 and STRAIGHT_HIGH[mask | 1 << r] >= 0}


def draw_outs(hole: list[int], board: list[int]) -> tuple[int, bool, bool]:
    """Returns (outs, flush_draw, straight_draw). Zero on the river."""
    if len(board) >= 5 or len(board) < 3:
        return 0, False, False
    cards = hole + board
    flush_draw = False
    for s in range(4):
        n_all = sum(1 for c in cards if c // 13 == s)
        n_hole = sum(1 for c in hole if c // 13 == s)
        n_board = n_all - n_hole
        if n_all == 4 and n_hole >= 1 and n_board <= 3:
            flush_draw = True
    mask_all = 0
    mask_board = 0
    for c in cards:
        mask_all |= 1 << (c % 13)
    for c in board:
        mask_board |= 1 << (c % 13)
    ranks = _straight_ranks(mask_all) - _straight_ranks(mask_board)
    straight_outs = 4 * len(ranks)
    outs = (9 if flush_draw else 0) + straight_outs
    if flush_draw and straight_outs:
        outs -= 2  # overlap of straight cards that also make the flush
    return min(outs, 15), flush_draw, straight_outs >= 8


def board_flush_possible(board: list[int]) -> bool:
    for s in range(4):
        if sum(1 for c in board if c // 13 == s) >= 3:
            return True
    return False


def board_paired(board: list[int]) -> bool:
    ranks = [c % 13 for c in board]
    return len(set(ranks)) < len(ranks)


def board_mask(board: list[int]) -> int:
    m = 0
    for c in board:
        m |= 1 << (c % 13)
    return m


def popcount(mask: int) -> int:
    return POPCOUNT[mask & 8191]
