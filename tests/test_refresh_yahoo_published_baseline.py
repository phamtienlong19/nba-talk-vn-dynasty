"""Regression coverage for refresh-yahoo.sh's published-floor/ceiling
source. It used to hardcode PUBLISHED_FLOOR/CEILING = 130, 175, which
silently went stale the moment a later PR promoted a new canonical
floor/ceiling (131/177) -- every future refresh then reported CHANGED
forever, even with no real Yahoo movement, since it was being compared
against the wrong baseline. Fixed to read
ai_exchange/CURRENT_STATE.json's canonicalState.capFloor/capCeiling,
with the old hardcoded pair kept only as a defensive fallback.

Extracts the actual heredoc body out of refresh-yahoo.sh (not a
hand-copied duplicate) so this can't drift from what runs in CI/production.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
REFRESH_SCRIPT = os.path.join(REPO_ROOT, "refresh-yahoo.sh")


def _extract_heredoc_body():
    with open(REFRESH_SCRIPT, encoding="utf-8") as f:
        text = f.read()
    start_marker = "<<'PYEOF'\n"
    start = text.index(start_marker) + len(start_marker)
    end = text.index("\nPYEOF", start)
    return text[start:end]


HEREDOC_BODY = _extract_heredoc_body()


class TestPublishedBaselineSource(unittest.TestCase):
    def _run(self, tmp_dir, current_state=None):
        os.makedirs(os.path.join(tmp_dir, "scripts"), exist_ok=True)
        os.makedirs(os.path.join(tmp_dir, "local_data", "yahoo"), exist_ok=True)
        os.makedirs(os.path.join(tmp_dir, "ai_exchange"), exist_ok=True)

        import shutil
        shutil.copy(os.path.join(REPO_ROOT, "scripts", "cap_model.py"), os.path.join(tmp_dir, "scripts", "cap_model.py"))

        players = [{"name": f"P{i}", "oRank": i, "capDollars": 1.0, "sourceTimestamp": "2026-10-01T000000Z"} for i in range(1, 145)]
        with open(os.path.join(tmp_dir, "local_data", "yahoo", "players_normalized.json"), "w") as f:
            json.dump(players, f)

        if current_state is not None:
            with open(os.path.join(tmp_dir, "ai_exchange", "CURRENT_STATE.json"), "w") as f:
                json.dump(current_state, f)

        script_path = os.path.join(tmp_dir, "run.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(HEREDOC_BODY)

        result = subprocess.run(
            [sys.executable, script_path, "/tmp/not-a-real-raw-snapshot.json"],
            cwd=tmp_dir, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_uses_canonical_state_floor_and_ceiling_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout = self._run(tmp, current_state={"canonicalState": {"capFloor": 131, "capCeiling": 177}})
        self.assertIn("Current published board: 131-177", stdout)

    def test_falls_back_to_hardcoded_defaults_when_state_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout = self._run(tmp, current_state=None)
        self.assertIn("Current published board: 130-175", stdout)

    def test_falls_back_to_hardcoded_defaults_when_state_file_malformed(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "ai_exchange"), exist_ok=True)
            with open(os.path.join(tmp, "ai_exchange", "CURRENT_STATE.json"), "w") as f:
                f.write("{not valid json")
            os.makedirs(os.path.join(tmp, "scripts"), exist_ok=True)
            os.makedirs(os.path.join(tmp, "local_data", "yahoo"), exist_ok=True)
            import shutil
            shutil.copy(os.path.join(REPO_ROOT, "scripts", "cap_model.py"), os.path.join(tmp, "scripts", "cap_model.py"))
            players = [{"name": f"P{i}", "oRank": i, "capDollars": 1.0, "sourceTimestamp": "t"} for i in range(1, 145)]
            with open(os.path.join(tmp, "local_data", "yahoo", "players_normalized.json"), "w") as f:
                json.dump(players, f)
            script_path = os.path.join(tmp, "run.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(HEREDOC_BODY)
            result = subprocess.run(
                [sys.executable, script_path, "/tmp/not-a-real-raw-snapshot.json"],
                cwd=tmp, capture_output=True, text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Current published board: 130-175", result.stdout)

    def test_published_floor_ceiling_written_into_cap_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._run(tmp, current_state={"canonicalState": {"capFloor": 131, "capCeiling": 177}})
            with open(os.path.join(tmp, "local_data", "yahoo", "cap_snapshot_latest.json")) as f:
                snapshot = json.load(f)
        self.assertEqual(snapshot["publishedFloor"], 131)
        self.assertEqual(snapshot["publishedCeiling"], 177)


if __name__ == "__main__":
    unittest.main()
