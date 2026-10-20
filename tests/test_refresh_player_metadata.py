"""Player metadata refresh (scripts/refresh_player_metadata.py): display fields move, identity/rank/price never do."""
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import league_state as ls  # noqa: E402
import refresh_player_metadata as rp  # noqa: E402


def raw_player(key, name, team, pos, elig, status=None, rank=999, price=77):
    p = {"player_key": key, "player_id": key.split(".p.")[1], "name": {"full": name}, "editorial_team_abbr": team,
         "display_position": pos, "eligible_positions": [{"position": e} for e in elig], "projected_auction_value": str(price),
         "player_ranks": [{"player_rank": {"rank_type": "OR", "rank_value": rank}}]}
    if status:
        p["status"] = status
    return {"player": p}


def registry():
    return {"source": "478.l.101", "fetchedAt": "x", "playerCount": 3, "players": [
        {"playerId": "1", "playerKey": "478.p.1", "name": "A One", "nbaTeam": "NYK", "displayPosition": "C", "eligiblePositions": ["C", "Util"],
         "projectedAuctionValue": 30.0, "oRank": 5},
        {"playerId": "2", "playerKey": "478.p.2", "name": "B Two", "nbaTeam": "BOS", "displayPosition": "PG", "eligiblePositions": ["PG", "G", "Util"],
         "projectedAuctionValue": 12.0, "oRank": 40},
        {"playerId": "3", "playerKey": "478.p.3", "name": "C Three", "nbaTeam": "LAL", "displayPosition": "SF", "eligiblePositions": ["SF", "F", "Util"],
         "projectedAuctionValue": 1.0, "oRank": 200}]}


def raw():
    players = [raw_player("478.p.1", "A One", "UTA", "C", ["C", "Util", "IL"], "O", rank=1, price=99),      # traded, hurt; rank/price moved
               raw_player("478.p.2", "B Two", "BOS", "PG,SG", ["PG", "SG", "G", "Util"], "Q", rank=2, price=98),  # gained SG
               raw_player("478.p.9", "New Guy", "MIA", "PF", ["PF", "F", "Util"])]                       # not in the registry
    return {"fantasy_content": {"league": {"league_key": "478.l.101", "players": players}}}


class TestMetadataRefresh(unittest.TestCase):
    def test_plan_reports_team_position_and_universe_changes(self):
        live = rp.live_fields(raw())
        p = rp.plan(registry(), live)
        by = {c["name"]: c["diff"] for c in p["changes"]}
        self.assertEqual(by["A One"]["nbaTeam"], ("NYK", "UTA"))
        self.assertEqual(by["B Two"]["displayPosition"], ("PG", "PG,SG"))
        self.assertEqual(p["missing"], ["C Three"])                      # not in the response: keep last known values
        self.assertEqual(p["newOnYahoo"], ["New Guy"])                    # reported, never added

    def test_apply_moves_display_fields_only(self):
        reg = registry()
        before = copy.deepcopy(reg)
        rp.apply(reg, rp.live_fields(raw()), "2026-10-20T00:00:00Z")
        self.assertEqual([p["playerKey"] for p in reg["players"]], [p["playerKey"] for p in before["players"]])  # same universe
        for a, b in zip(before["players"], reg["players"]):
            self.assertEqual((a["oRank"], a["projectedAuctionValue"], a["name"]), (b["oRank"], b["projectedAuctionValue"], b["name"]))
        self.assertEqual((reg["players"][0]["nbaTeam"], reg["players"][0]["eligiblePositions"]), ("UTA", ["C", "Util", "IL"]))
        self.assertEqual(reg["players"][1]["displayPosition"], "PG,SG")
        self.assertEqual(reg["players"][2], before["players"][2])          # untouched when Yahoo does not return him
        self.assertEqual(reg["metadataRefreshedAt"], "2026-10-20T00:00:00Z")

    def test_status_table_lists_only_players_with_a_status(self):
        doc = rp.status_doc(rp.live_fields(raw()), "2026-10-20T00:00:00Z")
        self.assertEqual(doc["statuses"], {"478.p.1": "O", "478.p.2": "Q"})

    def test_dry_run_writes_nothing(self):
        import io
        import tempfile
        from contextlib import redirect_stdout
        d = tempfile.mkdtemp()
        path = os.path.join(d, "raw.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw(), f)
        before = os.path.getmtime(rp.REGISTRY), os.path.exists(rp.STATUS) and os.path.getmtime(rp.STATUS)
        with redirect_stdout(io.StringIO()) as out:
            rp.main(["--raw", path])
        self.assertIn("dry run", out.getvalue())
        self.assertEqual((os.path.getmtime(rp.REGISTRY), os.path.exists(rp.STATUS) and os.path.getmtime(rp.STATUS)), before)

    def test_live_registry_invariants(self):
        i = ls.load_inputs()
        reg = list(i["registry"].values())
        self.assertEqual(len(reg), 600)
        self.assertEqual(len({p["playerKey"] for p in reg}), 600)
        with open(rp.STATUS, encoding="utf-8") as f:
            st = json.load(f)
        self.assertTrue(set(st["statuses"]) <= set(i["registry"]) | {"478.p.10134", "478.p.10404"})
        for p in reg:                                                       # every player keeps a team, a position and eligibility
            self.assertTrue(p["nbaTeam"] and p["displayPosition"] and p["eligiblePositions"], p["name"])
        self.assertEqual(i["registry"]["478.p.5352"]["oRank"], 1)           # Jokić: preseason O-Rank 1, untouched by the refresh


if __name__ == "__main__":
    unittest.main()
