"""
Team D2 - "Field Day" (exploit-the-field team)

Approach: solid fundamentals (ranked preflop chart and Monte Carlo equity
postflop), plus hard exploitation of the AI-written bots we expect in the
field. Every opponent is profiled by player id (VPIP, PFR, shove rate,
fold-to-raise, fold-to-bet, aggression) and labelled as allin, maniac,
station, rock or reg. The decision rules switch depending on who is in the
pot.

Iterations (about 2 days):
  v1  Ranked 169-hand chart, pot-odds calls, fixed-size value bets.
  v2  Per-player-id profiler with labels; calling ranges against shove
      bots from MC equity against random hands, counting overcallers.
  v3  Exploits: open any two cards into folders, never bluff stations and
      value-bet them pot-sized, trap and call down maniacs, give up against
      rocks that show aggression.
  v4  Postflop MC with class-based ranges and an "aggression = made hand"
      filter for non-maniacs. Clock-scaled sample counts and an emergency
      chart-only mode.
  v5  Tuned sizings and thresholds against house bots and our own older
      builds.

Strategy:
  1. Profile each player id and pick per-label ranges: wide against
     maniacs and shove bots, tight against rocks that put money in.
  2. Steal relentlessly when only folders are left to act. Isolate limpers
     with big raises. Against stations and maniacs, play for value only:
     big value bets, no bluffs.
  3. Postflop, MC equity against the labelled ranges sets value bets,
     calls and folds. Sizes are pot-sized against stations, small against
     rocks, and we trap against maniacs.
"""

import random
import time

from macpoker import Bot

RANK_CHARS = "23456789TJQKA"
SUIT_CHARS = "cdhs"


def parse(c):
    return SUIT_CHARS.index(c[1].lower()) * 13 + RANK_CHARS.index(c[0].upper())


# ---------------------------------------------------------------------------
# 7-card evaluator (card = suit*13 + rank). Returns a comparable int.
# ---------------------------------------------------------------------------
BITS = [bin(i).count("1") for i in range(1 << 13)]
STRAIGHT_HI = [-1] * (1 << 13)
for mask in range(1 << 13):
    m = (mask << 1) | (1 if mask & (1 << 12) else 0)  # bit0 = low ace
    for hi in range(13, 3, -1):
        w = 0b11111 << (hi - 4)
        if m & w == w:
            STRAIGHT_HI[mask] = hi - 1
            break


def top_bits(mask, k):
    out = []
    r = 12
    while r >= 0 and len(out) < k:
        if mask & (1 << r):
            out.append(r)
        r -= 1
    return out


def pack(cat, ranks):
    v = cat
    for i in range(5):
        v = v * 16 + (ranks[i] + 1 if i < len(ranks) else 0)
    return v


def evaluate(cards):
    suits = [0, 0, 0, 0]
    hist = [0] * 13
    for c in cards:
        s, r = divmod(c, 13)
        suits[s] |= 1 << r
        hist[r] += 1
    flush = -1
    for s in range(4):
        if BITS[suits[s]] >= 5:
            flush = s
            break
    if flush >= 0:
        fm = suits[flush]
        sh = STRAIGHT_HI[fm]
        if sh >= 0:
            return pack(8, [sh])
    four = []
    three = []
    two = []
    one = []
    for r in range(12, -1, -1):
        h = hist[r]
        if h == 4:
            four.append(r)
        elif h == 3:
            three.append(r)
        elif h == 2:
            two.append(r)
        elif h == 1:
            one.append(r)
    if four:
        rest = sorted(three + two + one, reverse=True)
        return pack(7, [four[0]] + rest[:1])
    if three and (len(three) > 1 or two):
        pr = max(three[1] if len(three) > 1 else -1, two[0] if two else -1)
        return pack(6, [three[0], pr])
    if flush >= 0:
        return pack(5, top_bits(suits[flush], 5))
    allmask = suits[0] | suits[1] | suits[2] | suits[3]
    sh = STRAIGHT_HI[allmask]
    if sh >= 0:
        return pack(4, [sh])
    if three:
        return pack(3, [three[0]] + one[:2])
    if len(two) >= 2:
        kick = sorted(two[2:] + one, reverse=True)
        return pack(2, two[:2] + kick[:1])
    if two:
        return pack(1, [two[0]] + one[:3])
    return pack(0, one[:5])


CAT_SHIFT = 16 ** 5


def category(v):
    return v // CAT_SHIFT


# ---------------------------------------------------------------------------
# Preflop ranking, best first. Card classes: "AKs", "AKo", "AA".
# ---------------------------------------------------------------------------
RANKING = (
    "AA KK QQ JJ AKs TT AQs AJs KQs AKo 99 ATs KJs QJs KTs AQo 88 JTs QTs A9s "
    "AJo KQo 77 A8s K9s T9s A7s J9s Q9s ATo A5s A6s KJo 66 A4s QJo K8s T8s A3s "
    "98s J8s A2s K7s KTo Q8s 55 JTo 87s QTo K6s 97s 44 K5s T7s A9o 76s K4s J7s "
    "33 Q7s K3s 86s 65s K2s 22 Q6s 54s T9o 96s Q5s 75s J9o Q4s A8o J6s K9o 64s "
    "Q3s T6s 85s Q9o J5s 53s Q2s A7o J4s 74s 95s 43s J3s A5o 98o T8o J2s 63s "
    "A6o T5s 84s A4o 52s T4s 42s K8o T3s 73s A3o 94s J8o 87o T2s 32s 62s 93s "
    "A2o Q8o K7o 92s 97o 83s 76o 82s K6o 72s T7o 86o 65o K5o J7o 54o Q7o 75o "
    "K4o 96o K3o 64o Q6o K2o 85o 53o T6o Q5o 43o 74o J6o Q4o 95o Q3o 63o J5o "
    "Q2o 84o 52o J4o T5o 42o J3o 73o J2o 94o T4o 32o T3o 62o 93o T2o 83o 92o "
    "82o 72o"
).split()


def hand_class(r1, r2, suited):
    hi, lo = max(r1, r2), min(r1, r2)
    if hi == lo:
        return RANK_CHARS[hi] * 2
    return RANK_CHARS[hi] + RANK_CHARS[lo] + ("s" if suited else "o")


def _build_pct():
    seen = []
    for k in RANKING:
        if k not in seen:
            seen.append(k)
    allk = []
    for a in range(13):
        for b in range(13):
            if a > b:
                allk.append(RANK_CHARS[a] + RANK_CHARS[b] + "s")
                allk.append(RANK_CHARS[a] + RANK_CHARS[b] + "o")
            elif a == b:
                allk.append(RANK_CHARS[a] * 2)
    for k in allk:
        if k not in seen:
            seen.append(k)
    pct = {}
    total = 0
    for k in seen:
        total += 6 if len(k) == 2 else (4 if k[2] == "s" else 12)
    acc = 0
    for k in seen:
        n = 6 if len(k) == 2 else (4 if k[2] == "s" else 12)
        pct[k] = (acc + n / 2.0) / total
        acc += n
    return pct


PCT = _build_pct()


def combo_pct(c1, c2):
    return PCT[hand_class(c1 % 13, c2 % 13, c1 // 13 == c2 // 13)]


# all 1326 combos sorted best-first, used to sample "top x%" ranges
COMBOS = sorted(
    [(a, b) for a in range(52) for b in range(a + 1, 52)],
    key=lambda ab: combo_pct(ab[0], ab[1]),
)
COMBO_P = [combo_pct(a, b) for a, b in COMBOS]


# ---------------------------------------------------------------------------
# Opponent profile
# ---------------------------------------------------------------------------
class Profile:
    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.shoves = 0
        self.pf_faced = 0
        self.pf_folds = 0
        self.agg = 0
        self.pas = 0
        self.faced = 0
        self.folds = 0
        self.sd = 0
        self.sd_weak = 0

    def r(self, a, b, prior, weight=5.0):
        return (a + prior * weight) / (b + weight)

    def label(self):
        if self.hands < 4:
            return "unknown"
        vpip = self.r(self.vpip, self.hands, 0.3)
        pfr = self.r(self.pfr, self.hands, 0.12)
        shove = self.r(self.shoves, self.hands, 0.02)
        ftr = self.r(self.pf_folds, self.pf_faced, 0.6)
        ftb = self.r(self.folds, self.faced, 0.45)
        aggr = self.r(self.agg, self.agg + self.pas, 0.3)
        if shove >= 0.35:
            return "allin"
        if pfr >= 0.38 or (aggr >= 0.55 and self.agg + self.pas >= 6):
            return "maniac"
        if vpip >= 0.5 and ftb <= 0.3 and ftr <= 0.45:
            return "station"
        if vpip <= 0.2 or (ftr >= 0.8 and ftb >= 0.6):
            return "rock"
        return "reg"

    def fold_to_raise(self):
        return self.r(self.pf_folds, self.pf_faced, 0.6)

    def fold_to_bet(self):
        return self.r(self.folds, self.faced, 0.45)

    def vpip_rate(self):
        return self.r(self.vpip, self.hands, 0.3)

    def pfr_rate(self):
        return self.r(self.pfr, self.hands, 0.12)


class FieldExploiter(Bot):
    name = "field_day"

    def __init__(self):
        self.rnd = random.Random(0xD2)
        self.prof = {}
        self.hands_total = 100
        self.stack0 = 200
        self.big = 2
        self.cur_hand = -1
        self.hand_flags = {}
        self.bets = []
        self.raises_pf = 0
        self.start_stacks = []

    # ---------------------------------------------------------------- hooks
    def P(self, pid):
        p = self.prof.get(pid)
        if p is None:
            p = Profile()
            self.prof[pid] = p
        return p

    def on_match_start(self, info):
        try:
            self.hands_total = int(info.get("num_hands", 100))
            self.stack0 = int(info.get("stack", 200))
            self.big = int(info.get("blinds", [1, 2])[1])
        except Exception:
            pass

    def on_hand_start(self, info):
        try:
            self.cur_hand = info.get("hand", -1)
            players = info.get("players", [])
            n = len(players)
            self.start_stacks = list(info.get("stacks", [self.stack0] * n))
            self.bets = [0] * n
            btn = info.get("button", 0)
            if n == 2:
                sbs, bbs = btn, (btn + 1) % n
            else:
                sbs, bbs = (btn + 1) % n, (btn + 2) % n
            if n >= 2:
                self.bets[sbs] = min(1, self.start_stacks[sbs])
                self.bets[bbs] = min(self.big, self.start_stacks[bbs])
            self.raises_pf = 0
            self.hand_flags = {pid: [False, False] for pid in players}
        except Exception:
            pass

    def on_street(self, event):
        try:
            self.bets = [0] * len(self.bets)
        except Exception:
            pass

    def on_action(self, ev):
        try:
            seat = ev["seat"]
            pid = ev["players"][seat]
            kind = ev["action"]
            amt = int(ev.get("amount") or 0)
            p = self.P(pid)
            if seat >= len(self.bets):
                return
            top = max(self.bets)
            facing = top > self.bets[seat]
            if ev.get("street") == "preflop":
                fl = self.hand_flags.setdefault(pid, [False, False])
                if facing and self.raises_pf > 0:
                    p.pf_faced += 1
                    if kind == "fold":
                        p.pf_folds += 1
                if kind in ("call", "raise"):
                    fl[0] = True
                if kind == "raise":
                    fl[1] = True
                    self.raises_pf += 1
                    st = self.start_stacks[seat] if seat < len(self.start_stacks) else self.stack0
                    if amt >= 0.9 * st:
                        p.shoves += 1
            else:
                if facing:
                    p.faced += 1
                    if kind == "fold":
                        p.folds += 1
                if kind == "raise":
                    p.agg += 1
                elif kind in ("call", "check"):
                    p.pas += 1
            if kind == "raise":
                self.bets[seat] = amt
            elif kind == "call":
                self.bets[seat] = top
        except Exception:
            pass

    def on_hand_end(self, info):
        try:
            for pid, fl in self.hand_flags.items():
                p = self.P(pid)
                p.hands += 1
                if fl[0]:
                    p.vpip += 1
                if fl[1]:
                    p.pfr += 1
        except Exception:
            pass

    # ---------------------------------------------------------------- act
    def act(self, state):
        try:
            return self.finalize(state, self.think(state))
        except Exception:
            try:
                return state.check() if state.to_call == 0 else state.fold()
            except Exception:
                return state.fold()

    def finalize(self, state, decision):
        kind, amount = decision
        if kind == "raise" and state.can_raise:
            lo, hi = state.min_raise_to, state.max_raise_to
            amount = int(amount)
            if amount >= 0.9 * hi:
                amount = hi
            amount = min(hi, max(lo, amount))
            return state.raise_to(amount)
        if kind == "raise":
            kind = "call"
        if kind == "call" and state.to_call > 0:
            return state.call()
        if state.to_call == 0:
            return state.check()
        return state.fold()

    # ---------------------------------------------------------------- helpers
    def opponents(self, state):
        return [s for s in range(state.num_players) if s != state.seat and not state.folded[s]]

    def lbl(self, state, seat):
        return self.P(state.players[seat]).label()

    def sims_allowed(self, state):
        clock = state.clock_ms
        left = max(1, self.hands_total - state.hand)
        spare = clock - 3000
        if spare <= 0:
            return 0, 0.0
        per_hand = spare / left
        t = min(0.09, per_hand / 3.0 / 1000.0)
        if t < 0.003:
            return 0, 0.0
        return 1500, t

    def range_for(self, state, seat):
        """Return (top fraction, need_made_hand_prob) for seat's likely holdings."""
        p = self.P(state.players[seat])
        lab = p.label()
        pf_raised = False
        pf_shoved = False
        pf_called = False
        post_aggr = False
        for h in state.history:
            if h[1] != seat:
                continue
            if h[0] == "preflop":
                if h[2] == "raise":
                    pf_raised = True
                    if h[3] >= 0.9 * self.stack0:
                        pf_shoved = True
                elif h[2] == "call":
                    pf_called = True
            elif h[2] == "raise":
                post_aggr = True
        if lab in ("allin", "maniac"):
            frac = 1.0 if lab == "allin" else 0.8
            return frac, 0.0 if lab == "allin" else (0.35 if post_aggr else 0.0)
        if pf_shoved:
            frac = 0.06 if lab == "rock" else max(0.06, min(0.4, p.pfr_rate() * 0.7))
        elif pf_raised:
            frac = max(0.05, min(0.7, p.pfr_rate()))
            if lab == "rock":
                frac = min(frac, 0.1)
        elif pf_called:
            frac = max(0.12, min(1.0, p.vpip_rate()))
        else:
            frac = 1.0
        need = 0.0
        if post_aggr:
            need = {"station": 0.85, "rock": 0.95, "reg": 0.7, "unknown": 0.65}.get(lab, 0.6)
        return frac, need

    def mc_equity(self, state, hole, board, seats, max_sims, tlimit):
        if not seats:
            return 1.0
        specs = [self.range_for(state, s) for s in seats]
        dead = set(hole + board)
        deck = [c for c in range(52) if c not in dead]
        pools = []
        for frac, need in specs:
            cut = 0
            limit = min(1.0, frac)
            while cut < len(COMBOS) and COMBO_P[cut] <= limit:
                cut += 1
            pool = [cb for cb in COMBOS[:max(cut, 20)] if cb[0] not in dead and cb[1] not in dead]
            pools.append(pool)
        rnd = self.rnd
        missing = 5 - len(board)
        wins = 0.0
        done = 0
        deadline = time.perf_counter() + tlimit
        board_cat = None
        while done < max_sims:
            if done >= 40 and (done & 7) == 0 and time.perf_counter() > deadline:
                break
            taken = set()
            hands = []
            for (frac, need), pool in zip(specs, pools):
                pick = None
                for _ in range(5):
                    cb = pool[int(rnd.random() * len(pool))] if pool else tuple(rnd.sample(deck, 2))
                    if cb[0] in taken or cb[1] in taken:
                        continue
                    if need > 0 and len(board) >= 3 and rnd.random() < need:
                        if board_cat is None:
                            board_cat = self.board_level(board)
                        cat = category(evaluate(list(cb) + board))
                        if cat < 1 or cat <= board_cat:
                            continue
                    pick = cb
                    break
                if pick is None:
                    while True:
                        cb = tuple(rnd.sample(deck, 2))
                        if cb[0] not in taken and cb[1] not in taken:
                            pick = cb
                            break
                taken.update(pick)
                hands.append(pick)
            runout = []
            if missing:
                for c in rnd.sample(deck, missing + 2 * len(hands)):
                    if c not in taken:
                        runout.append(c)
                        if len(runout) == missing:
                            break
            full = board + runout
            me = evaluate(hole + full)
            best = 0
            tie = 0
            for h in hands:
                v = evaluate(list(h) + full)
                if v > best:
                    best, tie = v, 1
                elif v == best:
                    tie += 1
            if me > best:
                wins += 1
            elif me == best:
                wins += 1.0 / (tie + 1)
            done += 1
        if done == 0:
            return None
        return wins / done

    @staticmethod
    def board_level(board):
        cnt = {}
        for c in board:
            cnt[c % 13] = cnt.get(c % 13, 0) + 1
        vals = sorted(cnt.values(), reverse=True)
        if vals[0] >= 3:
            return 3
        if vals[0] == 2:
            return 2 if len(vals) > 1 and vals[1] == 2 else 1
        return 0

    def rough_equity(self, hole, board, nopp):
        if len(board) < 3:
            e = 0.8 - 0.5 * combo_pct(hole[0], hole[1])
        else:
            cat = category(evaluate(hole + board))
            e = [0.3, 0.55, 0.75, 0.82, 0.86, 0.88, 0.94, 0.97, 0.99][cat]
        return e ** max(1, nopp)

    def equity(self, state, hole, board, seats):
        n, t = self.sims_allowed(state)
        e = None
        if n:
            e = self.mc_equity(state, hole, board, seats, n, t)
        if e is None:
            e = self.rough_equity(hole, board, len(seats))
        return e

    # ---------------------------------------------------------------- brain
    def think(self, state):
        hole = [parse(c) for c in state.hole]
        board = [parse(c) for c in state.board]
        if state.street == "preflop":
            return self.preflop(state, hole)
        return self.postflop(state, hole, board)

    def preflop(self, state, hole):
        n = state.num_players
        seat = state.seat
        bb = self.big
        pct = combo_pct(hole[0], hole[1])
        hist = [h for h in state.history if h[0] == "preflop"]
        raises = [h for h in hist if h[2] == "raise"]
        opener = state.button if n == 2 else (state.button + 3) % n
        order = [(opener + i) % n for i in range(n)]
        me_i = order.index(seat)
        acted = {h[1] for h in hist}
        behind = [s for s in order[me_i + 1:] if not state.folded[s] and s not in acted]
        labels_behind = [self.lbl(state, s) for s in behind]
        opps = self.opponents(state)
        top_bet = max(state.street_bets)
        my_total = state.my_stack + state.street_bets[seat]

        if not raises:
            limpers = [h[1] for h in hist if h[2] == "call"]
            # who is left to act and how foldy are they
            foldy = all(
                self.P(state.players[s]).fold_to_raise() >= 0.72 or self.lbl(state, s) == "rock"
                for s in behind
            ) if behind else True
            sticky = any(l in ("station", "allin", "maniac") for l in labels_behind)
            k = len(behind)
            if n == 2:
                open_thr = 0.85
            else:
                open_thr = {0: 0.35, 1: 0.55, 2: 0.45, 3: 0.32, 4: 0.24, 5: 0.19}.get(k, 0.16)
            size = int(2.5 * bb)
            if foldy and not limpers and self.cur_hand >= 0 and all(self.P(state.players[s]).hands >= 4 for s in behind):
                open_thr = 1.0  # steal any two
                size = 2 * bb if n > 2 else int(2.5 * bb)
            elif "allin" in labels_behind:
                # shove-bot behind: only open what we'd happily get in with, min size
                open_thr = 0.16 if len(opps) <= 3 else 0.12
                size = 2 * bb
            elif sticky:
                open_thr = min(open_thr, 0.25)
                size = 4 * bb
            if limpers:
                limp_labels = [self.lbl(state, s) for s in limpers]
                if all(l in ("station", "unknown", "reg") for l in limp_labels):
                    open_thr = 0.3 if "station" in limp_labels else 0.22
                else:
                    open_thr *= 0.6
                size = int((4 + 1.5 * len(limpers)) * bb)
            if state.to_call == 0:
                if pct <= min(0.15, open_thr) and state.can_raise:
                    return ("raise", top_bet + size)
                return ("check", 0)
            if pct <= open_thr and state.can_raise:
                return ("raise", max(size, state.min_raise_to))
            if state.to_call <= bb // 2 + 0 and k == 1 and pct <= 0.7:
                return ("call", 0)  # SB complete vs one player
            if limpers and state.to_call <= bb and pct <= 0.45:
                return ("call", 0)
            return ("fold", 0)

        # ---- facing raises
        aggressor = raises[-1][1]
        alab = self.lbl(state, aggressor)
        to_call = state.to_call
        pot = state.pot
        # expected overcallers among sticky players still to act
        extra = 0.0
        seats_mc = []
        for s in opps:
            owe = top_bet - state.street_bets[s]
            if owe <= 0 or state.stacks[s] == 0:
                seats_mc.append(s)
                continue
            pc = 1.0 - self.P(state.players[s]).fold_to_raise()
            if s in behind:
                if pc >= 0.5:
                    seats_mc.append(s)
                    extra += pc * min(owe, state.stacks[s])
            else:
                seats_mc.append(s)
        if not seats_mc:
            seats_mc = [aggressor]
        e = self.equity(state, hole, [], seats_mc)
        need = to_call / float(pot + to_call + extra)
        shove_faced = to_call >= state.my_stack * 0.9 or raises[-1][3] >= 0.9 * self.stack0
        multi = len(seats_mc)
        fair = 1.0 / (multi + 1)

        # value re-raise
        if state.can_raise and not shove_faced:
            if alab in ("maniac", "allin"):
                if e >= max(0.5, fair + 0.18):
                    return ("raise", state.max_raise_to)  # get it in vs maniacs
            elif len(raises) == 1:
                if e >= max(0.58, fair + 0.22) or (pct <= 0.04):
                    ip = seat == state.button
                    amt = int(raises[-1][3] * (3.0 if ip else 3.5))
                    if amt >= my_total * 0.35:
                        return ("raise", state.max_raise_to)
                    return ("raise", amt)
                # light 3-bet vs foldy openers
                if (self.P(state.players[aggressor]).fold_to_raise() >= 0.65 and multi == 1
                        and pct <= 0.35 and self.rnd.random() < 0.35):
                    return ("raise", int(raises[-1][3] * 3.2))
            else:
                if e >= max(0.62, fair + 0.26):
                    return ("raise", state.max_raise_to)
        margin = 0.02 + 0.01 * len(behind)
        if alab == "rock":
            margin += 0.05
        if e >= need + margin:
            return ("call", 0)
        return ("fold", 0)

    def postflop(self, state, hole, board):
        seat = state.seat
        opps = self.opponents(state)
        nopp = len(opps)
        pot = state.pot
        to_call = state.to_call
        street = state.street
        river = street == "river"
        labels = [self.lbl(state, s) for s in opps]
        e = self.equity(state, hole, board, opps)
        rel = e * (nopp + 1)
        my_total = state.my_stack + state.street_bets[seat]
        stack = state.my_stack
        top_bet = max(state.street_bets)
        any_station = any(l in ("station", "allin") for l in labels)
        any_maniac = any(l == "maniac" for l in labels)
        all_foldy = all(
            l == "rock" or self.P(state.players[s]).fold_to_bet() >= 0.6 for s, l in zip(opps, labels)
        )
        cat = category(evaluate(hole + board))
        pf_raiser = None
        for h in state.history:
            if h[0] == "preflop" and h[2] == "raise":
                pf_raiser = h[1]
        r = self.rnd.random()

        def bet(frac):
            amt = int(pot * frac)
            if amt >= stack * 0.55:
                return ("raise", state.max_raise_to)
            return ("raise", max(amt, state.min_raise_to))

        if to_call == 0:
            if not state.can_raise:
                return ("check", 0)
            strong = rel >= (1.38 if river else 1.25)
            if strong:
                if any_maniac and not river and e < 0.9 and r < 0.6 and nopp == 1:
                    return ("check", 0)  # let the maniac bluff
                if any_station:
                    return bet(1.0 if e > 0.7 else 0.8)
                if all_foldy:
                    return bet(0.4)
                return bet(0.7 if rel >= 1.6 else 0.55)
            # thin value vs stations on river with a decent made hand
            if river and any_station and nopp == 1 and e >= 0.55:
                return bet(0.5)
            if any_station or any_maniac:
                return ("check", 0)  # no bluffs into callers
            if all_foldy and nopp <= 2:
                return bet(0.45)
            if pf_raiser == seat and street == "flop" and nopp <= 2 and r < (0.6 if nopp == 1 else 0.3):
                return bet(0.5)
            if nopp == 1 and street == "turn" and pf_raiser == seat and e > 0.35 and r < 0.4:
                return bet(0.55)
            return ("check", 0)

        # facing a bet
        need = to_call / float(pot + to_call)
        bettor = None
        for h in state.history:
            if h[0] == street and h[2] == "raise":
                bettor = h[1]
        blab = self.lbl(state, bettor) if bettor is not None else "unknown"
        adj = e
        if blab == "rock":
            adj *= 0.85
        elif blab in ("maniac", "allin"):
            adj = min(0.99, adj * 1.05)
        if not river and cat <= 1:
            # implied odds for draws when deep
            outs_bonus = self.draw_bonus(hole, board)
            if outs_bonus and stack > pot:
                adj += outs_bonus
        raise_thr = 1.6 if river else 1.5
        if adj * (nopp + 1) >= raise_thr and state.can_raise:
            if blab in ("maniac", "allin") and not river and stack > pot:
                return ("call", 0)  # keep them bluffing; raise later
            amt = int(top_bet * 3 + (pot - top_bet) * 0.2)
            if amt >= my_total * 0.45:
                return ("raise", state.max_raise_to)
            return ("raise", amt)
        margin = 0.01 * (nopp - 1) + (0.03 if river and blab not in ("maniac", "allin") else 0.0)
        if adj >= need + margin:
            return ("call", 0)
        # cheap bluff-catch vs maniacs
        if blab in ("maniac", "allin") and cat >= 1 and adj >= need - 0.04:
            return ("call", 0)
        return ("fold", 0)

    def draw_bonus(self, hole, board):
        cards = hole + board
        suits = [0, 0, 0, 0]
        mask = 0
        for c in cards:
            suits[c // 13] += 1
            mask |= 1 << (c % 13)
        bonus = 0.0
        if any(suits[c // 13] == 4 for c in hole):
            bonus += 0.06
        if STRAIGHT_HI[mask] < 0:
            outs = sum(1 for r in range(13) if not mask & (1 << r) and STRAIGHT_HI[mask | (1 << r)] >= 0)
            if outs >= 2:
                bonus += 0.04
            elif outs == 1:
                bonus += 0.015
        return bonus
