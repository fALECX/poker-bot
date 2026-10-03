"""Every tunable constant of the strategy, in one place.

Values are defaults; local tuning tools overwrite this dict and the bot only
ever reads from P.
"""

P = {
    # --- preflop: open shares (top x% of HAND_ORDER) by players left to act behind us
    "open_pct_by_behind": {1: 0.40, 2: 0.42, 3: 0.27, 4: 0.20, 5: 0.15, 6: 0.13, 7: 0.12, 8: 0.11},
    "open_pct_heads_up": 0.70,
    "open_size_bb": 2.5,
    "open_mult": 1.3,
    "open_size_sb_bb": 3.0,
    "limper_add_bb": 1.0,
    "iso_pct": 0.12,
    "bb_raise_vs_limp_pct": 0.10,
    # facing one raise
    "threebet_value_pct": 0.040,
    "threebet_value_pct_late": 0.055,
    "call_open_pct_ip": 0.08,
    "call_open_pct_oop": 0.05,
    "bb_defend_pct": {2.5: 0.30, 3.0: 0.24, 4.0: 0.16, 6.0: 0.09},
    "threebet_mult_ip": 3.0,
    "threebet_mult_oop": 3.6,
    # facing 3bet / 4bet
    "fourbet_pct": 0.026,
    "call_3bet_pct": 0.065,
    "call_3bet_max_stack_share": 0.22,
    "jam_vs_4bet_pct": 0.022,
    # facing all-in / huge preflop bets
    "default_shove_range": {1: 0.20, 2: 0.07, 3: 0.04},  # by number of raises incl. the shove
    "allin_call_margin": 0.02,
    "big_bet_stack_share": 0.40,
    # --- postflop fallback
    "value_hs": 0.82,
    "thin_value_hs_hu": 0.66,
    "cbet_freq_hu": 0.55,
    "cbet_size": 0.40,
    "value_size": 0.66,
    "semibluff_freq": 0.45,
    "raise_hs": 0.93,
    "call_margin": 0.04,
    "big_bet_discount": 0.9,
    # --- opponent model (priors are population estimates, refined from sims)
    "shrink_k": 15.0,
    "prior_open": 0.24,
    "prior_3bet": 0.05,
    "prior_4bet_range": 0.035,
    "prior_vpip": 0.28,
    "prior_bet_when_checked": 0.36,
    "prior_fold_vs_bet": [0.26, 0.33, 0.55],  # by size bucket small / medium / large
    "prior_raise_vs_bet": 0.09,
    "call_3bet_range": 0.08,
    "bb_check_exclude": 0.12,
    # --- range narrowing
    "draw_floor": 0.60,
    "draw_floor_strong": 0.72,
    "narrow_width": 0.09,
    "bet_center_base": 0.45,
    "bet_center_slope": 0.20,
    "bluff_floor_small": 0.15,
    "bluff_floor_big": 0.08,
    "call_center_base": 0.25,
    "call_center_slope": 0.15,
    "check_trim": 0.50,
    # --- postflop EV engine
    "bet_sizes": [0.33, 0.5, 0.75, 1.0, 1.5],
    "realize_ip": 0.95,
    "realize_oop": 0.85,
    "mix_eps_pot": 0.02,
    "min_samples": 150,
    "fold_to_raise_prior": 0.45,
    "allin_max_pot_ratio": 3.0,
    # --- risk / endgame (rank-based scoring)
    "risk_lambda": 0.0,
    "endgame_hands": 0,
    "endgame_protect_lambda": 0.4,
    "endgame_gamble_lambda": -0.3,
}
