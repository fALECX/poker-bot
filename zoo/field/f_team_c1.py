"""
Team C1: Basic Poker Strategy

Prompts:
  1. "write me a poker bot that wins"
  2. "it loses to the all-in bot, fix it"

Iterations: 2

Strategy:
  Preflop: Play strong hands (pairs, broadway) in early position, looser in late position.
  Postflop: Call with draws/pairs, fold marginal holdings. Handles aggressive all-ins by
  calling more often with playable hands and being less afraid of aggressive bets.
"""

from macpoker import Bot, GameState, Action


class Team1Bot(Bot):
    name = "team-c1"

    def __init__(self):
        self.player_stats = {}

    def act(self, state: GameState) -> Action:
        # Preflop
        if state.street == "preflop":
            return self._act_preflop(state)

        # Postflop
        return self._act_postflop(state)

    def _act_preflop(self, state: GameState) -> Action:
        """Preflop strategy: position-based hand strength."""
        hole = state.hole
        pot_odds = self._pot_odds(state)

        # Get hand strength
        strength = self._hand_strength_preflop(hole, state)

        # Position relative to button
        my_pos = (state.seat - state.button) % state.num_players
        early_pos = my_pos in [1, 2]  # small blind, big blind area
        mid_pos = my_pos in [3, 4]
        late_pos = my_pos in [0, 5] if state.num_players >= 6 else my_pos == 0

        if state.to_call == 0:
            # We can check or raise
            if strength >= 6:
                return state.raise_to(min(state.max_raise_to, int(state.pot * 0.4)))
            return state.check()

        # Someone raised before us
        to_call = state.to_call

        # Premium hands: always call/raise
        if strength >= 7:
            if state.can_raise and state.my_stack > to_call * 2:
                return state.raise_to(min(state.max_raise_to, to_call * 2))
            return state.call()

        # Good hands: position-dependent
        if strength >= 5:
            if early_pos and to_call > state.pot * 0.2:
                return state.fold()
            if mid_pos and to_call > state.pot * 0.3:
                return state.fold()
            # Late position: more willing to call
            return state.call()

        # Medium hands: very position-dependent
        if strength >= 3:
            if late_pos:
                return state.call() if to_call <= state.pot * 0.2 else state.fold()
            return state.fold()

        # Weak hands: fold
        return state.fold()

    def _act_postflop(self, state: GameState) -> Action:
        """Postflop strategy: hand strength and draws."""
        hand_rank = self._hand_rank(state.hole, state.board)
        pot_odds = self._pot_odds(state)

        if state.to_call == 0:
            # Check or bet
            if hand_rank >= 4:  # Good hand
                return state.raise_to(min(state.max_raise_to, int(state.pot * 0.5)))
            return state.check()

        # Someone bet
        to_call = state.to_call

        # Pair or better: call/raise
        if hand_rank >= 3:
            if state.can_raise and hand_rank >= 5:
                return state.raise_to(min(state.max_raise_to, to_call * 2))
            return state.call()

        # Draw (2 overcards, gutshot, etc.): call if odds good
        if hand_rank == 2:
            if to_call <= state.pot * 0.3:
                return state.call()
            return state.fold()

        # No made hand, no draw: fold
        return state.fold()

    def _hand_strength_preflop(self, hole, state) -> int:
        """Rate hole cards preflop. Higher is better (1-8)."""
        h1, h2 = hole
        r1, r2 = h1[0], h2[0]

        ranks = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10,
                 '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}

        rv1, rv2 = ranks[r1], ranks[r2]
        suited = h1[1] == h2[1]

        # Pairs
        if rv1 == rv2:
            if rv1 >= 10:  # TT+: premium
                return 8
            if rv1 >= 7:   # 77-99: good
                return 6
            return 5  # 22-66: playable

        # High cards
        high = max(rv1, rv2)
        low = min(rv1, rv2)

        # Broadway cards (A, K, Q, J, T)
        if high >= 11 and low >= 10:
            if high == 14:  # AK, AQ
                return 8
            return 7  # KQ, KJ, QJ, etc.

        # Ace combinations
        if high == 14:
            if low >= 9:  # AJ, AT
                return 6
            if low >= 7:  # A9, A8, A7
                return 5
            if low >= 3:  # A6 down to A2
                return 3

        # Connectors and gappers
        if abs(rv1 - rv2) <= 2:
            if high >= 9:  # T9, J9, etc.
                return 5
            if high >= 7:  # 98, 87, etc.
                return 4

        # Default weak
        return 2

    def _hand_rank(self, hole, board) -> int:
        """Rate hole + board. Higher is better (0-6)."""
        # Simplified: just count pairs, trips, etc.
        # 0 = nothing
        # 1 = ace high / high card
        # 2 = draw (overcards / gutshot)
        # 3 = pair
        # 4 = two pair
        # 5 = trips / straight
        # 6 = flush / boat+

        all_cards = hole + board

        # Count rank frequencies
        rank_counts = {}
        for card in all_cards:
            r = card[0]
            rank_counts[r] = rank_counts.get(r, 0) + 1

        counts = sorted(rank_counts.values(), reverse=True)

        # Check for trips or boat
        if counts[0] >= 3:
            return 5 if counts[0] == 3 else 6

        # Check for pairs
        if len(counts) > 1 and counts[0] == 2 and counts[1] == 2:
            return 4  # Two pair

        if counts[0] == 2:
            return 3  # One pair

        # Check for draws (at least 2 high cards)
        ranks = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10,
                 '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}

        high_cards = sum(1 for r in rank_counts if ranks.get(r, 0) >= 10)
        if high_cards >= 2:
            return 2

        # Check for ace or face
        if 'A' in rank_counts or 'K' in rank_counts:
            return 1

        return 0

    def _pot_odds(self, state: GameState) -> float:
        """Return pot odds as a simple ratio."""
        if state.pot == 0:
            return 0
        return state.to_call / (state.pot + state.to_call)


bot = Team1Bot()
