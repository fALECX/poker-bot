"""Zoo archetypes must be as robust as our bot: legal actions, no crashes."""

import glob
import os
import unittest

from tests.helpers import ROOT, run_checked

ARCHETYPES = sorted(
    os.path.relpath(p, ROOT).replace("\\", "/")
    for p in glob.glob(str(ROOT / "zoo" / "archetypes" / "z_*.py"))
)
TABLES = [
    ["house:allin"],
    ["house:call", "house:random", "house:allin", "zoo/archetypes/z_lag_pressure.py"],
    ["zoo/archetypes/z_nit.py", "zoo/archetypes/z_station_smart.py", "zoo/archetypes/z_pushfold.py",
     "house:random", "zoo/archetypes/z_mc_random.py"],
]


class ZooRobustnessTest(unittest.TestCase):
    def test_archetypes(self):
        for bot in ARCHETYPES:
            for i, table in enumerate(TABLES):
                with self.subTest(bot=bot, table=i):
                    results, problems, max_ms, _ = run_checked(bot, table, deals=60, seed=f"zoo-{i}", games=2)
                    self.assertEqual(problems, [], problems[:3])
                    for r in results:
                        self.assertEqual(r.verdicts[0], "OK")
                    self.assertLess(max_ms, 300)


if __name__ == "__main__":
    unittest.main()
