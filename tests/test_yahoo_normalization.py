import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from normalize_yahoo_players import normalize_snapshot, NormalizationError  # noqa: E402


def _fixture_snapshot(players):
    """Shape mirrors a real fetched Yahoo response (format=json_f), trimmed
    to the fields the normalizer reads. See docs/YAHOO_DATA_SOURCE.md."""
    return {
        "fantasy_content": {
            "league": {
                "league_key": "478.l.101",
                "players": [{"player": p} for p in players],
            }
        }
    }


def _player(player_id, name, team, positions, o_rank, cap_dollars, avg_cost="0.0"):
    return {
        "player_id": player_id,
        "player_key": f"478.p.{player_id}",
        "name": {"full": name},
        "editorial_team_abbr": team,
        "eligible_positions": [{"position": p} for p in positions],
        "player_ranks": [{"player_rank": {"rank_type": "OR", "rank_value": str(o_rank)}}],
        "projected_auction_value": cap_dollars,
        "average_auction_cost": avg_cost,
    }


class TestYahooNormalization(unittest.TestCase):
    def test_normalizes_expected_fields(self):
        snapshot = _fixture_snapshot([
            _player("10094", "Victor Wembanyama", "SAS", ["C", "Util"], 1, "61", "70.0"),
        ])
        result = normalize_snapshot(snapshot, source_timestamp="2026-09-16T000000Z")
        self.assertEqual(len(result["players"]), 1)
        row = result["players"][0]
        self.assertEqual(row["playerId"], "10094")
        self.assertEqual(row["playerKey"], "478.p.10094")
        self.assertEqual(row["name"], "Victor Wembanyama")
        self.assertEqual(row["nbaTeam"], "SAS")
        self.assertEqual(row["eligiblePositions"], ["C", "Util"])
        self.assertEqual(row["oRank"], 1)
        self.assertEqual(row["capDollars"], 61.0)
        self.assertEqual(row["auctionValue"], 70.0)
        self.assertEqual(row["sourceLeagueKey"], "478.l.101")
        self.assertEqual(row["sourceTimestamp"], "2026-09-16T000000Z")

    def test_zero_dollar_player_normalized(self):
        snapshot = _fixture_snapshot([
            _player("999", "Deep Bench Guy", "DET", ["PF"], 300, "0"),
        ])
        result = normalize_snapshot(snapshot)
        self.assertEqual(result["players"][0]["capDollars"], 0.0)

    def test_unicode_player_name(self):
        snapshot = _fixture_snapshot([
            _player("5352", "Nikola Jokić", "DEN", ["C"], 2, "60"),
            _player("3", "Luka Dončić", "LAL", ["PG"], 3, "59"),
        ])
        result = normalize_snapshot(snapshot)
        names = {p["name"] for p in result["players"]}
        self.assertIn("Nikola Jokić", names)
        self.assertIn("Luka Dončić", names)

    def test_player_missing_or_rank_is_skipped_not_crashed(self):
        broken = _player("1", "No Rank Guy", "BOS", ["SF"], 1, "10")
        broken["player_ranks"] = [{"player_rank": {"rank_type": "ADP", "rank_value": "5"}}]
        snapshot = _fixture_snapshot([broken])
        result = normalize_snapshot(snapshot)
        self.assertEqual(result["players"], [])
        self.assertEqual(len(result["skipped"]), 1)

    def test_player_missing_cap_value_is_skipped_not_crashed(self):
        broken = _player("1", "No Cost Guy", "BOS", ["SF"], 1, "10")
        broken["projected_auction_value"] = None
        snapshot = _fixture_snapshot([broken])
        result = normalize_snapshot(snapshot)
        self.assertEqual(result["players"], [])
        self.assertEqual(len(result["skipped"]), 1)

    def test_malformed_response_raises_clearly(self):
        with self.assertRaises(NormalizationError):
            normalize_snapshot({"fantasy_content": {"league": {}}})

        with self.assertRaises(NormalizationError):
            normalize_snapshot({"unexpected": "shape"})


if __name__ == "__main__":
    unittest.main()
