#!/usr/bin/env python3
"""Deployment-freshness verification.

Distinguishes "site reachable" (HTTP 200) from "latest revision actually
serving" using a small public `build.json` fingerprint committed next to
`index.html`:

    {"commit": "<sha>", "generatedAt": "<iso timestamp>"}

Design note (why comparing against local build.json, not `git rev-parse
HEAD`): the marker is written and committed *before* it can know its own
future commit SHA, so it always records the commit it was generated
against (which becomes the parent of the commit that carries it). Rather
than chase that one-commit lag, freshness is verified by comparing the
*live* build.json against the *local, already-committed* build.json byte
for byte on the `commit` field. If they match, GitHub Pages is serving at
least that push. This sidesteps the self-reference problem entirely and
needs no prediction of a not-yet-created commit hash.

CLI:
    python3 scripts/deployment_freshness.py write <commit-sha> [path]
    python3 scripts/deployment_freshness.py check <public-url> [--local-path build.json] [--attempts 6] [--delay 10] [--fetch-cmd <executable>]

`--fetch-cmd` swaps the real HTTP fetch for `<executable> <marker-url>`
(stdout must be the JSON marker body, non-zero exit == unreachable). It
exists so callers like sync-after-merge.sh can inject a deterministic,
offline verifier in tests instead of polling a real site -- see
DEPLOYMENT_FRESHNESS_FETCH_CMD in sync-after-merge.sh. Production runs
never set it, so the real network check below is unchanged.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Callable, Optional

DEFAULT_MARKER_PATH = "build.json"


def write_marker(commit_sha: str, path: str = DEFAULT_MARKER_PATH) -> dict:
    marker = {
        "commit": commit_sha,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(marker, f, indent=2)
        f.write("\n")
    return marker


def load_local_marker(path: str = DEFAULT_MARKER_PATH) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def markers_match(live: Optional[dict], local: Optional[dict]) -> bool:
    """PASS requires both markers present and commit fields equal.

    A live HTTP 200 with a missing/garbled/mismatched marker is NOT a
    pass -- that is the whole point of this check over a bare HTTP probe.
    """
    if not live or not local:
        return False
    live_commit = live.get("commit")
    local_commit = local.get("commit")
    if not live_commit or not local_commit:
        return False
    return live_commit == local_commit


FetchFn = Callable[[str], Optional[dict]]


def fetch_via_cmd(cmd: str) -> FetchFn:
    """Build a fetch function that shells out to `cmd <url>` instead of
    making a real HTTP request -- the injectable test-mode seam."""

    def _fetch(url: str) -> Optional[dict]:
        try:
            result = subprocess.run(
                [cmd, url], capture_output=True, text=True, timeout=15
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

    return _fetch


def default_fetch(url: str, timeout: int = 15) -> Optional[dict]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            body = resp.read().decode("utf-8")
        return json.loads(body)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def check_freshness(
    public_url: str,
    local_marker: Optional[dict],
    attempts: int = 6,
    delay: int = 10,
    fetch: FetchFn = default_fetch,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[bool, Optional[dict]]:
    """Poll `<public_url>/build.json` up to `attempts` times.

    Returns (matched, last_live_marker).
    """
    marker_url = public_url.rstrip("/") + "/build.json?cb=" + str(int(time.time()))
    live = None
    for attempt in range(1, attempts + 1):
        live = fetch(marker_url)
        if markers_match(live, local_marker):
            return True, live
        if attempt < attempts:
            sleep(delay)
    return False, live


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_write = sub.add_parser("write")
    p_write.add_argument("commit_sha")
    p_write.add_argument("path", nargs="?", default=DEFAULT_MARKER_PATH)

    p_check = sub.add_parser("check")
    p_check.add_argument("public_url")
    p_check.add_argument("--local-path", default=DEFAULT_MARKER_PATH)
    p_check.add_argument("--attempts", type=int, default=6)
    p_check.add_argument("--delay", type=int, default=10)
    p_check.add_argument(
        "--fetch-cmd",
        default=None,
        help="Executable invoked as `<cmd> <marker-url>` instead of a real "
        "HTTP fetch (injectable test-mode verifier).",
    )

    args = parser.parse_args(argv[1:])

    if args.cmd == "write":
        marker = write_marker(args.commit_sha, args.path)
        print(f"Wrote {args.path}: {marker}")
        return 0

    if args.cmd == "check":
        local = load_local_marker(args.local_path)
        if local is None:
            print(f"ERROR: no local marker at {args.local_path}", file=sys.stderr)
            return 2
        fetch = fetch_via_cmd(args.fetch_cmd) if args.fetch_cmd else default_fetch
        matched, live = check_freshness(
            args.public_url, local, attempts=args.attempts, delay=args.delay, fetch=fetch
        )
        if matched:
            print(f"FRESH: live build.json commit {live.get('commit')} matches local")
            return 0
        print(
            f"STALE: live build.json {live!r} does not match local {local!r}",
            file=sys.stderr,
        )
        return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
