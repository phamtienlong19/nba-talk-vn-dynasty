import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from cap_model import apply_cap_policy, compute_cap_model, load_cap_policy  # noqa: E402
from export_yahoo_top300 import parse_markdown  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURE_MD = os.path.join(REPO_ROOT, "tests", "fixtures", "yahoo_top300_2026-10-04.md")


def _players():
    with open(FIXTURE_MD, encoding="utf-8") as f:
        return [{"capDollars": d, "oRank": r} for _, d, r in parse_markdown(f.read())]


class TestOfficialCapPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = load_cap_policy()
        self.result = apply_cap_policy(compute_cap_model(_players()), self.policy)

    def test_official_band_is_131_178(self):
        self.assertEqual((self.result["officialFloor"], self.result["officialCeiling"]), (131, 178))

    def test_raw_and_formula_values_are_untouched_by_the_override(self):
        self.assertEqual(self.result["top144Sum"], 2468)
        self.assertAlmostEqual(self.result["benchmark"], 154.25)
        self.assertAlmostEqual(self.result["rawFloor"], 131.1125)
        self.assertAlmostEqual(self.result["rawCeiling"], 177.3875)
        self.assertEqual((self.result["formulaFloor"], self.result["formulaCeiling"]), (131, 177))

    def test_override_is_recorded_separately_with_a_reason(self):
        self.assertTrue(self.result["ceilingOverride"])
        self.assertFalse(self.result["floorOverride"])
        self.assertIn("Commissioner", self.result["overrideReason"])

    def test_cap_model_itself_does_not_know_about_the_override(self):
        raw = compute_cap_model(_players())
        self.assertNotIn("officialCeiling", raw)
        self.assertEqual(raw["roundedCeiling"], 177)

    def test_formula_matches_the_approved_baseline(self):
        self.assertTrue(self.result["formulaMatchesApproved"])

    def test_a_formula_change_is_flagged_without_touching_the_official_band(self):
        shifted = [dict(p, capDollars=p["capDollars"] + 1) for p in _players()]
        result = apply_cap_policy(compute_cap_model(shifted), self.policy)
        self.assertFalse(result["formulaMatchesApproved"])
        self.assertEqual(result["officialCeiling"], 178)

    def test_no_override_when_policy_equals_formula(self):
        policy = dict(self.policy, officialCeiling=177)
        self.assertFalse(apply_cap_policy(compute_cap_model(_players()), policy)["ceilingOverride"])


class TestOfficialBandEverywhereCurrent(unittest.TestCase):
    def test_board_pills_and_denominators_show_131_178(self):
        with open(os.path.join(REPO_ROOT, "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertEqual(set(re.findall(r'class="pill-v">(\d+)–(\d+)</span>', html)), {("131", "178")})
        self.assertEqual(set(re.findall(r'<span>/(\d+)</span>', html)), {"178"})

    def test_current_state_and_tracked_snapshot_carry_the_official_band(self):
        with open(os.path.join(REPO_ROOT, "ai_exchange", "CURRENT_STATE.json"), encoding="utf-8") as f:
            cs = json.load(f)["canonicalState"]
        self.assertEqual((cs["capFloor"], cs["capCeiling"]), (131, 178))
        self.assertEqual((cs["capFormulaFloor"], cs["capFormulaCeiling"]), (131, 177))
        with open(os.path.join(REPO_ROOT, "data", "yahoo", "cap_snapshot.json"), encoding="utf-8") as f:
            snap = json.load(f)
        self.assertEqual((snap["officialFloor"], snap["officialCeiling"]), (131, 178))
        self.assertEqual(snap["formulaCeiling"], 177)
        self.assertAlmostEqual(snap["rawCeiling"], 177.3875)
        self.assertTrue(snap["ceilingOverride"])

    def test_policy_file_matches_current_state(self):
        policy = load_cap_policy()
        with open(os.path.join(REPO_ROOT, "ai_exchange", "CURRENT_STATE.json"), encoding="utf-8") as f:
            cs = json.load(f)["canonicalState"]
        self.assertEqual((policy["officialFloor"], policy["officialCeiling"]), (cs["capFloor"], cs["capCeiling"]))


if __name__ == "__main__":
    unittest.main()
