"""Every action our bot sends must be accepted by the engine unchanged."""

import unittest

from tests.helpers import run_checked

CANDIDATE = "scaffold/main.py"
TABLES = [
    ["house:call"],
    ["house:allin"],
    ["house:random", "house:call", "house:allin"],
    ["house:call", "house:checkfold", "house:random", "house:allin"],
    ["house:random", "house:random", "house:call", "house:random", "house:allin"],
]


class LegalityTest(unittest.TestCase):
    def test_tables(self):
        for i, table in enumerate(TABLES):
            with self.subTest(table=table):
                results, problems, max_ms, bots = run_checked(CANDIDATE, table, deals=100, seed=f"legal-{i}")
                self.assertEqual(problems, [], problems[:3])
                for r in results:
                    self.assertEqual(r.verdicts[0], "OK")
                for b in bots:
                    self.assertEqual(b.agent.errors, 0)
                self.assertLess(max_ms, 250)


if __name__ == "__main__":
    unittest.main()
