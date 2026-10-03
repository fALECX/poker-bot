"""Fast scalar 5-7 card hand evaluator.

evaluate(cards) returns an int; a higher int is a better hand and equal ints
tie. Layout: category << 20 | five 4-bit rank slots (kickers in order).
Categories: 0 high card, 1 pair, 2 two pair, 3 trips, 4 straight, 5 flush,
6 full house, 7 quads, 8 straight flush.
"""

from __future__ import annotations

HIGH_CARD, PAIR, TWO_PAIR, TRIPS, STRAIGHT, FLUSH, FULL_HOUSE, QUADS, STRAIGHT_FLUSH = range(9)


def _straight_high(mask: int) -> int:
    for high in range(12, 3, -1):
        need = 0b11111 << (high - 4)
        if mask & need == need:
            return high
    wheel = (1 << 12) | 0b1111  # A-2-3-4-5, five-high
    if mask & wheel == wheel:
        return 3
    return -1


def _top_ranks(mask: int) -> list[int]:
    return [r for r in range(12, -1, -1) if mask >> r & 1]


def _pack(ranks: list[int], slots: int) -> int:
    """Pack up to `slots` ranks into the high-order 4-bit kicker slots."""
    v = 0
    for i in range(5):
        v = (v << 4) | (ranks[i] if i < len(ranks) and i < slots else 0)
    return v


STRAIGHT_HIGH = [_straight_high(m) for m in range(8192)]
POPCOUNT = [bin(m).count("1") for m in range(8192)]
_TOP = [_top_ranks(m) for m in range(8192)]
TOP5 = [_pack(t, 5) for t in _TOP]
HIGHEST = [t[0] if t else 0 for t in _TOP]


def evaluate(cards) -> int:
    counts = [0] * 13
    sm = [0, 0, 0, 0]
    for c in cards:
        r = c % 13
        counts[r] += 1
        sm[c // 13] |= 1 << r
    rank_mask = sm[0] | sm[1] | sm[2] | sm[3]

    flush = 0
    for m in sm:
        if POPCOUNT[m] >= 5:
            sh = STRAIGHT_HIGH[m]
            if sh >= 0:
                return (STRAIGHT_FLUSH << 20) | (sh << 16)
            flush = (FLUSH << 20) | TOP5[m]
            break

    quad = -1
    trips = []
    pairs = []
    for r in range(12, -1, -1):
        n = counts[r]
        if n == 2:
            pairs.append(r)
        elif n == 3:
            trips.append(r)
        elif n == 4:
            quad = r

    if quad >= 0:
        return (QUADS << 20) | (quad << 16) | (HIGHEST[rank_mask & ~(1 << quad)] << 12)
    if trips and (len(trips) > 1 or pairs):
        second = trips[1] if len(trips) > 1 else -1
        if pairs and pairs[0] > second:
            second = pairs[0]
        return (FULL_HOUSE << 20) | (trips[0] << 16) | (second << 12)
    if flush:
        return flush
    sh = STRAIGHT_HIGH[rank_mask]
    if sh >= 0:
        return (STRAIGHT << 20) | (sh << 16)
    if trips:
        t = trips[0]
        k = _TOP[rank_mask & ~(1 << t)]
        return (TRIPS << 20) | (t << 16) | (k[0] << 12) | (k[1] << 8)
    if len(pairs) >= 2:
        p1, p2 = pairs[0], pairs[1]
        return (TWO_PAIR << 20) | (p1 << 16) | (p2 << 12) | (HIGHEST[rank_mask & ~(1 << p1) & ~(1 << p2)] << 8)
    if pairs:
        p = pairs[0]
        k = _TOP[rank_mask & ~(1 << p)]
        return (PAIR << 20) | (p << 16) | (k[0] << 12) | (k[1] << 8) | (k[2] << 4)
    return TOP5[rank_mask]


def category(score: int) -> int:
    return score >> 20
