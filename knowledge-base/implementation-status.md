# Implementation status

Working notes for the tournament bot, the opponent zoo and the evaluation
tools. Plan: `~/.claude/plans/enchanted-cuddling-gem.md`.

## Layout

| Path | Purpose |
|---|---|
| `scaffold/main.py` | Submission entry point (one `Bot` subclass, delegates to `pokerbot.agent.Agent`). |
| `scaffold/pokerbot/` | Bot package (relative imports only). `params.py` holds every tunable constant. |
| `scaffold/pokerbot/core/` | Cards, 7-card evaluator (~2 µs/eval, checked against the engine), preflop equity tables, ranges, equity simulation, legalizer, clock budget. |
| `scaffold/pokerbot/model/` | Opponent tracker (per player id, shrunk to population priors), live standings, opponent range model. |
| `scaffold/pokerbot/strategy/` | Preflop chart + preflop EV, postflop one-step EV engine, extreme-opponent exploits, endgame risk, zero-simulation fallback. |
| `zoo/field/` | Eight "field replica" bots written by isolated AI agents playing typical teams (beginner to strong). |
| `zoo/archetypes/` | Tier A archetypes (parametric `zcore.rulebot`) and special bots (crash at hand K, raise-semantics bug). |
| `testing/arena.py` | Parallel, paired, points-based A/B evaluation against a sampled pool. |
| `testing/tournament.py` | 4-round Swiss tournament simulator. |
| `tools/` | Table generator, snapshot tool, zip builder/auditor, diagnostics, population stats, archetype tuner. |
| `tests/` | Evaluator oracle, legality fuzzer (ours + zoo), crafted edge cases. |

## Commands

```bash
.venv/Scripts/python.exe -m unittest tests.test_core tests.test_legality tests.test_edge tests.test_zoo
.venv/Scripts/python.exe tools/snapshot.py v3                       # freeze current bot
.venv/Scripts/python.exe -m testing.arena --cand snapshots/v3/main.py --cand snapshots/v2/main.py \
    --pool zoo/field --pool zoo/archetypes --tables 96 --seed X
.venv/Scripts/python.exe tools/diagnose.py --pool zoo/field --pool zoo/archetypes --tables 24
.venv/Scripts/python.exe tools/population_stats.py --pool zoo/field --pool zoo/archetypes --tables 32
.venv/Scripts/python.exe tools/build_zip.py                         # -> dist/submission.zip (audited)
```

## Findings so far (paired arena, points per game, 5-seat tables)

- The postflop EV engine beats the chart-only fallback (+0.30 vs a house-heavy pool,
  +0.085 vs the full zoo).
- Measured field fold rates vs bets: 26 % small, 33 % medium, 55 % large; preflop
  fold vs a raise 82 %. Using them as priors removed losing river bluffs (+0.048).
- Variance aversion **hurts** (λ = 0.4: −0.11 ± 0.05). In this field points follow
  chips, so the bot maximizes chip EV. The endgame risk module is disabled
  (`endgame_hands = 0`).
- Capping overbet shoves at 3× pot: neutral to slightly positive (kept).
- Wider opens (1.3×): neutral within noise.
- A bot that crashes at hand 25 still averages ~2.8 points/game: avoiding big
  losses is valuable, and a crash is not automatically last place.
- Preflop EV module for facing raises (`pf_ev`) **lost** −0.157 ± 0.059: it 3-bet far
  too often. Measured fold-to-3bet is bimodal: rule-based archetypes fold ~75 %,
  but the realistic field replicas almost never fold (D1 2 %, D2 15 %, B1/C1/C2 0 %).
  Disabled; the chart is kept. Light 3-bet bluffs are a losing idea in this field.
- Clock: the bot uses ~0.4–0.75 s of its 40 s per game in subprocess mode.
- Swiss simulation (6 tournaments, 20-bot zoo field, v3): final ranks
  [1, 1, 1, 14, 2, 9], mean 4.67, top 3 in 4 of 6.

## Current submission

`dist/submission.zip` = snapshot `v3` (chart preflop, EV postflop, calibrated priors,
all-in cap 3× pot, endgame off, `pf_ev` off). Audit and subprocess games pass.
