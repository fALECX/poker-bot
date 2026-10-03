"""Final gate between a strategy intent and the engine.

Strategies express an intent (fold / check / call / raise-to amount). This
module turns it into an SDK action that the engine will accept exactly as
sent, so we never depend on the engine's coercion of illegal actions.
"""

from __future__ import annotations

FOLD, CHECK, CALL, RAISE = "fold", "check", "call", "raise"

# Raising to at least this share of our maximum is treated as an all-in, so we
# never strand a sliver of stack behind.
ALL_IN_SHARE = 0.85


class Intent:
    __slots__ = ("kind", "amount", "tag")

    def __init__(self, kind: str, amount: int = 0, tag: str = ""):
        self.kind = kind
        self.amount = amount
        self.tag = tag  # free-form reason, used for debugging and tests

    def __repr__(self) -> str:
        return f"Intent({self.kind}, {self.amount}, {self.tag!r})"


def fold(tag: str = "") -> Intent:
    return Intent(FOLD, 0, tag)


def check(tag: str = "") -> Intent:
    return Intent(CHECK, 0, tag)


def call(tag: str = "") -> Intent:
    return Intent(CALL, 0, tag)


def raise_to(amount: float, tag: str = "") -> Intent:
    return Intent(RAISE, int(round(amount)), tag)


def all_in(tag: str = "") -> Intent:
    return Intent(RAISE, 10**9, tag)


def passive(state):
    """Check if free, otherwise fold. Always legal."""
    return state.check() if state.to_call == 0 else state.fold()


def finalize(state, intent: Intent):
    """Convert an intent into a legal SDK action."""
    to_call = state.to_call
    kind = intent.kind

    if kind == RAISE:
        if not state.can_raise:
            kind = CALL if to_call > 0 else CHECK
        else:
            lo, hi = state.min_raise_to, state.max_raise_to
            amount = int(intent.amount)
            if amount >= hi * ALL_IN_SHARE:
                amount = hi
            else:
                # do not leave less than a quarter pot behind after raising
                behind = hi - amount
                pot_after = state.pot + (amount - state.street_bets[state.seat])
                if behind < 0.25 * pot_after:
                    amount = hi
            amount = max(lo, min(amount, hi))
            if amount <= max(state.street_bets):
                kind = CALL if to_call > 0 else CHECK
            elif amount >= hi:
                return state.all_in()
            else:
                return state.raise_to(amount)

    if kind == CALL:
        return state.call() if to_call > 0 else state.check()
    # CHECK and FOLD both mean "put no more chips in"
    return passive(state)
