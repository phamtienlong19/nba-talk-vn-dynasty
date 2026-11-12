"""Commissioner-recorded violations: the file is validated, handed to the page, and shown on the team's card and My team page as written."""
import copy
import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import _phone  # noqa: E402
import league_state as ls  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402
import violations as vi  # noqa: E402

IDS = {t["franchiseId"] for t in ls.load_inputs()["freeze"]["teams"]}
HCMC = "franchise-05"


class TestFile(unittest.TestCase):
    def test_the_recorded_violation_is_hcmc_week_3_with_points_not_set(self):
        recs = vi.load(IDS)
        self.assertEqual([(v["id"], v["franchiseId"], v["kind"], v["week"], v["points"]) for v in recs], [("VIOL-2026-001", HCMC, "TANK_VIOLATION", 3, None)])
        ev = recs[0]["evidence"]
        self.assertEqual((ev[0]["date"], ev[0]["slot"], ev[0]["player"]), ("2026-11-07", "IL", "Jalen Johnson"))

    def write(self, mutate):
        with open(vi.PATH, encoding="utf-8") as f:
            doc = json.load(f)
        mutate(doc)
        d = tempfile.mkdtemp()
        p = os.path.join(d, "v.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        return p

    def test_a_bad_record_is_refused(self):
        for name, mutate in (("franchise", lambda d: d["violations"][0].update(franchiseId="franchise-99")),
                             ("kind", lambda d: d["violations"][0].update(kind="OTHER")),
                             ("week", lambda d: d["violations"][0].update(week=0)),
                             ("points", lambda d: d["violations"][0].update(points=-1)),
                             ("date", lambda d: d["violations"][0]["evidence"][0].update(date="Nov 7")),
                             ("dollar", lambda d: d["violations"][0].update(detail="costs $5")),
                             ("repeat", lambda d: d["violations"].append(copy.deepcopy(d["violations"][0])))):
            with self.assertRaises(vi.ViolationError, msg=name):
                vi.load(IDS, self.write(mutate))

    def test_a_withdrawn_record_is_kept_in_the_file_and_not_shown(self):
        p = self.write(lambda d: d["violations"][0].update(status="WITHDRAWN"))
        self.assertEqual(vi.page_view(vi.load(IDS, p)), [])

    def test_the_page_view_carries_no_verdict_of_ours(self):
        text = json.dumps(vi.page_view(vi.load(IDS)))
        self.assertNotIn("$", text)
        for word in ("should", "penalty applied", "guilty", "deserves"):
            self.assertNotIn(word, text)


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestPage(unittest.TestCase):
    JS = ("var cards=[].slice.call(document.querySelectorAll('section.team-card'));var hit=cards.filter(function(c){return c.querySelector('.viol-tag');});"
          "R.tags=hit.length;R.name=hit[0]?hit[0].querySelector('.team-name').textContent:'';R.tag=hit[0]?hit[0].querySelector('.viol-tag').textContent:'';"
          "var btn=hit[0].querySelector('.tc-info');btn.click();var v=hit[0].querySelector('.viol');R.panel=v?v.textContent:'';R.first=v&&v.parentNode.firstChild===v;"
          "R.sw=document.documentElement.scrollWidth;R.cw=document.documentElement.clientWidth;"
          "var hd=hit[0].querySelector('header');R.hdOver=hd.scrollWidth>hd.clientWidth+1;")

    def test_only_hcmc_shows_the_record_on_its_card_and_it_fits_a_phone(self):
        r = _phone.phone_run(self.JS, wait_ms=2500)
        self.assertIsNone(r.get("error"), r)
        self.assertEqual(r["tags"], 1)
        self.assertIn("HCMC", r["name"])
        self.assertIn("Tank violation", r["tag"])
        self.assertIn("W3", r["tag"])
        self.assertIn("Jalen Johnson", r["panel"])
        self.assertIn("not set", r["panel"])                                       # no points are invented
        self.assertTrue(r["first"])
        self.assertLessEqual(r["sw"], r["cw"])
        self.assertFalse(r["hdOver"])

    def test_my_team_page_lists_it_for_hcmc_only(self):
        js = ("document.getElementById('tb-me').click();R.mine=!!document.querySelector('#me-root .viol-c');R.row=(document.querySelector('#me-root .viol-c .me-r')||{}).textContent||'';"
              "var sel=document.querySelector('#me-root .me-sel');sel.value='franchise-01';sel.dispatchEvent(new Event('change'));R.other=!!document.querySelector('#me-root .viol-c');")
        r = _phone.phone_run(js, pre_js="localStorage.setItem('nbaTalkVN.myTeam','franchise-05')", wait_ms=2500)
        self.assertIsNone(r.get("error"), r)
        self.assertTrue(r["mine"])
        self.assertIn("Tank violation", r["row"])
        self.assertFalse(r["other"])


if __name__ == "__main__":
    unittest.main()
