# PokerBot project guidance

## Project purpose

This project builds one autonomous no-limit Texas hold'em bot for the MAC Poker
Bot Hackathon. The authoritative references are the captured documentation in
[`knowledge-base/poker-docs`](knowledge-base/poker-docs/README.md) and the
provided [`scaffold`](scaffold/README.md). The live documentation is
https://docs.poker.monashcoding.com/.

## Notes language

Write all new project notes, research notes, strategy evaluations, and similar
working documentation in English. Existing notes do not need to be translated
unless they are being substantially revised.

## Current project layout

- [`scaffold/`](scaffold/) is the unpacked starter template. Its `main.py` is
  the intended submission entry point.
- [`knowledge-base/poker-docs/`](knowledge-base/poker-docs/) contains the
  crawled HTML and Markdown documentation.
- [`knowledge-base/source-html/`](knowledge-base/source-html/) contains the
  supplied local HTML export and its assets.
- [`knowledge-base/opening-slides.txt`](knowledge-base/opening-slides.txt)
  contains text extracted from the supplied opening slides.
- `macpoker-scaffold.zip` is the original scaffold archive. Do not submit the
  archive itself; submit a new ZIP with `main.py` at its root.

## Non-negotiable submission requirements

- Use Python 3.10+ locally; production runs Python 3.12.
- The ZIP must contain `main.py` at its root.
- Define exactly one `macpoker.Bot` subclass, or expose one module-level
  `bot = MyBot()` instance.
- Additional Python modules are allowed only when imported from `main.py`.
- The unpacked submission must be at most 20 MB and contain at most 300 files.
- Runtime dependencies are limited to the Python standard library, `numpy`, and
  the `macpoker` SDK. Do not add packages, vendored dependencies, GPU code, or
  assumptions about local files.
- The tournament sandbox has one CPU core, 512 MB memory, read-only storage,
  and a 64 MB `/tmp` that is wiped after each game.
- There is no network access. Do not use HTTP, sockets, external APIs,
  subprocesses, background threads, scheduled work, or AI/LLM calls at runtime.
- A small, self-developed neural network with bundled weights is allowed at
  runtime; a complete LLM or external AI service is not. Keep inference
  deterministic and bounded. See
  [`knowledge-base/neural-network-feasibility.md`](knowledge-base/neural-network-feasibility.md).
- All bot computation must happen during the bot's own turn (`act()` and the
  supported observer hooks). Do not compute while opponents are acting.
- Submissions are manually reviewed. Cheating, collusion, hidden-information
  recovery, shared-resource exhaustion, or interference with other bots means
  removal and disqualification.

## Bot API and correctness

Implement `act(self, state)` and return one SDK action:

- `state.check()` only when `state.to_call == 0`
- `state.call()`
- `state.fold()`
- `state.raise_to(amount)` using raise-to total semantics, not an increment
- `state.all_in()`

Use the state fields rather than relying on illegal-action coercion:
`hole`, `board`, `street`, `hand`, `seat`, `button`, `pot`, `to_call`,
`min_raise_to`, `max_raise_to`, `can_raise`, `stacks`, `street_bets`,
`my_stack`, `folded`, `players`, `player`, `history`, and `clock_ms`.

Seats change every hand. Player IDs remain stable within a game, so any
opponent statistics must be keyed by player ID, not seat. State stored on
`self` persists for one game and is reset when the engine starts a new game.
Do not assume an opponent's hole cards or future deck order is visible.

Optional observers (`on_match_start`, `on_hand_start`, `on_action`,
`on_street`, `on_hand_end`, and `on_match_end`) are useful for bounded
bookkeeping, but they are not a way to run work outside the allowed turn
computation.

Keep stdout/protocol behavior SDK-managed. Use normal `print()` only for
diagnostics that the SDK redirects to the game log; never write raw JSON to
the protocol stream.

## Tournament ramifications

- Games are fixed at 100 hands, with fresh 200-chip stacks each hand, 1/2
  blinds, no antes, and no elimination. Optimize cumulative chip outcome,
  not survival across hands.
- A round uses duplicate deals: the same hands are replayed from every seat,
  so decisions rather than card luck determine the comparison. The button
  rotates each hand.
- Tables usually contain about five bots. Each bot plays one game per seat.
- Four Swiss-style rounds use game points and placement points. Ties share
  points; groups regroup by cumulative placement points. Final standings sum
  four rounds, with head-to-head games breaking prize ties.
- Every game gives the bot a 30-second time bank plus 0.1 seconds per hand.
  `state.clock_ms` is the remaining budget. A timeout (`TLE`), crash (`RTE`),
  or protocol violation (`PV`) causes check-folding for the rest of the game.
  Prefer predictable bounded algorithms and avoid expensive per-action work.

## Development and validation workflow

From the bot folder, install the SDK in a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install https://poker.monashcoding.com/dl/macpoker-0.1.0-py3-none-any.whl
```

Run house-bot tests and production-parity subprocess tests:

```powershell
macpoker play main.py house:call house:random --deals 50
macpoker play main.py house:call --deals 100 --subprocess --history out.json
```

Use `--seed` while iterating so a decision change can be compared on the same
cards. Test every legal action path, short-stack and all-in situations,
preflop/flop/turn/river, changing seats, and low-clock behavior. Before
submission, inspect the ZIP contents and verify `main.py` is at the archive
root, imports only allowed dependencies, and stays within the size/file caps.
Upload it at https://poker.monashcoding.com/app and select a passing upload as
the main entry before the deadline.

## Implementation priorities

1. Preserve protocol and legal-action correctness.
2. Guarantee bounded runtime and graceful behavior under low clock.
3. Build deterministic, testable decision logic before adding strategy.
4. Track opponent information only from events legitimately exposed by the SDK.
5. Keep the final submission minimal, auditable, and free of development-only
   files, secrets, network code, and hidden side channels.
