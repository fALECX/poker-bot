"""The agent behind the tournament Bot: bookkeeping plus a guarded decision.

Safety contract: no method here may raise. Any failure in the main strategy
falls back to the simulation-free policy, and any failure there falls back to
check/fold. Every returned action is passed through legal.finalize.
"""

from __future__ import annotations

import random
import zlib

from .core import legal
from .core.gamectx import Ctx
from .model.range_model import RangeModel
from .model.standings import Standings
from .model.tracker import Tracker
from .strategy import fallback

LOW_CLOCK_MS = 1500


class Agent:
    def __init__(self, strategy=None):
        self.tracker = Tracker()
        self.standings = Standings()
        self.sb, self.bb = 1, 2
        self.num_hands = 100
        self.player = None
        self.strategy = strategy  # callable(agent, ctx, rng, clock_ms) -> Intent, or None
        self.errors = 0
        self.range_model = RangeModel()
        self.last_debug = None

    # ---- observer hooks (all guarded) ----------------------------------
    def on_match_start(self, msg: dict) -> None:
        try:
            blinds = msg.get("blinds") or [1, 2]
            self.sb, self.bb = int(blinds[0]), int(blinds[1])
            self.num_hands = int(msg.get("num_hands", 100) or 100)
            self.player = msg.get("player")
            self.tracker.set_blinds(self.sb, self.bb)
            self.standings.on_match_start(msg)
        except Exception:
            self.errors += 1

    def on_hand_start(self, msg: dict) -> None:
        try:
            self.tracker.on_hand_start(msg)
        except Exception:
            self.errors += 1

    def on_action(self, msg: dict) -> None:
        try:
            self.tracker.on_action(msg)
        except Exception:
            self.errors += 1

    def on_street(self, msg: dict) -> None:
        try:
            self.tracker.on_street(msg)
        except Exception:
            self.errors += 1

    def on_hand_end(self, msg: dict) -> None:
        try:
            self.tracker.on_hand_end(msg)
        except Exception:
            self.errors += 1
        try:
            self.standings.on_hand_end(msg)
        except Exception:
            self.errors += 1

    # ---- decision -------------------------------------------------------
    def _rng(self, state) -> random.Random:
        key = f"{state.hand}|{state.hole}|{state.board}|{len(state.history)}|{self.player}"
        return random.Random(zlib.crc32(key.encode()))

    def act(self, state):
        intent = None
        ctx = None
        try:
            ctx = Ctx(state, self.bb)
            rng = self._rng(state)
            clock = state.clock_ms
            if self.strategy is not None and clock >= LOW_CLOCK_MS:
                try:
                    intent = self.strategy(self, ctx, rng, clock)
                except Exception:
                    self.errors += 1
                    intent = None
            if intent is None:
                intent = fallback.decide(ctx, self.tracker, rng, cheap=clock < LOW_CLOCK_MS)
        except Exception:
            self.errors += 1
            intent = None
        try:
            if intent is None:
                return legal.passive(state)
            return legal.finalize(state, intent)
        except Exception:
            self.errors += 1
            return legal.passive(state)
