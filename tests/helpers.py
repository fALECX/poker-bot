"""Shared test utilities: legality-checking transport and quick game runner."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scaffold") not in sys.path:
    sys.path.insert(0, str(ROOT / "scaffold"))

from macpoker.actions import ALL_IN  # noqa: E402
from macpoker.bots.builtin import BUILTINS  # noqa: E402
from macpoker.match import MatchConfig, play_set  # noqa: E402
from macpoker.sdk import load_bot_from_file  # noqa: E402
from macpoker.transport import InProcessTransport  # noqa: E402


def illegal_reason(view: dict, action) -> str | None:
    """Why the engine would have to coerce `action`, or None if it is exact."""
    to_call = view["to_call"]
    kind = action.kind
    if kind == "check":
        return None if to_call == 0 else "check while facing a bet"
    if kind == "fold":
        return None if to_call > 0 else "fold with nothing to call"
    if kind == "call":
        return None if to_call > 0 else "call with nothing to call"
    if kind == "raise":
        if not view["can_raise"]:
            return "raise when raising is not allowed"
        amt = action.amount
        if amt == ALL_IN:
            return None
        if amt < view["min_raise_to"] or amt > view["max_raise_to"]:
            return f"raise {amt} outside [{view['min_raise_to']}, {view['max_raise_to']}]"
        if amt <= max(view["street_bets"]):
            return "raise not above the current bet"
        return None
    return f"unknown action kind {kind!r}"


class CheckingTransport(InProcessTransport):
    def __init__(self, bot, name, problems: list, max_ms: list):
        super().__init__(bot, name)
        self.problems = problems
        self.max_ms = max_ms

    def act(self, view, timeout_ms):
        action, elapsed = super().act(view, timeout_ms)
        reason = illegal_reason(view, action)
        if reason:
            self.problems.append((reason, {k: view[k] for k in (
                "street", "to_call", "min_raise_to", "max_raise_to", "can_raise", "street_bets", "pot")}, action))
        self.max_ms[0] = max(self.max_ms[0], elapsed)
        return action, elapsed


def make_bot(spec: str):
    if spec.startswith("house:"):
        return BUILTINS[spec.split(":", 1)[1]]()
    return load_bot_from_file(str(ROOT / spec))


def run_checked(candidate: str, opponents: list[str], deals: int = 100, seed: str = "t", games: int | None = None):
    """Play a duplicate set; returns (results, problems, max act ms, candidate bots)."""
    problems: list = []
    max_ms = [0.0]
    cands = []

    def make(k):
        bot = make_bot(candidate)
        cands.append(bot)
        return [CheckingTransport(bot, candidate, problems, max_ms)] + [
            InProcessTransport(make_bot(o), o) for o in opponents
        ]

    cfg = MatchConfig(seats=1 + len(opponents), deals=deals, seed=seed)
    results = play_set(cfg, make, games=games)
    return results, problems, max_ms[0], cands
