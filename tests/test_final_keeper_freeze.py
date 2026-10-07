import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_league_state as bls  # noqa: E402
import league_state as ls  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
SEA, DHA, BSY, TULY = "franchise-11", "franchise-08", "franchise-01", "franchise-14"


def _html():
    with open(os.path.join(REPO_ROOT, "index.html"), encoding="utf-8") as f:
        return f.read()


class TestFinalKeeperDeclarations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = ls.load_inputs()
        cls.base = ls.initial_state(cls.i)
        cls.html = _html()
        cls.names = {fid: {ls.player_name(cls.i, k) for k in ls.team_players(cls.i, cls.base, fid)} for fid in cls.i["franchises"]}
        m = re.search(r'<script type="application/json" id="league-data">(.*?)</script>', cls.html, re.S)
        cls.data = json.loads(m.group(1).replace("<\\/", "</"))

    def test_thinh_keeps_isaiah_jackson_and_cuts_royce_oneale(self):
        self.assertIn("Isaiah Jackson", self.names[SEA])
        self.assertNotIn("Royce O'Neale", self.names[SEA])

    def test_dha_keeps_bilal_and_kuminga_and_cuts_nurkic_and_poeltl(self):
        self.assertTrue({"Bilal Coulibaly", "Jonathan Kuminga"} <= self.names[DHA])
        self.assertFalse({"Jusuf Nurkić", "Jakob Poeltl"} & self.names[DHA])

    def test_bsy_keeps_schroder_and_cuts_sexton(self):
        self.assertIn("Dennis Schröder", self.names[BSY])
        self.assertNotIn("Collin Sexton", self.names[BSY])

    def test_tuly_keeps_oubre_and_cuts_christie(self):
        self.assertIn("Kelly Oubre Jr.", self.names[TULY])
        self.assertNotIn("Max Christie", self.names[TULY])

    def test_every_franchise_has_exactly_nine_keepers_and_no_player_is_owned_twice(self):
        for fid, names in self.names.items():
            self.assertEqual(len(names), 9, fid)
        owners = [k for t in self.i["freeze"]["teams"] for k in (x["playerKey"] for x in t["keepers"])]
        self.assertEqual(len(owners), len(set(owners)))
        self.assertEqual(len(owners), 144)

    def test_keeper_caps_recompute_from_the_registry_and_match_the_board(self):
        expect = {"Bsy": 149, "CrazyCat": 101, "Melo": 138, "LC": 175, "HCMC": 167, "Dũng": 126, "Maxfixe": 129, "DHA": 154,
                  "Đạt": 174, "DonTrick": 120, "Thịnh": 177, "sup fam": 144, "Quân": 160, "TuLy": 146, "Bz": 173, "TT": 174}
        got = {self.i["shorts"][f]: ls.team_cap(self.i, self.base, f) for f in self.i["franchises"]}
        self.assertEqual(got, expect)
        teams, _ = bls.parse_board(self.html)
        for t in teams:
            self.assertEqual(sum(c for _, c in t["kept"]), got[t["short"]], t["short"])

    def test_dha_cap_delta_from_the_old_projection(self):
        self.assertEqual(ls.team_cap(self.i, self.base, DHA), 160 - (4 + 2))  # Nurkić $4 + Poeltl $2 out, Bilal/Kuminga $0 in

    def test_freeze_is_official_locked_and_immutable(self):
        f = self.i["freeze"]
        self.assertEqual(f["status"], "locked")
        self.assertTrue(ls.verify_lock(f))
        with self.assertRaises(ls.StateError):
            ls.lock_keepers(f, "later")
        tampered = json.loads(json.dumps(f))
        tampered["teams"][0]["keepers"].pop()
        self.assertFalse(ls.verify_lock(tampered))

    def test_checkpoint_records_the_official_band_and_per_team_caps(self):
        cp = self.i["freeze"]["checkpoint"]
        self.assertEqual((cp["capBand"]["floor"], cp["capBand"]["ceiling"]), (131, 178))
        self.assertEqual(len(cp["teams"]), 16)
        for fid, row in cp["teams"].items():
            self.assertEqual(row, ls.checkpoint_team(self.i, self.base, fid))
        self.assertEqual(cp["teams"][SEA]["roomToCeiling"], 1)
        self.assertEqual(cp["teams"][DHA]["keeperCap"], 154)
        self.assertEqual(cp["teams"]["franchise-02"]["status"], "UNDER_FLOOR")
        self.assertTrue(cp["provenance"]["declaration"])

    def test_snapshot_file_reproduces_from_the_locked_inputs(self):
        with open(os.path.join(ls.DATA_DIR, "snapshots", "KEEPER_FREEZE.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), ls.make_snapshot(self.i, "KEEPER_FREEZE"))

    # ----- availability / recommendation derive from the locked baseline
    def test_new_cuts_are_available_and_new_keepers_are_not(self):
        keys = {r[1] for r in self.data["available"]["rows"]}
        for cut in ("Royce O'Neale", "Jusuf Nurkić", "Jakob Poeltl", "Collin Sexton", "Max Christie"):
            self.assertIn(cut, keys, cut)
        for kept in ("Isaiah Jackson", "Bilal Coulibaly", "Jonathan Kuminga", "Dennis Schröder", "Kelly Oubre Jr."):
            self.assertNotIn(kept, keys, kept)
        avail_keys = [r[0] for r in self.data["available"]["rows"]]
        self.assertEqual(len(avail_keys), len(set(avail_keys)))  # stable identity, no duplicates
        owned = set(self.base["playerOwner"])
        self.assertFalse(owned & set(avail_keys))

    def test_nurkic_and_poeltl_cut_sources_and_cap_first_order(self):
        rows = {r[1]: r for r in self.data["available"]["rows"]}
        self.assertEqual((rows["Jusuf Nurkić"][7], rows["Jusuf Nurkić"][4]), ("DHA", 4.0))
        self.assertEqual((rows["Jakob Poeltl"][7], rows["Jakob Poeltl"][4]), ("DHA", 2.0))
        on_board = sorted((r for r in self.data["available"]["rows"] if r[6]), key=lambda r: r[6])
        caps = [r[4] for r in on_board]
        self.assertEqual(caps, sorted(caps, reverse=True))  # recommendation board still CAP-first
        self.assertIn("Jusuf Nurkić", [r[1] for r in on_board])

    def test_cuts_lists_are_cap_descending_on_every_card(self):
        for card in re.findall(r'<section class="team-card[^"]*".*?</section>', self.html, re.S):
            chips = re.findall(r'<span class="cut-chip">([^<]*?)(?: <strong>(\d+)</strong>)?(?:<span.*?</span>)?</span>', card)
            caps = [int(c) if c else 0 for _, c in chips]
            self.assertEqual(caps, sorted(caps, reverse=True))

    # ----- Trade Lab rebased on the locked baseline
    def test_trade_lab_cap_before_derives_from_the_locked_freeze(self):
        s = ls.resolve(self.i, ["TRADE-A"], "SCENARIO")
        r = s["tradeResults"][0]
        self.assertEqual(r["teams"][BSY]["capBefore"], self.i["freeze"]["checkpoint"]["teams"][BSY]["keeperCap"])
        self.assertEqual((r["teams"][BSY]["capBefore"], r["teams"][BSY]["playerCapDelta"], r["teams"][BSY]["capAfter"]), (149, 29, 178))
        self.assertEqual(r["teams"]["franchise-15"]["capBefore"], 173)

    def test_bsy_scenario_uses_the_new_roster_not_the_old_one(self):
        s = ls.resolve(self.i, ["TRADE-A"], "SCENARIO")
        roster = {r["n"] for r in ls.team_report(self.i, s, BSY)["roster"]}
        self.assertIn("Dennis Schröder", roster)
        self.assertNotIn("Collin Sexton", roster)
        self.assertIn("Jamal Murray", roster)
        self.assertNotIn("Rudy Gobert", roster)

    def test_official_mode_is_unchanged_by_proposed_trades_and_scenarios_still_apply(self):
        off = ls.resolve(self.i, ["TRADE-A", "TRADE-B", "TRADE-C"], "OFFICIAL")
        self.assertEqual(off["playerOwner"], self.base["playerOwner"])
        self.assertEqual(off["pickOwner"], self.base["pickOwner"])
        scn = ls.resolve(self.i, ["TRADE-A", "TRADE-B", "TRADE-C"], "SCENARIO")
        self.assertTrue(all(r["applied"] for r in scn["tradeResults"]))
        self.assertEqual(ls.team_cap(self.i, scn, "franchise-15"), 151)

    def test_other_trade_scenarios_rederive_from_the_same_baseline(self):
        d = ls.resolve(self.i, ["TRADE-D"], "SCENARIO")["tradeResults"][0]
        self.assertEqual((d["teams"]["franchise-04"]["capBefore"], d["teams"]["franchise-03"]["capBefore"]), (175, 138))
        for views in (self.data["scenarios"],):
            self.assertEqual(views, ls.enumerate_scenarios(self.i))

    def test_no_trade_is_official(self):
        self.assertEqual({t["status"] for t in self.i["trades"]["trades"]}, {"PROPOSED"})

    def test_public_wording_says_the_keeper_layer_is_locked_not_projected(self):
        js = re.search(r'<script id="league-app">(.*?)</script>', self.html, re.S).group(1)
        self.assertIn("KEEPERS LOCKED", js)
        self.assertEqual(self.data["keeperStatus"], "locked")
        static = self.html.split('<script id="league-app">')[0]
        self.assertNotIn("PROJECTED (NOT FROZEN)", static)
        self.assertNotIn("KEEPERS: PROJECTED", static)


if __name__ == "__main__":
    unittest.main()
