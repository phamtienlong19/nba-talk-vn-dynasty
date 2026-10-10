import html as html_lib
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import league_state as ls  # noqa: E402
import refresh_team_cap_summary as cap_summary  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
INDEX = os.path.join(REPO_ROOT, "index.html")
SUP, BSY, DUNG, BZ = "franchise-12", "franchise-01", "franchise-06", "franchise-15"
ABC = ["TRADE-A", "TRADE-B", "TRADE-C"]


class TestCapStatusModel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = ls.load_inputs()

    def test_status_boundaries(self):
        i = self.i
        self.assertEqual(ls.cap_status(i, 130), "UNDER_FLOOR")
        self.assertEqual(ls.cap_status(i, 131), "AT_FLOOR")
        self.assertEqual(ls.cap_status(i, 132), "IN_RANGE")
        self.assertEqual(ls.cap_status(i, 173), "IN_RANGE")
        self.assertEqual(ls.cap_status(i, 174), "NEAR_CEILING")
        self.assertEqual(ls.cap_status(i, 177), "NEAR_CEILING")
        self.assertEqual(ls.cap_status(i, 178), "AT_CEILING")
        self.assertEqual(ls.cap_status(i, 179), "OVER_CEILING")

    def test_near_ceiling_matches_the_boards_existing_convention(self):
        self.assertEqual(ls.NEAR_CEILING_ROOM, cap_summary.NEAR_THRESHOLD)

    def test_scenario_teams_are_classified(self):
        s = {k: ls.team_report(self.i, ls.resolve(self.i, ABC + ["TRADE-D"], "SCENARIO"), k) for k in (SUP, BSY, DUNG, BZ)}
        self.assertEqual((s[BSY]["cap"], s[BSY]["status"]), (178, "AT_CEILING"))
        self.assertEqual((s[SUP]["cap"], s[SUP]["status"]), (131, "AT_FLOOR"))
        self.assertEqual((s[DUNG]["cap"], s[DUNG]["status"]), (132, "IN_RANGE"))
        self.assertEqual((s[BZ]["cap"], s[BZ]["status"], s[BZ]["room"]), (151, "IN_RANGE", 27))

    def test_under_floor_fixture(self):
        rep = ls.team_report(self.i, ls.initial_state(self.i), "franchise-02")  # CrazyCat 101
        self.assertEqual((rep["status"], rep["toFloor"]), ("UNDER_FLOOR", 30))


class TestScenarioStateIsOneObject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = ls.load_inputs()
        cls.base = ls.initial_state(cls.i)
        cls.state = ls.resolve(cls.i, ABC, "SCENARIO")
        cls.sup = ls.team_report(cls.i, cls.state, SUP, cls.base)

    def names(self):
        return [r["n"] for r in self.sup["roster"]]

    def test_sup_fam_scenario_roster(self):
        self.assertNotIn("Jalen Williams", self.names())
        self.assertNotIn("Reed Sheppard", self.names())
        self.assertIn("Julius Randle", self.names())
        self.assertEqual(self.sup["count"], 8)
        self.assertEqual(len(self.sup["roster"]), 8)

    def test_cap_count_and_roster_agree_with_each_other(self):
        self.assertEqual(self.sup["cap"], 131)
        self.assertEqual(self.sup["cap"], sum(r["c"] for r in self.sup["roster"]))
        self.assertEqual(self.sup["count"], len(self.sup["roster"]))
        self.assertEqual(self.sup["room"], 178 - 131)

    def test_scenario_picks(self):
        self.assertEqual(self.sup["picks"], ["1.03", "1.14", "2.12", "3.06"])
        self.assertNotIn("3.12", self.sup["picks"])

    def test_official_sup_fam_is_unchanged(self):
        off = ls.team_report(self.i, ls.resolve(self.i, ABC, "OFFICIAL"), SUP, self.base)
        self.assertEqual((off["cap"], off["count"]), (144, 9))
        self.assertEqual(off["picks"], ["1.14", "2.12", "3.12"])
        self.assertIn("Jalen Williams", [r["n"] for r in off["roster"]])
        self.assertEqual(off["inKeys"], [])

    def test_received_players_are_marked_in(self):
        self.assertEqual(self.sup["inKeys"], ["478.p.5318"])  # Randle only

    def test_official_view_is_exactly_the_keeper_baseline(self):
        for fid in self.i["franchises"]:
            a = ls.team_report(self.i, ls.resolve(self.i, [], "OFFICIAL"), fid, self.base)
            self.assertEqual(a["roster"], ls.team_roster(self.i, self.base, fid))
            self.assertEqual(a["cap"], a["baselineCap"])


def _chrome():
    for c in (os.environ.get("CHROME_BIN"), "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              shutil.which("google-chrome"), shutil.which("google-chrome-stable"), shutil.which("chromium"),
              shutil.which("chromium-browser")):
        if c and os.path.exists(c):
            return c
    return None


def _dump(url):
    out = subprocess.run([_chrome(), "--headless=new", "--disable-gpu", "--no-sandbox", "--dump-dom", url],
                         capture_output=True, text=True, timeout=90)
    return out.stdout


def _card(dom, short):
    for card in re.findall(r'<section class="team-card[^"]*".*?</section>', dom, re.S):
        if f'<span class="identity-tag">{short}</span>' in card:
            return card
    raise AssertionError(short)


def _read(card):
    names = [html_lib.unescape(re.sub(r"<span.*?</span>", "", n)).strip() for n in re.findall(r'<div class="pname">(.*?)</div>', card, re.S)]
    cap = re.search(r'<div class="cap-total">(.*?)<span>/(\d+)</span>', card, re.S)
    return {"names": names, "cap": cap.group(1), "ceiling": cap.group(2),
            "gap": re.search(r'<div class="gap-big">(.*?)</div>', card).group(1),
            "picks": re.search(r'<span class="picks-tag">(.*?)</span>', card).group(1),
            "rows": len(re.findall(r'class="player-row', card))}


@unittest.skipUnless(_chrome(), "no headless Chrome available")
class TestRenderedCards(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base = "file://" + os.path.abspath(INDEX)
        cls.official = _dump(base)
        cls.scenario = _dump(base + "?mode=scenario&trades=" + ",".join(ABC))
        with open(INDEX, encoding="utf-8") as f:
            cls.static = f.read()

    def test_scenario_cards_render_derived_state_not_the_official_roster(self):
        sup = _read(_card(self.scenario, "sup fam"))
        self.assertNotIn("Jalen Williams", sup["names"])
        self.assertNotIn("Reed Sheppard", sup["names"])
        self.assertIn("Julius Randle", sup["names"])
        self.assertEqual((sup["cap"], sup["ceiling"], sup["rows"]), ("131", "178", 8))
        self.assertEqual(sup["gap"], "AT FLOOR")
        self.assertEqual(sup["picks"], "1.03 · 1.14 · 2.12 · 3.06")
        bsy = _read(_card(self.scenario, "Bsy"))
        self.assertEqual((bsy["cap"], bsy["gap"]), ("178", "AT CEILING"))
        self.assertIn("Jamal Murray", bsy["names"])
        self.assertNotIn("Rudy Gobert", bsy["names"])
        self.assertEqual(_read(_card(self.scenario, "Dũng"))["cap"], "132")

    def test_no_card_mixes_an_official_roster_with_a_scenario_cap(self):
        for short in ("Bsy", "Dũng", "sup fam", "Bz"):
            c = _read(_card(self.scenario, short))
            caps = [float(x) for x in re.findall(r'<div class="cap">([\d.]+)</div>', _card(self.scenario, short))]
            self.assertEqual(sum(caps), float(c["cap"]), short)
            self.assertEqual(len(caps), c["rows"], short)

    def test_unaffected_teams_are_untouched_in_scenario(self):
        self.assertEqual(_read(_card(self.scenario, "Quân")), _read(_card(self.official, "Quân")))

    def test_official_mode_restores_the_canonical_rosters_exactly(self):
        for short in ("Bsy", "Dũng", "sup fam", "Bz", "LC", "Melo"):
            static = _read(_card(self.static, short))
            rendered = _read(_card(self.official, short))
            self.assertEqual(rendered["names"], static["names"], short)
            self.assertEqual((rendered["cap"], rendered["gap"], rendered["picks"]), (static["cap"], static["gap"], static["picks"]), short)
        body = self.official.split("<body", 1)[1].split('<script id="league-app">')[0]
        self.assertNotIn('class="scn-strip"', body)
        self.assertNotIn("scn-card", body)

    def test_every_owned_pick_is_listed_and_never_clipped(self):
        i = ls.load_inputs()
        state = ls.resolve(i, ABC, "SCENARIO")
        shorts = {t["franchiseId"]: t["short"] for t in i["freeze"]["teams"]}
        for fid, short in shorts.items():
            want = " · ".join(ls.pick_label(i["pickIndex"][k]) for k in ls.team_picks(state, fid))
            self.assertEqual(_read(_card(self.scenario, short))["picks"], want, short)
        css = re.search(r"\.picks-tag\{background:#edf2f9[^}]*\}", self.static).group(0)
        for bad in ("nowrap", "ellipsis", "overflow:hidden"):
            self.assertNotIn(bad, css)

    def test_public_ui_says_keepers_are_locked(self):
        for dom in (self.official, self.scenario):
            m = re.search(r'id="lab-keeper-status">(.*?)</span>', dom)
            self.assertEqual(m.group(1), "KEEPERS LOCKED · OFFICIAL")
            self.assertNotIn("NOT FROZEN", dom.split("<body", 1)[1].split('<script id="league-app">')[0])

    def test_keeper_freeze_cuts_label_only_on_changed_cards(self):
        self.assertIn("KEEPER-FREEZE CUTS", _card(self.scenario, "sup fam"))
        self.assertNotIn("KEEPER-FREEZE CUTS", _card(self.scenario, "Quân"))
        self.assertNotIn("KEEPER-FREEZE CUTS", _card(self.official, "sup fam"))


if __name__ == "__main__":
    unittest.main()
