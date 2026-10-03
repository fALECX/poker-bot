"""Derived, decision-relevant features of the current spot.

Built once per act() from the GameState. Seats are per hand; anything that
must persist across hands is keyed by player id elsewhere.
"""

from __future__ import annotations

from .cards import class_index, parse_cards


def preflop_order(n: int, button: int) -> list[int]:
    if n == 2:
        return [button, (button + 1) % n]
    return [(button + 3 + i) % n for i in range(n)]


def postflop_order(n: int, button: int) -> list[int]:
    if n == 2:
        return [(button + 1) % n, button]
    return [(button + 1 + i) % n for i in range(n)]


class Ctx:
    def __init__(self, state, bb: int = 2):
        self.state = state
        self.bb = bb
        self.n = n = state.num_players
        self.seat = seat = state.seat
        self.button = state.button
        self.hand = state.hand
        self.street = state.street
        self.hole = parse_cards(state.hole)
        self.board = parse_cards(state.board)
        self.cls = class_index(self.hole[0], self.hole[1])
        self.pot = state.pot
        self.to_call = state.to_call
        self.stack = state.my_stack
        self.street_bets = list(state.street_bets)
        self.my_bet = self.street_bets[seat]
        self.current_bet = max(self.street_bets)
        self.can_raise = state.can_raise
        self.min_raise_to = state.min_raise_to
        self.max_raise_to = state.max_raise_to
        self.players = list(state.players)
        self.me = self.players[seat]
        folded = state.folded
        stacks = state.stacks
        self.stacks = list(stacks)
        self.active = [s for s in range(n) if not folded[s]]
        self.opponents = [s for s in self.active if s != seat]
        self.num_opp = len(self.opponents)
        # opponents who can still put chips in (not all-in)
        self.live_opponents = [s for s in self.opponents if stacks[s] > 0]

        self.pre_order = preflop_order(n, self.button)
        self.post_order = postflop_order(n, self.button)
        # 0 = button; for n == 2 the button is also the small blind
        self.pos_from_button = (seat - self.button) % n
        self.is_sb = (seat == (self.button if n == 2 else (self.button + 1) % n))
        self.is_bb = (seat == ((self.button + 1) % n if n == 2 else (self.button + 2) % n))

        order = self.pre_order if self.street == "preflop" else self.post_order
        idx = order.index(seat)
        self.behind = [s for s in order[idx + 1:] if not folded[s]]
        # in position postflop: nobody active acts after us on later streets
        pidx = self.post_order.index(seat)
        self.in_position = not any(not folded[s] for s in self.post_order[pidx + 1:])

        # opponent all-in / effective stacks
        opp_total = [stacks[s] + self.street_bets[s] for s in self.opponents]
        mine_total = self.stack + self.my_bet
        self.eff_stack = min(mine_total, max(opp_total)) if opp_total else mine_total
        self.eff_behind = min(self.stack, max((stacks[s] for s in self.opponents), default=0))
        self.spr = self.eff_behind / max(self.pot, 1)
        self.pot_odds = self.to_call / (self.pot + self.to_call) if self.to_call > 0 else 0.0
        self.facing_allin = any(stacks[s] == 0 for s in self.opponents)

        self._parse_history(state.history)

    def _parse_history(self, history) -> None:
        self.pf_raises = 0
        self.pf_limpers = 0
        self.pf_callers_after_raise = 0
        self.pf_aggressor = None  # seat
        self.pf_last_raise_to = 0
        self.street_raises = 0
        self.street_aggressor = None
        self.street_actions = 0
        self.voluntary_seats = set()
        for street, seat, kind, amount in history:
            if street == "preflop":
                if kind == "raise":
                    self.pf_raises += 1
                    self.pf_aggressor = seat
                    self.pf_last_raise_to = amount
                    self.pf_callers_after_raise = 0
                    self.voluntary_seats.add(seat)
                elif kind == "call":
                    if self.pf_raises == 0:
                        self.pf_limpers += 1
                    else:
                        self.pf_callers_after_raise += 1
                    self.voluntary_seats.add(seat)
            if street == self.street:
                self.street_actions += 1
                if kind == "raise":
                    self.street_raises += 1
                    self.street_aggressor = seat

    @property
    def is_pf_aggressor(self) -> bool:
        return self.pf_aggressor == self.seat

    def bet_fraction(self) -> float:
        """Size of the bet we face relative to the pot before it was made."""
        if self.to_call <= 0:
            return 0.0
        pot_before = max(self.pot - (self.current_bet - self.my_bet), 1)
        return self.to_call / pot_before
