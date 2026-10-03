import random
import unittest

from tests import helpers  # noqa: F401  (sets sys.path)

from macpoker.evaluator import evaluate as oracle
from pokerbot.core.cards import COMBOS, class_combos, class_index, class_name, parse_card
from pokerbot.core.evaluator import evaluate
from pokerbot.core.preflop_rank import CLASS_PCT, eq_vs_top


def _sign(a, b):
    return (a > b) - (a < b)


class EvaluatorTest(unittest.TestCase):
    def test_matches_engine_oracle(self):
        rng = random.Random(7)
        hands = [rng.sample(range(52), rng.choice((5, 6, 7))) for _ in range(40000)]
        ours = [evaluate(h) for h in hands]
        ref = [oracle(h) for h in hands]
        for o, r in zip(ours, ref):
            self.assertEqual(o >> 20, r[0])
        order = sorted(range(len(hands)), key=lambda i: ref[i])
        for x, y in zip(order, order[1:]):
            self.assertEqual(_sign(ours[x], ours[y]), _sign(ref[x], ref[y]))

    def test_crafted(self):
        def ev(s):
            return evaluate([parse_card(c) for c in s.split()])
        self.assertGreater(ev("5s 4s 3s 2s As Kd Qd"), ev("Ah Kh Qh Jh 9h 2c 3d"))  # steel wheel > flush
        self.assertGreater(ev("6d 5c 4h 3s 2d Ac Kc"), ev("5d 4c 3h 2s Ad Kc Qc"))  # 6-high > wheel
        self.assertGreater(ev("Ah Kh 2h 7h 9h 9c 9d"), ev("Tc Jd Qh Ks Ac 2d 3d"))  # flush > straight
        self.assertEqual(ev("2c 3d Ah Ad Ac Ks Kd"), ev("4c 5d Ah Ad Ac Ks Kd"))  # board plays
        self.assertGreater(ev("Kc Kd Ks Qh Qd Qs 2c"), ev("Jc Jd Js Ah Ad 2s 3c"))  # two trips -> boat
        self.assertGreater(ev("9c 9d 9h 9s Ac 2d 3h"), ev("9c 9d 9h 9s Kc Qd Jh"))  # quads kicker


class CardsTest(unittest.TestCase):
    def test_classes(self):
        counts = [0] * 169
        for a, b in COMBOS:
            counts[class_index(a, b)] += 1
        self.assertEqual(counts, [class_combos(i) for i in range(169)])
        self.assertEqual(class_name(class_index(parse_card("As"), parse_card("Ah"))), "AA")
        self.assertEqual(class_name(class_index(parse_card("Ks"), parse_card("As"))), "AKs")
        self.assertEqual(class_name(class_index(parse_card("7c"), parse_card("2d"))), "72o")

    def test_tables(self):
        aa = class_index(parse_card("As"), parse_card("Ah"))
        trash = class_index(parse_card("7c"), parse_card("2d"))
        self.assertLess(CLASS_PCT[aa], 0.01)
        self.assertGreater(CLASS_PCT[trash], 0.9)
        self.assertGreater(eq_vs_top(aa, 0.05), 0.78)
        self.assertLess(eq_vs_top(trash, 0.05), 0.25)


if __name__ == "__main__":
    unittest.main()
