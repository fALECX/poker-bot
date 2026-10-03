"""Parallel, points-based paired evaluation of bot versions (dev only).

    python -m testing.arena --cand scaffold/main.py --cand snapshots/v0/main.py \
        --pool zoo/field --pool house:call --tables 40 --seats 5 --workers 8

For each table i, a seeded draw picks (seats - 1) opponents from the pool and
a deck seed. Every candidate plays the same duplicate set (one game per seat)
against the same opponents and decks, so differences are paired. Scoring is
the tournament's: per game, chip rank -> points (n for 1st .. 1 for last,
ties share the average). Global `random`/numpy RNGs are re-seeded per game so
in-process runs are reproducible.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import random
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def expand_pool(items: list[str]) -> list[str]:
    out = []
    for item in items:
        if item.startswith("house:"):
            out.append(item)
            continue
        p = ROOT / item
        if p.is_dir():
            out += sorted(str(Path(x).relative_to(ROOT)).replace("\\", "/") for x in glob.glob(str(p / "*.py"))
                          if not Path(x).name.startswith("_"))
        else:
            out.append(item)
    return out


def game_points(chips: list[int]) -> list[float]:
    n = len(chips)
    pts = [0.0] * n
    order = sorted(range(n), key=lambda i: -chips[i])
    i = 0
    while i < n:
        j = i
        while j + 1 < n and chips[order[j + 1]] == chips[order[i]]:
            j += 1
        avg = sum(n - k for k in range(i, j + 1)) / (j - i + 1)
        for k in range(i, j + 1):
            pts[order[k]] = avg
        i = j + 1
    return pts


def _make_bot(spec: str):
    from macpoker.bots.builtin import BUILTINS
    from macpoker.sdk import load_bot_from_file
    if spec.startswith("house:"):
        return BUILTINS[spec.split(":", 1)[1]]()
    return load_bot_from_file(str(ROOT / spec))


def run_table(job: dict) -> dict:
    from macpoker.match import MatchConfig, play_set
    from macpoker.transport import InProcessTransport
    try:
        import numpy as np
    except ImportError:  # pragma: no cover
        np = None
    specs = job["specs"]
    seed = job["seed"]

    def make(k):
        random.seed(f"{seed}:{k}")
        if np is not None:
            np.random.seed(abs(hash((seed, k))) % (2**32))
        return [InProcessTransport(_make_bot(s), s) for s in specs]

    cfg = MatchConfig(seats=len(specs), deals=job["deals"], seed=seed,
                      base_time_ms=job.get("time_ms", 30000))
    results = play_set(cfg, make, games=job.get("games"))
    return {
        "table": job["table"], "cand": job["cand"], "specs": specs, "seed": seed,
        "chips": [r.chips for r in results],
        "points": [game_points(r.chips) for r in results],
        "verdicts": [r.verdicts for r in results],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", action="append", required=True)
    ap.add_argument("--pool", action="append", required=True)
    ap.add_argument("--tables", type=int, default=20)
    ap.add_argument("--seats", type=int, default=5)
    ap.add_argument("--deals", type=int, default=100)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", default="arena")
    ap.add_argument("--games", type=int, default=None, help="games per table (default one per seat)")
    ap.add_argument("--out", default=None, help="write raw results JSON")
    args = ap.parse_args()

    pool = expand_pool(args.pool)
    rng = random.Random(args.seed)
    jobs = []
    for t in range(args.tables):
        opps = [rng.choice(pool) for _ in range(args.seats - 1)]
        seed = f"{args.seed}-{t}"
        for c, cand in enumerate(args.cand):
            jobs.append({"table": t, "cand": c, "specs": [cand] + opps, "seed": seed,
                         "deals": args.deals, "games": args.games})

    with Pool(args.workers) as p:
        res = p.map(run_table, jobs, chunksize=1)

    per = {c: {} for c in range(len(args.cand))}
    bad = {c: 0 for c in range(len(args.cand))}
    opp_points: dict[str, list[float]] = {}
    for r in res:
        pts = [g[0] for g in r["points"]]
        per[r["cand"]][r["table"]] = (sum(pts) / len(pts), sum(sum(g[0] for g in [c]) for c in r["chips"]))
        bad[r["cand"]] += sum(v[0] != "OK" for v in r["verdicts"])
        if r["cand"] == 0:
            for g in r["points"]:
                for spec, p_ in zip(r["specs"][1:], g[1:]):
                    opp_points.setdefault(spec, []).append(p_)

    def stats(xs):
        m = sum(xs) / len(xs)
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / max(len(xs) - 1, 1))
        return m, sd / math.sqrt(len(xs))

    print(f"{args.tables} tables x {args.seats} seats, pool={len(pool)} bots")
    for c, cand in enumerate(args.cand):
        pts = [per[c][t][0] for t in range(args.tables)]
        chips = [per[c][t][1] for t in range(args.tables)]
        m, se = stats(pts)
        cm, cse = stats(chips)
        print(f"  [{c}] {cand:<40} points/game {m:.3f} ± {se:.3f}   chips/set {cm:+.0f} ± {cse:.0f}   bad verdicts {bad[c]}")
    for c in range(1, len(args.cand)):
        d = [per[0][t][0] - per[c][t][0] for t in range(args.tables)]
        m, se = stats(d)
        print(f"  paired [0]-[{c}]: {m:+.3f} ± {se:.3f} points/game")
    print("  opponents (vs cand 0), mean points/game:")
    for spec, ps in sorted(opp_points.items(), key=lambda kv: -sum(kv[1]) / len(kv[1])):
        print(f"    {spec:<40} {sum(ps) / len(ps):.2f}  (n={len(ps)})")
    if args.out:
        Path(args.out).write_text(json.dumps(res), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
