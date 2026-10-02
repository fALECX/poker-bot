# protocol

Source: https://docs.poker.monashcoding.com/protocol/

Wire protocol | macpoker docs- - - - - Skip to content
You normally never touch this: the SDK’s runner speaks it for you. It is
documented for the curious and for anyone testing with --subprocess.
A bot is a process. The engine writes newline-delimited JSON messages to
your stdin; you write exactly one JSON line to stdout whenever you receive
an act message, and nothing otherwise. Your print() output goes to
stderr, which the SDK arranges automatically.
Messages you receive
Section titled “Messages you receive”
- {"type": "hello", "player": 2, "num_players": 5, "num_hands": 100,
"stack": 200, "blinds": [1, 2],
"time_bank_ms": 30000, "increment_ms": 100}
{"type": "hand_start", "hand": 17, "seat": 2, "button": 0,
"stacks": [200, 200, 200, 200, 200], "hole": ["As", "Kd"],
"players": [0, 1, 2, 3, 4]}
{"type": "blinds", "sb_seat": 1, "bb_seat": 2, "sb": 1, "bb": 2}
{"type": "action", "hand": 17, "street": "preflop", "seat": 3,
"action": "raise", "amount": 6, "pot": 9}
{"type": "street", "hand": 17, "street": "flop",
"board": ["7h", "2d", "Qc"]}
{"type": "act", "hand": 17, "seat": 2, "street": "flop",
"board": ["7h", "2d", "Qc"], "hole": ["As", "Kd"],
"pot": 12, "to_call": 4, "min_raise_to": 8, "max_raise_to": 198,
"can_raise": true, "stacks": [194, 198, 196, 190, 200],
"street_bets": [0, 0, 0, 4, 0], "folded": [false, false, false, false, true],
"button": 0, "history": [["preflop", 3, "raise", 6]], "clock_ms": 29140,
"players": [0, 1, 2, 3, 4]}
{"type": "hand_end", "hand": 17, "board": ["7h", "2d", "Qc", "3s", "5s"],
"deltas": [12, -2, -4, -6, 0],
"revealed": {"0": ["As", "Kd"], "3": ["Qh", "Jh"]},
"pots": [{"amount": 24, "winners": [0]}]}
{"type": "match_end", "chips": [140, -80, -20, -40, 0],
"verdicts": ["OK", "OK", "OK", "OK", "OK"]}
The message you send
Section titled “The message you send”
Only ever in response to act, one line:
{"action": "fold"}
{"action": "check"}
{"action": "call"}
{"action": "raise", "amount": 14}
{"action": "allin"}
amount uses raise-to semantics: the total your bet for this street
becomes, not the increment.
Hands, seats and player ids
Section titled “Hands, seats and player ids”
Seat indices are per hand. The button is always seat 0 and the bots move
one seat every hand, so your seat changes from hand to hand; hand_start
tells you where you are sitting.
Player ids are per game. Every bot at the table gets a player id from 0
to num_players - 1 that never changes during the game. hello tells you
your own id as player, and every later message except match_end
carries players, a list mapping seat to player id for the current hand.
To find who made an action, look up players[seat]. match_end chips and
verdicts are listed by player id. Card strings are rank then suit:
2 3 4 5 6 7 8 9 T J Q K A and s h d c.
