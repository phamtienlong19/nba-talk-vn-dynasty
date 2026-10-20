"""Commissioner's draft-order rules (2026-10-20): no top 2 twice in a row; one number-one pick per 3-year span."""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import league_state as ls  # noqa: E402
import lottery_eligibility as le  # noqa: E402

SUP, MAX, LC, HCMC = "franchise-12", "franchise-07", "franchise-04", "franchise-05"


class TestLotteryEligibility(unittest.TestCase):
    def setUp(self):
        self.cfg = le.load()

    def test_the_owners_examples_for_2027_and_2028(self):
        e27, e28 = le.eligibility(self.cfg, 2027), le.eligibility(self.cfg, 2028)
        # 2027: sup fam picked 1st in 2025 -> cannot pick 1st, but can pick 2nd
        self.assertEqual((e27[SUP]["canPick1"], e27[SUP]["canPickTop2"]), (False, True))
        # 2027: Maxfixe (1st) and Long con (2nd) in 2026 -> no top 2 at all
        for fid in (MAX, LC):
            self.assertEqual((e27[fid]["canPick1"], e27[fid]["canPickTop2"]), (False, False))
        self.assertNotIn(HCMC, e27)
        # 2028: sup fam is free again; Long con can go 1st; Maxfixe can pick 2nd but not 1st
        self.assertNotIn(SUP, e28)
        self.assertNotIn(LC, e28)
        self.assertEqual((e28[MAX]["canPick1"], e28[MAX]["canPickTop2"]), (False, True))
        self.assertEqual(le.eligibility(self.cfg, 2029), {})

    def test_history_matches_the_recorded_2026_draft(self):
        i = ls.load_inputs()
        o = ls.resolve(i, (), "OFFICIAL")
        h = next(x for x in self.cfg["history"] if x["draft"] == 2026)
        self.assertEqual(o["completedPicks"]["2026-R1-01"]["franchiseId"], h["slot1"])
        self.assertEqual(o["completedPicks"]["2026-R1-02"]["franchiseId"], h["slot2"])
        self.assertEqual({SUP, MAX, LC} <= set(i["franchises"]), True)

    def test_later_results_extend_the_restrictions(self):
        cfg = copy.deepcopy(self.cfg)
        cfg["history"].append({"draft": 2027, "slot1": HCMC, "slot2": SUP, "source": "test"})
        e28 = le.eligibility(cfg, 2028)
        self.assertEqual((e28[SUP]["canPickTop2"], e28[SUP]["canPick1"]), (False, False))   # 2nd in 2027: no top 2 in 2028
        self.assertEqual((e28[HCMC]["canPickTop2"], e28[HCMC]["canPick1"]), (False, False))
        self.assertEqual(e28[MAX]["canPick1"], False)                                        # 2026 No.1 still inside 2026-2028
        self.assertEqual(le.eligibility(cfg, 2029)[HCMC]["canPick1"], False)                 # No.1 in 2027: blocked through 2029
        self.assertNotIn(MAX, le.eligibility(cfg, 2029))                                     # 2026 No.1 has aged out

    def test_the_rule_is_recorded_not_hidden_in_code(self):
        r = self.cfg["rules"]
        self.assertEqual((r["noTop2TwiceInARow"]["slots"], r["oneNumberOnePerWindow"]["windowDrafts"]), ([1, 2], 3))
        self.assertIn("Commissioner", r["source"])
        self.assertEqual(len(self.cfg["openQuestions"]), 2)                                  # undecided points are listed, not guessed


if __name__ == "__main__":
    unittest.main()
