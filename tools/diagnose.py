"""Where does our bot win and lose chips? (dev only)

    python tools/diagnose.py --pool zoo/field --pool zoo/archetypes --tables 24

Plays tables like testing.arena with decision logging enabled and groups our
per-hand chip results by preflop line, final decision and street.
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

from testing.arena import _make_bot, expand_pool  # noqa: E402


def run(job):
    from macpoker.match import MatchConfig, play_set
    from macpoker.transport import InProcessTransport
    logs = []

    def make(k):
        random.seed(f"{job['seed']}:{k}")
        me = _make_bot(job["cand"])
        me.agent.log = []
        logs.append(me.agent.log)
        return [InProcessTransport(me, "me")] + [InProcessTransport(_make_bot(s), s) for s in job["opps"]]

    play_set(MatchConfig(seats=1 + len(job["opps"]), deals=100, seed=job["seed"]), make)
    return [(entry, job["opps"]) for log in logs for entry in log]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", default="scaffold/main.py")
    ap.add_argument("--pool", action="append", required=True)
    ap.add_argument("--tables", type=int, default=16)
    ap.add_argument("--seed", default="diag")
    ap.add_argument("--worst", type=int, default=12)
    args = ap.parse_args()
    pool = expand_pool(args.pool)
    rng = random.Random(args.seed)
    jobs = [{"cand": args.cand, "opps": [rng.choice(pool) for _ in range(4)], "seed": f"{args.seed}-{t}"}
            for t in range(args.tables)]
    with Pool(8) as p:
        hands = [h for r in p.map(run, jobs) for h in r]

    by_pf = defaultdict(lambda: [0, 0])
    by_last = defaultdict(lambda: [0, 0])
    by_street = defaultdict(lambda: [0, 0])
    for (decisions, delta), _ in hands:
        if not decisions:
            continue
        pf = next((d[1] for d in decisions if d[0] == "preflop"), "-")
        last = decisions[-1]
        for key, tab in ((pf, by_pf), (f"{last[0]}:{last[1]}", by_last), (last[0], by_street)):
            tab[key][0] += delta
            tab[key][1] += 1
    total = sum(d for (_, d), _ in hands)
    print(f"{len(hands)} hands, total {total:+d} chips ({total / max(len(hands), 1):+.2f}/hand)")
    for title, tab in (("preflop first decision", by_pf), ("street of last decision", by_street),
                       ("last decision", by_last)):
        print(f"\n== {title}")
        for k, (s, n) in sorted(tab.items(), key=lambda kv: kv[1][0]):
            print(f"  {k:<28} {s:+7d}  n={n:<5} {s / n:+.1f}/hand")
    print("\n== worst hands")
    for (decisions, delta), opps in sorted(hands, key=lambda h: h[0][1])[: args.worst]:
        print(f"  {delta:+d} vs {[o.split('/')[-1] for o in opps]}")
        for d in decisions:
            print(f"      {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
