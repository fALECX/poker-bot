# game-format-information

Source: https://docs.poker.monashcoding.com/game-format/information/

Opponents and information | macpoker docs- - - - - Skip to content
- Your table is fixed for a round: you play all of the round’s games
against the same opponents. Tables are redrawn between rounds.
- Opponents are anonymous but trackable. Your bot is never told names or
teams, but every opponent has a player id that stays fixed for the whole
game, and every message maps seats to player ids. Seats move every
hand, so use the player id to learn how each opponent plays. See
writing a bot.
- Each game runs your bot as a fresh process with a read-only filesystem,
so nothing carries over between games. Keep per-game state on self.
- Opponents’ hole cards are revealed only at showdown, where every player
still in the hand shows. Hands won by everyone else folding reveal
nothing.
- Your bot sees every public action as it happens. History from earlier
hands is yours to store from the observer hooks.
One hand, from your seat
You are bluffalo, player 0, in the big blind this hand.
‹›
What your bot receives
Folded hands are never shown. At showdown, every player still in the hand reveals their cards, and that is the only way you learn what an opponent held.
The full message reference is in the wire protocol. The SDK
turns these messages into state and the observer hooks, so most bots
never read them directly.
