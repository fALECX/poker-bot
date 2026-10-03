"""Card encoding shared by every module.

A card is an int 0..51 with the same layout as the engine:
rank = card % 13 (0 = deuce .. 12 = ace), suit = card // 13 (c, d, h, s).

Starting hands are grouped into the 169 strategic classes on a 13x13 grid:
pairs on the diagonal, suited hands above it, offsuit hands below it. Row and
column 0 are aces, so class 0 is AA.
"""

from __future__ import annotations

RANKS = "23456789TJQKA"
SUITS = "cdhs"


def parse_card(s: str) -> int:
    return SUITS.index(s[1].lower()) * 13 + RANKS.index(s[0].upper())


def parse_cards(strs) -> list[int]:
    return [parse_card(s) for s in strs]


def card_str(c: int) -> str:
    return RANKS[c % 13] + SUITS[c // 13]


def class_index(c1: int, c2: int) -> int:
    """169-class index of a two-card starting hand."""
    r1, r2 = c1 % 13, c2 % 13
    hi, lo = (r1, r2) if r1 >= r2 else (r2, r1)
    if hi == lo:
        return (12 - hi) * 14
    if c1 // 13 == c2 // 13:  # suited: above the diagonal
        return (12 - hi) * 13 + (12 - lo)
    return (12 - lo) * 13 + (12 - hi)  # offsuit: below the diagonal


def class_name(idx: int) -> str:
    row, col = divmod(idx, 13)
    if row == col:
        return RANKS[12 - row] * 2
    if row < col:
        return RANKS[12 - row] + RANKS[12 - col] + "s"
    return RANKS[12 - col] + RANKS[12 - row] + "o"


def class_combos(idx: int) -> int:
    row, col = divmod(idx, 13)
    if row == col:
        return 6
    return 4 if row < col else 12


# All 1326 two-card combos as (low card, high card), plus reverse lookup.
COMBOS: list[tuple[int, int]] = [(a, b) for a in range(52) for b in range(a + 1, 52)]
COMBO_INDEX: dict[tuple[int, int], int] = {c: i for i, c in enumerate(COMBOS)}
COMBO_CLASS: list[int] = [class_index(a, b) for a, b in COMBOS]


def combo_index(c1: int, c2: int) -> int:
    return COMBO_INDEX[(c1, c2) if c1 < c2 else (c2, c1)]
