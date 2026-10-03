"""Opponent hand ranges, rebuilt from this hand's public action history.

Preflop: a top-x% range whose width comes from the player's shrunk
statistics and the kind of action (open, 3bet, call, limp, check).
Postflop: each bet, raise, call or check reweights combos by their strength
percentile *within that player's current range* on the board at that time:
- bets/raises keep the top of the range plus a bluff floor; bigger bets keep
  a narrower top (the field rarely bluffs big),
- calls drop the bottom and trim the very top (strong hands tend to raise),
- checks trim the top (strong hands tend to bet).

Strength = made-hand percentile among all live combos, lifted for strong
draws so that semi-bluffs and draw calls stay in the range.
"""

from __future__ import annotations

import math

from ..core.cards import COMBOS
from ..core.evaluator import POPCOUNT, STRAIGHT_HIGH, evaluate
from ..core.ranges import band_range, remove_dead, top_range
from ..params import P


def _sig(x: float) -> float:
    if x > 30:
        return 1.0
    if x < -30:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def _straight_outs_ranks(mask: int) -> int:
    if STRAIGHT_HIGH[mask] >= 0:
        return 0
    n = 0
    for r in range(13):
        if not mask >> r & 1 and STRAIGHT_HIGH[mask | 1 << r] >= 0:
            n += 1
    return n


class BoardStrength:
    """Strength of every combo on a fixed board (computed once per board)."""

    def __init__(self, board: list[int]):
        self.board = board
        n = len(board)
        dead = set(board)
        bsuit = [0, 0, 0, 0]
        bmask = 0
        for c in board:
            bsuit[c // 13] += 1
            bmask |= 1 << (c % 13)
        board_straight_ranks = _straight_outs_ranks(bmask) if n < 5 else 0
        raw = [None] * 1326
        draw = [0.0] * 1326
        for i, (a, b) in enumerate(COMBOS):
            if a in dead or b in dead:
                continue
            raw[i] = evaluate([a, b, *board])
            if n >= 5:
                continue
            outs = 0
            sa, sb = a // 13, b // 13
            if sa == sb:
                if bsuit[sa] + 2 == 4:
                    outs += 9
            else:
                if bsuit[sa] + 1 == 4:
                    outs += 9
                elif bsuit[sb] + 1 == 4:
                    outs += 9
            m = bmask | 1 << (a % 13) | 1 << (b % 13)
            if POPCOUNT[m] > POPCOUNT[bmask]:
                k = _straight_outs_ranks(m) - board_straight_ranks
                if k > 0:
                    outs += 4 * k
            if outs >= 8:
                floor = P["draw_floor_strong"] if outs >= 12 else P["draw_floor"]
                if n == 4:
                    floor -= 0.12
                draw[i] = floor
        live = [i for i in range(1326) if raw[i] is not None]
        live.sort(key=lambda i: raw[i])
        made = [0.0] * 1326
        m = len(live)
        j = 0
        while j < m:  # equal scores share their percentile
            k = j
            while k + 1 < m and raw[live[k + 1]] == raw[live[j]]:
                k += 1
            p = ((j + k) / 2 + 0.5) / m
            for t in range(j, k + 1):
                made[live[t]] = p
            j = k + 1
        self.strength = [max(made[i], draw[i]) if raw[i] is not None else 0.0 for i in range(1326)]
        self.raw = raw
        self.order = sorted(live, key=lambda i: self.strength[i])


def range_percentiles(weights: list[float], bs: BoardStrength) -> list[float]:
    """Percentile (0 weakest .. 1 strongest) of each combo within `weights`."""
    tot = 0.0
    for i in bs.order:
        tot += weights[i]
    pct = [0.0] * 1326
    if tot <= 0:
        return pct
    acc = 0.0
    for i in bs.order:
        w = weights[i]
        pct[i] = (acc + w / 2) / tot
        acc += w
    return pct


def _apply(weights, pct, fn):
    return [w * fn(p) if w else 0.0 for w, p in zip(weights, pct)]


class RangeModel:
    """Per-hand cache of board strengths; ranges rebuilt per decision."""

    def __init__(self):
        self.hand = None
        self.cache: dict[tuple, BoardStrength] = {}

    def board_strength(self, board: list[int]) -> BoardStrength:
        key = tuple(board)
        bs = self.cache.get(key)
        if bs is None:
            bs = self.cache[key] = BoardStrength(list(board))
        return bs

    def build(self, ctx, tracker) -> dict[int, list[float]]:
        if self.hand != ctx.hand:
            self.hand = ctx.hand
            self.cache = {}
        replay = _replay(ctx)
        ranges = {}
        dead = ctx.hole + ctx.board
        for seat in ctx.opponents:
            pid = ctx.players[seat]
            st = tracker.get(pid)
            w = _preflop_range(seat, replay, st, ctx)
            w = remove_dead(w, dead)
            for street, kind, frac, raised_over in replay["post"].get(seat, []):
                board = ctx.board[: {"flop": 3, "turn": 4, "river": 5}[street]]
                bs = self.board_strength(board)
                pct = range_percentiles(w, bs)
                w = _narrow(w, pct, kind, frac, raised_over, st)
                if sum(w) <= 1e-9:  # model contradiction: fall back to a wide range
                    w = remove_dead(top_range(0.6), dead)
            ranges[seat] = w
        return ranges


def _replay(ctx) -> dict:
    """Walk the hand's history, recording each opponent's actions with sizes."""
    n = ctx.n
    sb_seat = ctx.button if n == 2 else (ctx.button + 1) % n
    bb_seat = (ctx.button + 1) % n if n == 2 else (ctx.button + 2) % n
    bb = ctx.bb
    street_bet = [0] * n
    street_bet[sb_seat] = bb // 2 if bb >= 2 else 1
    street_bet[bb_seat] = bb
    pot = sum(street_bet)
    cur_street = "preflop"
    current = bb
    raises = 0
    pf_actions = {}  # seat -> list of (kind, raises_before, amount)
    post = {}
    for street, seat, kind, amount in ctx.state.history:
        if street != cur_street:
            cur_street = street
            street_bet = [0] * n
            current = 0
            raises = 0
        to_call = max(0, current - street_bet[seat])
        pot_before_bet = max(pot - (current - street_bet[seat]) if to_call else pot, 1)
        if kind == "raise":
            added = amount - street_bet[seat]
            frac = (amount - current) / max(pot + to_call, 1) if current else added / max(pot, 1)
        elif kind == "call":
            added = amount
            frac = to_call / pot_before_bet
        else:
            added = 0
            frac = 0.0
        if street == "preflop":
            pf_actions.setdefault(seat, []).append((kind, raises, amount))
        else:
            post.setdefault(seat, []).append((street, kind, frac, current > 0 and kind == "raise"))
        if kind == "raise":
            raises += 1
        street_bet[seat] += max(added, 0)
        pot += max(added, 0)
        current = max(current, street_bet[seat])
    return {"pf": pf_actions, "post": post, "sb": sb_seat, "bb": bb_seat}


def _preflop_range(seat, replay, st, ctx) -> list[float]:
    acts = [a for a in replay["pf"].get(seat, []) if a[0] in ("raise", "call")]
    k = P["shrink_k"]
    if not acts:
        # only checked (big blind option) or nothing voluntary
        return band_range(1.0, P["bb_check_exclude"], 0.3)
    kind, raises_before, amount = acts[-1]
    first_kind, first_raises, _ = acts[0]
    if kind == "raise":
        if raises_before == 0:
            top = st.open.est(P["prior_open"], k)
        elif raises_before == 1:
            top = st.threebet.est(P["prior_3bet"], k) * 1.2
        else:
            top = P["prior_4bet_range"]
        if amount >= ctx.stack + ctx.my_bet and raises_before == 0:  # open shove
            top = max(top, st.pf_allin.est(0.08, 6.0))
        return top_range(max(top, 0.02), floor=0.0)
    # calls
    if raises_before == 0:
        top = st.vpip.est(P["prior_vpip"], k)
        return band_range(top, 0.05, 0.4)
    if raises_before == 1:
        top = min(st.vpip.est(P["prior_vpip"], k), 0.45) * 0.8
        if first_kind == "call" and first_raises == 0:  # limp-call
            top *= 0.9
        return band_range(top, 0.035, 0.35)
    if first_kind == "raise":  # opened, then called a 3bet
        return band_range(P["call_3bet_range"], 0.025, 0.4)
    return band_range(P["call_3bet_range"] * 0.8, 0.025, 0.5)


def _narrow(w, pct, kind, frac, raised_over, st) -> list[float]:
    s = P["narrow_width"]
    if kind == "raise":
        agg = st.bet_when_checked.est(P["prior_bet_when_checked"], P["shrink_k"])
        agg_mult = max(0.5, min(3.0, agg / P["prior_bet_when_checked"]))
        center = min(0.85, max(0.35, P["bet_center_base"] + P["bet_center_slope"] * frac))
        floor = P["bluff_floor_small"] if frac < 0.6 else P["bluff_floor_big"]
        if raised_over:
            center = min(0.9, center + 0.12)
            floor *= 0.6
        floor = min(0.6, floor * agg_mult)
        return _apply(w, pct, lambda p: floor + (1 - floor) * _sig((p - center) / s))
    if kind == "call":
        center = P["call_center_base"] + P["call_center_slope"] * min(frac, 2.0)
        return _apply(w, pct, lambda p: (0.12 + 0.88 * _sig((p - center) / s)) * (1 - 0.35 * _sig((p - 0.93) / 0.03)))
    if kind == "check":
        return _apply(w, pct, lambda p: 1 - P["check_trim"] * _sig((p - 0.82) / 0.05))
    return w
