"""Regression coverage for refresh-yahoo.sh's cap handling.

The OFFICIAL league band (config/cap_policy.json, currently 131-178) is
commissioner governance, separate from the formula-derived band (131-177 on
the current snapshot). A refresh must report formula-vs-approved status but
never overwrite the official band with the formula result.

Extracts the actual heredoc body out of refresh-yahoo.sh (not a
hand-copied duplicate) so this can't drift from what runs in CI/production.
"""
import json
import shutil
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


FIXTURE_MD = os.path.join(REPO_ROOT, "tests", "fixtures", "yahoo_top300_2026-10-04.md")


def _snapshot_players():
    sys.path.insert(0, os.path.join(REPO_ROOT, "scripts"))
    from export_yahoo_top300 import parse_markdown
    with open(FIXTURE_MD, encoding="utf-8") as f:
        rows = parse_markdown(f.read())
    return [{"name": n, "oRank": r, "capDollars": float(d), "sourceTimestamp": "2026-10-04T000000Z"}
            for n, d, r in rows]


class TestOfficialCapPolicyInRefresh(unittest.TestCase):
    def _run(self, tmp_dir, players, policy=None):
        os.makedirs(os.path.join(tmp_dir, "scripts"), exist_ok=True)
        os.makedirs(os.path.join(tmp_dir, "config"), exist_ok=True)
        os.makedirs(os.path.join(tmp_dir, "local_data", "yahoo"), exist_ok=True)
        shutil.copy(os.path.join(REPO_ROOT, "scripts", "cap_model.py"), os.path.join(tmp_dir, "scripts", "cap_model.py"))
        shutil.copy(os.path.join(REPO_ROOT, "config", "cap_policy.json"), os.path.join(tmp_dir, "config", "cap_policy.json"))
        if policy is not None:
            with open(os.path.join(tmp_dir, "config", "cap_policy.json"), "w") as f:
                json.dump(policy, f)
        with open(os.path.join(tmp_dir, "local_data", "yahoo", "players_normalized.json"), "w") as f:
            json.dump(players, f)
        script_path = os.path.join(tmp_dir, "run.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(HEREDOC_BODY)
        result = subprocess.run(
            [sys.executable, script_path, "/tmp/not-a-real-raw-snapshot.json"],
            cwd=tmp_dir, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(os.path.join(tmp_dir, "local_data", "yahoo", "cap_snapshot_latest.json")) as f:
            return result.stdout, json.load(f)

    def test_current_snapshot_official_178_formula_177_raw_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            stdout, snap = self._run(tmp, _snapshot_players())
        self.assertAlmostEqual(snap["rawCeiling"], 177.3875)
        self.assertEqual((snap["formulaFloor"], snap["formulaCeiling"]), (131, 177))
        self.assertEqual((snap["officialFloor"], snap["officialCeiling"]), (131, 178))
        self.assertTrue(snap["ceilingOverride"])
        self.assertIn("Commissioner confirmed", snap["overrideReason"])
        self.assertEqual((snap["publishedFloor"], snap["publishedCeiling"]), (131, 178))
        self.assertIn("Status: MATCH", stdout)

    def test_refresh_never_overwrites_official_ceiling_with_formula_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            players = [{"name": f"P{i}", "oRank": i, "capDollars": 1.0, "sourceTimestamp": "t"} for i in range(1, 145)]
            stdout, snap = self._run(tmp, players)
        self.assertNotEqual(snap["formulaCeiling"], 178)
        self.assertEqual(snap["officialCeiling"], 178)
        self.assertEqual(snap["publishedCeiling"], 178)
        self.assertIn("CHANGED", stdout)  # formula moved off the approved baseline -> human review

    def test_status_compares_formula_to_approved_formula_not_to_official(self):
        policy = {"officialFloor": 131, "officialCeiling": 178, "approvedFormulaFloor": 131,
                  "approvedFormulaCeiling": 177, "overrideReason": "x"}
        with tempfile.TemporaryDirectory() as tmp:
            stdout, _ = self._run(tmp, _snapshot_players(), policy)
        self.assertIn("Status: MATCH", stdout)


if __name__ == "__main__":
    unittest.main()
