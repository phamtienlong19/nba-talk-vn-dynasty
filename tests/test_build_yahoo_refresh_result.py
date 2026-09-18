import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from build_yahoo_refresh_result import build_ranking_changes  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "build_yahoo_refresh_result.py")


def _write(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


class TestBuildRankingChanges(unittest.TestCase):
    def test_no_changes_when_names_match(self):
        current = [{"oRank": 1, "name": "A"}, {"oRank": 2, "name": "B"}]
        previous = [{"oRank": 1, "name": "A"}, {"oRank": 2, "name": "B"}]
        self.assertEqual(build_ranking_changes(current, previous), [])

    def test_detects_rank_occupant_change(self):
        current = [{"oRank": 1, "name": "A"}, {"oRank": 2, "name": "C"}]
        previous = [{"oRank": 1, "name": "A"}, {"oRank": 2, "name": "B"}]
        changes = build_ranking_changes(current, previous)
        self.assertEqual(changes, [
            {"oRank": 2, "previousPlayer": "B", "currentPlayer": "C"},
        ])

    def test_detects_rank_added_or_removed(self):
        current = [{"oRank": 1, "name": "A"}]
        previous = [{"oRank": 1, "name": "A"}, {"oRank": 2, "name": "B"}]
        changes = build_ranking_changes(current, previous)
        self.assertEqual(changes, [
            {"oRank": 2, "previousPlayer": "B", "currentPlayer": None},
        ])


class TestBuildYahooRefreshResultCLI(unittest.TestCase):
    def _run(self, tmpdir, previous_players=None):
        cap_snapshot_path = os.path.join(tmpdir, "cap_snapshot_latest.json")
        current_players_path = os.path.join(tmpdir, "players_normalized.json")
        source_config_path = os.path.join(tmpdir, "yahoo_source.json")
        output_path = os.path.join(tmpdir, "yahoo-refresh-result.json")

        _write(cap_snapshot_path, {
            "fetchedAt": "2026-09-18T000000Z",
            "roundedFloor": 130,
            "roundedCeiling": 175,
            "publishedFloor": 130,
            "publishedCeiling": 175,
        })
        _write(current_players_path, [{"oRank": 1, "name": "A"}])
        _write(source_config_path, {"leagueKey": "478.l.public"})

        args = [
            sys.executable, SCRIPT,
            "--cap-snapshot", cap_snapshot_path,
            "--current-players", current_players_path,
            "--source-config", source_config_path,
            "--output", output_path,
        ]
        if previous_players:
            previous_path = os.path.join(tmpdir, "previous_players.json")
            _write(previous_path, previous_players)
            args += ["--previous-players", previous_path]

        subprocess.run(args, check=True, capture_output=True, text=True)
        with open(output_path, encoding="utf-8") as f:
            return json.load(f)

    def test_match_status_and_no_baseline_note(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run(tmpdir)
        self.assertEqual(result["source"], "478.l.public")
        self.assertEqual(result["status"], "MATCH")
        self.assertEqual(result["previous"], {"floor": 130, "ceiling": 175})
        self.assertEqual(result["current"], {"floor": 130, "ceiling": 175})
        self.assertEqual(result["rankingChanges"], [])
        self.assertIn("rankingChangesNote", result)

    def test_ranking_changes_populated_when_previous_given(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self._run(tmpdir, previous_players=[{"oRank": 1, "name": "Z"}])
        self.assertEqual(result["rankingChanges"], [
            {"oRank": 1, "previousPlayer": "Z", "currentPlayer": "A"},
        ])
        self.assertNotIn("rankingChangesNote", result)


if __name__ == "__main__":
    unittest.main()
