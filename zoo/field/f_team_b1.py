"""Team "Monte Carlo Mavericks" (b1).

Prompt used: "Build a Monte Carlo poker bot: simulate the win probability of our
hand against the opponents, compare it to the pot odds, and raise when we are a
big favourite. Write our own hand evaluator."
Follow-ups (3 iterations): "it's too slow" (fewer sims + clock-aware budget),
"it loses to the all-in bot" (call big bets with equity > pot odds + margin,
shove strong hands), "make it more aggressive" (lower raise threshold, bet
when checked to).

Strategy: each decision runs a random-opponent Monte Carlo (own 7-card
evaluator) for equity vs. the number of live opponents. Fold if equity is
below pot odds, call if above, raise (sized by pot) when equity is a big
favourite; sims scale down as the clock drains.
"""
import random
import time

from macpoker import Bot

RANKS = "23456789TJQKA"
RVAL = {r: i for i, r in enumerate(RANKS)}
SUITS = "shdc"
DECK = [r + s for r in RANKS for s in SUITS]


def card_id(c):
    return RVAL[c[0]] * 4 + SUITS.index(c[1])


IDS = {c: card_id(c) for c in DECK}


def eval7(cards):
    """cards: list of ints (rank*4+suit). Returns comparable tuple."""
    rc = [0] * 13
    sc = [[] for _ in range(4)]
    for c in cards:
        r = c >> 2
        rc[r] += 1
        sc[c & 3].append(r)
    # flush
    flush = None
    for s in sc:
        if len(s) >= 5:
            flush = sorted(s, reverse=True)
            break
    def straight(present):
        # present: set of ranks; returns top rank of best straight or -1
        best = -1
        for hi in range(12, 3, -1):
            if all((hi - k) in present for k in range(5)):
                return hi
        if all(r in present for r in (12, 0, 1, 2, 3)):
            return 3
        return best
    if flush:
        sf = straight(set(flush))
        if sf >= 0:
            return (8, sf)
    quads, trips, pairs, singles = [], [], [], []
    for r in range(12, -1, -1):
        n = rc[r]
        if n == 4:
            quads.append(r)
        elif n == 3:
            trips.append(r)
        elif n == 2:
            pairs.append(r)
        elif n == 1:
            singles.append(r)
    if quads:
        rest = [r for r in trips + pairs + singles]
        return (7, quads[0], max(rest))
    if trips and (len(trips) > 1 or pairs):
        p = pairs[0] if pairs else -1
        if len(trips) > 1:
            p = max(p, trips[1])
        return (6, trips[0], p)
    if flush:
        return (5,) + tuple(flush[:5])
    st = straight({r for r in range(13) if rc[r]})
    if st >= 0:
        return (4, st)
    if trips:
        return (3, trips[0]) + tuple((singles + pairs)[:0]) + tuple(sorted(singles + pairs, reverse=True)[:2])
    if len(pairs) >= 2:
        kick = max(pairs[2:] + singles) if (pairs[2:] + singles) else -1
        return (2, pairs[0], pairs[1], kick)
    if pairs:
        return (1, pairs[0]) + tuple(singles[:3])
    return (0,) + tuple(singles[:5])


def equity(hole, board, n_opp, sims):
    h = [IDS[c] for c in hole]
    b = [IDS[c] for c in board]
    used = set(h + b)
    rest = [i for i in range(52) if i not in used]
    need = 5 - len(b)
    k = need + 2 * n_opp
    wins = 0.0
    for _ in range(sims):
        s = random.sample(rest, k)
        full = b + s[:need]
        mine = eval7(h + full)
        best = True
        tie = 1
        for o in range(n_opp):
            oc = s[need + 2 * o: need + 2 * o + 2]
            sc = eval7(oc + full)
            if sc > mine:
                best = False
                break
            if sc == mine:
                tie += 1
        if best:
            wins += 1.0 / tie
    return wins / sims


class MonteCarloBot(Bot):
    name = "MonteCarloMavericks"

    def on_match_start(self, info):
        self.hands = info.get("num_hands", 100)

    def sims_budget(self, state):
        clock = state.clock_ms
        hands_left = max(1, 100 - state.hand)
        per_hand = clock / hands_left
        # about 3 decisions per hand; stay far under budget
        if per_hand < 40:
            return 0
        if per_hand < 120:
            return 60
        if per_hand < 300:
            return 150
        return 250

    def act(self, state):
        try:
            return self._act(state)
        except Exception:
            return state.check() if state.to_call == 0 else state.fold()

    def _act(self, state):
        n_opp = max(1, sum(1 for i, f in enumerate(state.folded) if not f and i != state.seat))
        sims = self.sims_budget(state)
        if sims == 0:
            eq = self.quick(state)
        else:
            eq = equity(state.hole, state.board, n_opp, sims)
        pot = state.pot
        call = state.to_call
        odds = call / (pot + call) if call > 0 else 0.0
        # equity vs random hands is inflated for multiway; baseline fair share
        fair = 1.0 / (n_opp + 1)

        big = fair + 0.28 - 0.02 * (n_opp - 1) * 0 # aggressive threshold
        if state.street == "preflop":
            big = max(fair + 0.22, 0.45)
        # shove monsters
        if eq > 0.85 and state.can_raise:
            return state.all_in()
        if eq > big and state.can_raise:
            size = int(state.pot * (0.75 if eq < 0.7 else 1.0)) + call
            target = state.street_bets[state.seat] + max(size, state.min_raise_to - state.street_bets[state.seat])
            target = max(state.min_raise_to, min(target, state.max_raise_to))
            if target >= state.max_raise_to:
                return state.all_in()
            return state.raise_to(int(target))
        if call == 0:
            # more aggressive: bet when a bit ahead
            if eq > fair + 0.12 and state.can_raise:
                target = max(state.min_raise_to, min(int(pot * 0.6), state.max_raise_to))
                return state.raise_to(target)
            return state.check()
        # facing a bet: pot odds plus margin (bigger margin for bigger bets)
        margin = 0.03 if call <= 40 else (0.0 if call >= 100 else 0.04)  # iter 2: stop folding to shoves
        if eq > odds + margin and eq > fair * 0.9 or (call >= 100 and eq > 0.42):
            return state.call()
        return state.fold()

    def quick(self, state):
        # low clock fallback: crude preflop strength
        h = sorted((RVAL[c[0]] for c in state.hole), reverse=True)
        s = 0.3 + h[0] / 40 + h[1] / 60
        if h[0] == h[1]:
            s += 0.25
        if state.hole[0][1] == state.hole[1][1]:
            s += 0.04
        return min(s, 0.8)
