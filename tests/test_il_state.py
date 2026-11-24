"""Injured vs healthy-on-IL: one rule in Python (season_state.il_state) and its mirror on the page (ilKind)."""
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import _site  # noqa: E402
import season_state as ss  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402
from _drive import drive_page  # noqa: E402

RULES = ss._load(ss.RULES_PATH)["longTermInjured"]


class TestIlState(unittest.TestCase):
    def st(self, slot, status, ok):
        return ss.il_state(slot, status, ok, RULES)

    def test_not_in_an_il_slot_is_not_an_il_state(self):
        for slot in ("BN", "PG", "Util", None):
            self.assertIsNone(self.st(slot, "O", True))

    def test_out_statuses_are_injured_whatever_the_registry_says(self):
        for status in ("O", "OUT", "INJ", "OFS", "o"):
            for ok in (True, False, None):
                self.assertEqual(self.st("IL", status, ok), "injured", (status, ok))              # the registry lags a day; Yahoo's status wins

    def test_ineligible_statuses_are_healthy_on_il(self):
        for status in ("P", "Q", "GTD", "DTD"):
            self.assertEqual(self.st("IL+", status, True), "healthy_on_il", status)

    def test_doubtful_is_il_eligible_per_the_league_settings(self):
        for ok in (True, False, None):
            self.assertEqual(self.st("IL", "D", ok), "injured", ok)

    def test_no_status_follows_the_registry_il_token(self):
        self.assertEqual(self.st("IL", None, True), "injured")             # Out stays eligible until the next morning / 3+ games: no status can still be legitimate
        self.assertEqual(self.st("IL", "", False), "healthy_on_il")
        self.assertEqual(self.st("IL", None, None), "unverified")          # provisional / unlisted player: say so, do not guess

    def test_an_unknown_status_code_is_unverified(self):
        self.assertEqual(self.st("IL", "SUSP", True), "unverified")
        self.assertEqual(self.st("IL", "NA", False), "unverified")

    def test_roster_rows_carry_the_registry_il_token_when_known(self):
        import league_state as ls
        si = ss.load_season(ls.load_inputs())
        state = ss.season_state(si)
        fid = sorted(si["franchises"])[0]
        rows = ss.team_view(si, state, fid, state)["roster"]
        self.assertTrue(any(r.get("ie") in (0, 1) for r in rows))
        for r in rows:
            self.assertIn(r.get("ie"), (None, 0, 1))
            meta = ls.player_meta(si, r["k"])
            if meta.get("eligiblePositions"):
                self.assertEqual(r["ie"], 1 if "IL" in meta["eligiblePositions"] else 0)
            else:
                self.assertNotIn("ie", r)


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestIlOnThePage(unittest.TestCase):
    def test_the_page_counts_match_the_python_rule_and_healthy_chips_are_distinct(self):
        with open(_site.INDEX, encoding="utf-8") as f:
            data = json.loads(re.search(r'id="league-data">(.*?)</script>', f.read(), re.S).group(1).replace("<\\/", "</"))
        want = {"injured": 0, "healthy_on_il": 0, "unverified": 0}
        for t in data["teams"]:
            for r in data["scenarios"][""]["teams"][t["id"]]["roster"]:
                k = ss.il_state(r.get("s"), r.get("st"), None if "ie" not in r else bool(r["ie"]), RULES)
                if k:
                    want[k] += 1
        r = drive_page("""
          var host=document.body,n={injured:0,healthy:0,unk:0};
          [].forEach.call(host.querySelectorAll('.il-head .il-inel-n'),function(e){var t=e.textContent,m;
            if(m=/(\\d+) injured/.exec(t))n.injured+=+m[1];if(m=/(\\d+) HEALTHY/.exec(t))n.healthy+=+m[1];if(m=/(\\d+) unverified/.exec(t))n.unk+=+m[1];});
          R.n=n;R.cls=[].map.call(document.querySelectorAll('#rosters-a .st-chip.il, #rosters-b .st-chip.il'),function(e){return e.className;});""", qs="#teams", wait=2500, start=600, size="1000,1400", budget=20000)
        self.assertEqual(r["n"]["healthy"], want["healthy_on_il"])
        self.assertEqual(r["n"]["unk"], want["unverified"])
        if want["healthy_on_il"]:
            self.assertTrue(any("healthy" in c for c in r["cls"]))                          # a distinct chip, not the injured one
        self.assertTrue(all("healthy" not in c or "inel" in c for c in r["cls"]))


if __name__ == "__main__":
    unittest.main()
