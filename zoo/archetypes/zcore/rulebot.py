"""Parametric rule engine behind the Tier A archetype bots (dev only).

Each archetype is a faithful, robust implementation of a common bot family,
expressed as a parameter dict. Shared guarantees: never raises, only legal
actions (via zcore.legal), private RNG, bounded time.

Strength modes
  "mc_random": Monte Carlo equity vs k random hands (the canonical LLM bot)
  "hs":        exact current hand strength vs random hands, raised to k
"""

from __future__ import annotations

import random
import zlib

from macpoker import Bot

from . import legal
from .clock import Deadline
from .evaluator import evaluate
from .gamectx import Ctx
from .handinfo import draw_outs, hand_strength
from .preflop_rank import eq_vs_random, eq_vs_top, pct
from .tracker import Tracker

DEFAULTS = {
    # preflop
    "open_pct_by_behind": {1: 0.40, 2: 0.42, 3: 0.27, 4: 0.20, 5: 0.15, 6: 0.13, 7: 0.12, 8: 0.11},
    "open_pct_hu": 0.65,
    "looseness": 1.0,
    "open_size_bb": 2.5,
    "open_size_jitter": 0.0,
    "limp_pct": 0.0,  # extra share of hands limped instead of folded (passive bots)
    "iso_pct": 0.10,
    "overlimp_pct": 0.18,
    "threebet_pct": 0.04,
    "threebet_bluff_freq": 0.0,
    "call_open_pct": 0.11,
    "bb_defend_pct": 0.30,
    "fourbet_pct": 0.025,
    "call_3bet_pct": 0.06,
    "jam_vs_4bet_pct": 0.02,
    "big_bet_share": 0.4,
    "allin_mode": "range",  # "range" | "eq_random"
    "allin_assumed_top": 0.12,
    "allin_margin": 0.03,
    # postflop
    "strength": "hs",
    "mc_samples": 250,
    "value_t": 0.80,
    "raise_t": 0.93,
    "call_margin": 0.04,
    "call_mode": "pot_odds",  # "pot_odds" | "station" | "mdf"
    "bet_size": 0.66,
    "size_mode": "fixed",  # "fixed" | "proportional"
    "size_min": 0.4,
    "size_max": 1.0,
    "bluff_freq": 0.0,
    "bluff_size": 0.5,
    "cbet_freq": 0.55,
    "cbet_size": 0.5,
    "semibluff_freq": 0.4,
    "slowplay_freq": 0.0,
    "raise_mult": 3.0,
    "bluff_raise_freq": 0.0,
    "barrel_freq": 0.0,  # keep betting turn/river as aggressor with air
    "overbet_freq": 0.0,
    "big_bet_respect": 0.6,  # strength discount exponent per pot-fraction faced
    "adaptive": False,
    "pushfold": False,
    "shove_pct": 0.18,
    # specials
    "die_at_hand": None,
    "bug_raise_increment": False,
}


class RuleBot(Bot):
    def __init__(self, params: dict, name: str = "rulebot"):
        self.p = dict(DEFAULTS)
        self.p.update(params)
        self.name = name
        self.tracker = Tracker()
        self.bb = 2
        self.player = 0
        self.hands_done = 0
        self.aggressor_streets: set = set()

    # ---- hooks -----------------------------------------------------------
    def on_match_start(self, info):
        try:
            blinds = info.get("blinds") or [1, 2]
            self.bb = int(blinds[1])
            self.player = info.get("player", 0)
            self.tracker.set_blinds(int(blinds[0]), self.bb)
        except Exception:
            pass

    def on_hand_start(self, info):
        try:
            self.tracker.on_hand_start(info)
            self.aggressor_streets = set()
        except Exception:
            pass

    def on_action(self, event):
        try:
            self.tracker.on_action(event)
        except Exception:
            pass

    def on_street(self, event):
        try:
            self.tracker.on_street(event)
        except Exception:
            pass

    def on_hand_end(self, info):
        try:
            self.tracker.on_hand_end(info)
            self.hands_done += 1
        except Exception:
            pass

    # ---- act -------------------------------------------------------------
    def act(self, state):
        die = self.p["die_at_hand"]
        if die is not None and state.hand >= die:
            raise RuntimeError("simulated crash")  # engine marks RTE -> check-fold
        try:
            ctx = Ctx(state, self.bb)
            rng = random.Random(zlib.crc32(f"{self.name}|{state.hand}|{state.hole}|{state.board}|{len(state.history)}".encode()))
            if self.p["pushfold"]:
                intent = self._pushfold(ctx, rng)
            elif ctx.street == "preflop":
                intent = self._preflop(ctx, rng)
            else:
                intent = self._postflop(ctx, rng, state.clock_ms)
            if intent.kind == legal.RAISE:
                self.aggressor_streets.add(ctx.street)
            if self.p["bug_raise_increment"] and intent.kind == legal.RAISE and intent.amount < 10**8:
                # classic bug: treats raise_to as "raise by"; engine clamps it
                return state.raise_to(max(1, intent.amount - ctx.current_bet))
            return legal.finalize(state, intent)
        except Exception:
            return legal.passive(state)

    # ---- preflop -----------------------------------------------------------
    def _open_pct(self, ctx):
        if ctx.n == 2:
            base = self.p["open_pct_hu"]
        else:
            base = self.p["open_pct_by_behind"].get(len(ctx.behind), 0.11)
        return min(1.0, base * self.p["looseness"])

    def _preflop(self, ctx, rng):
        p = pct(ctx.cls)
        P = self.p
        bb = ctx.bb
        L = P["looseness"]
        if ctx.to_call > 0 and (ctx.to_call >= P["big_bet_share"] * ctx.stack or ctx.facing_allin):
            if P["allin_mode"] == "eq_random":
                eq = eq_vs_random(ctx.cls, 1)
            else:
                eq = eq_vs_top(ctx.cls, P["allin_assumed_top"] * L)
            if eq >= ctx.pot_odds + P["allin_margin"]:
                return legal.call("allin-call")
            return legal.fold("allin-fold")
        if ctx.pf_raises == 0:
            if ctx.to_call == 0:
                if p < P["iso_pct"] * L:
                    return legal.raise_to((3 + ctx.pf_limpers) * bb, "bb-raise")
                return legal.check("bb-check")
            if ctx.pf_limpers:
                if p < P["iso_pct"] * L:
                    return legal.raise_to((4 + ctx.pf_limpers) * bb, "iso")
                if p < P["overlimp_pct"] * L or (ctx.is_sb and p < 0.35 * L):
                    return legal.call("overlimp")
                return legal.fold("fold")
            op = self._open_pct(ctx)
            if p < op:
                size = P["open_size_bb"] + (rng.random() - 0.5) * 2 * P["open_size_jitter"]
                if ctx.is_sb and ctx.n > 2:
                    size += 0.5
                return legal.raise_to(size * bb, "open")
            if p < op + P["limp_pct"]:
                return legal.call("limp")
            return legal.fold("fold")
        r = ctx.current_bet / bb
        if ctx.pf_raises == 1:
            if p < P["threebet_pct"] * L or (p < 0.35 and rng.random() < P["threebet_bluff_freq"]):
                mult = 3.0 if ctx.in_position else 3.6
                return legal.raise_to(ctx.current_bet * (mult + ctx.pf_callers_after_raise), "3bet")
            scale = min(1.0, 3.0 / max(r, 1.0))
            if ctx.is_bb:
                if p < P["bb_defend_pct"] * L * scale:
                    return legal.call("defend")
                return legal.fold("fold")
            if p < P["call_open_pct"] * L * scale:
                return legal.call("flat")
            return legal.fold("fold")
        if ctx.pf_raises == 2:
            if p < P["fourbet_pct"] * L:
                return legal.raise_to(ctx.current_bet * 2.3, "4bet")
            if p < P["call_3bet_pct"] * L and ctx.to_call < 0.25 * ctx.stack:
                return legal.call("call3b")
            return legal.fold("fold")
        if p < P["jam_vs_4bet_pct"] * L:
            return legal.all_in("jam")
        return legal.fold("fold")

    # ---- postflop ------------------------------------------------------------
    def _strength(self, ctx, rng, clock_ms):
        k = max(1, ctx.num_opp)
        if self.p["strength"] == "mc_random":
            n = self.p["mc_samples"] if clock_ms > 5000 else 40
            deadline = Deadline(60)
            dead = set(ctx.hole) | set(ctx.board)
            deck = [c for c in range(52) if c not in dead]
            need = 5 - len(ctx.board)
            won = 0.0
            done = 0
            for i in range(n):
                if i % 32 == 31 and deadline.expired():
                    break
                draw = rng.sample(deck, need + 2 * k)
                board = ctx.board + draw[:need]
                mine = evaluate(ctx.hole + board)
                best, ties = -1, 0
                for j in range(k):
                    v = evaluate([draw[need + 2 * j], draw[need + 2 * j + 1], *board])
                    if v > best:
                        best, ties = v, 1
                    elif v == best:
                        ties += 1
                won += 1.0 if mine > best else (1.0 / (ties + 1) if mine == best else 0.0)
                done += 1
            return won / max(done, 1)
        return hand_strength(ctx.hole, ctx.board) ** k

    def _size(self, s):
        P = self.p
        if P["size_mode"] == "proportional":
            t = max(0.0, min(1.0, (s - P["value_t"]) / max(1 - P["value_t"], 1e-6)))
            return P["size_min"] + (P["size_max"] - P["size_min"]) * t
        return P["bet_size"]

    def _opp_adjust(self, ctx):
        """(bluff multiplier, call-margin delta) from opponent stats (adaptive bots)."""
        if not self.p["adaptive"] or not ctx.opponents:
            return 1.0, 0.0
        folds = []
        aggs = []
        for s in ctx.opponents:
            st = self.tracker.get(ctx.players[s])
            folds.append(st.fold_vs_bet[1].est(0.45, 8))
            aggs.append(st.bet_when_checked.est(0.35, 8))
        f = min(folds)
        a = max(aggs)
        bluff_mult = max(0.2, min(3.0, (f / 0.45) ** 2))
        margin = -0.05 if a > 0.5 else (0.04 if a < 0.2 else 0.0)
        return bluff_mult, margin

    def _postflop(self, ctx, rng, clock_ms):
        P = self.p
        pot = ctx.pot
        s = self._strength(ctx, rng, clock_ms)
        outs, _, _ = draw_outs(ctx.hole, ctx.board)
        cards_left = {"flop": 2, "turn": 1}.get(ctx.street, 0)
        draw_eq = 1 - (1 - outs / 47) ** cards_left if outs else 0.0
        bluff_mult, margin_adj = self._opp_adjust(ctx)
        aggressor = ctx.is_pf_aggressor or ("flop" in self.aggressor_streets and ctx.street != "flop")

        if ctx.to_call == 0:
            if not ctx.can_raise:
                return legal.check("check")
            if s >= P["raise_t"] and rng.random() < P["slowplay_freq"]:
                return legal.check("trap")
            if s >= P["value_t"]:
                size = self._size(s)
                if rng.random() < P["overbet_freq"]:
                    size = 1.5
                return legal.raise_to(pot * size, "value")
            if cards_left and outs >= 8 and rng.random() < P["semibluff_freq"] * bluff_mult:
                return legal.raise_to(pot * P["bluff_size"], "semibluff")
            if ctx.street == "flop" and ctx.is_pf_aggressor and rng.random() < P["cbet_freq"] * min(bluff_mult, 1.5):
                return legal.raise_to(pot * P["cbet_size"], "cbet")
            if aggressor and ctx.street != "flop" and rng.random() < P["barrel_freq"] * bluff_mult:
                return legal.raise_to(pot * P["bluff_size"], "barrel")
            if rng.random() < P["bluff_freq"] * bluff_mult:
                return legal.raise_to(pot * P["bluff_size"], "bluff")
            return legal.check("check")

        frac = ctx.bet_fraction()
        adj = s ** (1 + P["big_bet_respect"] * frac)
        if s >= P["raise_t"] and ctx.can_raise:
            return legal.raise_to(ctx.current_bet + (P["raise_mult"] - 1) * ctx.to_call + pot * 0.3, "raise")
        if ctx.can_raise and rng.random() < P["bluff_raise_freq"] * bluff_mult and ctx.num_opp == 1:
            return legal.raise_to(ctx.current_bet + 2 * ctx.to_call + pot * 0.3, "bluff-raise")
        mode = P["call_mode"]
        if mode == "station":
            made = evaluate(ctx.hole + ctx.board) >> 20
            if made >= 1 or outs >= 4 or s >= 0.4:
                return legal.call("station-call")
            return legal.fold("fold")
        if mode == "mdf":
            pot_before = max(pot - ctx.to_call, 1)
            mdf = pot_before / (pot_before + ctx.to_call)
            if hand_strength(ctx.hole, ctx.board) >= 1 - mdf or draw_eq >= ctx.pot_odds:
                return legal.call("mdf-call")
            return legal.fold("fold")
        if max(adj, draw_eq) >= ctx.pot_odds + P["call_margin"] + margin_adj:
            return legal.call("call")
        return legal.fold("fold")

    # ---- push/fold -----------------------------------------------------------
    def _pushfold(self, ctx, rng):
        p = pct(ctx.cls)
        P = self.p
        if ctx.street == "preflop":
            if ctx.to_call == 0:
                return legal.check("check")
            if ctx.pf_raises == 0:
                return legal.all_in("shove") if p < P["shove_pct"] * P["looseness"] else legal.fold("fold")
            # facing a raise/shove: call or re-shove with the top of the range
            eq = eq_vs_top(ctx.cls, P["allin_assumed_top"])
            if eq >= ctx.pot_odds + P["allin_margin"]:
                return legal.all_in("reshove") if ctx.can_raise else legal.call("call")
            return legal.fold("fold")
        s = hand_strength(ctx.hole, ctx.board) ** max(1, ctx.num_opp)
        outs, _, _ = draw_outs(ctx.hole, ctx.board)
        made = evaluate(ctx.hole + ctx.board) >> 20
        if made >= 1 and s >= 0.5 or outs >= 8:
            return legal.all_in("jam")
        return legal.check("check") if ctx.to_call == 0 else legal.fold("fold")
