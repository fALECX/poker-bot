"""Team A1 ("Pot Odds Pirates").
Prompt: "Write me a strong poker bot for this SDK. Use hand strength and pot odds,
play position, and make it hard to beat."  Follow-up: "make it win more against the
house bots" (3 iterations total: v1 tight/passive, v2 more value bets + fix crash on
short stacks, v3 bigger value bets vs callers and less folding to tiny bets).

Strategy: preflop Chen-style hand score with position-adjusted open/call/3bet thresholds;
postflop 7-card hand-rank + draw detection, bets for value (~65% pot) and semi-bluffs.
Calls when equity-estimate beats pot odds; folds weak hands to big bets.
"""
from __future__ import annotations

import random
from itertools import combinations

from macpoker import Bot

RANKS = "23456789TJQKA"
RV = {r: i + 2 for i, r in enumerate(RANKS)}


def eval5(cards):
    vals = sorted((RV[c[0]] for c in cards), reverse=True)
    suits = [c[1] for c in cards]
    flush = len(set(suits)) == 1
    uniq = sorted(set(vals), reverse=True)
    straight_hi = 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            straight_hi = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            straight_hi = 5
    counts = {}
    for v in vals:
        counts[v] = counts.get(v, 0) + 1
    groups = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape = [g[1] for g in groups]
    ranks = [g[0] for g in groups]
    if straight_hi and flush:
        return (8, [straight_hi])
    if shape == [4, 1]:
        return (7, ranks)
    if shape == [3, 2]:
        return (6, ranks)
    if flush:
        return (5, vals)
    if straight_hi:
        return (4, [straight_hi])
    if shape == [3, 1, 1]:
        return (3, ranks)
    if shape == [2, 2, 1]:
        return (2, ranks)
    if shape == [2, 1, 1, 1]:
        return (1, ranks)
    return (0, vals)


def best_hand(cards):
    best = None
    for combo in combinations(cards, 5):
        e = eval5(combo)
        if best is None or e > best:
            best = e
    return best


def chen(hole):
    a, b = hole
    ra, rb = RV[a[0]], RV[b[0]]
    hi, lo = max(ra, rb), min(ra, rb)
    pts = {14: 10, 13: 8, 12: 7, 11: 6}.get(hi, hi / 2.0)
    if ra == rb:
        return max(5, pts * 2)
    if a[1] == b[1]:
        pts += 2
    gap = hi - lo - 1
    pts -= {0: 0, 1: 1, 2: 2, 3: 4}.get(gap, 5)
    if gap <= 1 and hi < 12:
        pts += 1
    return pts


def draws(hole, board):
    cards = hole + board
    suits = {}
    for c in cards:
        suits[c[1]] = suits.get(c[1], 0) + 1
    flush_draw = any(
        n == 4 and any(h[1] == s for h in hole) for s, n in suits.items()
    )
    vals = set(RV[c[0]] for c in cards)
    if 14 in vals:
        vals.add(1)
    oesd = False
    for lo in range(1, 11):
        window = set(range(lo, lo + 5))
        if len(window & vals) == 4:
            oesd = True
    return flush_draw, oesd


class PotOddsBot(Bot):
    name = "PotOddsPirates"

    def __init__(self):
        self.rng = random.Random(7)

    # position: ~0.3 early ... 1 = button
    def pos_factor(self, state):
        n = state.num_players
        d = (state.seat - state.button) % n  # 0 = button
        if d == 0:
            return 1.0
        if d == n - 1:
            return 0.8  # cutoff
        if d in (1, 2):
            return 0.3
        return 0.5

    def strength(self, state):
        """0..1 rough postflop strength."""
        hole, board = state.hole, state.board
        cat, ranks = best_hand(hole + board)
        base = {0: 0.15, 1: 0.45, 2: 0.7, 3: 0.8, 4: 0.88, 5: 0.9, 6: 0.95, 7: 0.98, 8: 1.0}[cat]
        hole_vals = [RV[h[0]] for h in hole]
        if cat == 1:
            pair = ranks[0]
            top = max(RV[c[0]] for c in board)
            if pair >= top and pair in hole_vals:
                base = 0.6 if pair >= 10 else 0.5
            elif pair in hole_vals:
                base = 0.38
            else:
                base = 0.2  # board pair only
        if cat == 0:
            base = 0.1 + (0.05 if max(hole_vals) >= 13 else 0)
        if state.street != "river":
            fd, oesd = draws(hole, board)
            if fd:
                base = max(base, 0.42)
            if oesd:
                base = max(base, 0.38)
        return base

    def raise_amt(self, state, frac):
        amt = int(state.pot * frac + state.to_call + state.street_bets[state.seat])
        return max(state.min_raise_to, min(state.max_raise_to, amt))

    def act(self, state):
        try:
            return self._act(state)
        except Exception:
            return state.check() if state.to_call == 0 else state.fold()

    def _act(self, state):
        can_check = state.to_call == 0
        pot = state.pot
        to_call = state.to_call
        odds = to_call / (pot + to_call) if to_call > 0 else 0.0
        opps = state.players_in_hand - 1

        if state.street == "preflop":
            score = chen(state.hole)
            pf = self.pos_factor(state)
            thr_open = 8 - 3 * pf  # button opens ~5, early ~7.1
            facing_raise = to_call > 2
            if not facing_raise:
                if score >= thr_open and state.can_raise:
                    sz = 6 if score < 10 else 7
                    return state.raise_to(max(state.min_raise_to, min(state.max_raise_to, sz)))
                if to_call > 0 and score >= 4:  # SB completes
                    return state.call()
                return state.check() if can_check else state.fold()
            if score >= 12 and state.can_raise:
                return state.raise_to(max(state.min_raise_to, min(state.max_raise_to, to_call * 3 + 3)))
            if score >= 9 and (to_call <= 20 or score >= 11):
                return state.call()
            if score >= 7 and to_call <= 8:
                return state.call()
            if odds < 0.2 and score >= 5.5:
                return state.call()
            return state.fold()

        s = self.strength(state)
        s -= 0.04 * max(0, opps - 1)  # multiway: tighten
        pf = self.pos_factor(state)
        if can_check:
            if not state.can_raise:
                return state.check()
            if s >= 0.6:
                return state.raise_to(self.raise_amt(state, 0.7))
            if s >= 0.38 and self.rng.random() < 0.5 + 0.2 * pf:
                return state.raise_to(self.raise_amt(state, 0.5))
            if s < 0.25 and opps == 1 and pf > 0.7 and self.rng.random() < 0.25:
                return state.raise_to(self.raise_amt(state, 0.6))  # stab
            return state.check()
        # facing a bet
        if s >= 0.85:
            if state.can_raise and self.rng.random() < 0.7:
                return state.raise_to(self.raise_amt(state, 0.8))
            return state.call()
        if s >= 0.6:
            return state.call()
        if s >= 0.38:
            return state.call() if odds <= s * 0.6 else state.fold()
        if odds < 0.15:
            return state.call()
        return state.fold()


bot = PotOddsBot()
