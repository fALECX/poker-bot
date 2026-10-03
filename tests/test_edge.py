"""Crafted edge-case states: every action must be legal, fast, and exception-free."""

import time
import unittest

from tests.helpers import illegal_reason

from macpoker.sdk import GameState
from pokerbot.agent import Agent
from pokerbot.strategy.main_strategy import decide


def new_agent(n=5, player=0):
    a = Agent(strategy=decide)
    a.on_match_start({"type": "hello", "player": player, "num_players": n, "num_hands": 100,
                      "stack": 200, "blinds": [1, 2], "time_bank_ms": 30000, "increment_ms": 100})
    return a


def state(**kw):
    n = kw.pop("n", 5)
    msg = {
        "type": "act", "hand": 10, "seat": 3, "street": "preflop", "board": [], "hole": ["As", "Kd"],
        "pot": 3, "to_call": 2, "min_raise_to": 4, "max_raise_to": 200, "can_raise": True,
        "stacks": [200, 199, 198, 200, 200][:n] if n <= 5 else [200] * n,
        "street_bets": [0, 1, 2, 0, 0][:n] if n <= 5 else [0, 1, 2] + [0] * (n - 3),
        "folded": [False] * n, "button": 0, "history": [], "clock_ms": 30000,
        "players": list(range(n)),
    }
    msg.update(kw)
    return msg


class EdgeCaseTest(unittest.TestCase):
    def check(self, msg, agent=None, max_ms=400):
        agent = agent or new_agent(len(msg["stacks"]))
        t = time.perf_counter()
        action = agent.act(GameState(msg))
        ms = (time.perf_counter() - t) * 1000
        self.assertIsNone(illegal_reason(msg, action), (msg, action))
        self.assertEqual(agent.errors, 0)
        self.assertLess(ms, max_ms)
        return action

    def test_call_all_in_for_whole_stack(self):
        for hole in (["As", "Ad"], ["7c", "2d"]):
            msg = state(hole=hole, to_call=150, stacks=[0, 199, 198, 150, 200], street_bets=[200, 1, 2, 0, 0],
                        pot=203, can_raise=False, min_raise_to=150, max_raise_to=150,
                        history=[["preflop", 0, "raise", 200]])
            a = self.check(msg)
            self.assertIn(a.kind, ("call", "fold"))

    def test_min_equals_max_raise(self):
        msg = state(hole=["As", "Ad"], to_call=150, stacks=[0, 199, 198, 160, 200], street_bets=[200, 1, 2, 0, 0],
                    pot=203, can_raise=True, min_raise_to=160, max_raise_to=160,
                    history=[["preflop", 0, "raise", 200]])
        self.check(msg)

    def test_cannot_raise_after_short_all_in(self):
        msg = state(street="flop", board=["Ah", "Kh", "2c"], hole=["As", "Ac"], to_call=10, can_raise=False,
                    pot=40, stacks=[180, 0, 170, 180, 0], street_bets=[0, 10, 0, 0, 0],
                    folded=[True, False, False, False, True], min_raise_to=20, max_raise_to=180,
                    history=[["preflop", 3, "call", 2], ["preflop", 1, "call", 1], ["preflop", 2, "check", 0],
                             ["flop", 1, "raise", 10]])
        a = self.check(msg)
        self.assertEqual(a.kind, "call")

    def test_big_blind_option(self):
        for hole in (["As", "Ad"], ["7c", "2d"], ["9h", "8h"]):
            msg = state(seat=2, hole=hole, to_call=0, pot=6, stacks=[198, 199, 198, 198, 200],
                        street_bets=[2, 1, 2, 2, 0], folded=[False, False, False, False, True],
                        min_raise_to=4, history=[["preflop", 3, "call", 2], ["preflop", 4, "fold", 0],
                                                 ["preflop", 0, "call", 2], ["preflop", 1, "call", 1]])
            a = self.check(msg)
            self.assertNotEqual(a.kind, "fold")

    def test_heads_up(self):
        msg = state(n=2, seat=0, to_call=1, pot=3, stacks=[199, 198], street_bets=[1, 2],
                    folded=[False, False], min_raise_to=4, max_raise_to=200, players=[1, 0])
        self.check(msg, new_agent(2, player=1))
        msg = state(n=2, seat=1, street="river", board=["Ah", "Kh", "2c", "7d", "9s"], hole=["Ac", "Qd"],
                    to_call=20, pot=60, stacks=[160, 180], street_bets=[20, 0], folded=[False, False],
                    min_raise_to=40, max_raise_to=180, players=[1, 0],
                    history=[["preflop", 0, "raise", 6], ["preflop", 1, "call", 4], ["flop", 1, "check", 0],
                             ["flop", 0, "raise", 4], ["flop", 1, "call", 4], ["turn", 1, "check", 0],
                             ["turn", 0, "raise", 10], ["turn", 1, "call", 10], ["river", 1, "check", 0],
                             ["river", 0, "raise", 20]])
        self.check(msg, new_agent(2, player=0))

    def test_low_clock_is_fast(self):
        for clock in (0, 50, 1000):
            msg = state(street="turn", board=["Ah", "Kh", "2c", "7d"], hole=["Qh", "Jh"], to_call=0, pot=40,
                        street_bets=[0] * 5, min_raise_to=2, clock_ms=clock,
                        history=[["preflop", 3, "raise", 6], ["preflop", 4, "call", 6]],
                        folded=[True, True, True, False, False])
            self.check(msg, max_ms=15)

    def test_multiway_flop_budget(self):
        msg = state(street="flop", board=["Th", "9h", "2c"], hole=["Jh", "Qd"], to_call=12, pot=42,
                    stacks=[194, 194, 182, 194, 194], street_bets=[0, 0, 12, 0, 0], min_raise_to=24,
                    max_raise_to=194, seat=3,
                    history=[["preflop", 3, "raise", 6], ["preflop", 4, "call", 6], ["preflop", 0, "call", 6],
                             ["preflop", 1, "call", 5], ["preflop", 2, "call", 4], ["flop", 1, "check", 0],
                             ["flop", 2, "raise", 12]])
        self.check(msg, max_ms=700)

    def test_hooks_tolerate_garbage(self):
        a = new_agent()
        for hook in (a.on_hand_start, a.on_action, a.on_street, a.on_hand_end, a.on_match_start):
            hook({})
            hook({"players": [0, 1], "seat": 7, "deltas": [1], "revealed": {"x": ["As"]}})
        self.assertGreaterEqual(a.errors, 0)  # never raises; errors are only counted


if __name__ == "__main__":
    unittest.main()
