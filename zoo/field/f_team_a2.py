"""Team A2 ("Nash Nerds").
Prompt: "Make our poker bot play game theory optimal (GTO) style: balanced ranges,
mixed strategies, proper bluff ratios."  3 iterations total (v1 mixed strategies via
random, v2 added MDF-based calling and fixed sizing crashes, v3 tuned frequencies after
it lost chips folding too much against the house bots).

Strategy: preflop position-based opening/3bet ranges with mixed frequencies by hand
percentile; postflop bets 33%/66%/pot with value:bluff ratio ~2:1 (bluffs from draws and
air), calls by minimum defense frequency alpha = bet/(pot+bet) scaled by hand strength.
"""
from __future__ import annotations

import random
from itertools import combinations

from macpoker import Bot

RANKS = "23456789TJQKA"
RV = {r: i + 2 for i, r in enumerate(RANKS)}


def eval5(cards):
    vals = sorted((RV[c[0]] for c in cards), reverse=True)
    flush = len(set(c[1] for c in cards)) == 1
    uniq = sorted(set(vals), reverse=True)
    sh = 0
    if len(uniq) == 5:
        if uniq[0] - uniq[4] == 4:
            sh = uniq[0]
        elif uniq == [14, 5, 4, 3, 2]:
            sh = 5
    cnt = {}
    for v in vals:
        cnt[v] = cnt.get(v, 0) + 1
    g = sorted(cnt.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape = [x[1] for x in g]
    rk = [x[0] for x in g]
    if sh and flush:
        return (8, [sh])
    if shape == [4, 1]:
        return (7, rk)
    if shape == [3, 2]:
        return (6, rk)
    if flush:
        return (5, vals)
    if sh:
        return (4, [sh])
    if shape == [3, 1, 1]:
        return (3, rk)
    if shape == [2, 2, 1]:
        return (2, rk)
    if shape == [2, 1, 1, 1]:
        return (1, rk)
    return (0, vals)


def best_hand(cards):
    return max(eval5(c) for c in combinations(cards, 5))


def preflop_pct(hole):
    """Approximate percentile (0 best .. 1 worst) of starting hand."""
    a, b = RV[hole[0][0]], RV[hole[1][0]]
    hi, lo = max(a, b), min(a, b)
    suited = hole[0][1] == hole[1][1]
    if a == b:
        score = 20 + hi * 2.2
    else:
        score = hi * 1.5 + lo * 0.9
        if suited:
            score += 4
        gap = hi - lo - 1
        if gap == 0:
            score += 3
        elif gap == 1:
            score += 1.5
        elif gap >= 3:
            score -= 2
    pct = 1 - (score - 14) / 36.0
    return min(1.0, max(0.0, pct))


def has_draw(hole, board):
    cards = hole + board
    suits = {}
    for c in cards:
        suits[c[1]] = suits.get(c[1], 0) + 1
    fd = any(n == 4 and any(h[1] == s for h in hole) for s, n in suits.items())
    vals = set(RV[c[0]] for c in cards)
    if 14 in vals:
        vals.add(1)
    sd = any(len(set(range(lo, lo + 5)) & vals) == 4 for lo in range(1, 11))
    return fd or sd


class GTOBot(Bot):
    name = "NashNerds"

    def __init__(self):
        self.rng = random.Random(1234)

    def on_match_start(self, info):
        self.rng = random.Random(1234)

    def to(self, state, target):
        return int(max(state.min_raise_to, min(state.max_raise_to, target)))

    def hand_value(self, state):
        hole, board = state.hole, state.board
        cat, rk = best_hand(hole + board)
        hv = {0: 0.1, 1: 0.45, 2: 0.72, 3: 0.82, 4: 0.88, 5: 0.9, 6: 0.95, 7: 0.98, 8: 1.0}[cat]
        hole_vals = [RV[h[0]] for h in hole]
        if cat == 1:
            top = max(RV[c[0]] for c in board)
            p = rk[0]
            if p not in hole_vals:
                hv = 0.12  # board pair
            elif p >= top:
                hv = 0.62
            else:
                hv = 0.42
        if cat == 0:
            hv = 0.08 + 0.01 * max(0, max(hole_vals) - 8)
        draw = False
        if state.street != "river" and cat < 4:
            draw = has_draw(hole, board)
            if draw:
                hv = max(hv, 0.36)
        return hv, draw

    def act(self, state):
        try:
            return self._act(state)
        except Exception:
            return state.check() if state.to_call == 0 else state.fold()

    def _act(self, state):
        r = self.rng.random()
        to_call = state.to_call
        pot = state.pot
        if state.street == "preflop":
            pct = preflop_pct(state.hole)
            n = state.num_players
            d = (state.seat - state.button) % n  # 0 button, 1 SB, 2 BB
            width = {0: 0.48, 1: 0.40, 2: 1.0}.get(d, 0.22 if d == 3 else 0.30)
            if d == n - 1:
                width = 0.38
            if to_call <= 2:  # unopened or BB option
                if d == 2 and to_call == 0:
                    if pct < 0.3 and r < 0.6 and state.can_raise:
                        return state.raise_to(self.to(state, 7))
                    return state.check()
                if (pct < width * 0.85 or (pct < width and r < 0.5)) and state.can_raise:
                    return state.raise_to(self.to(state, 6 if r < 0.7 else 5))
                if d == 1 and pct < 0.55:
                    return state.call()
                return state.check() if to_call == 0 else state.fold()
            odds = to_call / (pot + to_call)
            if pct < 0.06:
                if state.can_raise:
                    return state.raise_to(self.to(state, to_call * 3 + 4))
                return state.call()
            if 0.55 < pct < 0.62 and r < 0.15 and state.can_raise and to_call < 12:
                return state.raise_to(self.to(state, to_call * 3 + 4))  # bluff 3bet
            call_cut = 0.2 + (0.2 if odds < 0.25 else 0.0)
            return state.call() if pct < call_cut else state.fold()

        hv, draw = self.hand_value(state)
        opps = state.players_in_hand - 1
        if opps > 1:
            hv -= 0.05 * (opps - 1)
        if to_call == 0:
            if not state.can_raise:
                return state.check()
            if hv >= 0.6:
                if r < 0.12:
                    return state.check()  # trap
                return state.raise_to(self.to(state, pot * (0.66 if r < 0.6 else 1.0)))
            if draw and r < 0.5:
                return state.raise_to(self.to(state, pot * 0.5))
            if hv < 0.3 and r < 0.18 and opps == 1:
                return state.raise_to(self.to(state, pot * 0.33))  # bluff
            if 0.3 <= hv < 0.6 and r < 0.3:
                return state.raise_to(self.to(state, pot * 0.33))  # thin value
            return state.check()
        # facing a bet: MDF
        alpha = to_call / (pot + to_call)
        mdf = 1 - alpha
        if hv >= 0.85:
            if state.can_raise and r < 0.5:
                return state.raise_to(self.to(state, (pot + to_call) * 0.9 + to_call))
            return state.call()
        if hv >= 0.55:
            return state.call()
        if draw:
            return state.call() if (alpha < 0.4 or r < 0.5) else state.fold()
        if hv >= 0.35:
            return state.call() if r < mdf * 0.8 else state.fold()
        if r < 0.05 and state.can_raise and state.street != "river":
            return state.raise_to(self.to(state, (pot + to_call) * 0.8 + to_call))
        return state.call() if r < mdf * 0.25 else state.fold()


bot = GTOBot()
