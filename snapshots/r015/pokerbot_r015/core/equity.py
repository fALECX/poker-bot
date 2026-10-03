"""Time-bounded equity simulation against weighted opponent ranges.

simulate() returns weighted samples (weight, our share of the pot, each
opponent's range percentile of the combo they held). The strategy uses the
percentiles to ask "what is our equity if only the top x% of their range
continues?" from a single simulation pass.

Heads-up on the river the result is exact (enumeration over the range).
"""

from __future__ import annotations

from bisect import bisect_left

from .cards import COMBOS
from .evaluator import evaluate


class Samples:
    __slots__ = ("w", "res", "pct")

    def __init__(self):
        self.w: list[float] = []
        self.res: list[float] = []
        self.pct: list[tuple] = []

    def __len__(self) -> int:
        return len(self.w)

    def equity(self, thresholds=None) -> tuple[float, float]:
        """(equity, probability mass) over samples where every opponent's
        percentile is >= its threshold (None = all samples)."""
        tw = 0.0
        tr = 0.0
        if thresholds is None:
            for w, r in zip(self.w, self.res):
                tw += w
                tr += w * r
        else:
            for w, r, p in zip(self.w, self.res, self.pct):
                ok = True
                for x, t in zip(p, thresholds):
                    if x < t:
                        ok = False
                        break
                if ok:
                    tw += w
                    tr += w * r
        total = sum(self.w)
        if tw <= 0:
            return 0.0, 0.0
        return tr / tw, tw / max(total, 1e-12)


def _cum(weights):
    cum = []
    acc = 0.0
    for w in weights:
        acc += w
        cum.append(acc)
    return cum, acc


def simulate(hole, board, ranges, pcts, rng, deadline, max_samples: int = 4000) -> Samples:
    """ranges/pcts: per opponent, 1326 weights and 1326 percentiles."""
    out = Samples()
    k = len(ranges)
    if k == 0:
        out.w.append(1.0)
        out.res.append(1.0)
        out.pct.append(())
        return out

    if k == 1 and len(board) == 5:
        mine = evaluate(hole + board)
        w0, p0 = ranges[0], pcts[0]
        for i, w in enumerate(w0):
            if w <= 0:
                continue
            a, b = COMBOS[i]
            v = evaluate([a, b, *board])
            out.w.append(w)
            out.res.append(1.0 if mine > v else 0.5 if mine == v else 0.0)
            out.pct.append((p0[i],))
        return out

    cums = [_cum(r) for r in ranges]
    used0 = set(hole) | set(board)
    deck = [c for c in range(52) if c not in used0]
    need = 5 - len(board)
    rand = rng.random
    n = 0
    while n < max_samples:
        if n % 64 == 0 and n >= 64 and deadline.expired():
            break
        n += 1
        used = set(used0)
        opp = []
        ok = True
        for j in range(k):
            cum, tot = cums[j]
            if tot <= 0:
                ok = False
                break
            for _ in range(25):
                i = bisect_left(cum, rand() * tot)
                if i >= 1326:
                    i = 1325
                a, b = COMBOS[i]
                if a not in used and b not in used:
                    break
            else:
                ok = False
                break
            used.add(a)
            used.add(b)
            opp.append(i)
        if not ok:
            continue
        runout = []
        while len(runout) < need:
            c = deck[int(rand() * len(deck))]
            if c not in used:
                used.add(c)
                runout.append(c)
        full = board + runout
        mine = evaluate(hole + full)
        best = -1
        ties = 0
        for i in opp:
            a, b = COMBOS[i]
            v = evaluate([a, b, *full])
            if v > best:
                best, ties = v, 1
            elif v == best:
                ties += 1
        if mine > best:
            r = 1.0
        elif mine == best:
            r = 1.0 / (ties + 1)
        else:
            r = 0.0
        out.w.append(1.0)
        out.res.append(r)
        out.pct.append(tuple(pcts[j][opp[j]] for j in range(k)))
    return out
