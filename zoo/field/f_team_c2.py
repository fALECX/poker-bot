"""
Team C2: Hand Scoring System with Thresholds

Prompts:
  1. "make a poker bot with a scoring system: give each starting hand a score
     (like the Chen formula), and after the flop score the made hand and draws,
     then decide fold/call/raise by thresholds; bluff sometimes at random"

Iterations: 1 (improved post-flop hand evaluation with multi-street betting logic)

Strategy:
  Preflop: Score hands 0-20 using hand strength heuristics. Thresholds depend on position.
  Postflop: Score made hands and draws separately, apply dynamic thresholds based on pot
  odds and position. Include position-aware bluffing with random element.
"""

import random
from macpoker import Bot, GameState, Action


class Team2Bot(Bot):
    name = "team-c2"

    def __init__(self):
        self.rng = random.Random()
        self.position_stats = {}

    def act(self, state: GameState) -> Action:
        if state.street == "preflop":
            return self._act_preflop(state)
        else:
            return self._act_postflop(state)

    def _act_preflop(self, state: GameState) -> Action:
        """Preflop: score hand and apply position-based thresholds."""
        hole = state.hole
        score = self._score_preflop(hole)

        # Position relative to button
        pos = (state.seat - state.button) % state.num_players

        if state.to_call == 0:
            # Blind or free flop option
            if score >= 12:
                raise_amount = min(state.max_raise_to, int(state.pot * 0.35))
                return state.raise_to(raise_amount)
            return state.check()

        # Someone raised before us
        # Determine action threshold based on position
        if pos in [1, 2]:  # Early position
            call_threshold = 11
            raise_threshold = 14
        elif pos in [3, 4]:  # Mid position
            call_threshold = 9
            raise_threshold = 13
        else:  # Late position / button
            call_threshold = 7
            raise_threshold = 11

        if score >= raise_threshold and state.can_raise:
            return state.raise_to(min(state.max_raise_to, state.to_call * 2))
        elif score >= call_threshold:
            return state.call()
        else:
            return state.fold()

    def _act_postflop(self, state: GameState) -> Action:
        """Postflop: score made hands and draws, apply dynamic thresholds."""
        made_score, draw_score = self._score_postflop(state.hole, state.board)
        combined_score = made_score * 2 + draw_score  # Weight made hands more

        pot_odds = state.to_call / (state.pot + state.to_call) if (state.pot + state.to_call) > 0 else 0

        # Street adjusts aggressiveness
        street_factor = {'flop': 1.0, 'turn': 0.85, 'river': 0.9}[state.street]
        adjusted_score = combined_score * street_factor

        if state.to_call == 0:
            # We can check or bet
            if made_score >= 6:
                # Strong hand: bet
                bet_amount = min(state.max_raise_to, int(state.pot * 0.4))
                return state.raise_to(bet_amount)
            elif made_score >= 3 or draw_score >= 4:
                # Medium strength: semi-bluff sometimes
                if self.rng.random() < 0.25 and state.can_raise:
                    bet_amount = min(state.max_raise_to, int(state.pot * 0.25))
                    return state.raise_to(bet_amount)
                return state.check()
            else:
                return state.check()

        # Someone bet before us
        to_call = state.to_call
        pot_contribution = to_call / (state.pot + to_call) if (state.pot + to_call) > 0 else 0

        # Strong made hand: call or raise
        if made_score >= 6:
            if state.can_raise and adjusted_score >= 12:
                return state.raise_to(min(state.max_raise_to, to_call * 2))
            return state.call()

        # Medium made hand: position and odds dependent
        if made_score >= 4:
            if pot_contribution <= 0.4:
                return state.call()
            elif state.can_raise:
                return state.raise_to(min(state.max_raise_to, to_call * 1.5))
            else:
                return state.fold()

        # Pair
        if made_score >= 3:
            if pot_contribution <= 0.3:
                return state.call()
            return state.fold()

        # Draw: call if odds allow
        if draw_score >= 4:
            if to_call <= state.pot * 0.25:
                return state.call()
            # Random bluff call occasionally
            elif self.rng.random() < 0.15:
                return state.call()
            else:
                return state.fold()

        # Weak: fold unless random bluff
        if self.rng.random() < 0.05 and to_call <= state.pot * 0.1:
            return state.call()  # Random bluff

        return state.fold()

    def _score_preflop(self, hole) -> float:
        """Score preflop hand 0-20."""
        h1, h2 = hole
        r1, r2 = h1[0], h2[0]

        ranks = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10,
                 '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}

        rv1, rv2 = ranks[r1], ranks[r2]
        suited = h1[1] == h2[1]

        high = max(rv1, rv2)
        low = min(rv1, rv2)

        score = 0

        # Pair bonus
        if rv1 == rv2:
            score += 10 + (high - 2) * 0.5
            if high >= 10:
                score += 3
            return min(20, score)

        # High card scoring
        score += high * 0.8
        score += low * 0.5

        # Suited bonus
        if suited:
            score += 2

        # Connector / gapper bonus
        gap = abs(rv1 - rv2)
        if gap <= 1:
            score += 1.5
        elif gap <= 3:
            score += 0.5

        return min(20, score)

    def _score_postflop(self, hole, board) -> tuple:
        """Return (made_hand_score, draw_score)."""
        all_cards = hole + board

        # Count ranks
        rank_counts = {}
        for card in all_cards:
            r = card[0]
            rank_counts[r] = rank_counts.get(r, 0) + 1

        # Count suits
        suit_counts = {}
        for card in all_cards:
            s = card[1]
            suit_counts[s] = suit_counts.get(s, 0) + 1

        counts = sorted(rank_counts.values(), reverse=True)

        made_score = 0
        draw_score = 0

        # Trips or boat
        if counts[0] >= 3:
            made_score = 8 if counts[0] == 3 else 9
            return (made_score, draw_score)

        # Two pair
        if len(counts) > 1 and counts[0] == 2 and counts[1] == 2:
            made_score = 7
            return (made_score, draw_score)

        # Pair
        if counts[0] == 2:
            made_score = 4

        # Draws
        # Flush draw (4 same suit)
        if max(suit_counts.values()) == 4:
            draw_score += 5

        # Straight possibilities (very simplified)
        ranks_vals = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, 'T': 10,
                      '9': 9, '8': 8, '7': 7, '6': 6, '5': 5, '4': 4, '3': 3, '2': 2}

        rank_list = sorted([ranks_vals[r] for r in rank_counts.keys()], reverse=True)

        # Overcards (with hole cards)
        h1_val = ranks_vals[hole[0][0]]
        h2_val = ranks_vals[hole[1][0]]

        if h1_val >= 12 and h2_val >= 12:  # Overcards
            if made_score == 0:
                draw_score += 3
        elif max(h1_val, h2_val) >= 12:
            if made_score == 0:
                draw_score += 1

        # Open-ended straight draw or gutshot
        if len(board) >= 3:
            if draw_score < 4:  # Only if no flush draw yet
                draw_score += 2

        return (made_score, draw_score)


bot = Team2Bot()
