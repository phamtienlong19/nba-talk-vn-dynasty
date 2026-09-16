#!/usr/bin/env python3
"""Pure helper functions for the GitHub-Issue-driven workflow
(`work-issue.sh`, `sync-after-merge.sh`).

Deliberately dependency-free (standard library only) and side-effect-free
so it can be unit tested without git/gh/claude, per CLAUDE.md's rule that
CI must not depend on live Claude invocation or mutable external state.

CLI usage (each subcommand prints one value/block to stdout):

    python3 scripts/issue_workflow.py slug "Some Title Here"
    python3 scripts/issue_workflow.py branch-name 12 "Some Title" "bug,help wanted"
    python3 scripts/issue_workflow.py active-md 12 https://.../issues/12 "Title" fix/issue-12-some-title
    python3 scripts/issue_workflow.py archive-name 12 "Some Title" 2026-09-17
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone

FIX_LABELS = {"bug", "data-correction"}
FEAT_LABELS = {"enhancement"}
CHORE_LABELS = {"workflow"}

FIX_KEYWORDS = (
    "bug", "fix", "wrong", "incorrect", "broken", "error",
    "double check", "double-check", "correct", "outdated", "stale",
)
FEAT_KEYWORDS = ("add", "implement", "create", "new", "support")

MAX_SLUG_WORDS = 6
MAX_BRANCH_LEN = 60


def slugify(text: str, max_words: int = MAX_SLUG_WORDS) -> str:
    """Lowercase, ASCII-ish, hyphen-separated slug capped at max_words."""
    text = text.strip().lower()
    # Drop anything that isn't alphanumeric or whitespace/hyphen.
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    words = re.split(r"[\s-]+", text)
    words = [w for w in words if w]
    words = words[:max_words]
    slug = "-".join(words)
    return slug or "issue"


def classify_prefix(title: str, labels: list[str]) -> str:
    """Return 'fix', 'feat', or 'chore' for a branch-name prefix."""
    label_set = {l.strip().lower() for l in labels if l.strip()}
    if label_set & FIX_LABELS:
        return "fix"
    if label_set & CHORE_LABELS:
        return "chore"
    if label_set & FEAT_LABELS:
        return "feat"

    lowered = title.lower()
    if any(kw in lowered for kw in FIX_KEYWORDS):
        return "fix"
    if any(kw in lowered for kw in FEAT_KEYWORDS):
        return "feat"
    return "chore"


def branch_name(issue_number: int, title: str, labels: list[str]) -> str:
    prefix = classify_prefix(title, labels)
    slug = slugify(title)
    name = f"{prefix}/issue-{issue_number}-{slug}"
    if len(name) > MAX_BRANCH_LEN:
        # Trim the slug (not the prefix/issue-number, which must stay exact)
        overhead = len(name) - len(slug)
        keep = max(MAX_BRANCH_LEN - overhead, 1)
        name = f"{prefix}/issue-{issue_number}-{slug[:keep].rstrip('-')}"
    return name


def archive_name(issue_number: int, title: str, date: str | None = None) -> str:
    date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = slugify(title)
    return f"{date}-issue-{issue_number}-{slug}.md"


def generate_active_md(
    issue_number: int,
    url: str,
    title: str,
    branch: str,
    generated_at: str | None = None,
) -> str:
    generated_at = generated_at or datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return f"""# Active Task

Issue: #{issue_number}
URL: {url}
Title: {title}
Branch: {branch}
Canonical specification: GitHub Issue #{issue_number}
Generated: {generated_at}

## Local Constraints
- Read `CLAUDE.md`.
- Preserve project source-of-truth boundaries.
- Do not make unrelated changes.
- Human-decision boundaries in `CLAUDE.md` remain active.
"""


def generate_no_active_task_md() -> str:
    return """# Active Task

No active task.

Run `./work-issue.sh <issue-number>` to start one.
"""


def _main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    cmd = argv[1]
    args = argv[2:]

    if cmd == "slug":
        print(slugify(args[0]))
    elif cmd == "branch-name":
        issue_number = int(args[0])
        title = args[1]
        labels = args[2].split(",") if len(args) > 2 and args[2] else []
        print(branch_name(issue_number, title, labels))
    elif cmd == "active-md":
        issue_number = int(args[0])
        url = args[1]
        title = args[2]
        branch = args[3]
        generated_at = args[4] if len(args) > 4 else None
        sys.stdout.write(generate_active_md(issue_number, url, title, branch, generated_at))
    elif cmd == "no-active-task-md":
        sys.stdout.write(generate_no_active_task_md())
    elif cmd == "archive-name":
        issue_number = int(args[0])
        title = args[1]
        date = args[2] if len(args) > 2 else None
        print(archive_name(issue_number, title, date))
    else:
        print(f"unknown subcommand: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
