"""Preflop EV decisions when facing a raise, from equity tables and opponent stats.

Unopened and limped pots use the chart in fallback.preflop. When facing an
open or a 3bet we compare fold / call / re-raise by chip EV:
- the raiser's range is the top x% given by their (shrunk) open or 3bet rate,
- calls realize only part of their equity (position-dependent),
- re-raises win the pot when the raiser folds (fold-to-3bet / 4bet rate) and
  otherwise play against the part of the range that continues.
"""

from __future__ import annotations

from ..core import legal
from ..core.preflop_rank import eq_vs_top
from ..params import P
from . import fallback


def decide(ctx, tracker, rng):
    if ctx.to_call > 0 and (ctx.to_call >= P["big_bet_stack_share"] * ctx.stack or ctx.facing_allin):
        return fallback.preflop(ctx, tracker, rng)
    if ctx.pf_raises == 1 and ctx.pf_aggressor is not None:
        return _facing_open(ctx, tracker, rng)
    if ctx.pf_raises == 2 and ctx.pf_aggressor is not None and fallback._we_raised_preflop(ctx):
        return _facing_3bet(ctx, tracker, rng)
    return fallback.preflop(ctx, tracker, rng)


def _pick(options, rng, pot):
    options.sort(key=lambda o: -o[0])
    eps = P["mix_eps_pot"] * pot
    close = [o for o in options if o[0] >= options[0][0] - eps]
    return close[int(rng.random() * len(close))][1] if len(close) > 1 else options[0][1]


def _facing_open(ctx, tracker, rng):
    k = P["shrink_k"]
    st = tracker.get(ctx.players[ctx.pf_aggressor])
    after_opener = ctx.n - 1 - ctx.pre_order.index(ctx.pf_aggressor)
    pos_factor = P["pf_open_pos_factor"].get(after_opener, 1.0) if ctx.n > 2 else 1.6
    top = max(0.04, min(1.0, st.open.est(P["prior_open"], k) * pos_factor * P["pf_open_range_scale"]))
    callers = ctx.pf_callers_after_raise
    behind = len(ctx.behind)
    pot, to_call = ctx.pot, ctx.to_call
    eq = eq_vs_top(ctx.cls, top) ** (1 + 0.6 * callers)
    if ctx.is_bb:
        realize = P["pf_realize_bb"]
    else:
        realize = P["pf_realize_ip"] if ctx.in_position else P["pf_realize_oop"]
    squeeze_risk = P["pf_squeeze_risk"] * behind * to_call
    options = [(0.0, legal.fold("pf-ev-fold"))]
    options.append((eq * realize * (pot + to_call) - to_call - squeeze_risk, legal.call("pf-ev-call")))
    if ctx.can_raise:
        mult = P["threebet_mult_ip"] if ctx.in_position else P["threebet_mult_oop"]
        target = ctx.current_bet * (mult + callers)
        add = target - ctx.my_bet
        if add < 0.6 * ctx.stack:
            fo = st.fold_to_3bet.est(P["prior_fold_to_3bet"], 10.0)
            p_fold = fo * (P["pf_caller_fold"] ** callers) * (0.92 ** behind)
            cont = max(0.02, top * (1 - fo))
            eq_c = eq_vs_top(ctx.cls, cont)
            pot_after = pot + add + (target - ctx.current_bet)
            ev = p_fold * pot + (1 - p_fold) * (eq_c * P["pf_realize_3bet"] * pot_after - add)
            options.append((ev, legal.raise_to(target, "pf-ev-3bet")))
    return _pick(options, rng, pot)


def _facing_3bet(ctx, tracker, rng):
    st = tracker.get(ctx.players[ctx.pf_aggressor])
    top = max(0.025, st.threebet.est(P["prior_3bet"], 10.0) * P["pf_3bet_range_scale"])
    pot, to_call = ctx.pot, ctx.to_call
    eq = eq_vs_top(ctx.cls, top)
    realize = P["pf_realize_ip"] if ctx.in_position else P["pf_realize_oop"]
    options = [(0.0, legal.fold("pf-ev-fold3b"))]
    options.append((eq * realize * (pot + to_call) - to_call, legal.call("pf-ev-call3b")))
    if ctx.can_raise:
        add = ctx.stack
        fo = P["prior_fold_to_4bet"]
        cont = max(0.015, top * (1 - fo))
        eq_c = eq_vs_top(ctx.cls, cont)
        their_extra = min(ctx.eff_behind, ctx.max_raise_to - ctx.current_bet)
        ev = fo * pot + (1 - fo) * (eq_c * (pot + add + their_extra) - add)
        options.append((ev, legal.all_in("pf-ev-4bet-jam")))
    return _pick(options, rng, pot)
