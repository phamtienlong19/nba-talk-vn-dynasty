"""Shared fixtures for testing promote-yahoo-refresh.sh end-to-end against a
throwaway git repo with a fake `gh` on PATH -- no live network or GitHub
auth, mirroring the pattern in tests/_workflow_test_utils.py."""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Fake `gh`, driven entirely by a JSON state file (FAKE_GH_PR_STATE) so
# multiple invocations (list/create/edit/view) within one test share
# state the same way the real `gh` would (a PR that actually exists).
# `pr create`'s FAKE_GH_SILENT_CREATE_FAILURE knob lets a test simulate
# "create reported success but no PR is actually listable afterwards"
# -- the scenario promote-yahoo-refresh.sh's own hard-fail guard (not
# just `set -e`) is meant to catch.
FAKE_GH = """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
state_path = os.environ["FAKE_GH_PR_STATE"]
call_log = os.environ.get("FAKE_GH_CALL_LOG")

def log(line):
    if call_log:
        with open(call_log, "a") as f:
            f.write(line + "\\n")

def load_state():
    if os.path.exists(state_path):
        with open(state_path) as f:
            return json.load(f)
    return None

def save_state(state):
    with open(state_path, "w") as f:
        json.dump(state, f)

if args[0:1] == ["pr"] and args[1:2] == ["list"]:
    log("pr list")
    state = load_state()
    if "--jq" in args:
        jq = args[args.index("--jq") + 1]
        if state is None:
            sys.stdout.write("\\n")  # `.[0].<field> // ""` on an empty list -> ""
        elif "number" in jq:
            sys.stdout.write(f"{state['number']}\\n")
        elif "url" in jq:
            sys.stdout.write(f"{state['url']}\\n")
    sys.exit(0)

if args[0:1] == ["pr"] and args[1:2] == ["create"]:
    log("pr create")
    if os.environ.get("FAKE_GH_SILENT_CREATE_FAILURE") == "1":
        # Simulate a create call that exits 0 but never actually
        # produces a listable open PR (the scenario the script's own
        # post-create assertion, not just `set -e`, must catch).
        sys.exit(0)
    number = 1
    url = f"https://github.com/example/test-project/pull/{number}"
    save_state({"number": number, "url": url})
    sys.stdout.write(url + "\\n")
    sys.exit(0)

if args[0:1] == ["pr"] and args[1:2] == ["edit"]:
    log("pr edit")
    sys.exit(0)

if args[0:1] == ["pr"] and args[1:2] == ["view"]:
    log("pr view")
    state = load_state()
    if state is None:
        sys.stderr.write("fake gh: no such pr\\n")
        sys.exit(1)
    sys.stdout.write(state["url"] + "\\n")
    sys.exit(0)

sys.stderr.write(f"fake gh: unhandled invocation {args}\\n")
sys.exit(1)
"""


def _chmod_x(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


MINIMAL_INDEX_HTML = """<!doctype html><html><body>
<section class="team-card">
<span class="identity-tag">TST</span>
<div class="players"><div class="player-row"><div class="pos">PG</div><div class="pname">Kept Player One</div><div class="nba">AAA</div><div class="cap">10</div></div></div>
<footer><div class="cuts-list"><span class="cut-chip">Cut Guy</span></div></footer>
</section>
<div class="pool-grid"></div>
<section class="page" id="cap"></section>
</body></html>
"""


def make_fake_bin(tmp_dir: Path) -> Path:
    bin_dir = tmp_dir / "fakebin"
    bin_dir.mkdir(exist_ok=True)
    gh_path = bin_dir / "gh"
    gh_path.write_text(FAKE_GH)
    _chmod_x(gh_path)
    return bin_dir


def make_repo(tmp_dir: Path) -> Path:
    """A minimal standalone repo (not a clone of the real one) with just
    enough structure for promote-yahoo-refresh.sh to run end-to-end: the
    real scripts it calls, a minimal real index.html, a local_data/yahoo
    Yahoo-snapshot fixture, and a bare 'origin' remote to push to."""
    repo = tmp_dir / "repo"
    repo.mkdir()

    shutil.copy(REPO_ROOT / "promote-yahoo-refresh.sh", repo / "promote-yahoo-refresh.sh")
    _chmod_x(repo / "promote-yahoo-refresh.sh")

    (repo / "scripts").mkdir()
    for name in (
        "build_fa_draft_pool.py",
        "refresh_keeper_board_display.py",
        "prepare_yahoo_data_pr.py",
    ):
        shutil.copy(REPO_ROOT / "scripts" / name, repo / "scripts" / name)

    (repo / "index.html").write_text(MINIMAL_INDEX_HTML)

    (repo / "data" / "dynasty").mkdir(parents=True)
    (repo / "data" / "dynasty" / "consensus.json").write_text(json.dumps({
        "generatedFrom": [], "playerCount": 2,
        "players": [
            {"name": "Kept Player One", "consensusRank": 1, "percentile": 0.1, "sourcesCount": 1, "sources": []},
            {"name": "Free Agent Guy", "consensusRank": 2, "percentile": 0.5, "sourcesCount": 1, "sources": []},
        ],
    }))

    (repo / "local_data" / "yahoo").mkdir(parents=True)
    (repo / "local_data" / "yahoo" / "players_normalized.json").write_text(json.dumps([
        {"name": "Kept Player One", "nbaTeam": "BBB", "eligiblePositions": ["SG"], "oRank": 5, "capDollars": 15.0},
        {"name": "Free Agent Guy", "nbaTeam": "CCC", "eligiblePositions": ["PF"], "oRank": 20, "capDollars": 3.0},
    ]))
    (repo / "local_data" / "yahoo" / "cap_snapshot_latest.json").write_text(json.dumps({
        "fetchedAt": "2026-10-01T000000Z",
        "rawSnapshot": "/tmp/not-tracked.json",
        "roundedFloor": 130, "roundedCeiling": 176,
        "publishedFloor": 131, "publishedCeiling": 177,
    }))

    (repo / ".gitignore").write_text("__pycache__/\n*.pyc\nlocal_data/\nartifacts/\n")

    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial commit")

    origin = tmp_dir / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "push", "-u", "origin", "main")

    return repo


def write_result_json(repo: Path, status: str, previous=None, current=None) -> Path:
    previous = previous or {"floor": 131, "ceiling": 177}
    current = current or ({"floor": 130, "ceiling": 176} if status == "CHANGED" else dict(previous))
    result = {
        "source": "478.l.public",
        "fetchedAt": "2026-10-01T000000Z",
        "status": status,
        "previous": previous,
        "current": current,
        "rankingChanges": [],
    }
    path = repo / "artifacts" / "yahoo-refresh" / "yahoo-refresh-result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result))
    return path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return _git(repo, *args)


def run_promote(
    repo: Path,
    result_json: Path,
    fake_bin: Path,
    fake_gh_state: Path,
    env_extra: dict | None = None,
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["FAKE_GH_PR_STATE"] = str(fake_gh_state)
    env["GH_TOKEN"] = "fake-token"
    # Fast, deterministic stand-ins for the real test/validate gate --
    # production default is the real suite (see promote-yahoo-refresh.sh).
    env.setdefault("PROMOTE_YAHOO_REFRESH_TEST_CMD", "true")
    env.setdefault("PROMOTE_YAHOO_REFRESH_VALIDATE_CMD", "true")
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        ["./promote-yahoo-refresh.sh", str(result_json.relative_to(repo))],
        cwd=repo, env=env, capture_output=True, text=True, timeout=60,
    )
