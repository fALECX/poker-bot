"""Measure field tendencies from public information only (dev only).

    python tools/population_stats.py --pool zoo/field --pool zoo/archetypes --tables 24

Plays tables with our bot and, at the end of each game, pools the tracker
statistics our bot gathered about its opponents (exactly what it can observe
in a real game). Prints population estimates to use as priors in params.py.
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

FIELDS = ["vpip", "pfr", "open", "limp", "threebet", "fold_to_3bet", "pf_allin", "pf_fold_vs_raise",
          "cbet", "bet_when_checked", "raise_vs_bet"]


def run(job):
    from macpoker.match import MatchConfig, play_set
    from macpoker.transport import InProcessTransport
    agents = []

    def make(k):
        random.seed(f"{job['seed']}:{k}")
        me = _make_bot(job["cand"])
        agents.append(me.agent)
        return [InProcessTransport(me, "me")] + [InProcessTransport(_make_bot(s), s) for s in job["opps"]]

    play_set(MatchConfig(seats=1 + len(job["opps"]), deals=100, seed=job["seed"]), make)
    out = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for k, agent in enumerate(agents):
        n = len(job["opps"]) + 1
        for pid, st in agent.tracker.stats.items():
            if pid == agent.player:
                continue
            # player id -> spec: bot b is player id b; candidate is bot 0
            spec = job["opps"][pid - 1] if 0 < pid < n else "?"
            for f in FIELDS:
                c = getattr(st, f)
                out[spec][f][0] += c.hits
                out[spec][f][1] += c.opps
            for b in range(3):
                c = st.fold_vs_bet[b]
                out[spec][f"fold_vs_bet{b}"][0] += c.hits
                out[spec][f"fold_vs_bet{b}"][1] += c.opps
    return {s: {f: list(v) for f, v in d.items()} for s, d in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", default="scaffold/main.py")
    ap.add_argument("--pool", action="append", required=True)
    ap.add_argument("--tables", type=int, default=16)
    ap.add_argument("--seed", default="pop")
    args = ap.parse_args()
    pool = expand_pool(args.pool)
    rng = random.Random(args.seed)
    jobs = [{"cand": args.cand, "opps": [rng.choice(pool) for _ in range(4)], "seed": f"{args.seed}-{t}"}
            for t in range(args.tables)]
    with Pool(8) as p:
        parts = p.map(run, jobs)
    agg = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for part in parts:
        for spec, d in part.items():
            for f, (h, o) in d.items():
                agg[spec][f][0] += h
                agg[spec][f][1] += o
    fields = FIELDS + ["fold_vs_bet0", "fold_vs_bet1", "fold_vs_bet2"]
    print("per bot (rate, opportunities):")
    print(f"{'bot':<26}" + "".join(f"{f[:11]:>12}" for f in fields))
    pop = {f: [] for f in fields}
    for spec in sorted(agg):
        row = []
        for f in fields:
            h, o = agg[spec][f]
            r = h / o if o else float("nan")
            row.append(f"{r:>12.2f}" if o else f"{'-':>12}")
            if o >= 5:
                pop[f].append(r)
        print(f"{spec.split('/')[-1][:25]:<26}" + "".join(row))
    print("\npopulation (unweighted mean over bots):")
    for f in fields:
        xs = pop[f]
        if xs:
            print(f"  {f:<18} {sum(xs) / len(xs):.3f}  (bots={len(xs)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
