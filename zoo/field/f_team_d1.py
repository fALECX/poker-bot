"""
Team D1 - "Range Rovers" (range-based equity team)

Approach: position charts preflop, Monte Carlo equity against opponent
ranges postflop. Each opponent's range starts from a Chen-score percentile
cut taken from their per-player-id VPIP/PFR/3-bet/shove stats, then gets
re-weighted street by street by what they did on that board.

Iterations (about 2 days):
  v1  Chen chart preflop, raw equity against random hands, pot odds only.
  v2  Fast bitmask 7-card evaluator, so MC is about 4x faster; clock-aware
      sample budget.
  v3  Per-player-id stats (VPIP/PFR/3bet/shove/fold-to-bet/aggression) to
      set preflop ranges.
  v4  Postflop action-weighted ranges (bet/raise/call acceptance by hand
      class), implied odds for draws, texture-aware bet sizing.
  v5  Tuning against house bots and older versions: tighter river value,
      c-bet frequency tied to fold-to-bet, shove-or-fold for short SPR.

Strategy:
  1. Preflop: open ranges set by position (players left to act). When
     facing raises, MC equity against the raisers' estimated ranges is
     compared with the pot odds to choose 3-bet, call or fold.
  2. Postflop: MC equity against weighted opponent ranges, compared with
     the pot odds plus implied odds for draws. Bets and raises for value
     scale with equity relative to the field size.
  3. Sizing is 1/2 to 3/4 pot (bigger on wet boards and against stations).
     Selective c-bets and semi-bluffs. Sample counts scale with the
     remaining clock, with a cheap fallback when the clock is low.
"""

import random
import time
from bisect import bisect_right

from macpoker import Bot

# ---------------------------------------------------------------------------
# Cards and evaluator. A card is rank*4 + suit, with rank 0 = deuce and
# 12 = ace.
# ---------------------------------------------------------------------------
_RANKS = "23456789TJQKA"
_SUITS = "cdhs"


def _card(s):
    return _RANKS.index(s[0].upper()) * 4 + _SUITS.index(s[1].lower())


_POP = [bin(m).count("1") for m in range(8192)]
_STRT = [0] * 8192
_SMASKS = []
for _top in range(12, 2, -1):
    _mk = 0
    for _r in range(_top - 4, _top + 1):
        _mk |= 1 << (12 if _r < 0 else _r)
    _SMASKS.append((_top, _mk))
for _m in range(8192):
    if _POP[_m] >= 5:
        for _top, _mk in _SMASKS:
            if _m & _mk == _mk:
                _STRT[_m] = _top + 1
                break


def ev(cards):
    """Evaluate 5-7 cards. Returns an int; higher is better. Category in bits 20+."""
    sm = [0, 0, 0, 0]
    cnt = [0] * 13
    for c in cards:
        r = c >> 2
        sm[c & 3] |= 1 << r
        cnt[r] += 1
    for m in sm:
        if _POP[m] >= 5:
            t = _STRT[m]
            if t:
                return (8 << 20) | t
            v = 0
            k = 0
            r = 12
            while k < 5:
                if (m >> r) & 1:
                    v = (v << 4) | r
                    k += 1
                r -= 1
            return (5 << 20) | v
    quads = trips = -1
    trips2 = -1
    pairs = []
    sing = []
    for r in range(12, -1, -1):
        n = cnt[r]
        if n == 0:
            continue
        if n == 1:
            sing.append(r)
        elif n == 2:
            pairs.append(r)
        elif n == 3:
            if trips < 0:
                trips = r
            elif trips2 < 0:
                trips2 = r
        else:
            quads = r
    if quads >= 0:
        k = -1
        for x in (trips, pairs[0] if pairs else -1, sing[0] if sing else -1):
            if x > k:
                k = x
        return (7 << 20) | (quads << 4) | max(k, 0)
    if trips >= 0 and (trips2 >= 0 or pairs):
        p = max(trips2, pairs[0] if pairs else -1)
        return (6 << 20) | (trips << 4) | p
    allm = sm[0] | sm[1] | sm[2] | sm[3]
    t = _STRT[allm]
    if t:
        return (4 << 20) | t
    if trips >= 0:
        v = (3 << 20) | (trips << 8)
        if len(sing) > 0:
            v |= sing[0] << 4
        if len(sing) > 1:
            v |= sing[1]
        return v
    if len(pairs) >= 2:
        k = sing[0] if sing else -1
        if len(pairs) > 2 and pairs[2] > k:
            k = pairs[2]
        return (2 << 20) | (pairs[0] << 8) | (pairs[1] << 4) | max(k, 0)
    if pairs:
        v = (1 << 20) | (pairs[0] << 12)
        sh = 8
        for x in sing[:3]:
            v |= x << sh
            sh -= 4
        return v
    v = 0
    for x in sing[:5]:
        v = (v << 4) | x
    return v


# ---------------------------------------------------------------------------
# Preflop percentile table (Chen formula), percentile 0 = best.
# ---------------------------------------------------------------------------
def _chen(r1, r2, suited):
    hi, lo = max(r1, r2), min(r1, r2)
    base = {12: 10.0, 11: 8.0, 10: 7.0, 9: 6.0}.get(hi, (hi + 2) / 2.0)
    if hi == lo:
        return max(5.0, base * 2) + hi * 0.01
    s = base
    if suited:
        s += 2
    gap = hi - lo - 1
    s -= (0, 1, 2, 4)[gap] if gap < 4 else 5
    if gap <= 1 and hi < 10:
        s += 1
    return s + hi * 0.01 + lo * 0.001


ALLCOMBOS = []  # (a, b) with a < b
_cls_score = {}
for _a in range(52):
    for _b in range(_a + 1, 52):
        ALLCOMBOS.append((_a, _b))
_scored = []
for _i, (_a, _b) in enumerate(ALLCOMBOS):
    _scored.append((_chen(_a >> 2, _b >> 2, (_a & 3) == (_b & 3)), _i))
_scored.sort(reverse=True)
COMBO_PCT = [0.0] * len(ALLCOMBOS)
_i = 0
_N = float(len(_scored))
while _i < len(_scored):
    _j = _i
    while _j < len(_scored) and _scored[_j][0] == _scored[_i][0]:
        _j += 1
    _p = (_i + _j) / 2.0 / _N
    for _k in range(_i, _j):
        COMBO_PCT[_scored[_k][1]] = _p
    _i = _j
COMBO_INDEX = {c: i for i, c in enumerate(ALLCOMBOS)}


def hand_pct(a, b):
    if a > b:
        a, b = b, a
    return COMBO_PCT[COMBO_INDEX[(a, b)]]


# ---------------------------------------------------------------------------
# Opponent statistics, keyed by player id.
# ---------------------------------------------------------------------------
class PStats:
    __slots__ = ("hands", "vpip", "pfr", "tb_opp", "tb", "shove", "pf_faced", "pf_fold",
                 "pa", "pp", "faced", "ftb")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.tb_opp = 0
        self.tb = 0
        self.shove = 0
        self.pf_faced = 0
        self.pf_fold = 0
        self.pa = 0  # postflop aggressive actions
        self.pp = 0  # postflop passive actions (check/call)
        self.faced = 0  # postflop: faced a bet
        self.ftb = 0  # postflop: folded to a bet

    @staticmethod
    def _b(k, n, prior, w):
        return (k + prior * w) / (n + w)

    def vpip_r(self):
        return self._b(self.vpip, self.hands, 0.35, 8)

    def pfr_r(self):
        return self._b(self.pfr, self.hands, 0.15, 8)

    def tb_r(self):
        return self._b(self.tb, self.tb_opp, 0.07, 6)

    def shove_r(self):
        return self._b(self.shove, self.hands, 0.04, 6)

    def ftb_r(self):
        return self._b(self.ftb, self.faced, 0.45, 6)

    def pf_fold_r(self):
        return self._b(self.pf_fold, self.pf_faced, 0.6, 6)

    def aggr_r(self):
        return self._b(self.pa, self.pa + self.pp, 0.3, 8)


STREET_IDX = {"preflop": 0, "flop": 1, "turn": 2, "river": 3}
BOARD_LEN = (0, 3, 4, 5)


class RangeEquityBot(Bot):
    name = "range_rovers"

    def __init__(self):
        self.rng = random.Random(0xD1)
        self.stats = {}
        self.num_hands = 100
        self.start_stack = 200
        self.bb = 2
        self._reset_hand(-1)

    # ------------------------------------------------------------------
    # bookkeeping
    # ------------------------------------------------------------------
    def _reset_hand(self, hand):
        self.h_no = hand
        self.h_players = []
        self.h_stacks = []
        self.h_bets = []
        self.h_street = "preflop"
        self.h_flags = {}
        self.h_pf_raises = 0
        self.h_board = []
        self.h_pf_raiser = None
        self.cache_pf = {}
        self.cache_cls = {}
        self.cache_rng = {}

    def _st(self, pid):
        s = self.stats.get(pid)
        if s is None:
            s = PStats()
            self.stats[pid] = s
        return s

    def on_match_start(self, info):
        try:
            self.num_hands = int(info.get("num_hands", 100))
            self.start_stack = int(info.get("stack", 200))
            bl = info.get("blinds", [1, 2])
            self.bb = int(bl[1])
        except Exception:
            pass

    def on_hand_start(self, info):
        try:
            self._reset_hand(info.get("hand", -1))
            self.h_players = list(info.get("players", []))
            n = len(self.h_players)
            self.h_stacks = list(info.get("stacks", [self.start_stack] * n))
            self.h_bets = [0] * n
            btn = info.get("button", 0)
            if n == 2:
                sb, bbs = btn, (btn + 1) % n
            else:
                sb, bbs = (btn + 1) % n, (btn + 2) % n
            if n >= 2:
                self.h_bets[sb] = min(1, self.h_stacks[sb])
                self.h_bets[bbs] = min(self.bb, self.h_stacks[bbs])
            for pid in self.h_players:
                self.h_flags[pid] = {"vpip": False, "pfr": False}
        except Exception:
            pass

    def on_street(self, event):
        try:
            self.h_street = event.get("street", self.h_street)
            self.h_board = [_card(c) for c in event.get("board", [])]
            self.h_bets = [0] * len(self.h_bets)
        except Exception:
            pass

    def on_action(self, event):
        try:
            seat = event["seat"]
            players = event.get("players", self.h_players)
            pid = players[seat]
            kind = event.get("action")
            amt = int(event.get("amount", 0) or 0)
            street = event.get("street", "preflop")
            st = self._st(pid)
            bets = self.h_bets
            if not bets or seat >= len(bets):
                return
            cur = max(bets)
            facing = cur > bets[seat]
            if street == "preflop":
                fl = self.h_flags.setdefault(pid, {"vpip": False, "pfr": False})
                if self.h_pf_raises >= 1:
                    if not fl.get("tbo"):
                        fl["tbo"] = True
                        st.tb_opp += 1
                if facing and self.h_pf_raises >= 1:
                    st.pf_faced += 1
                    if kind == "fold":
                        st.pf_fold += 1
                if kind in ("call", "raise"):
                    fl["vpip"] = True
                if kind == "raise":
                    fl["pfr"] = True
                    if self.h_pf_raises >= 1:
                        st.tb += 1
                    self.h_pf_raises += 1
                    self.h_pf_raiser = pid
                    total = self.h_stacks[seat] if seat < len(self.h_stacks) else self.start_stack
                    if amt >= total * 0.9:
                        st.shove += 1
            else:
                if facing:
                    st.faced += 1
                    if kind == "fold":
                        st.ftb += 1
                if kind == "raise":
                    st.pa += 1
                elif kind in ("call", "check"):
                    st.pp += 1
            if kind == "raise":
                bets[seat] = amt
            elif kind == "call":
                bets[seat] = max(bets[seat] + amt, cur) if amt else cur
        except Exception:
            pass

    def on_hand_end(self, info):
        try:
            for pid, fl in self.h_flags.items():
                st = self._st(pid)
                st.hands += 1
                if fl.get("vpip"):
                    st.vpip += 1
                if fl.get("pfr"):
                    st.pfr += 1
        except Exception:
            pass

    # ------------------------------------------------------------------
    # action entry point
    # ------------------------------------------------------------------
    def act(self, state):
        try:
            a = self._decide(state)
            return self._legal(state, a)
        except Exception:
            try:
                if state.to_call == 0:
                    return state.check()
                if state.to_call <= 2:
                    return state.call()
                return state.fold()
            except Exception:
                return state.fold()

    def _legal(self, state, a):
        kind, amt = a
        to_call = state.to_call
        if kind == "raise":
            if not state.can_raise:
                kind = "call"
            else:
                lo, hi = state.min_raise_to, state.max_raise_to
                amt = int(amt)
                if amt >= hi * 0.92 or amt >= hi:
                    return state.raise_to(hi)
                amt = max(lo, min(hi, amt))
                return state.raise_to(amt)
        if kind == "call":
            return state.call() if to_call > 0 else state.check()
        if kind == "check":
            return state.check() if to_call == 0 else state.fold()
        return state.check() if to_call == 0 else state.fold()

    # ------------------------------------------------------------------
    def _budget(self, state):
        clock = state.clock_ms
        left = max(1, self.num_hands - state.hand)
        avail = clock - 2500
        if avail <= 0:
            return 0.0
        per = avail / (left * 2.6)
        return max(0.004, min(0.14, per / 1000.0))

    def _decide(self, state):
        if state.hand != self.h_no:
            # missed hand_start (should not happen); keep going safely
            self.h_no = state.hand
        self.hole = [_card(c) for c in state.hole]
        self.board = [_card(c) for c in state.board]
        self.seat = state.seat
        self.n = state.num_players
        self.players = state.players
        self.budget = self._budget(state)
        if state.street == "preflop":
            return self._preflop(state)
        return self._postflop(state)

    # ------------------------------------------------------------------
    # ranges
    # ------------------------------------------------------------------
    def _pf_profile(self, state, seat):
        """Return (fraction, top_discount) describing seat's preflop range."""
        pid = state.players[seat]
        st = self._st(pid)
        acts = [h for h in state.history if h[0] == "preflop"]
        nr = 0
        best = None  # 'shove', '3bet', 'open', 'call', None
        start = self.start_stack
        for h in acts:
            if h[2] == "raise":
                nr += 1
                if h[1] == seat:
                    if h[3] >= start * 0.9:
                        best = "shove"
                    elif nr >= 2:
                        if best != "shove":
                            best = "3bet"
                    elif best is None or best == "call":
                        best = "open"
            elif h[2] == "call" and h[1] == seat and best is None:
                best = "call"
        if best == "shove":
            f = max(st.shove_r() * 1.2, 0.05)
            if nr >= 2:
                f = min(f, max(0.05, st.tb_r()))
            return min(1.0, f), 1.0
        if best == "3bet":
            return max(0.03, min(0.5, st.tb_r() * 1.1)), 1.0
        if best == "open":
            return max(0.05, min(0.85, st.pfr_r() * 1.1)), 1.0
        if best == "call":
            return max(0.12, min(1.0, st.vpip_r())), 0.45
        return 1.0, 1.0

    def _pf_range(self, state, seat):
        f, disc = self._pf_profile(state, seat)
        key = (seat, round(f, 3), disc)
        r = self.cache_pf.get(key)
        if r is not None:
            return r
        pfr = self._st(state.players[seat]).pfr_r()
        dead = set(self.hole) | set(self.board)
        idx = []
        w = []
        tail = 0.08
        for i, (a, b) in enumerate(ALLCOMBOS):
            if a in dead or b in dead:
                continue
            p = COMBO_PCT[i]
            if p <= f:
                x = 1.0
            elif p < f + tail:
                x = 1.0 - (p - f) / tail
            else:
                continue
            if disc < 1.0 and p < pfr * 0.6:
                x *= disc
            idx.append(i)
            w.append(x)
        if not idx:
            idx = [i for i, (a, b) in enumerate(ALLCOMBOS) if a not in dead and b not in dead]
            w = [1.0] * len(idx)
        r = (idx, w)
        self.cache_pf[key] = r
        return r

    def _classify(self, ci, board):
        """Hand class of combo index on board: 5 nuts-ish, 4 two pair+, 3 top pair,
        2 weaker pair, 1.5 strong draw, 1 weak draw/overs, 0 air."""
        key = (ci, len(board))
        v = self.cache_cls.get(key)
        if v is not None:
            return v
        a, b = ALLCOMBOS[ci]
        cards = [a, b] + board
        val = ev(cards)
        cat = val >> 20
        bc = [0] * 13
        for c in board:
            bc[c >> 2] += 1
        bpairs = sum(1 for x in bc if x >= 2)
        btrips = any(x >= 3 for x in bc)
        bcat = 3 if btrips else (2 if bpairs >= 2 else (1 if bpairs == 1 else 0))
        btop = max(c >> 2 for c in board)
        res = 0.0
        if cat >= 4 or (cat >= 2 and cat > bcat and cat != 2) or (cat == 3 and bcat < 3):
            res = 5.0 if cat >= 3 else 4.0
        elif cat == 2 and bcat < 2:
            res = 4.0
        elif cat >= 1 and cat > bcat:
            pr = (val >> 12) & 15
            ra, rb = a >> 2, b >> 2
            if pr >= btop and (ra == pr or rb == pr):
                res = 3.0
            elif ra == pr or rb == pr:
                res = 2.0
        if res < 2.0 and len(board) < 5:
            # draws
            sc = [0, 0, 0, 0]
            for c in cards:
                sc[c & 3] += 1
            fd = (sc[a & 3] >= 4) or (sc[b & 3] >= 4)
            m = 0
            for c in cards:
                m |= 1 << (c >> 2)
            outs = 0
            for r in range(13):
                if not (m >> r) & 1 and _STRT[m | (1 << r)]:
                    outs += 1
            if fd or outs >= 2:
                res = max(res, 1.5)
            elif outs == 1 or ((a >> 2) > btop and (b >> 2) > btop):
                res = max(res, 1.0)
        self.cache_cls[key] = res
        return res

    def _accept(self, cls, summary, st):
        bluff = 0.08 + 0.55 * max(0.0, st.aggr_r() - 0.2)
        if summary == "raise":
            table = {5.0: 1.0, 4.0: 0.85, 3.0: 0.45, 2.0: 0.15, 1.5: 0.35, 1.0: 0.1, 0.0: bluff * 0.6}
        elif summary == "bet":
            table = {5.0: 1.0, 4.0: 1.0, 3.0: 0.85, 2.0: 0.45, 1.5: 0.6, 1.0: 0.25, 0.0: bluff}
        elif summary == "call":
            loose = max(0.0, 0.55 - st.ftb_r())
            table = {5.0: 0.8, 4.0: 0.95, 3.0: 1.0, 2.0: 0.75, 1.5: 0.8, 1.0: 0.35 + loose,
                     0.0: 0.08 + loose}
        else:  # check
            table = {5.0: 0.6, 4.0: 0.75, 3.0: 0.9, 2.0: 1.0, 1.5: 1.0, 1.0: 1.0, 0.0: 1.0}
        return table.get(cls, 0.5)

    def _street_summary(self, state, seat, street):
        s = None
        for h in state.history:
            if h[0] != street or h[1] != seat:
                continue
            k = h[2]
            if k == "raise":
                # bet if first aggression on street, else raise
                s = "raise" if self._was_bet_before(state, street, h) else ("bet" if s != "raise" else s)
            elif k == "call" and s not in ("raise", "bet"):
                s = "call"
            elif k == "check" and s is None:
                s = "check"
        return s

    @staticmethod
    def _was_bet_before(state, street, target):
        for h in state.history:
            if h is target:
                return False
            if h[0] == street and h[2] == "raise":
                return True
        return False

    def _range(self, state, seat):
        idx, w0 = self._pf_range(state, seat)
        si = STREET_IDX.get(state.street, 0)
        if si == 0:
            return self._finish_range(idx, w0)
        st = self._st(state.players[seat])
        sums = []
        for s in range(1, si + 1):
            sname = ("preflop", "flop", "turn", "river")[s]
            sums.append(self._street_summary(state, seat, sname))
        key = (seat, id(w0), tuple(sums))
        r = self.cache_rng.get(key)
        if r is not None:
            return r
        w = list(w0)
        full = self.board
        for s, summ in enumerate(sums, start=1):
            if summ is None:
                continue
            bd = full[:BOARD_LEN[s]]
            if len(bd) < 3:
                continue
            for j, ci in enumerate(idx):
                if w[j] <= 0.0:
                    continue
                w[j] *= self._accept(self._classify(ci, bd), summ, st)
        r = self._finish_range(idx, w)
        self.cache_rng[key] = r
        return r

    @staticmethod
    def _finish_range(idx, w):
        combos = []
        cum = []
        tot = 0.0
        for i, x in zip(idx, w):
            if x > 1e-4:
                tot += x
                combos.append(ALLCOMBOS[i])
                cum.append(tot)
        return combos, cum, tot

    # ------------------------------------------------------------------
    # Monte Carlo equity
    # ------------------------------------------------------------------
    def _equity(self, ranges, budget, max_iter=2500):
        hole = self.hole
        board = self.board
        need = 5 - len(board)
        dead = set(hole) | set(board)
        deck = [c for c in range(52) if c not in dead]
        rng = self.rng
        rnd = rng.random
        nopp = len(ranges)
        t_end = time.perf_counter() + budget
        wins = 0.0
        n = 0
        draw_n = need + 2 * nopp
        while n < max_iter:
            if (n & 15) == 0 and n >= 48 and time.perf_counter() > t_end:
                break
            used = set()
            opp = []
            for combos, cum, tot in ranges:
                got = None
                if combos:
                    for _ in range(6):
                        i = bisect_right(cum, rnd() * tot)
                        if i >= len(combos):
                            i = len(combos) - 1
                        a, b = combos[i]
                        if a not in used and b not in used:
                            got = (a, b)
                            break
                if got is None:
                    while True:
                        a, b = rng.sample(deck, 2)
                        if a not in used and b not in used:
                            got = (a, b)
                            break
                used.add(got[0])
                used.add(got[1])
                opp.append(got)
            if need:
                extra = []
                for c in rng.sample(deck, draw_n):
                    if c not in used:
                        extra.append(c)
                        if len(extra) == need:
                            break
                fb = board + extra
            else:
                fb = board
            mine = ev(hole + fb)
            best = -1
            ties = 0
            for a, b in opp:
                v = ev([a, b] + fb)
                if v > best:
                    best = v
                    ties = 1
                elif v == best:
                    ties += 1
            if mine > best:
                wins += 1.0
            elif mine == best:
                wins += 1.0 / (ties + 1)
            n += 1
        if n == 0:
            return None
        return wins / n

    def _quick_equity(self, nopp):
        """Cheap fallback when the clock is low."""
        if not self.board:
            p = hand_pct(self.hole[0], self.hole[1])
            e = 0.85 - 0.55 * p
        else:
            v = ev(self.hole + self.board)
            cat = v >> 20
            e = (0.3, 0.55, 0.72, 0.8, 0.85, 0.88, 0.93, 0.97, 0.99)[cat]
        return max(0.02, min(0.98, e ** max(1, nopp)))

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _opps(self, state):
        return [s for s in range(self.n) if s != self.seat and not state.folded[s]]

    def _pf_order(self, state):
        n = self.n
        b = state.button
        opener = b if n == 2 else (b + 3) % n
        return [(opener + i) % n for i in range(n)]

    def _eff_stack(self, state, opps):
        me = state.my_stack + state.street_bets[self.seat]
        best = 0
        for s in opps:
            best = max(best, state.stacks[s] + state.street_bets[s])
        return min(me, best)

    def _my_draw(self):
        cards = self.hole + self.board
        sc = [0, 0, 0, 0]
        for c in cards:
            sc[c & 3] += 1
        fd = any(sc[c & 3] >= 4 for c in self.hole)
        m = 0
        for c in cards:
            m |= 1 << (c >> 2)
        outs = 0
        if not _STRT[m]:
            for r in range(13):
                if not (m >> r) & 1 and _STRT[m | (1 << r)]:
                    outs += 4
        return (9 if fd else 0) + min(outs, 8)

    # ------------------------------------------------------------------
    # preflop
    # ------------------------------------------------------------------
    def _preflop(self, state):
        bb = self.bb
        n = self.n
        seat = self.seat
        to_call = state.to_call
        pot = state.pot
        pct = hand_pct(self.hole[0], self.hole[1])
        hist = [h for h in state.history if h[0] == "preflop"]
        raises = [h for h in hist if h[2] == "raise"]
        nr = len(raises)
        order = self._pf_order(state)
        my_i = order.index(seat)
        behind = [s for s in order[my_i + 1:] if not state.folded[s]]
        acted = set(h[1] for h in hist)
        behind_unacted = [s for s in behind if s not in acted]
        opps = self._opps(state)
        cur = max(state.street_bets)
        mystreet = state.street_bets[seat]
        stack_total = state.my_stack + mystreet

        if nr == 0:
            limpers = sum(1 for h in hist if h[2] == "call")
            k = len(behind_unacted)
            if n == 2:
                thr = 0.80
            else:
                thr = {0: 0.30, 1: 0.48, 2: 0.42, 3: 0.30, 4: 0.22, 5: 0.17}.get(k, 0.14)
            # moderate stat adjustment: fold-prone players behind -> open wider
            if behind_unacted:
                ff = sum(self._st(state.players[s]).pf_fold_r() for s in behind_unacted) / len(behind_unacted)
                vp = sum(self._st(state.players[s]).vpip_r() for s in behind_unacted) / len(behind_unacted)
                thr += 0.25 * (ff - 0.6)
                if vp > 0.6:
                    thr -= 0.05
            thr = max(0.08, min(0.9, thr))
            if limpers:
                thr *= 0.65
            if to_call == 0:
                # big blind option
                if pct < max(0.12, thr * 0.5) and state.can_raise:
                    return ("raise", cur + bb * (3 + limpers))
                return ("check", 0)
            if pct < thr and state.can_raise:
                size = int(bb * (2.5 if n > 2 else 2.5) + bb * limpers)
                if k == 1 and n > 2:
                    size = 3 * bb
                if pct < 0.03 and limpers == 0:
                    size += bb // 2
                return ("raise", max(size, state.min_raise_to))
            # limp / complete
            if to_call <= bb:
                if (limpers and pct < thr * 1.5 + 0.05) or (k == 1 and n > 2 and pct < 0.65):
                    return ("call", 0)
            return ("fold", 0)

        # facing a raise: equity vs ranges. Players still to act who rarely
        # fold to raises are counted as likely overcallers (money + range).
        live_opps = []
        extra = 0.0
        for s in opps:
            need = cur - state.street_bets[s]
            if need <= 0 or state.stacks[s] == 0:
                live_opps.append(s)
                continue
            p_call = 1.0 - self._st(state.players[s]).pf_fold_r()
            if p_call >= 0.5:
                live_opps.append(s)
                extra += p_call * min(need, state.stacks[s])
            elif s not in behind:
                live_opps.append(s)
        if not live_opps:
            live_opps = opps
        ranges = [self._range(state, s) for s in live_opps]
        e = None
        if self.budget > 0:
            e = self._equity(ranges, self.budget * 0.8, max_iter=900)
        if e is None:
            e = self._quick_equity(len(live_opps))
        req = to_call / float(pot + to_call + extra)
        opps = live_opps
        eff = self._eff_stack(state, opps)
        deep = eff - cur > 10 * to_call
        r1, r2 = self.hole[0] >> 2, self.hole[1] >> 2
        speculative = (r1 == r2) or ((self.hole[0] & 3) == (self.hole[1] & 3) and abs(r1 - r2) <= 2)
        if deep and speculative and len(opps) >= 1:
            req *= 0.85
        margin = 0.02 + 0.015 * len(behind_unacted)
        # out of position penalty
        if n > 2 and (seat - state.button) % n in (1, 2):
            margin += 0.02
        last_raise = raises[-1][3]
        allin_pressure = to_call >= state.my_stack
        fair = 1.0 / (len(opps) + 1)

        if state.can_raise and not allin_pressure:
            if nr == 1:
                tb_thr = max(0.56, fair + 0.2) if len(opps) > 1 else 0.57
                if e >= tb_thr:
                    ip = n == 2 and seat == state.button or (n > 2 and (seat - state.button) % n == 0)
                    size = int(last_raise * (3.0 if ip else 3.6)) + 2 * bb * max(0, len(opps) - 1)
                    if size >= stack_total * 0.38:
                        return ("raise", state.max_raise_to)
                    return ("raise", size)
            else:
                if e >= max(0.6, fair + 0.25):
                    size = int(last_raise * 2.3)
                    if size >= stack_total * 0.38:
                        return ("raise", state.max_raise_to)
                    return ("raise", size)
        if e >= req + margin:
            return ("call", 0)
        return ("fold", 0)

    # ------------------------------------------------------------------
    # postflop
    # ------------------------------------------------------------------
    def _postflop(self, state):
        seat = self.seat
        to_call = state.to_call
        pot = state.pot
        opps = self._opps(state)
        nopp = len(opps)
        street = state.street
        river = street == "river"
        cur = max(state.street_bets)
        if self.budget > 0:
            ranges = [self._range(state, s) for s in opps]
            e = self._equity(ranges, self.budget)
            if e is None:
                e = self._quick_equity(nopp)
        else:
            e = self._quick_equity(nopp)
        rel = e * (nopp + 1)
        eff = self._eff_stack(state, opps)
        my_left = state.my_stack
        draw = self._my_draw() if not river else 0
        ost = [self._st(state.players[s]) for s in opps]
        avg_ftb = sum(s.ftb_r() for s in ost) / max(1, len(ost))
        station = avg_ftb < 0.25
        pf_aggr = self._i_was_pf_aggressor(state)
        wet = self._wet()
        rnd = self.rng.random()

        if to_call == 0:
            val_thr = 1.42 if river else 1.3
            if rel >= val_thr and state.can_raise:
                frac = 0.55
                if rel >= 1.7 or (wet and not river):
                    frac = 0.75
                if station:
                    frac += 0.25
                bet = int(pot * frac)
                if bet >= my_left * 0.6 or pot >= eff * 0.9:
                    return ("raise", state.max_raise_to)
                return ("raise", max(bet, state.min_raise_to))
            if state.can_raise and not station:
                # c-bet as preflop aggressor
                if street == "flop" and pf_aggr and nopp <= 2:
                    p = (0.65 if nopp == 1 else 0.35) * (avg_ftb / 0.45)
                    if not wet:
                        p += 0.1
                    if rnd < p:
                        return ("raise", max(int(pot * 0.5), state.min_raise_to))
                # semi-bluff draws
                if draw >= 8 and nopp <= 2 and rnd < 0.5:
                    return ("raise", max(int(pot * 0.6), state.min_raise_to))
                # probe when everyone checked to us heads-up on turn/river with some showdown value
                if nopp == 1 and street != "flop" and rnd < 0.25 * (avg_ftb / 0.45) and e < 0.35:
                    if self._checked_to_me(state):
                        return ("raise", max(int(pot * 0.5), state.min_raise_to))
            return ("check", 0)

        # facing a bet
        req = to_call / float(pot + to_call)
        e_eff = e
        if draw >= 8 and not river:
            implied = min(0.12, 0.03 * (eff - cur) / max(1.0, pot))
            e_eff = e + max(0.0, implied)
        raise_thr = 1.62 if river else 1.52
        if rel >= raise_thr and state.can_raise:
            size = int(cur * 2.8 + (pot - cur) * 0.3)
            if size >= (my_left + state.street_bets[seat]) * 0.45:
                return ("raise", state.max_raise_to)
            return ("raise", size)
        if (draw >= 12 and street == "flop" and nopp == 1 and state.can_raise
                and not station and rnd < 0.3 and to_call < my_left * 0.25):
            size = int(cur * 3)
            if size >= (my_left + state.street_bets[seat]) * 0.45:
                return ("raise", state.max_raise_to)
            return ("raise", size)
        margin = 0.015 * max(0, nopp - 1)
        if river:
            margin += 0.02
        if e_eff >= req + margin:
            return ("call", 0)
        return ("fold", 0)

    def _i_was_pf_aggressor(self, state):
        last = None
        for h in state.history:
            if h[0] == "preflop" and h[2] == "raise":
                last = h[1]
        return last == self.seat

    def _checked_to_me(self, state):
        for h in state.history:
            if h[0] == state.street and h[2] != "check":
                return False
        return True

    def _wet(self):
        b = self.board
        sc = [0, 0, 0, 0]
        for c in b:
            sc[c & 3] += 1
        if max(sc) >= 2 and len(b) <= 4:
            return True
        rs = sorted(set(c >> 2 for c in b))
        for i in range(len(rs) - 1):
            if rs[i + 1] - rs[i] <= 2:
                return True
        return False
