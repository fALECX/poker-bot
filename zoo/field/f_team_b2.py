"""Team "Exploit Engine" (b2).

Prompt used: "Our bot should learn how each opponent plays (track VPIP, PFR,
aggression by player id using the observer hooks) and exploit them: bluff the
tight ones, value bet the calling stations."
Follow-ups (3 iterations): "it folds too much before we have stats" (default
to a solid TAG baseline for the first ~12 hands), "bluffs get called by the
call/all-in bots" (only bluff opponents with low VPIP and high fold rate),
"value bet bigger vs stations".

Strategy: per-player-id counters (VPIP, PFR, postflop aggression, fold-to-bet)
from on_hand_start/on_action; a heuristic hand-strength score (Chen-like
preflop, made-hand category postflop) drives a tight-aggressive baseline.
Against tight/foldy opponents we bluff on checked-to spots; against loose
callers we value bet thinner and bigger and never bluff.
"""
from collections import defaultdict

from macpoker import Bot

RV = {r: i + 2 for i, r in enumerate("23456789TJQKA")}


class P:
    __slots__ = ("hands", "vpip", "pfr", "bets", "calls", "folds_to_bet", "faced_bet")

    def __init__(self):
        self.hands = 0
        self.vpip = 0
        self.pfr = 0
        self.bets = 0
        self.calls = 0
        self.folds_to_bet = 0
        self.faced_bet = 0


class ExploitBot(Bot):
    name = "ExploitEngine"

    def __init__(self):
        self.stats = defaultdict(P)
        self.me = None
        self.seen_vpip = set()
        self.seen_pfr = set()
        self.bet_open = False

    def on_match_start(self, info):
        self.me = info.get("player")

    def on_hand_start(self, info):
        self.seen_vpip = set()
        self.seen_pfr = set()
        self.bet_open = False
        for pid in info.get("players", []):
            self.stats[pid].hands += 1

    def on_action(self, event):
        try:
            who = event["players"][event["seat"]]
        except Exception:
            return
        st = self.stats[who]
        a = event.get("action")
        street = event.get("street")
        if street == "preflop":
            if a in ("call", "raise", "allin") and who not in self.seen_vpip:
                st.vpip += 1
                self.seen_vpip.add(who)
            if a in ("raise", "allin") and who not in self.seen_pfr:
                st.pfr += 1
                self.seen_pfr.add(who)
        else:
            if a in ("raise", "bet", "allin"):
                st.bets += 1
            elif a == "call":
                st.calls += 1
            if self.bet_open and a == "fold":
                st.folds_to_bet += 1
                st.faced_bet += 1
            elif self.bet_open and a == "call":
                st.faced_bet += 1
        if street != "preflop" and a in ("raise", "bet", "allin"):
            self.bet_open = True

    def on_street(self, event):
        self.bet_open = False

    # ---------- opponent reads ----------
    def read(self, pid):
        s = self.stats[pid]
        if s.hands < 12:
            return "unk"
        vpip = s.vpip / s.hands
        agg = s.bets / max(1, s.bets + s.calls)
        ftb = s.folds_to_bet / s.faced_bet if s.faced_bet >= 4 else 0.4
        if vpip > 0.55 and ftb < 0.3 and agg < 0.5:
            return "station"
        if vpip > 0.55 and agg >= 0.5:
            return "maniac"
        if vpip < 0.25 and ftb > 0.45:
            return "nit"
        return "reg"

    # ---------- hand strength ----------
    def pre_score(self, hole):
        a, b = sorted((RV[hole[0][0]], RV[hole[1][0]]), reverse=True)
        suited = hole[0][1] == hole[1][1]
        pts = {14: 10, 13: 8, 12: 7, 11: 6}.get(a, a / 2.0)
        if a == b:
            return max(5, pts * 2)
        if suited:
            pts += 2
        gap = a - b - 1
        pts -= {0: 0, 1: 1, 2: 2, 3: 4}.get(gap, 5)
        if gap <= 1 and a < 12:
            pts += 1
        return pts

    def post_strength(self, hole, board):
        """0..1 rough made-hand strength."""
        allc = hole + board
        cnt = defaultdict(int)
        suits = defaultdict(int)
        for c in allc:
            cnt[RV[c[0]]] += 1
            suits[c[1]] += 1
        hr = [RV[c[0]] for c in hole]
        br = [RV[c[0]] for c in board]
        mx = max(cnt.values())
        pairs = sum(1 for v in cnt.values() if v == 2)
        uniq = set(cnt)
        straight = any(all((lo + k) in uniq for k in range(5)) for lo in range(2, 11)) or all(
            x in uniq for x in (14, 2, 3, 4, 5))
        flush = max(suits.values()) >= 5
        if mx == 4 or (mx == 3 and pairs >= 1):
            return 0.97
        if flush or (straight and mx < 3):
            return 0.9
        if mx == 3:
            return 0.85 if any(cnt[r] == 3 for r in hr) else 0.7
        if pairs >= 2:
            return 0.75 if any(cnt[r] == 2 for r in hr) else 0.4
        if pairs == 1:
            pr = [r for r, v in cnt.items() if v == 2][0]
            if pr in hr:
                if pr >= max(br):
                    return 0.62 if hr[0] != hr[1] else 0.7
                return 0.4 if pr > min(br) else 0.3
            return 0.25
        draw = 0.15 if max(suits.values()) == 4 and len(board) < 5 else 0.0
        return 0.12 + draw + (0.05 if max(hr) > max(br) else 0.0)

    # ---------- action ----------
    def act(self, state):
        try:
            return self._act(state)
        except Exception:
            return state.check() if state.to_call == 0 else state.fold()

    def _raise(self, state, amt):
        if not state.can_raise:
            return state.call() if state.to_call > 0 else state.check()
        amt = int(max(state.min_raise_to, min(amt, state.max_raise_to)))
        if amt >= state.max_raise_to:
            return state.all_in()
        return state.raise_to(amt)

    def _act(self, state):
        me = state.seat
        opps = [state.players[i] for i in range(len(state.folded)) if not state.folded[i] and i != me]
        reads = [self.read(p) for p in opps]
        n = len(opps)
        call = state.to_call
        pot = state.pot
        stack = state.my_stack
        bb = 2
        station = "station" in reads
        nitty = "nit" in reads and not station and "maniac" not in reads
        maniac = "maniac" in reads

        if state.street == "preflop":
            sc = self.pre_score(state.hole)
            raised = call > bb
            if not raised:
                thr = 6 if station else 7
                if sc >= thr:
                    return self._raise(state, 3 * bb + bb * max(0, n - 3) if station else 3 * bb)
                if call == 0:
                    return state.check()
                return state.call() if sc >= 4 else state.fold()
            need = 9 if call > 8 else 7
            if maniac:
                need -= 1
            if sc >= 12:
                return self._raise(state, call * 3 + state.street_bets[me])
            if sc >= need and (call < stack * 0.4 or sc >= 10):
                return state.call()
            return state.fold()

        st = self.post_strength(state.hole, state.board)
        big = call > pot * 0.6
        if call == 0:
            if st >= 0.6:
                return self._raise(state, pot * (0.9 if station else 0.6))
            if st >= 0.4 and station:
                return self._raise(state, pot * 0.4)
            if nitty and n <= 2 and (state.hand + len(state.board)) % 3 != 0:
                return self._raise(state, pot * 0.6)  # bluff the tight ones
            return state.check()
        if st >= 0.85:
            return self._raise(state, call * 3 + pot)
        if st >= 0.55:
            return state.call()
        if st >= 0.38 and not big:
            return state.call()
        if maniac and st >= 0.25 and call < pot:
            return state.call()
        return state.fold()
