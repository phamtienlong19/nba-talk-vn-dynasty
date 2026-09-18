import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from cap_model import compute_cap_model  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "prepare_yahoo_data_pr.py")


def _write(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


def _run_prepare_script(tmpdir, result, current_players, cap_snapshot, extra_args=None):
    result_path = os.path.join(tmpdir, "yahoo-refresh-result.json")
    current_players_path = os.path.join(tmpdir, "players_normalized.json")
    cap_snapshot_path = os.path.join(tmpdir, "cap_snapshot_latest.json")
    data_dir = os.path.join(tmpdir, "data", "yahoo")
    pr_title_path = os.path.join(tmpdir, "pr_title.txt")
    pr_body_path = os.path.join(tmpdir, "pr_body.md")

    _write(result_path, result)
    _write(current_players_path, current_players)
    _write(cap_snapshot_path, cap_snapshot)

    args = [
        sys.executable, SCRIPT,
        "--result", result_path,
        "--current-players", current_players_path,
        "--cap-snapshot", cap_snapshot_path,
        "--data-dir", data_dir,
        "--pr-title-out", pr_title_path,
        "--pr-body-out", pr_body_path,
    ]
    if extra_args:
        args += extra_args

    subprocess.run(args, check=True, capture_output=True, text=True)

    with open(pr_title_path, encoding="utf-8") as f:
        title = f.read()
    with open(pr_body_path, encoding="utf-8") as f:
        body = f.read()
    return data_dir, title, body


class TestPrepareYahooDataPR(unittest.TestCase):
    def test_changed_snapshot_writes_candidate_files_and_pr_text(self):
        result = {
            "source": "478.l.public",
            "fetchedAt": "2026-09-18T030405Z",
            "status": "CHANGED",
            "previous": {"floor": 130, "ceiling": 175},
            "current": {"floor": 131, "ceiling": 177},
            "rankingChanges": [
                {"oRank": 5, "previousPlayer": "Old Guy", "currentPlayer": "New Guy"},
            ],
        }
        current_players = [{"oRank": 1, "name": "A", "playerId": "1"}]
        cap_snapshot = {
            "fetchedAt": "2026-09-18T030405Z",
            "rawSnapshot": "/some/local/gitignored/path.json",
            "bands": [1.0] * 9,
            "benchmark": 152.5,
            "rawFloor": 129.6,
            "rawCeiling": 175.4,
            "roundedFloor": 131,
            "roundedCeiling": 177,
            "publishedFloor": 130,
            "publishedCeiling": 175,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir, title, body = _run_prepare_script(
                tmpdir, result, current_players, cap_snapshot,
                extra_args=[
                    "--run-id", "12345",
                    "--run-attempt", "1",
                    "--repository", "phamtienlong19/nba-talk-vn-dynasty",
                    "--server-url", "https://github.com",
                ],
            )

            with open(os.path.join(data_dir, "players_normalized.json")) as f:
                self.assertEqual(json.load(f), current_players)

            with open(os.path.join(data_dir, "cap_snapshot.json")) as f:
                written_cap_snapshot = json.load(f)
            self.assertNotIn("rawSnapshot", written_cap_snapshot)
            self.assertEqual(written_cap_snapshot["roundedFloor"], 131)

            with open(os.path.join(data_dir, "provenance.json")) as f:
                provenance = json.load(f)
            self.assertEqual(provenance["source"], "478.l.public")
            self.assertEqual(provenance["workflowRunId"], "12345")
            self.assertEqual(provenance["workflowRunAttempt"], "1")
            self.assertEqual(
                provenance["workflowRunUrl"],
                "https://github.com/phamtienlong19/nba-talk-vn-dynasty/actions/runs/12345/attempts/1",
            )
            self.assertEqual(provenance["normalizedPlayerCount"], 1)
            self.assertEqual(provenance["derivedFloor"], 131)
            self.assertEqual(provenance["derivedCeiling"], 177)

        self.assertIn("2026-09-18", title)

        self.assertIn("130 / 175", body)
        self.assertIn("131 / 177", body)
        self.assertIn("R5: Old Guy → New Guy", body)
        self.assertIn("actions/runs/12345", body)
        self.assertIn("Merging this PR is", body)
        self.assertIn("Propagate canonical Yahoo refresh", body)

    def test_no_ranking_changes_note_falls_back_in_body(self):
        result = {
            "source": "478.l.public",
            "fetchedAt": "2026-09-18T030405Z",
            "status": "CHANGED",
            "previous": {"floor": 130, "ceiling": 175},
            "current": {"floor": 131, "ceiling": 177},
            "rankingChanges": [],
            "rankingChangesNote": "no previous tracked-run snapshot available",
        }
        current_players = [{"oRank": 1, "name": "A"}]
        cap_snapshot = {
            "fetchedAt": "2026-09-18T030405Z",
            "roundedFloor": 131, "roundedCeiling": 177,
            "publishedFloor": 130, "publishedCeiling": 175,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            _, _, body = _run_prepare_script(tmpdir, result, current_players, cap_snapshot)

        self.assertIn("no previous tracked-run snapshot available", body)

    def test_does_not_touch_files_outside_data_dir(self):
        result = {
            "source": "478.l.public",
            "fetchedAt": "2026-09-18T030405Z",
            "status": "CHANGED",
            "previous": {"floor": 130, "ceiling": 175},
            "current": {"floor": 131, "ceiling": 177},
            "rankingChanges": [],
        }
        current_players = [{"oRank": 1, "name": "A"}]
        cap_snapshot = {
            "fetchedAt": "2026-09-18T030405Z",
            "roundedFloor": 131, "roundedCeiling": 177,
            "publishedFloor": 130, "publishedCeiling": 175,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            index_path = os.path.join(tmpdir, "index.html")
            keepers_path = os.path.join(tmpdir, "data", "2026-27", "prekeeper_rosters.json")
            os.makedirs(os.path.dirname(keepers_path))
            with open(index_path, "w") as f:
                f.write("<html>untouched</html>")
            with open(keepers_path, "w") as f:
                f.write('{"untouched": true}')

            _run_prepare_script(tmpdir, result, current_players, cap_snapshot)

            with open(index_path) as f:
                self.assertEqual(f.read(), "<html>untouched</html>")
            with open(keepers_path) as f:
                self.assertEqual(f.read(), '{"untouched": true}')


class TestCandidateCapDerivesFromCandidatePlayers(unittest.TestCase):
    def test_written_cap_snapshot_matches_recompute_from_written_players(self):
        players = [
            {"oRank": r, "capDollars": float(300 - r)}
            for r in range(1, 145)
        ]
        computed = compute_cap_model(players)

        result = {
            "source": "478.l.public",
            "fetchedAt": "2026-09-18T030405Z",
            "status": "CHANGED",
            "previous": {"floor": 130, "ceiling": 175},
            "current": {"floor": computed["roundedFloor"], "ceiling": computed["roundedCeiling"]},
            "rankingChanges": [],
        }
        cap_snapshot = {
            "fetchedAt": "2026-09-18T030405Z",
            "rawSnapshot": "/some/local/gitignored/path.json",
            "bands": computed["bands"],
            "benchmark": computed["benchmark"],
            "rawFloor": computed["rawFloor"],
            "rawCeiling": computed["rawCeiling"],
            "roundedFloor": computed["roundedFloor"],
            "roundedCeiling": computed["roundedCeiling"],
            "publishedFloor": 130,
            "publishedCeiling": 175,
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir, _, _ = _run_prepare_script(tmpdir, result, players, cap_snapshot)

            with open(os.path.join(data_dir, "players_normalized.json")) as f:
                written_players = json.load(f)
            with open(os.path.join(data_dir, "cap_snapshot.json")) as f:
                written_cap_snapshot = json.load(f)

        # The whole point of shipping cap_snapshot.json alongside
        # players_normalized.json: a downstream consumer with no network
        # access must be able to recompute the same cap model from the
        # committed player snapshot and get the committed cap numbers back.
        recomputed = compute_cap_model(written_players)
        self.assertEqual(recomputed["roundedFloor"], written_cap_snapshot["roundedFloor"])
        self.assertEqual(recomputed["roundedCeiling"], written_cap_snapshot["roundedCeiling"])
        self.assertEqual(recomputed["bands"], written_cap_snapshot["bands"])
        self.assertEqual(recomputed["benchmark"], written_cap_snapshot["benchmark"])


if __name__ == "__main__":
    unittest.main()
