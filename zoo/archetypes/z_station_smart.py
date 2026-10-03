"""A8 Calling station with logic: calls any pair or draw down, raises only near-nuts, limps a lot.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'call_mode': 'station', 'value_t': 0.88, 'raise_t': 0.97, 'cbet_freq': 0.2, 'call_open_pct': 0.35, 'bb_defend_pct': 0.7, 'overlimp_pct': 0.5, 'limp_pct': 0.3, 'allin_mode': 'eq_random', 'allin_margin': -0.02, 'semibluff_freq': 0.0}

bot = RuleBot(PARAMS, name="z_station_smart")
