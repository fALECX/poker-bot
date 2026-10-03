"""Swiss tournament simulator mirroring the MAC format (dev only).

    python -m testing.tournament --entry scaffold/main.py --pool zoo/field --pool zoo/archetypes \
        --runs 6 --rounds 4 --table 5

Each round: tables of ~5, one game per seat (duplicate deals), game points by
chip rank, table placement points from summed game points (ties share).
Between rounds bots regroup by cumulative placement points (ties broken by
total game points). Reports the final-rank distribution of every --entry.
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from testing.arena import expand_pool, game_points, run_table  # noqa: E402


def split_tables(order: list[int], size: int) -> list[list[int]]:
    n = len(order)
    k = max(1, round(n / size))
    base, extra = divmod(n, k)
    tables, i = [], 0
    for t in range(k):
        m = base + (1 if t < extra else 0)
        tables.append(order[i:i + m])
        i += m
    return tables


def placement(values: list[float]) -> list[float]:
    return game_points(values)  # same rank->points rule, scale follows table size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--entry", action="append", required=True)
    ap.add_argument("--pool", action="append", required=True)
    ap.add_argument("--field-size", type=int, default=20)
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("--table", type=int, default=5)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", default="swiss")
    args = ap.parse_args()

    pool = expand_pool(args.pool)
    final_ranks = defaultdict(list)
    with Pool(args.workers) as workers:
        for run in range(args.runs):
            rng = random.Random(f"{args.seed}-{run}")
            field = list(args.entry) + [rng.choice(pool) for _ in range(args.field_size - len(args.entry))]
            n = len(field)
            cum_place = [0.0] * n
            cum_game = [0.0] * n
            order = list(range(n))
            rng.shuffle(order)
            for rnd in range(args.rounds):
                if rnd > 0:
                    order = sorted(range(n), key=lambda i: (-cum_place[i], -cum_game[i], rng.random()))
                tables = split_tables(order, args.table)
                jobs = [{"table": t, "cand": 0, "specs": [field[i] for i in tab],
                         "seed": f"{args.seed}-{run}-{rnd}-{t}", "deals": 100}
                        for t, tab in enumerate(tables)]
                results = workers.map(run_table, jobs, chunksize=1)
                for tab, res in zip(tables, results):
                    totals = [sum(g[j] for g in res["points"]) for j in range(len(tab))]
                    for j, p in zip(tab, placement(totals)):
                        cum_place[j] += p
                    for j, g in zip(tab, totals):
                        cum_game[j] += g
            final = sorted(range(n), key=lambda i: (-cum_place[i], -cum_game[i]))
            for e in range(len(args.entry)):
                final_ranks[args.entry[e]].append(final.index(e) + 1)
            top = ", ".join(f"{field[i].split('/')[-1]}({cum_place[i]:.1f})" for i in final[:5])
            print(f"run {run}: " + "  ".join(f"{args.entry[e]} -> #{final.index(e) + 1}" for e in range(len(args.entry)))
                  + f"   top5: {top}", flush=True)
    for e, ranks in final_ranks.items():
        print(f"{e}: mean final rank {sum(ranks) / len(ranks):.2f} of {args.field_size}, "
              f"top3 {sum(r <= 3 for r in ranks)}/{len(ranks)}, ranks {ranks}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
