#!/usr/bin/env python3
"""Render a Yahoo refresh result JSON as a GitHub Actions Job Summary.

Standard library only.

Usage:
    python3 scripts/write_yahoo_job_summary.py <result.json> [summary-file]

If summary-file is omitted, writes to $GITHUB_STEP_SUMMARY (append mode,
matching how GitHub Actions expects job summary output).
"""
from __future__ import annotations

import json
import os
import sys


MAX_RANKING_CHANGES_SHOWN = 25


def render(result: dict) -> str:
    lines = [
        "## Yahoo Ranking Refresh",
        "",
        f"**Source:** `{result.get('source', 'unknown')}`",
        "",
        f"**Status:** {result.get('status', 'UNKNOWN')}",
        "",
        f"**Old cap:** {result['previous']['floor']} / {result['previous']['ceiling']}",
        f"**New cap:** {result['current']['floor']} / {result['current']['ceiling']}",
        "",
        "**Ranking changes:**",
        "",
    ]

    changes = result.get("rankingChanges") or []
    if changes:
        lines.append("| O-Rank | Previous | Current |")
        lines.append("|---|---|---|")
        for change in changes[:MAX_RANKING_CHANGES_SHOWN]:
            lines.append(
                f"| {change['oRank']} | {change.get('previousPlayer') or '—'} "
                f"| {change.get('currentPlayer') or '—'} |"
            )
        if len(changes) > MAX_RANKING_CHANGES_SHOWN:
            lines.append("")
            lines.append(f"...and {len(changes) - MAX_RANKING_CHANGES_SHOWN} more.")
    elif result.get("rankingChangesNote"):
        lines.append(result["rankingChangesNote"])
    else:
        lines.append("None.")

    lines.append("")
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("usage: write_yahoo_job_summary.py <result.json> [summary-file]", file=sys.stderr)
        sys.exit(2)

    with open(sys.argv[1], encoding="utf-8") as f:
        result = json.load(f)

    summary_path = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        print("no summary file target (pass one, or set GITHUB_STEP_SUMMARY)", file=sys.stderr)
        sys.exit(1)

    with open(summary_path, "a", encoding="utf-8") as f:
        f.write(render(result))


if __name__ == "__main__":
    main()
