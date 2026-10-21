"""2026 rookies are recognised by the draft-class list, not only by the league draft: an undrafted rookie picked up from free
agency by an automated roster import (e.g. Christian Anderson) must still be a rookie."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_fa_draft_pool as pool  # noqa: E402
import build_league_state as bls  # noqa: E402
import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402


class RookieKeys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.si = ss.load_season(ls.load_inputs())
        cls.keys = set(bls.rookie_keys(cls.si))

    def test_every_league_draft_rookie_is_included(self):
        drafted = {e["playerKey"] for e in self.si["draft"]["events"] if e.get("rookie")}
        self.assertTrue(drafted <= self.keys)

    def test_every_rostered_player_on_the_draft_class_list_is_a_rookie(self):
        names = pool.load_rookie_names()
        self.assertTrue(names)
        snap = self.si["rosterSnapshot"]
        for fid, rows in snap["teams"].items():
            for r in rows:
                if pool.normalize_name(ls.player_name(self.si, r["playerKey"])) in names:
                    self.assertIn(r["playerKey"], self.keys, r["name"])

    def test_an_unlisted_undrafted_rookie_is_still_a_rookie(self):
        """The failure: a rookie on the class list who was not drafted here arrives via an import as an unlisted player."""
        with open(pool.ROOKIE_SOURCE, encoding="utf-8") as f:
            name = json.load(f)["players"][0]["name"]
        si = dict(self.si)
        si["unlistedPlayers"] = {**self.si.get("unlistedPlayers", {}), "478.p.99999": {
            "playerKey": "478.p.99999", "name": name, "nbaTeam": "CHA", "displayPosition": "PG", "cap": 0.0}}
        self.assertIn("478.p.99999", bls.rookie_keys(si))

    def test_a_veteran_is_not_marked(self):
        veteran = next(m for m in self.si["registry"].values() if pool.normalize_name(m["name"]) not in pool.load_rookie_names())
        self.assertNotIn(veteran["playerKey"], self.keys)


if __name__ == "__main__":
    unittest.main()
