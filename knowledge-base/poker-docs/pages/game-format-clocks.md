# game-format-clocks

Source: https://docs.poker.monashcoding.com/game-format/clocks/

Clocks and verdicts | macpoker docs- - - - - Skip to content
Each bot has a chess-style clock: a 30-second time bank per game plus
0.1 seconds added every hand. There is no fixed per-move limit. The clock
runs while the engine waits on your act().
Your clock over one game
30 s to start, 0.1 s added every hand, 100 hands.
Average thinking per hand
Thinking for 0.1 s a hand or less never shrinks the bank. Anything above that spends it down, and a bot that reaches zero gets a TLE verdict and check-folds the rest of the game.
Verdicts
Section titled “Verdicts”
Verdict
Meaning
OK
Played the whole game.
TLE
Ran out of clock.
RTE
Crashed, or the process died.
PV
Broke the wire protocol.
A bot that earns TLE, RTE or PV is check-folded for the remainder of
the game. Games always finish and always produce a result.
Your bot computes only on its own turn: see the rules.
state.clock_ms tells you how much time is left at every decision.
