"""End-to-end tests for sync-after-merge.sh, run against a throwaway git
repo with a fake `gh` on PATH -- no live network or GitHub auth (see
tests/_workflow_test_utils.py)."""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from _workflow_test_utils import (
    CALL_LOG_NAME,
    make_fake_bin,
    make_repo,
    git,
    run_script,
    write_fixture,
)

try:
    import pty
except ImportError:  # pragma: no cover - pty is Unix-only; this repo targets macOS/Linux
    pty = None


class SyncAfterMergeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)
        self.fake_bin = make_fake_bin(self.tmp_dir)
        self.repo = make_repo(self.tmp_dir)

    def tearDown(self):
        self._tmp.cleanup()

    def run_sync(self, args, env_extra=None, stdin=subprocess.DEVNULL):
        return run_script(self.repo, "sync-after-merge.sh", args, self.fake_bin, env_extra, stdin=stdin)

    def call_log_lines(self):
        """Lines recorded by the fake validate/test/handoff commands (see
        _workflow_test_utils.FAKE_CALL_LOG) -- empty if none ran."""
        log_path = self.fake_bin.parent / CALL_LOG_NAME
        if not log_path.exists():
            return []
        return log_path.read_text().splitlines()


class TestUnmergedPrRejected(SyncAfterMergeTestCase):
    def test_open_pr_rejected(self):
        fixture = write_fixture(
            self.tmp_dir,
            "pr.json",
            {
                "number": 7,
                "url": "https://github.com/example/test-project/pull/7",
                "state": "OPEN",
                "mergeCommit": None,
                "headRefName": "fix/issue-7-something",
                "closingIssuesReferences": [],
                "title": "Something",
            },
        )
        result = self.run_sync(["7"], env_extra={"FAKE_GH_PR_FIXTURE": str(fixture)})
        self.assertEqual(result.returncode, 1)
        self.assertIn("not merged", result.stderr.lower())


class TestDirtyTreeRejected(SyncAfterMergeTestCase):
    def test_dirty_tree_rejected(self):
        (self.repo / "tasks" / "ACTIVE.md").write_text("dirty\n")
        result = self.run_sync(["7"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("dirty", result.stderr.lower())


class TestMergedPrSyncsMain(SyncAfterMergeTestCase):
    def _simulate_merged_pr(self, issue_number=9, title="Fix the thing"):
        """Create a feature branch carrying a real work-issue.sh-style
        tasks/ACTIVE.md pointer, merge it into main for real (so the
        merge commit genuinely exists and is an ancestor of main), and
        return (merge_commit_sha, branch_name)."""
        branch = f"fix/issue-{issue_number}-the-thing"
        git(self.repo, "checkout", "-b", branch)
        active_md = (
            "# Active Task\n\n"
            f"Issue: #{issue_number}\n"
            f"URL: https://github.com/example/test-project/issues/{issue_number}\n"
            f"Title: {title}\n"
            f"Branch: {branch}\n"
            "Canonical specification: GitHub Issue\n"
            "Generated: 2026-01-01T00:00:00Z\n"
        )
        (self.repo / "tasks" / "ACTIVE.md").write_text(active_md)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", f"implement issue #{issue_number}")
        git(self.repo, "checkout", "main")
        git(self.repo, "merge", "--no-ff", branch, "-m", f"Merge PR: {title}")
        git(self.repo, "push", "origin", "main")
        merge_sha = git(self.repo, "rev-parse", "HEAD").stdout.strip()
        return merge_sha, branch

    def test_merged_pr_syncs_state_and_archives_task(self):
        merge_sha, branch = self._simulate_merged_pr()
        fixture = write_fixture(
            self.tmp_dir,
            "pr.json",
            {
                "number": 9,
                "url": "https://github.com/example/test-project/pull/9",
                "state": "MERGED",
                "mergeCommit": {"oid": merge_sha},
                "headRefName": branch,
                "closingIssuesReferences": [
                    {"number": 9, "url": "https://github.com/example/test-project/issues/9"}
                ],
                "title": "Fix the thing",
            },
        )
        # Non-interactive stdin -> branch deletion prompt is auto-skipped.
        result = self.run_sync(["9"], env_extra={"FAKE_GH_PR_FIXTURE": str(fixture)})
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

        # The re-validate step ran the fake validate/test/handoff commands
        # (injected via SYNC_AFTER_MERGE_{VALIDATE,TEST,HANDOFF}_CMD, see
        # _workflow_test_utils.py) rather than being skipped or recursively
        # re-running the real ./validate.sh / full unit suite / ./handoff.sh.
        self.assertEqual(self.call_log_lines(), ["validate", "test", "handoff"])

        # ACTIVE task cleared...
        active_md = (self.repo / "tasks" / "ACTIVE.md").read_text()
        self.assertIn("No active task", active_md)
        self.assertNotIn("Issue: #9", active_md)

        # ...and archived.
        archive_dir = self.repo / "tasks" / "archive"
        archived = [p for p in archive_dir.iterdir() if p.name != ".gitkeep"]
        self.assertEqual(len(archived), 1, archived)
        archived_content = archived[0].read_text()
        self.assertIn("#9", archived_content)
        self.assertIn("pull/9", archived_content)
        self.assertIn(merge_sha, archived_content)

        # State refreshed.
        state = json.loads((self.repo / "ai_exchange" / "CURRENT_STATE.json").read_text())
        self.assertEqual(state["deployed"]["commit"], merge_sha)
        self.assertEqual(state["working"]["issue"], None)
        self.assertEqual(state["working"]["status"], "NONE")

        # Deployment-freshness marker refreshed to the new main HEAD.
        build_json = json.loads((self.repo / "build.json").read_text())
        self.assertEqual(build_json["commit"], merge_sha)

        # Everything landed as a real commit on main, pushed to origin.
        self.assertEqual(
            git(self.repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip(), "main"
        )
        log = git(self.repo, "log", "--oneline", "-1").stdout
        self.assertIn("sync", log.lower())

    def test_rerun_when_nothing_changed_is_a_clean_noop(self):
        merge_sha, branch = self._simulate_merged_pr(issue_number=11, title="Another fix")
        fixture = write_fixture(
            self.tmp_dir,
            "pr.json",
            {
                "number": 11,
                "url": "https://github.com/example/test-project/pull/11",
                "state": "MERGED",
                "mergeCommit": {"oid": merge_sha},
                "headRefName": branch,
                "closingIssuesReferences": [],
                "title": "Another fix",
            },
        )
        first = self.run_sync(["11"], env_extra={"FAKE_GH_PR_FIXTURE": str(fixture)})
        self.assertEqual(first.returncode, 0, msg=first.stdout + first.stderr)

        # A rerun for the same already-synced PR is a clean no-op: no
        # duplicate archive files, and the build.json / ACTIVE.md state
        # stays anchored to the same PR.
        second = self.run_sync(["11"], env_extra={"FAKE_GH_PR_FIXTURE": str(fixture)})
        self.assertEqual(second.returncode, 0, msg=second.stdout + second.stderr)

        archive_dir = self.repo / "tasks" / "archive"
        archived = [p for p in archive_dir.iterdir() if p.name != ".gitkeep"]
        self.assertEqual(len(archived), 1, archived)

        active_md = (self.repo / "tasks" / "ACTIVE.md").read_text()
        self.assertIn("No active task", active_md)

        build_json = json.loads((self.repo / "build.json").read_text())
        self.assertEqual(build_json["commit"], merge_sha)

        # The fake validate/test/handoff commands ran once per invocation
        # (two runs -> six lines), never the real, self-recursing versions.
        self.assertEqual(
            self.call_log_lines(),
            ["validate", "test", "handoff", "validate", "test", "handoff"],
        )

    def test_deployment_freshness_check_is_deterministic_when_public_url_set(self):
        """When a real publicUrl is configured, the merged-PR path must run
        the deployment-freshness check -- but through the injected
        DEPLOYMENT_FRESHNESS_FETCH_CMD (see _workflow_test_utils.py), not a
        real HTTP poll. This proves the check itself is exercised and stays
        fast/offline rather than merely being skipped."""
        state_path = self.repo / "ai_exchange" / "CURRENT_STATE.json"
        state = json.loads(state_path.read_text())
        state["publicUrl"] = "https://example.test/site/"
        state_path.write_text(json.dumps(state, indent=2) + "\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-m", "configure publicUrl")
        git(self.repo, "push", "origin", "main")

        merge_sha, branch = self._simulate_merged_pr(issue_number=42, title="Freshness check")
        fixture = write_fixture(
            self.tmp_dir,
            "pr.json",
            {
                "number": 42,
                "url": "https://github.com/example/test-project/pull/42",
                "state": "MERGED",
                "mergeCommit": {"oid": merge_sha},
                "headRefName": branch,
                "closingIssuesReferences": [],
                "title": "Freshness check",
            },
        )
        result = self.run_sync(["42"], env_extra={"FAKE_GH_PR_FIXTURE": str(fixture)})
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        self.assertIn("Deployment:    FRESH", result.stdout)

    def test_real_test_command_stays_scoped_and_does_not_recurse(self):
        """Regression test for the reported root cause: with
        SYNC_AFTER_MERGE_{VALIDATE,TEST,HANDOFF}_CMD left unset (production
        defaults -- real ./validate.sh, real `python3 -m unittest discover
        -s tests`, real ./handoff.sh, which internally runs that same
        discovery again), the internal test run must only discover this
        throwaway repo's own single smoke test. It must NOT reach back into
        the real outer suite that is running this very test method -- that
        would be this test recursively invoking itself."""
        merge_sha, branch = self._simulate_merged_pr(issue_number=99, title="No recursion")
        fixture = write_fixture(
            self.tmp_dir,
            "pr.json",
            {
                "number": 99,
                "url": "https://github.com/example/test-project/pull/99",
                "state": "MERGED",
                "mergeCommit": {"oid": merge_sha},
                "headRefName": branch,
                "closingIssuesReferences": [],
                "title": "No recursion",
            },
        )
        result = self.run_sync(
            ["99"],
            env_extra={
                "FAKE_GH_PR_FIXTURE": str(fixture),
                "SYNC_AFTER_MERGE_VALIDATE_CMD": "",
                "SYNC_AFTER_MERGE_TEST_CMD": "",
                "SYNC_AFTER_MERGE_HANDOFF_CMD": "",
            },
        )
        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

        # Nothing was faked for this run, so the call log stays untouched.
        self.assertEqual(self.call_log_lines(), [])

        test_log = Path("/tmp/dynasty_sync_tests.log").read_text()
        self.assertIn("Ran 1 test", test_log)
        self.assertNotIn("test_merged_pr_syncs_state_and_archives_task", test_log)
        self.assertNotIn("test_real_test_command_stays_scoped", test_log)

    @unittest.skipUnless(pty, "pty module unavailable (Unix-only)")
    def test_stdin_tty_dependence_is_the_root_cause_of_the_reported_hang(self):
        """Regression test for the reported "intermittent 30s hang, macOS
        only" bug (issue #11 follow-up). The real mechanism isn't OS-specific:
        sync-after-merge.sh's branch-deletion step probes `[ -t 0 ]` and, if
        stdin is a tty, blocks on an interactive `read` (see that step's
        `stage "delete-local-branch:interactive-prompt"` marker). All other
        tests in this file run with run_script()'s default stdin=DEVNULL,
        which deterministically takes the non-interactive fallback no matter
        what tty the invoking test runner itself has. This test proves the
        *mechanism* directly by handing the script a real pty as stdin --
        reproducing why running the suite from an interactive terminal
        (common on macOS; uncommon in scripted CI) used to hang until the
        30s subprocess timeout, while providing queued input here so this
        test itself completes quickly instead of hanging.
        """
        merge_sha, branch = self._simulate_merged_pr(issue_number=123, title="tty regression")
        fixture = write_fixture(
            self.tmp_dir,
            "pr.json",
            {
                "number": 123,
                "url": "https://github.com/example/test-project/pull/123",
                "state": "MERGED",
                "mergeCommit": {"oid": merge_sha},
                "headRefName": branch,
                "closingIssuesReferences": [],
                "title": "tty regression",
            },
        )

        master_fd, slave_fd = pty.openpty()
        try:
            # Queue the "decline" answer before the script ever reads, so a
            # real tty stdin still lets this test finish quickly -- an
            # inherited tty with nothing queued (the actual reported bug) is
            # exactly what would block on `read` until the 30s timeout.
            os.write(master_fd, b"n\n")
            result = self.run_sync(
                ["123"],
                env_extra={"FAKE_GH_PR_FIXTURE": str(fixture)},
                stdin=slave_fd,
            )
        finally:
            os.close(master_fd)
            os.close(slave_fd)

        self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
        # Proves the script actually took the interactive branch (tty stdin
        # -> reads our queued "n" -> declines deletion), not the
        # non-interactive fallback every other test exercises.
        self.assertIn("SYNC-STAGE: delete-local-branch:interactive-prompt", result.stderr)
        self.assertIn("kept (declined)", result.stdout)


if __name__ == "__main__":
    unittest.main()
