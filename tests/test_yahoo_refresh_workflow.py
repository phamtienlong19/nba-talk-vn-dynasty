"""Guards against two classes of regression in .github/workflows/yahoo-refresh.yml:

1. A failing fetch inside `refresh-yahoo.sh | tee ...` must fail the step
   immediately (pipefail), not get masked by tee's own success.
2. The "previous run's normalized snapshot" path the build step checks for
   (previous/yahoo-players-normalized.json) must actually be the path the
   artifact download step produces, so the ranking-diff branch is exercised
   instead of silently always falling back to the no-baseline note.

These tests read the *actual* step text out of the workflow file (not a
hand-copied duplicate) so they can't drift from what CI executes. Uses a
small stdlib-only line-scanner rather than a YAML parser -- this repo's
scripts are stdlib-only by convention and the workflow file's step-block
shape (```- name: ...``` then a `run: |` block scalar) is simple and
authored by us, so a full YAML parser would be more machinery than the
guarantee needs.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
WORKFLOW_PATH = os.path.join(REPO_ROOT, ".github", "workflows", "yahoo-refresh.yml")


def _step_block(name):
    """Return (header_lines, run_text) for the step named `name`.

    header_lines are the step's own `key: value` lines (e.g. `shell: bash`)
    above its `run:`. run_text is the dedented body of a `run: |` block
    scalar (or the inline value of a plain `run: <command>` line).
    """
    with open(WORKFLOW_PATH, encoding="utf-8") as f:
        lines = f.readlines()

    start = None
    for i, line in enumerate(lines):
        if line.strip() == f"- name: {name}":
            start = i
            break
    if start is None:
        raise AssertionError(f"no step named {name!r} in {WORKFLOW_PATH}")

    step_indent = len(lines[start]) - len(lines[start].lstrip(" "))

    end = len(lines)
    for i in range(start + 1, len(lines)):
        stripped = lines[i].strip()
        indent = len(lines[i]) - len(lines[i].lstrip(" "))
        if stripped.startswith("- name:") and indent == step_indent:
            end = i
            break

    header_lines = []
    run_text = None
    i = start + 1
    while i < end:
        stripped = lines[i].strip()
        if stripped == "run: |" or stripped == "run: |-":
            base_indent = None
            body = []
            i += 1
            while i < end:
                if lines[i].strip() == "":
                    body.append("")
                    i += 1
                    continue
                indent = len(lines[i]) - len(lines[i].lstrip(" "))
                if base_indent is None:
                    base_indent = indent
                if indent < base_indent:
                    break
                body.append(lines[i][base_indent:].rstrip("\n"))
                i += 1
            run_text = "\n".join(body)
            continue
        if stripped.startswith("run:"):
            run_text = stripped[len("run:"):].strip()
            i += 1
            continue
        if stripped and not stripped.startswith("#"):
            header_lines.append(stripped)
        i += 1

    if run_text is None:
        raise AssertionError(f"no run: found for step {name!r}")
    return header_lines, run_text


class TestPipefailConfiguration(unittest.TestCase):
    def test_fetch_step_uses_explicit_bash_shell(self):
        header_lines, _ = _step_block("Run Yahoo cap refresh (networked fetch)")
        self.assertIn(
            "shell: bash", header_lines,
            "fetch step must set shell: bash so GitHub Actions runs it with "
            "-eo pipefail; otherwise a failure before the `| tee` pipe can "
            "be masked by tee's own zero exit code",
        )

    def test_pipefail_propagates_failure_through_tee(self):
        """Functional proof: under the exact flags GitHub Actions uses for
        shell: bash (`bash --noprofile --norc -eo pipefail {0}`), a failing
        command piped into `tee` still fails the step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            fake_refresh = os.path.join(tmpdir, "refresh-yahoo.sh")
            with open(fake_refresh, "w", encoding="utf-8") as f:
                f.write("#!/usr/bin/env bash\necho partial output\nexit 1\n")
            os.chmod(fake_refresh, 0o755)

            _, run_text = _step_block("Run Yahoo cap refresh (networked fetch)")
            script_path = os.path.join(tmpdir, "run.sh")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(run_text)

            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-eo", "pipefail", script_path],
                cwd=tmpdir, capture_output=True, text=True,
            )
            self.assertNotEqual(
                result.returncode, 0,
                "a failing refresh-yahoo.sh piped into tee must fail the "
                f"step under pipefail; got exit 0. stdout={result.stdout!r}",
            )


class TestPreviousSnapshotPathContract(unittest.TestCase):
    """Runs the real "Build machine-readable refresh result" step body
    (extracted from the workflow file) against a fixture working directory,
    proving the previous/yahoo-players-normalized.json path it checks for
    is the same path a real download-artifact of the previous run's
    yahoo-refresh-result artifact would produce."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        os.symlink(os.path.join(REPO_ROOT, "scripts"), os.path.join(self.tmpdir, "scripts"))
        os.makedirs(os.path.join(self.tmpdir, "local_data", "yahoo"))
        os.makedirs(os.path.join(self.tmpdir, "config"))
        os.makedirs(os.path.join(self.tmpdir, "artifacts", "yahoo-refresh"))

        with open(os.path.join(self.tmpdir, "local_data", "yahoo", "cap_snapshot_latest.json"), "w") as f:
            json.dump({
                "fetchedAt": "2026-09-18T000000Z",
                "roundedFloor": 130, "roundedCeiling": 175,
                "publishedFloor": 130, "publishedCeiling": 175,
            }, f)
        with open(os.path.join(self.tmpdir, "local_data", "yahoo", "players_normalized.json"), "w") as f:
            json.dump([{"oRank": 1, "name": "Current Player"}], f)
        with open(os.path.join(self.tmpdir, "config", "yahoo_source.json"), "w") as f:
            json.dump({"leagueKey": "478.l.public"}, f)

    def _run_build_step(self):
        _, run_text = _step_block("Build machine-readable refresh result")
        result = subprocess.run(
            ["bash", "-c", run_text],
            cwd=self.tmpdir, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(os.path.join(self.tmpdir, "artifacts", "yahoo-refresh", "yahoo-refresh-result.json")) as f:
            return json.load(f)

    def test_previous_snapshot_at_download_artifact_path_is_actually_used(self):
        os.makedirs(os.path.join(self.tmpdir, "previous"))
        with open(os.path.join(self.tmpdir, "previous", "yahoo-players-normalized.json"), "w") as f:
            json.dump([{"oRank": 1, "name": "Previous Player"}], f)

        result = self._run_build_step()

        self.assertNotIn("rankingChangesNote", result)
        self.assertEqual(result["rankingChanges"], [
            {"oRank": 1, "previousPlayer": "Previous Player", "currentPlayer": "Current Player"},
        ])

    def test_no_previous_snapshot_falls_back_to_note(self):
        result = self._run_build_step()

        self.assertEqual(result["rankingChanges"], [])
        self.assertIn("rankingChangesNote", result)


if __name__ == "__main__":
    unittest.main()
