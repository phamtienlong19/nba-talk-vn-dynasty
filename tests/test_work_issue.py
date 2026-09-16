"""End-to-end guard-clause tests for work-issue.sh, run against a throwaway
git repo with fake `gh`/`claude` on PATH -- no live network, GitHub auth,
or Claude invocation (see tests/_workflow_test_utils.py)."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from _workflow_test_utils import make_fake_bin, make_repo, git, run_script, write_fixture

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from issue_workflow import branch_name  # noqa: E402

OPEN_ISSUE = {
    "number": 5,
    "title": "John Collins cap is wrong",
    "url": "https://github.com/example/test-project/issues/5",
    "state": "OPEN",
    "labels": [{"name": "bug"}],
}

CLOSED_ISSUE = {**OPEN_ISSUE, "state": "CLOSED"}


class WorkIssueTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)
        self.fake_bin = make_fake_bin(self.tmp_dir)
        self.repo = make_repo(self.tmp_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def run_work_issue(self, args, env_extra=None):
        return run_script(self.repo, "work-issue.sh", args, self.fake_bin, env_extra)


class TestMissingOrInvalidArgs(WorkIssueTestCase):
    def test_missing_issue_number(self):
        result = self.run_work_issue([])
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage", result.stderr.lower())

    def test_non_numeric_issue_number(self):
        result = self.run_work_issue(["not-a-number"])
        self.assertEqual(result.returncode, 2)


class TestDirtyTreeRejected(WorkIssueTestCase):
    def test_dirty_tree_rejected(self):
        (self.repo / "tasks" / "ACTIVE.md").write_text("dirty change\n")
        result = self.run_work_issue(["5"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("dirty", result.stderr.lower())


class TestIssueFetchFailures(WorkIssueTestCase):
    def test_closed_issue_rejected(self):
        fixture = write_fixture(self.tmp_dir, "issue.json", CLOSED_ISSUE)
        result = self.run_work_issue(
            ["5"], env_extra={"FAKE_GH_ISSUE_FIXTURE": str(fixture)}
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("CLOSED", result.stderr)

    def test_nonexistent_issue_rejected(self):
        # No FAKE_GH_ISSUE_FIXTURE set -> fake gh simulates "not found".
        result = self.run_work_issue(["999"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not fetch issue", result.stderr.lower())


class TestSuccessfulRun(WorkIssueTestCase):
    def test_lightweight_active_pointer_generated(self):
        fixture = write_fixture(self.tmp_dir, "issue.json", OPEN_ISSUE)
        result = self.run_work_issue(
            ["5"], env_extra={"FAKE_GH_ISSUE_FIXTURE": str(fixture)}
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

        branch = git(self.repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.assertTrue(branch.startswith("fix/issue-5-"), branch)

        active_md = (self.repo / "tasks" / "ACTIVE.md").read_text()
        self.assertIn("Issue: #5", active_md)
        self.assertIn("Title: John Collins cap is wrong", active_md)
        self.assertIn(f"Branch: {branch}", active_md)
        # Lightweight: must not balloon into a full issue-body copy.
        self.assertLess(len(active_md), 1000)

        state = json.loads((self.repo / "ai_exchange" / "CURRENT_STATE.json").read_text())
        self.assertEqual(state["working"]["issue"], 5)
        self.assertEqual(state["working"]["branch"], branch)
        self.assertEqual(state["working"]["status"], "IN_PROGRESS")

    def test_rerun_reuses_existing_matching_branch(self):
        fixture = write_fixture(self.tmp_dir, "issue.json", OPEN_ISSUE)
        env = {"FAKE_GH_ISSUE_FIXTURE": str(fixture)}
        first = self.run_work_issue(["5"], env_extra=env)
        self.assertEqual(first.returncode, 0, msg=first.stdout + first.stderr)
        branch = git(self.repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()

        second = self.run_work_issue(["5"], env_extra=env)
        self.assertEqual(second.returncode, 0, msg=second.stdout + second.stderr)
        self.assertIn("reusing", second.stdout.lower())
        branch_after = git(self.repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.assertEqual(branch, branch_after)


class TestBranchCollision(WorkIssueTestCase):
    def test_existing_unrelated_branch_collision_is_refused(self):
        fixture = write_fixture(self.tmp_dir, "issue.json", OPEN_ISSUE)

        # Pre-create the exact branch name work-issue.sh would derive for
        # issue #5, but for unrelated content (no matching Issue: line).
        expected_branch = branch_name(5, OPEN_ISSUE["title"], ["bug"])
        git(self.repo, "checkout", "-b", expected_branch)
        (self.repo / "tasks" / "ACTIVE.md").write_text(
            "# Active Task\n\nSome unrelated manual work, not via work-issue.sh.\n"
        )
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "unrelated work on a colliding branch name")
        git(self.repo, "checkout", "main")

        result = self.run_work_issue(
            ["5"], env_extra={"FAKE_GH_ISSUE_FIXTURE": str(fixture)}
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stderr.lower())

        # Must not have silently switched onto / mutated the colliding branch.
        branch = git(self.repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.assertEqual(branch, "main")


if __name__ == "__main__":
    unittest.main()
