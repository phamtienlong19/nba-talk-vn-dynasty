"""The standalone tools/yahoo-roto tests run with the repository's suite."""
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL_TESTS = os.path.join(HERE, "..", "tools", "yahoo-roto", "tests")


def load_tests(loader, tests, pattern):
    """Add the tool's own tests by file path (a nested discover() would change the loader's top-level directory and break the outer discovery)."""
    import importlib.util
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestParityWithTheDynastyCode))
    spec = importlib.util.spec_from_file_location("yahoo_roto_tool_tests", os.path.join(TOOL_TESTS, "test_yahoo_roto.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    suite.addTests(loader.loadTestsFromModule(mod))
    return suite


if __name__ == "__main__":
    unittest.main()


class TestParityWithTheDynastyCode(unittest.TestCase):
    """The standalone tool's roto and all-play must equal scripts/roto.py (the code the LIVE tab is tested against) on a real stored week."""

    def test_week_1_roto_and_all_play_match_for_all_16_teams(self):
        import json
        import sys
        from fractions import Fraction
        sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
        sys.path.insert(0, os.path.join(HERE, "..", "tools", "yahoo-roto"))
        import roto as ref  # noqa: E402
        import yahoo_roto as tool  # noqa: E402
        with open(os.path.join(HERE, "..", "data", "2026-27", "matchups", "week-01.json"), encoding="utf-8") as f:
            wk = json.load(f)
        stats = {t["teamId"]: t["stats"] for m in wk["matchups"] for t in m["teams"]}
        self.assertEqual(len(stats), 16)
        cols = {tid: {"FGM/A*": tuple(s["fg"]), "FTM/A*": tuple(s["ft"]), "3PTM": Fraction(s["tpm"]), "PTS": Fraction(s["pts"]), "REB": Fraction(s["reb"]),
                      "AST": Fraction(s["ast"]), "ST": Fraction(s["st"]), "BLK": Fraction(s["blk"]), "TO": Fraction(s["to"])} for tid, s in stats.items()}
        specs, skipped = tool.plan(["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO"],
                                   ["Team", "FGM/A*", "FG%", "FTM/A*", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO"])
        self.assertEqual(skipped, [])
        res, _ = tool.roto(cols, specs)
        want = ref.roto(stats)
        for t in stats:
            self.assertAlmostEqual(res[t]["total"], want[t]["total"], places=9)
            self.assertEqual(res[t]["rank"], want[t]["rank"])
        cells, rec = tool.all_play(cols, specs)
        ap = ref.all_play(stats)
        for a in stats:
            self.assertEqual(rec[a], ap["record"][a])
            for b in stats:
                if a != b:
                    c = ap["cells"][a][b]
                    self.assertEqual(cells[a][b], [c["w"], c["l"], c["t"]])
