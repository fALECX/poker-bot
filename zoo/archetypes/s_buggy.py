"""Special: A2 logic with the classic raise_to-as-increment bug (engine clamps its raises).

Zoo opponent (dev only). Parameters on top of zcore.rulebot.DEFAULTS.
"""

from zcore.rulebot import RuleBot

PARAMS = {'bug_raise_increment': True, 'strength': 'mc_random', 'allin_mode': 'eq_random', 'value_t': 0.62, 'size_mode': 'proportional', 'looseness': 1.3, 'limp_pct': 0.1}

bot = RuleBot(PARAMS, name="s_buggy")
