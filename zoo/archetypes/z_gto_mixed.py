"""A4 'GTO-inspired' bot: mixed frequencies, MDF defence, polarized bluffs, some 3bet bluffs and traps.

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'call_mode': 'mdf', 'bluff_freq': 0.15, 'semibluff_freq': 0.6, 'cbet_freq': 0.65, 'threebet_bluff_freq': 0.15, 'barrel_freq': 0.35, 'slowplay_freq': 0.12, 'value_t': 0.75, 'open_size_jitter': 0.3}

bot = RuleBot(PARAMS, name="z_gto_mixed")
