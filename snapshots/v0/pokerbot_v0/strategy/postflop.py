"""Postflop one-step EV engine.

For every candidate action we estimate its chip EV from:
- our equity against each opponent's action-narrowed range (one simulation),
- how often each opponent folds to a given bet size (tracker, shrunk to
  population priors); the folding part of a range is its weakest part,
- how often they raise, in which case we only continue when strong.
Future streets enter only through a realization factor, so this is a
deliberately simple, robust lookahead.
"""

from __future__ import annotations

from ..core import legal
from ..core.equity import simulate
from ..model.range_model import range_percentiles
from ..model.tracker import size_bucket
from ..params import P


def _fold_prob(tracker, ctx, seat, frac, facing_raise=False) -> float:
    if ctx.stacks[seat] == 0:
        return 0.0  # all-in players cannot fold
    st = tracker.get(ctx.players[seat])
    b = size_bucket(frac)
    f = st.fold_vs_bet[b].est(P["prior_fold_vs_bet"][b], P["shrink_k"])
    if facing_raise:
        f *= 0.8  # a bettor's range is stronger than a checker's
    return max(0.0, min(0.95, f))


def _raise_prob(tracker, ctx, seat) -> float:
    if ctx.stacks[seat] == 0:
        return 0.0
    st = tracker.get(ctx.players[seat])
    return max(0.0, min(0.5, st.raise_vs_bet.est(P["prior_raise_vs_bet"], P["shrink_k"])))


def decide(agent, ctx, rng, deadline):
    tracker = agent.tracker
    seats = list(ctx.opponents)
    ranges_by_seat = agent.range_model.build(ctx, tracker)
    bs = agent.range_model.board_strength(ctx.board)
    ranges = [ranges_by_seat[s] for s in seats]
    pcts = [range_percentiles(r, bs) for r in ranges]
    samples = simulate(ctx.hole, ctx.board, ranges, pcts, rng, deadline)
    if len(samples) < P["min_samples"] and not (len(seats) == 1 and len(ctx.board) == 5):
        return None  # not enough information: let the fallback decide
    eq_all, _ = samples.equity()

    pot = ctx.pot
    river = ctx.street == "river"
    realize = 1.0 if river else (P["realize_ip"] if ctx.in_position else P["realize_oop"])
    options = []  # (ev, intent)

    def bet_ev(add, frac, facing_raise, pot_now, their_call_extra):
        """EV of putting `add` more chips in with a bet/raise of relative size `frac`."""
        folds = [_fold_prob(tracker, ctx, s, frac, facing_raise) for s in seats]
        raises = [_raise_prob(tracker, ctx, s) for s in seats]
        p_all_fold = 1.0
        for f in folds:
            p_all_fold *= f
        p_raise = 0.0 if add >= ctx.stack else min(0.6, sum(q * (1 - f) for q, f in zip(raises, folds)))
        p_call = max(0.0, 1.0 - p_all_fold - p_raise)
        thresholds = [f for f in folds]
        e_call, mass = samples.equity(thresholds)
        if mass <= 0:
            e_call = eq_all
        n_callers = max(1.0, sum(1 - f for f in folds))
        all_in = add >= ctx.stack
        r = 1.0 if all_in else realize
        ev_call = e_call * r * (pot_now + add + n_callers * their_call_extra) - add
        ev = p_all_fold * pot_now + p_call * ev_call
        if p_raise > 0:
            e_raise, mass_r = samples.equity([max(1 - q, f) for q, f in zip(raises, folds)])
            if mass_r <= 0:
                e_raise = e_call
            re_size = 3 * their_call_extra + add
            if e_raise >= 0.45:
                ev_r = e_raise * (pot_now + 2 * re_size) - re_size
            else:
                ev_r = -add
            ev += p_raise * ev_r
        return ev

    if ctx.to_call == 0:
        options.append((eq_all * realize * pot, legal.check("check")))
        if ctx.can_raise:
            sizes = list(P["bet_sizes"])
            for frac in sizes:
                add = frac * pot
                if add >= ctx.stack * 0.85:
                    continue
                if add < ctx.min_raise_to:
                    add = ctx.min_raise_to
                ev = bet_ev(add, add / pot, False, pot, add)
                options.append((ev, legal.raise_to(add, f"bet-{frac}")))
            add = ctx.stack
            ev = bet_ev(add, add / pot, False, pot, min(add, ctx.eff_behind))
            options.append((ev, legal.all_in("bet-allin")))
    else:
        options.append((0.0, legal.fold("fold")))
        call_amt = ctx.to_call
        r = 1.0 if call_amt >= ctx.stack else realize
        options.append((eq_all * r * (pot + call_amt) - call_amt, legal.call("call")))
        if ctx.can_raise:
            for m in (0.7, 1.1):
                target = ctx.current_bet + m * (pot + ctx.to_call)
                if target >= ctx.max_raise_to * 0.85:
                    continue
                target = max(target, ctx.min_raise_to)
                add = target - ctx.my_bet
                extra = target - ctx.current_bet
                ev = bet_ev(add, extra / max(pot + ctx.to_call, 1), True, pot, extra)
                options.append((ev, legal.raise_to(target, f"raise-{m}")))
            add = ctx.stack
            extra = max(ctx.max_raise_to - ctx.current_bet, 0)
            ev = bet_ev(add, extra / max(pot + ctx.to_call, 1), True, pot, min(extra, ctx.eff_behind))
            options.append((ev, legal.all_in("raise-allin")))

    options.sort(key=lambda o: -o[0])
    best_ev = options[0][0]
    eps = P["mix_eps_pot"] * pot
    close = [o for o in options if o[0] >= best_ev - eps]
    choice = close[int(rng.random() * len(close))] if len(close) > 1 else options[0]
    agent.last_debug = (round(eq_all, 3), [(round(e, 1), i.tag) for e, i in options[:4]])
    return choice[1]
