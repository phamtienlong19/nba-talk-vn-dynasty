import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import prepare_yahoo_data_pr as prep  # noqa: E402

SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "prepare_yahoo_data_pr.py")


class TestBuildPrText(unittest.TestCase):
    def _result(self, **overrides):
        result = {
            "source": "478.l.public",
            "fetchedAt": "2026-10-01T000000Z",
            "status": "CHANGED",
            "previous": {"floor": 131, "ceiling": 177},
            "current": {"floor": 130, "ceiling": 176},
            "rankingChanges": [],
            "_provenance": {"workflowRunUrl": "https://example/actions/runs/1", "normalizedPlayerCount": 300},
        }
        result.update(overrides)
        return result

    def test_pr_title_uses_fetch_date(self):
        title = prep.build_pr_title(self._result())
        self.assertEqual(title, "data: refresh Yahoo rankings — 2026-10-01")

    def test_pr_title_falls_back_without_fetch_timestamp(self):
        title = prep.build_pr_title(self._result(fetchedAt=None))
        self.assertEqual(title, "data: refresh Yahoo rankings")

    def test_pr_body_contains_required_sections(self):
        body = prep.build_pr_body(self._result(), keeper_board_updates=3, test_status="PASS")
        self.assertIn("478.l.public", body)
        self.assertIn("2026-10-01T000000Z", body)
        self.assertIn("131 / 177", body)
        self.assertIn("130 / 176", body)
        self.assertIn("## Yahoo ranking-change summary", body)
        self.assertIn("## Board regeneration status", body)
        self.assertIn("3 kept-player row(s)", body)
        self.assertIn("FA/DRAFT 60 pool", body)
        self.assertIn("## Tests", body)
        self.assertIn("PASS", body)
        self.assertIn("https://example/actions/runs/1", body)

    def test_pr_body_does_not_ask_for_a_second_pr_or_issue(self):
        """The whole point of this fix is ONE candidate PR -- no second
        issue/PR friction, unlike the earlier (never-merged) design."""
        body = prep.build_pr_body(self._result(), keeper_board_updates=0, test_status="PASS")
        self.assertNotIn("open a GitHub Issue", body)
        self.assertIn("no further issue or PR is needed", body)

    def test_pr_body_shows_ranking_changes_when_present(self):
        result = self._result(rankingChanges=[
            {"oRank": 5, "previousPlayer": "Old Guy", "currentPlayer": "New Guy"},
        ])
        body = prep.build_pr_body(result, keeper_board_updates=0, test_status="PASS")
        self.assertIn("R5: Old Guy → New Guy", body)


class TestMainWritesCandidateFiles(unittest.TestCase):
    def test_strips_raw_snapshot_path_and_writes_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            result_path = os.path.join(tmp, "result.json")
            players_path = os.path.join(tmp, "players.json")
            cap_path = os.path.join(tmp, "cap_snapshot.json")
            stats_path = os.path.join(tmp, "stats.json")
            data_dir = os.path.join(tmp, "data", "yahoo")
            title_out = os.path.join(tmp, "pr_title.txt")
            body_out = os.path.join(tmp, "pr_body.md")

            with open(result_path, "w") as f:
                json.dump({
                    "source": "478.l.public", "fetchedAt": "2026-10-01T000000Z",
                    "status": "CHANGED",
                    "previous": {"floor": 131, "ceiling": 177},
                    "current": {"floor": 130, "ceiling": 176},
                    "rankingChanges": [],
                }, f)
            with open(players_path, "w") as f:
                json.dump([{"name": "A"}, {"name": "B"}], f)
            with open(cap_path, "w") as f:
                json.dump({"rawSnapshot": "/not/tracked.json", "roundedFloor": 130, "roundedCeiling": 176}, f)
            with open(stats_path, "w") as f:
                json.dump({"keptPlayerRowsUpdated": 4}, f)

            subprocess.run(
                [sys.executable, SCRIPT_PATH,
                 "--result", result_path,
                 "--current-players", players_path,
                 "--cap-snapshot", cap_path,
                 "--data-dir", data_dir,
                 "--keeper-board-stats", stats_path,
                 "--test-status", "PASS",
                 "--pr-title-out", title_out,
                 "--pr-body-out", body_out],
                check=True, capture_output=True, text=True,
            )

            with open(os.path.join(data_dir, "cap_snapshot.json")) as f:
                cap_snapshot = json.load(f)
            self.assertNotIn("rawSnapshot", cap_snapshot)

            with open(os.path.join(data_dir, "provenance.json")) as f:
                provenance = json.load(f)
            self.assertEqual(provenance["normalizedPlayerCount"], 2)
            self.assertEqual(provenance["keeperBoardPlayerRowsUpdated"], 4)
            self.assertTrue(provenance["faDraftPoolRebuilt"])
            self.assertEqual(provenance["testStatus"], "PASS")

            with open(os.path.join(data_dir, "players_normalized.json")) as f:
                self.assertEqual(json.load(f), [{"name": "A"}, {"name": "B"}])

            self.assertTrue(os.path.isfile(title_out))
            self.assertTrue(os.path.isfile(body_out))


if __name__ == "__main__":
    unittest.main()
