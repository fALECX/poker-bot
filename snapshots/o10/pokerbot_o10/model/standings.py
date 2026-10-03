"""Live chip totals per player id, built from every hand_end's deltas.

The game is scored by finishing rank, so knowing the gaps to the players
directly above and below us lets the strategy trade chips for rank late in
the game.
"""

from __future__ import annotations

import math


class Standings:
    def __init__(self):
        self.totals: dict[int, int] = {}
        self.hands_done = 0
        self.num_hands = 100
        self.me = None
        self.sum_sq = 0.0  # running sum of our squared hand results, for volatility

    def on_match_start(self, msg: dict) -> None:
        self.num_hands = msg.get("num_hands", self.num_hands) or self.num_hands
        self.me = msg.get("player", self.me)
        n = msg.get("num_players", 0) or 0
        for pid in range(n):
            self.totals.setdefault(pid, 0)

    def on_hand_end(self, msg: dict) -> None:
        players = msg.get("players") or []
        for seat, d in enumerate(msg.get("deltas") or []):
            if seat < len(players):
                pid = players[seat]
                self.totals[pid] = self.totals.get(pid, 0) + d
                if pid == self.me:
                    self.sum_sq += d * d
        self.hands_done += 1

    def hands_left(self, current_hand: int | None = None) -> int:
        done = self.hands_done if current_hand is None else current_hand
        return max(self.num_hands - done, 0)

    def sigma_hand(self) -> float:
        # prior of ~30 chips per hand blended with what we have seen
        n = self.hands_done
        prior = 30.0
        seen = math.sqrt(self.sum_sq / n) if n else prior
        w = n / (n + 30)
        return w * seen + (1 - w) * prior

    def gaps(self) -> tuple[float, float, int]:
        """(gap to the player just above us, gap to the player just below, rank 1..n)."""
        if self.me is None or self.me not in self.totals:
            return math.inf, math.inf, 1
        mine = self.totals[self.me]
        others = [v for p, v in self.totals.items() if p != self.me]
        above = [v - mine for v in others if v >= mine]
        below = [mine - v for v in others if v < mine]
        rank = 1 + sum(1 for v in others if v > mine)
        return (min(above) if above else math.inf, min(below) if below else math.inf, rank)
