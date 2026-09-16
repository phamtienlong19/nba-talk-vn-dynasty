"""Shared fixtures for testing work-issue.sh / sync-after-merge.sh.

Not itself a test module (filename doesn't match unittest discover's
"test*.py" pattern). Builds a throwaway git repo with fake `gh` and
`claude` executables on PATH, so the real scripts can be exercised
end-to-end without any live network, GitHub auth, or Claude invocation --
per CLAUDE.md's rule that CI must not depend on those.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FAKE_GH = """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]

if args[:2] == ["auth", "status"]:
    sys.exit(0)

if args[:2] == ["issue", "view"]:
    fixture = os.environ.get("FAKE_GH_ISSUE_FIXTURE")
    if not fixture or not os.path.exists(fixture):
        sys.stderr.write("fake gh: issue not found\\n")
        sys.exit(1)
    sys.stdout.write(open(fixture).read())
    sys.exit(0)

if args[:2] == ["pr", "view"]:
    fixture = os.environ.get("FAKE_GH_PR_FIXTURE")
    if not fixture or not os.path.exists(fixture):
        sys.stderr.write("fake gh: pr not found\\n")
        sys.exit(1)
    sys.stdout.write(open(fixture).read())
    sys.exit(0)

sys.stderr.write(f"fake gh: unhandled invocation {args}\\n")
sys.exit(1)
"""

FAKE_CLAUDE = """#!/usr/bin/env bash
if [ "$1" = "--help" ]; then
  echo "Usage: claude [options] [prompt]"
  echo "  (fake claude for tests -- deliberately no -p/--print support,"
  echo "   so callers take the manual-fallback branch instead of exec-ing"
  echo "   this process away mid-test)"
  exit 0
fi
echo "FAKE CLAUDE INVOKED: $*"
exit 0
"""

MINIMAL_VALIDATE_SH = """#!/usr/bin/env bash
exit 0
"""

# Injected via DEPLOYMENT_FRESHNESS_FETCH_CMD (see sync-after-merge.sh /
# scripts/deployment_freshness.py --fetch-cmd) so that any test exercising
# the deployment-freshness step gets an instant, offline "Pages is fresh"
# response -- echoing back the very build.json the script just wrote --
# instead of a real HTTP poll against a live GitHub Pages site.
FAKE_DEPLOYMENT_FETCH = """#!/usr/bin/env python3
import sys

with open("build.json", encoding="utf-8") as f:
    sys.stdout.write(f.read())
"""


def _chmod_x(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def make_fake_bin(tmp_dir: Path) -> Path:
    bin_dir = tmp_dir / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    gh_path = bin_dir / "gh"
    gh_path.write_text(FAKE_GH)
    _chmod_x(gh_path)
    claude_path = bin_dir / "claude"
    claude_path.write_text(FAKE_CLAUDE)
    _chmod_x(claude_path)
    fetch_path = bin_dir / "fake-deployment-fetch"
    fetch_path.write_text(FAKE_DEPLOYMENT_FETCH)
    _chmod_x(fetch_path)
    return bin_dir


def make_repo(tmp_dir: Path) -> Path:
    """Build a minimal standalone repo (not a clone of the real one) with
    just enough structure for work-issue.sh / sync-after-merge.sh to run:
    the scripts themselves, their python helpers, a stub validate.sh, an
    empty tests/ dir, and ai_exchange/CURRENT_STATE.json.
    """
    repo = tmp_dir / "repo"
    repo.mkdir()

    for name in ("work-issue.sh", "sync-after-merge.sh", "handoff.sh"):
        shutil.copy(REPO_ROOT / name, repo / name)
        _chmod_x(repo / name)

    (repo / "scripts").mkdir()
    for name in ("issue_workflow.py", "deployment_freshness.py", "handoff.sh"):
        shutil.copy(REPO_ROOT / "scripts" / name, repo / "scripts" / name)
    _chmod_x(repo / "scripts" / "handoff.sh")

    (repo / "validate.sh").write_text(MINIMAL_VALIDATE_SH)
    _chmod_x(repo / "validate.sh")

    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\n")

    (repo / "tests").mkdir()
    # A real, always-passing test rather than an empty dir: some
    # `unittest discover` versions treat "zero tests collected" as a
    # failure, which would make sync-after-merge.sh's internal test step
    # spuriously fail regardless of what this fixture is meant to check.
    (repo / "tests" / "test_smoke.py").write_text(
        "import unittest\n\n"
        "class TestSmoke(unittest.TestCase):\n"
        "    def test_true(self):\n"
        "        self.assertTrue(True)\n"
    )

    (repo / "tasks").mkdir()
    (repo / "tasks" / "ACTIVE.md").write_text(
        "# Active Task\n\nNo active task.\n"
    )
    (repo / "tasks" / "archive").mkdir()
    (repo / "tasks" / "archive" / ".gitkeep").write_text("")

    (repo / "ai_exchange").mkdir()
    state = {
        "project": "test-project",
        "status": "LIVE",
        "repositoryUrl": "https://github.com/example/test-project",
        "publicUrl": "",
        "deployed": {"branch": "main", "commit": None, "verifiedAt": None, "liveContentCheck": "unknown"},
        "working": {"branch": "main", "commit": None, "issue": None, "prUrl": None, "status": "NONE"},
        "canonicalState": {"capFloor": 0, "capCeiling": 0, "lastYahooRefresh": {}, "rosterBaseline": {}},
    }
    (repo / "ai_exchange" / "CURRENT_STATE.json").write_text(json.dumps(state, indent=2) + "\n")

    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial commit")

    # work-issue.sh / sync-after-merge.sh both `git pull --ff-only` and
    # (sync-after-merge.sh) `git push origin main` -- give them a real
    # (local, bare) "origin" to talk to instead of failing on no remote.
    origin = tmp_dir / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-u", "origin", "main")

    return repo


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return _git(repo, *args)


def run_script(
    repo: Path,
    script: str,
    args: list[str],
    fake_bin: Path,
    env_extra: dict | None = None,
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    # Default test-mode seam for sync-after-merge.sh's deployment-freshness
    # step (no-op unless a test actually configures a non-empty publicUrl).
    # Callers can override via env_extra.
    env["DEPLOYMENT_FRESHNESS_FETCH_CMD"] = str(fake_bin / "fake-deployment-fetch")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [f"./{script}", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def write_fixture(tmp_dir: Path, name: str, data: dict) -> Path:
    path = tmp_dir / name
    path.write_text(json.dumps(data))
    return path
