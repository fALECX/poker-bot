# writing-a-bot

Source: https://docs.poker.monashcoding.com/writing-a-bot/

Writing a bot | macpoker docs- - - - - Skip to content
Your submission is a zip with a main.py at its root. main.py defines
exactly one Bot subclass (or a module-level bot = MyBot() instance).
You may split code into other modules in the zip and import them from
main.py.
- main.pyfrom macpoker import Bot
class MyBot(Bot):
def act(self, state):
...
return state.call()
The decision method
Section titled “The decision method”
act(state) is called every time it is your turn. It must return an action
before your clock runs out.
Actions
Section titled “Actions”
Return
Meaning
state.check()
Pass the action. Only legal when state.to_call == 0.
state.call()
Match the current bet (state.to_call chips).
state.fold()
Give up the hand.
state.raise_to(n)
Raise so your total bet this street becomes n.
state.all_in()
Raise to state.max_raise_to.
Illegal actions are coerced to the nearest legal action rather than
punished: an impossible raise becomes a call, checking a bet folds, and
out-of-range raise amounts are clamped. Rely on the fields below instead of
the coercion.
GameState reference
Section titled “GameState reference”
Your cards and the table
Section titled “Your cards and the table”
Field
Type
Meaning
state.hole
list[str]
Your two cards, e.g. ["As", "Td"]. Ranks 2..9 T J Q K A, suits s h d c.
state.board
list[str]
Community cards dealt so far (0, 3, 4 or 5).
state.street
str
"preflop", "flop", "turn" or "river".
state.hand
int
Hand number within the game.
state.seat
int
Your seat index this hand.
state.button
int
Seat of the dealer button.
Chips
Section titled “Chips”
Field
Type
Meaning
state.pot
int
All chips committed to the pot so far.
state.to_call
int
Chips you must add to stay in. 0 means you may check.
state.min_raise_to
int
Smallest legal raise-to total.
state.max_raise_to
int
Raise-to total that puts you all in.
state.can_raise
bool
Whether raising is legal for you right now.
state.stacks
list[int]
Remaining chips per seat.
state.street_bets
list[int]
Chips each seat has bet on this street.
state.my_stack
int
Shorthand for state.stacks[state.seat].
Everyone else
Section titled “Everyone else”
Field
Type
Meaning
state.players
list[int]
Player id in each seat this hand. Ids stay fixed for the whole game.
state.player
int
Your own player id.
state.player_at(seat)
int
Player id sitting in seat.
state.seat_of(player)
int
Seat a player is in this hand.
state.folded
list[bool]
Which seats have folded this hand.
state.num_players
int
Seats at the table.
state.players_in_hand
int
Seats not folded.
state.history
list
Every action this hand: [street, seat, kind, amount].
state.clock_ms
int
Milliseconds left on your clock.
There is no equity calculator and no pot-odds helper. Working out the maths
is your job; that is the tournament.
Observing the game
Section titled “Observing the game”
Beyond act, you may override optional hooks. All are silent no-ops by
default:
class MyBot(Bot):
def on_match_start(self, info): ... # game config, blinds, clocks
def on_hand_start(self, info): ... # your seat and hole cards
def on_action(self, event): ... # every action by every seat
def on_street(self, event): ... # board reveals
def on_hand_end(self, info): ... # results, revealed cards, pots
def on_match_end(self, info): ... # final chip totals
Every event also carries players (seat to player id), so you can key what
you learn by player id. Seats move every hand, but player ids stay fixed
for the whole game:
from collections import defaultdict
class MyBot(Bot):
def __init__(self):
self.raises = defaultdict(int)
def on_action(self, event):
who = event["players"][event["seat"]]
if event["action"] == "raise":
self.raises[who] += 1
Keep state between hands on self. Each game runs your bot as one process,
so self persists for the whole game and resets between games.
Printing
Section titled “Printing”
print() is safe: stdout is redirected to the game log, which you can read
in the app when a validation game finishes. Do not try to write to the
protocol stream yourself.
