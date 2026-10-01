"""End-to-end tests for promote-yahoo-refresh.sh, run against a throwaway
git repo with a fake `gh` on PATH -- no live network or GitHub auth (see
tests/_yahoo_promote_test_utils.py).

Covers the required regression matrix for the Yahoo-refresh PR-automation
fix: MATCH must not open a PR; CHANGED must write candidate files, push a
branch, and create/update exactly one PR; CHANGED with no PR actually
listable afterwards must fail the whole run rather than report success.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from _yahoo_promote_test_utils import (
    make_fake_bin,
    make_repo,
    git,
    run_promote,
    write_result_json,
)

BRANCH = "automation/yahoo-refresh"


class PromoteYahooRefreshTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)
        self.fake_bin = make_fake_bin(self.tmp_dir)
        self.repo = make_repo(self.tmp_dir)
        self.fake_gh_state = self.tmp_dir / "fake-gh-pr-state.json"
        self.origin = self.tmp_dir / "origin.git"

    def tearDown(self):
        self._tmp.cleanup()

    def run_promote(self, status, env_extra=None, **result_kwargs):
        result_json = write_result_json(self.repo, status, **result_kwargs)
        return run_promote(self.repo, result_json, self.fake_bin, self.fake_gh_state, env_extra)


class TestMatchTakesNoAction(PromoteYahooRefreshTestCase):
    def test_match_opens_no_pr_and_touches_nothing(self):
        result = self.run_promote("MATCH")
        self.assertEqual(result.returncode, 0, result.stderr)

        # No automation branch anywhere -- neither local nor pushed.
        local_branches = git(self.repo, "branch", "--list", BRANCH).stdout
        self.assertEqual(local_branches.strip(), "")
        remote_refs = subprocess.run(
            ["git", "ls-remote", str(self.origin), f"refs/heads/{BRANCH}"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertEqual(remote_refs.strip(), "")

        self.assertFalse((self.repo / "data").exists())
        self.assertFalse(self.fake_gh_state.exists(), "no PR should have been created on MATCH")


class TestChangedWritesCandidateFiles(PromoteYahooRefreshTestCase):
    def test_candidate_data_files_and_board_regen_are_written(self):
        result = self.run_promote("CHANGED")
        self.assertEqual(result.returncode, 0, result.stderr)

        for name in ("players_normalized.json", "cap_snapshot.json", "provenance.json"):
            self.assertTrue((self.repo / "data" / "yahoo" / name).exists(), f"missing data/yahoo/{name}")

        provenance = json.loads((self.repo / "data" / "yahoo" / "provenance.json").read_text())
        self.assertEqual(provenance["derivedFloor"], 130)
        self.assertEqual(provenance["derivedCeiling"], 176)
        self.assertTrue(provenance["faDraftPoolRebuilt"])
        self.assertEqual(provenance["testStatus"], "PASS")

        cap_snapshot = json.loads((self.repo / "data" / "yahoo" / "cap_snapshot.json").read_text())
        self.assertNotIn("rawSnapshot", cap_snapshot, "local/gitignored raw-snapshot path must not be committed")

        # Mechanical keeper-board display refresh actually touched the one
        # kept player whose Yahoo fixture data differs from index.html.
        index_html = (self.repo / "index.html").read_text()
        self.assertIn(
            '<div class="pname">Kept Player One</div><div class="nba">BBB</div><div class="cap">15</div>',
            index_html,
        )
        # Roster membership itself is untouched -- still exactly one kept row.
        self.assertEqual(index_html.count('<div class="pname">'), 1)

        stats = json.loads((self.repo / "artifacts" / "yahoo-refresh" / "keeper_board_stats.json").read_text())
        self.assertEqual(stats["keptPlayerRowsUpdated"], 1)

    def test_discretionary_keeper_selection_is_never_changed(self):
        before = (self.repo / "index.html").read_text()
        before_kept_names = ["Kept Player One"]  # only kept player in the fixture
        self.run_promote("CHANGED")
        after = (self.repo / "index.html").read_text()
        for name in before_kept_names:
            self.assertIn(name, after)
        self.assertEqual(before.count("player-row"), after.count("player-row"))


class TestChangedPushesBranch(PromoteYahooRefreshTestCase):
    def test_branch_is_pushed_to_origin_with_a_real_commit(self):
        result = self.run_promote("CHANGED")
        self.assertEqual(result.returncode, 0, result.stderr)

        remote_refs = subprocess.run(
            ["git", "ls-remote", str(self.origin), f"refs/heads/{BRANCH}"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertNotEqual(remote_refs.strip(), "", "automation/yahoo-refresh was never pushed to origin")

        log = subprocess.run(
            ["git", "log", "-1", "--format=%s", f"refs/heads/{BRANCH}"],
            cwd=self.origin, capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertIn("refresh Yahoo rankings", log)


class TestChangedOpensOrUpdatesExactlyOnePr(PromoteYahooRefreshTestCase):
    def test_pr_is_created_when_none_exists(self):
        result = self.run_promote("CHANGED")
        self.assertEqual(result.returncode, 0, result.stderr)

        state = json.loads(self.fake_gh_state.read_text())
        self.assertEqual(state["number"], 1)
        self.assertIn(f"#{state['number']}", result.stdout)
        self.assertIn(state["url"], result.stdout)

        pr_number_artifact = (self.repo / "artifacts" / "yahoo-refresh" / "pr_number.txt").read_text().strip()
        self.assertEqual(pr_number_artifact, "1")

    def test_existing_open_pr_is_updated_not_duplicated(self):
        self.fake_gh_state.write_text(json.dumps({
            "number": 7, "url": "https://github.com/example/test-project/pull/7",
        }))
        call_log = self.tmp_dir / "gh-calls.log"
        result = self.run_promote("CHANGED", env_extra={"FAKE_GH_CALL_LOG": str(call_log)})
        self.assertEqual(result.returncode, 0, result.stderr)

        self.assertIn("pr edit", call_log.read_text())
        self.assertNotIn("pr create", call_log.read_text())

        # Still exactly the one PR -- number unchanged, no second PR made.
        state = json.loads(self.fake_gh_state.read_text())
        self.assertEqual(state["number"], 7)


class TestChangedWithNoPrFailsTheRun(PromoteYahooRefreshTestCase):
    def test_silent_create_failure_fails_the_whole_run(self):
        """gh pr create exits 0 but no PR is actually listable afterwards --
        the script's own post-create assertion (not just `set -e`) must
        catch this and fail, never report green success."""
        result = self.run_promote("CHANGED", env_extra={"FAKE_GH_SILENT_CREATE_FAILURE": "1"})
        self.assertNotEqual(result.returncode, 0, "CHANGED with no resulting PR must fail the run")
        self.assertIn("no open PR exists", result.stdout + result.stderr)

        # The branch may have been pushed (the data is real and fine to
        # keep), but there must be no PR state anywhere.
        self.assertFalse(self.fake_gh_state.exists())


if __name__ == "__main__":
    unittest.main()
