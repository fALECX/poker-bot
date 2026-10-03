"""Per-opponent statistics from public events only, keyed by player id.

The tracker replays the betting of every hand from the observer events, so
it knows for each action whether the actor faced a bet and how large it was.
All updates are O(1) per event. Estimates are shrunk toward population
priors: est = (hits + prior * k) / (opportunities + k).
"""

from __future__ import annotations

SIZE_BUCKETS = (0.45, 0.85)  # bet / pot-before-bet: small | medium | large
STREETS = ("preflop", "flop", "turn", "river")


def size_bucket(frac: float) -> int:
    if frac < SIZE_BUCKETS[0]:
        return 0
    if frac < SIZE_BUCKETS[1]:
        return 1
    return 2


class Counter:
    __slots__ = ("hits", "opps")

    def __init__(self):
        self.hits = 0
        self.opps = 0

    def add(self, hit: bool) -> None:
        self.opps += 1
        if hit:
            self.hits += 1

    def est(self, prior: float, k: float) -> float:
        return (self.hits + prior * k) / (self.opps + k)


class PlayerStats:
    def __init__(self):
        self.hands = 0
        self.vpip = Counter()
        self.pfr = Counter()
        self.open = Counter()  # raised when first in
        self.limp = Counter()  # limped when first in
        self.threebet = Counter()  # re-raised facing exactly one raise
        self.fold_to_3bet = Counter()
        self.pf_allin = Counter()  # preflop raises that were all-in, per hand
        self.pf_fold_vs_raise = Counter()
        self.cbet = Counter()
        # postflop, aggregated over flop/turn/river
        self.bet_when_checked = Counter()  # bet/raise when to_call == 0
        self.fold_vs_bet = [Counter(), Counter(), Counter()]  # by size bucket
        self.raise_vs_bet = Counter()
        self.allin_any = 0
        self.actions = 0
        self.aggressive_actions = 0
        self.passive_streak = 0  # consecutive decisions that were only check/fold
        self.facing_folds_in_streak = 0
        self.showdowns = 0
        self.showdown_hands: list[tuple[list[str], int, str]] = []  # (cards, max bet frac, street)
        self.net = 0


class Tracker:
    def __init__(self):
        self.stats: dict[int, PlayerStats] = {}
        self.sb, self.bb = 1, 2
        self._reset_hand([])

    def get(self, pid: int) -> PlayerStats:
        st = self.stats.get(pid)
        if st is None:
            st = self.stats[pid] = PlayerStats()
        return st

    # ---- hand replay state -------------------------------------------
    def _reset_hand(self, players) -> None:
        self.players = list(players)
        n = len(players)
        self.street = "preflop"
        self.street_bet = [0] * n
        self.stacks = [0] * n
        self.current_bet = 0
        self.pot = 0
        self.pf_raises = 0
        self.pf_raiser = None
        self.street_first_bet_done = False
        self.vpip_flag = set()
        self.pfr_flag = set()
        self.allin_flag = set()
        self.max_frac: dict[int, float] = {}
        self.cbet_pending = False

    def on_hand_start(self, msg: dict) -> None:
        players = msg.get("players") or []
        self._reset_hand(players)
        n = len(players)
        self.stacks = list(msg.get("stacks") or [0] * n)
        for pid in players:
            self.get(pid).hands += 1
        if n < 2:
            return
        # The SDK has no hook for the blinds message, so post them here the
        # same way the engine does.
        button = msg.get("button", 0) or 0
        if n == 2:
            sb_seat, bb_seat = button, (button + 1) % n
        else:
            sb_seat, bb_seat = (button + 1) % n, (button + 2) % n
        for seat, amt in ((sb_seat, self.sb), (bb_seat, self.bb)):
            paid = min(amt, self.stacks[seat])
            self.street_bet[seat] += paid
            self.stacks[seat] -= paid
            self.pot += paid
        self.current_bet = max(self.street_bet)

    def set_blinds(self, sb: int, bb: int) -> None:
        self.sb, self.bb = sb, bb

    def on_street(self, msg: dict) -> None:
        if self.street == "preflop":
            self.cbet_pending = self.pf_raiser is not None
        else:
            self.cbet_pending = False
        self.street = msg.get("street", self.street)
        self.street_bet = [0] * len(self.street_bet)
        self.current_bet = 0
        self.street_first_bet_done = False

    def on_action(self, msg: dict) -> None:
        seat = msg.get("seat")
        if seat is None or seat >= len(self.players):
            return
        pid = self.players[seat]
        st = self.get(pid)
        kind = msg.get("action")
        amount = msg.get("amount", 0) or 0
        street = msg.get("street", self.street)
        to_call = max(0, self.current_bet - self.street_bet[seat])
        pot_before_bet = max(self.pot - (self.current_bet - self.street_bet[seat]) if to_call else self.pot, 1)
        frac = to_call / pot_before_bet if to_call else 0.0

        if kind == "raise":
            added = amount - self.street_bet[seat]
        elif kind == "call":
            added = amount
        else:
            added = 0
        added = max(0, min(added, self.stacks[seat]))

        st.actions += 1
        aggressive = kind == "raise"
        voluntary = kind in ("raise", "call")
        if aggressive:
            st.aggressive_actions += 1
        if voluntary:
            st.passive_streak = 0
            st.facing_folds_in_streak = 0
        else:
            st.passive_streak += 1
            if kind == "fold" and to_call > 0:
                st.facing_folds_in_streak += 1

        if street == "preflop":
            first_in = self.pf_raises == 0
            if voluntary and pid not in self.vpip_flag:
                self.vpip_flag.add(pid)
            if aggressive and pid not in self.pfr_flag:
                self.pfr_flag.add(pid)
            if first_in and kind != "check":
                st.open.add(aggressive)
                st.limp.add(kind == "call")
            elif self.pf_raises == 1 and kind != "check":
                st.threebet.add(aggressive)
                if kind != "raise":
                    st.pf_fold_vs_raise.add(kind == "fold")
            elif self.pf_raises >= 2 and self.pf_raiser == pid:
                st.fold_to_3bet.add(kind == "fold")
            if aggressive:
                self.pf_raises += 1
                self.pf_raiser = pid
        else:
            if to_call == 0:
                st.bet_when_checked.add(aggressive)
                if self.cbet_pending and street == "flop" and pid == self.pf_raiser and not self.street_first_bet_done:
                    st.cbet.add(aggressive)
            else:
                st.fold_vs_bet[size_bucket(frac)].add(kind == "fold")
                st.raise_vs_bet.add(aggressive)
            if aggressive:
                self.street_first_bet_done = True
                bet_frac = added / max(self.pot, 1)
                if bet_frac > self.max_frac.get(pid, 0.0):
                    self.max_frac[pid] = bet_frac

        self.street_bet[seat] += added
        self.stacks[seat] -= added
        self.pot += added
        if self.street_bet[seat] > self.current_bet:
            self.current_bet = self.street_bet[seat]
        if aggressive and self.stacks[seat] == 0 and pid not in self.allin_flag:
            self.allin_flag.add(pid)
            st.allin_any += 1

    def on_hand_end(self, msg: dict) -> None:
        players = msg.get("players") or self.players
        deltas = msg.get("deltas") or []
        for seat, d in enumerate(deltas):
            if seat < len(players):
                self.get(players[seat]).net += d
        for pid in players:
            st = self.get(pid)
            st.vpip.add(pid in self.vpip_flag)
            st.pfr.add(pid in self.pfr_flag)
            st.pf_allin.add(pid in self.allin_flag and pid in self.pfr_flag)
        revealed = msg.get("revealed") or {}
        for seat_s, cards in revealed.items():
            try:
                seat = int(seat_s)
                pid = players[seat]
            except (ValueError, IndexError, TypeError):
                continue
            st = self.get(pid)
            st.showdowns += 1
            if len(st.showdown_hands) < 40:
                st.showdown_hands.append((list(cards), round(self.max_frac.get(pid, 0.0), 2), self.street))
