"""Simulation-free policy: preflop charts plus postflop hand strength and pot odds.

Used as the safety net when the main strategy raises, and as the whole
strategy when the clock is low. Cost: one table lookup preflop, and at most
one ~1000-evaluation enumeration postflop (skipped when `cheap`).
"""

from __future__ import annotations

from ..core import legal
from ..core.handinfo import draw_outs, hand_strength
from ..core.evaluator import evaluate
from ..core.preflop_rank import eq_vs_top, pct
from ..params import P


def decide(ctx, tracker, rng, cheap: bool = False) -> legal.Intent:
    if ctx.street == "preflop":
        return preflop(ctx, tracker, rng)
    return postflop(ctx, tracker, rng, cheap)


# ---------------------------------------------------------------- preflop

def _interp(table: dict, x: float) -> float:
    keys = sorted(table)
    if x <= keys[0]:
        return table[keys[0]]
    for a, b in zip(keys, keys[1:]):
        if x <= b:
            t = (x - a) / (b - a)
            return table[a] * (1 - t) + table[b] * t
    return table[keys[-1]]


def _we_raised_preflop(ctx) -> bool:
    return any(st == "preflop" and seat == ctx.seat and kind == "raise"
               for st, seat, kind, _ in ctx.state.history)


def shove_range(ctx, tracker, aggressor_seat) -> float:
    """Estimated top-x share an all-in / huge raise represents."""
    default = P["default_shove_range"][min(max(ctx.pf_raises, 1), 3)]
    if aggressor_seat is None:
        return default
    st = tracker.get(ctx.players[aggressor_seat])
    freq = st.pf_allin.est(default * 0.5, 6.0)  # how often they shove per hand
    vpip = st.vpip.est(0.3, 10.0)
    # a player who shoves every other hand is shoving a wide range
    return max(default, min(freq * 1.15, vpip, 1.0))


def preflop(ctx, tracker, rng) -> legal.Intent:
    p = pct(ctx.cls)
    bb = ctx.bb
    stack_total = ctx.stack + ctx.my_bet

    # facing an all-in or a raise that commits a big part of our stack
    if ctx.to_call > 0 and (ctx.to_call >= P["big_bet_stack_share"] * ctx.stack or ctx.facing_allin):
        top = shove_range(ctx, tracker, ctx.pf_aggressor)
        eq = eq_vs_top(ctx.cls, top)
        extra = max(0, len([s for s in ctx.opponents if s in ctx.voluntary_seats]) - 1)
        eq = eq ** (1 + 0.7 * extra)
        need = ctx.pot_odds + P["allin_call_margin"] + 0.015 * len(ctx.behind)
        lam = getattr(ctx, "risk_lambda", 0.0) / 200.0
        pf = ctx.pot + ctx.to_call
        need += lam * eq * (1 - eq) * pf  # risk penalty, expressed in equity units
        if eq >= need:
            if ctx.can_raise and p < 0.03:
                return legal.all_in("pf-jam-premium")
            return legal.call("pf-call-big")
        return legal.fold("pf-fold-big")

    raises = ctx.pf_raises
    if raises == 0:
        limpers = ctx.pf_limpers
        if ctx.to_call == 0:  # big blind option
            if p < P["bb_raise_vs_limp_pct"] and ctx.can_raise:
                return legal.raise_to((3 + limpers) * bb, "bb-raise-limps")
            return legal.check("bb-check")
        if limpers > 0:
            if p < P["iso_pct"] * P["open_mult"]:
                return legal.raise_to((4 + P["limper_add_bb"] * limpers) * bb, "iso")
            if ctx.is_sb and p < 0.30:
                return legal.call("sb-complete-limped")
            if p < 0.18 and len(ctx.behind) <= 2:
                return legal.call("overlimp")
            return legal.fold("fold-vs-limp")
        if ctx.n == 2:
            open_pct = P["open_pct_heads_up"]
        else:
            open_pct = P["open_pct_by_behind"].get(len(ctx.behind), 0.11)
        open_pct = min(1.0, open_pct * P["open_mult"])
        if p < open_pct:
            size = P["open_size_sb_bb"] if ctx.is_sb else P["open_size_bb"]
            return legal.raise_to(size * bb, "open")
        return legal.fold("fold-unopened")

    raise_to = ctx.current_bet
    r = raise_to / bb
    if raises == 1:
        opener = ctx.pf_aggressor
        late_opener = opener is not None and opener in (ctx.button, (ctx.button - 1) % ctx.n)
        tb = P["threebet_value_pct_late"] if late_opener else P["threebet_value_pct"]
        if p < tb and ctx.can_raise:
            mult = P["threebet_mult_ip"] if ctx.in_position else P["threebet_mult_oop"]
            return legal.raise_to(raise_to * (mult + ctx.pf_callers_after_raise), "3bet")
        if opener is not None:
            open_freq = tracker.get(ctx.players[opener]).open.est(0.25, 12.0)
        else:
            open_freq = 0.25
        loose = max(0.8, min(1.5, open_freq / 0.25))
        if ctx.is_bb:
            defend = _interp(P["bb_defend_pct"], r) * loose
            return legal.call("bb-defend") if p < defend else legal.fold("bb-fold")
        base = P["call_open_pct_ip"] if ctx.in_position else P["call_open_pct_oop"]
        if p < base * min(1.0, 3.0 / max(r, 1.0)) * loose:
            return legal.call("flat")
        return legal.fold("fold-vs-open")

    if raises == 2:
        if _we_raised_preflop(ctx):
            if p < P["fourbet_pct"] and ctx.can_raise:
                return legal.raise_to(raise_to * 2.3, "4bet")
            if p < P["call_3bet_pct"] and ctx.to_call <= P["call_3bet_max_stack_share"] * stack_total:
                return legal.call("call-3bet")
            return legal.fold("fold-vs-3bet")
        if p < P["fourbet_pct"] * 0.8 and ctx.can_raise:
            return legal.all_in("cold-4bet-jam")
        return legal.fold("fold-cold-3bet")

    if p < P["jam_vs_4bet_pct"]:
        return legal.all_in("jam-vs-4bet") if ctx.can_raise else legal.call("call-vs-4bet")
    return legal.fold("fold-vs-4bet")


# ---------------------------------------------------------------- postflop

def _cheap_strength(ctx) -> float:
    """Rough hand strength from the made-hand category alone."""
    mine = evaluate(ctx.hole + ctx.board) >> 20
    board_cat = 0
    ranks = [c % 13 for c in ctx.board]
    if len(set(ranks)) < len(ranks):
        board_cat = 1
    base = [0.25, 0.55, 0.80, 0.88, 0.92, 0.94, 0.97, 0.99, 1.0][mine]
    if mine <= board_cat + 1 and mine <= 2:
        base *= 0.8
    return base


def postflop(ctx, tracker, rng, cheap: bool) -> legal.Intent:
    pot = ctx.pot
    k = max(1, ctx.num_opp)
    hs = _cheap_strength(ctx) if cheap else hand_strength(ctx.hole, ctx.board)
    hsk = hs ** k
    outs, _, _ = draw_outs(ctx.hole, ctx.board)
    cards_left = {"flop": 2, "turn": 1}.get(ctx.street, 0)
    draw_eq = 1 - (1 - outs / 47) ** cards_left if outs else 0.0

    if ctx.to_call == 0:
        if not ctx.can_raise:
            return legal.check("no-raise")
        if hsk >= P["value_hs"]:
            return legal.raise_to(pot * P["value_size"], "value")
        if k == 1 and hsk >= P["thin_value_hs_hu"] and (ctx.in_position or ctx.street != "river"):
            return legal.raise_to(pot * 0.5, "thin-value")
        if cards_left and outs >= 8 and k <= 2 and rng.random() < P["semibluff_freq"]:
            return legal.raise_to(pot * 0.5, "semibluff")
        if ctx.street == "flop" and ctx.is_pf_aggressor and k == 1 and rng.random() < P["cbet_freq_hu"]:
            return legal.raise_to(pot * P["cbet_size"], "cbet")
        return legal.check("check")

    frac = ctx.bet_fraction()
    discount = P["big_bet_discount"] * (1.3 if ctx.street == "river" else 1.0)
    adj = hsk ** (1 + discount * frac)
    if hsk >= P["raise_hs"] and ctx.can_raise:
        return legal.raise_to(ctx.current_bet + 0.75 * (pot + ctx.to_call), "value-raise")
    eq = max(adj, draw_eq)
    if eq >= ctx.pot_odds + P["call_margin"]:
        return legal.call("call")
    return legal.fold("fold")
