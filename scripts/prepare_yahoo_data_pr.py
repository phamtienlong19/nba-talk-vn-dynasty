#!/usr/bin/env python3
"""Materialize the committed Yahoo data-PR candidate files + PR text.

Consumes the outputs already produced by ./refresh-yahoo.sh and
scripts/build_yahoo_refresh_result.py -- no re-fetching, no re-deriving
cap/ranking numbers. Writes exactly three tracked files under a data
directory (default data/yahoo/):

    players_normalized.json  -- verified normalized Yahoo snapshot, copied
                                 as-is from the refresh's local output
    cap_snapshot.json        -- the refresh's own cap-model output, minus
                                 the local/gitignored raw-snapshot path
    provenance.json          -- source, fetch timestamp, workflow run
                                 identity, player count, derived floor/ceiling

...plus two plain-text files (PR title, PR body markdown) the calling
workflow passes straight to `gh pr create`/`gh pr edit`. Never touches
index.html, keeper data, or any file outside --data-dir.

Standard library only.

Usage:
    python3 scripts/prepare_yahoo_data_pr.py \
        --result artifacts/yahoo-refresh/yahoo-refresh-result.json \
        --current-players local_data/yahoo/players_normalized.json \
        --cap-snapshot local_data/yahoo/cap_snapshot_latest.json \
        --data-dir data/yahoo \
        --pr-title-out pr_title.txt \
        --pr-body-out pr_body.md \
        --run-id "$GITHUB_RUN_ID" \
        --run-attempt "$GITHUB_RUN_ATTEMPT" \
        --repository "$GITHUB_REPOSITORY" \
        --server-url "$GITHUB_SERVER_URL"
"""
from __future__ import annotations

import argparse
import json
import os

MAX_RANKING_CHANGES_IN_BODY = 25


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def build_provenance(result, current_players, run_id, run_attempt, repository, server_url):
    run_url = None
    if repository and run_id:
        run_url = f"{server_url}/{repository}/actions/runs/{run_id}"
        if run_attempt:
            run_url += f"/attempts/{run_attempt}"

    return {
        "source": result["source"],
        "fetchedAt": result.get("fetchedAt"),
        "workflowRunId": run_id or None,
        "workflowRunAttempt": run_attempt or None,
        "workflowRunUrl": run_url,
        "normalizedPlayerCount": len(current_players),
        "derivedFloor": result["current"]["floor"],
        "derivedCeiling": result["current"]["ceiling"],
    }


def build_pr_title(result):
    fetched_at = result.get("fetchedAt") or ""
    date = fetched_at.split("T", 1)[0] if "T" in fetched_at else fetched_at
    return f"data: refresh Yahoo rankings — {date}" if date else "data: refresh Yahoo rankings"


def build_pr_body(result):
    previous, current = result["previous"], result["current"]
    changes = result.get("rankingChanges") or []

    lines = [
        f"**Yahoo source:** `{result['source']}`",
        f"**Fetch timestamp:** {result.get('fetchedAt', 'unknown')}",
        "",
        f"**Old floor / ceiling:** {previous['floor']} / {previous['ceiling']}",
        f"**New floor / ceiling:** {current['floor']} / {current['ceiling']}",
        "",
        "## Ranking-change summary",
        "",
    ]

    if changes:
        for change in changes[:MAX_RANKING_CHANGES_IN_BODY]:
            lines.append(
                f"- R{change['oRank']}: {change.get('previousPlayer') or '—'} "
                f"→ {change.get('currentPlayer') or '—'}"
            )
        if len(changes) > MAX_RANKING_CHANGES_IN_BODY:
            lines.append(f"- ...and {len(changes) - MAX_RANKING_CHANGES_IN_BODY} more.")
    elif result.get("rankingChangesNote"):
        lines.append(result["rankingChangesNote"])
    else:
        lines.append("No player-level ranking diff available.")

    provenance = result.get("_provenance")
    lines += [
        "",
        "## Workflow run provenance",
        "",
        f"- Run: {provenance['workflowRunUrl'] if provenance and provenance.get('workflowRunUrl') else 'n/a'}",
        f"- Normalized players: {provenance['normalizedPlayerCount'] if provenance else 'n/a'}",
        "",
        "---",
        "",
        "This PR is the canonical Yahoo-data promotion boundary: it only "
        "updates `data/yahoo/`, nothing else. `index.html` and keeper/roster "
        "state are **not** touched by this workflow. **Merging this PR is "
        "the human approval to promote this snapshot** — no separate "
        "approval step follows.",
        "",
        "Next step after merge: open a GitHub Issue — \"Propagate canonical "
        "Yahoo refresh through cap/keeper/site state\" — for the offline "
        "Claude issue agent to pick up. That task can read `data/yahoo/` "
        "directly from `main` and needs no network access.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--result", required=True)
    parser.add_argument("--current-players", required=True)
    parser.add_argument("--cap-snapshot", required=True)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--pr-title-out", required=True)
    parser.add_argument("--pr-body-out", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-attempt", default="")
    parser.add_argument("--repository", default="")
    parser.add_argument("--server-url", default="https://github.com")
    args = parser.parse_args()

    result = load_json(args.result)
    current_players = load_json(args.current_players)
    cap_snapshot = dict(load_json(args.cap_snapshot))
    cap_snapshot.pop("rawSnapshot", None)  # local/gitignored temp-file path, not meaningful once committed

    provenance = build_provenance(
        result, current_players, args.run_id, args.run_attempt, args.repository, args.server_url,
    )

    write_json(os.path.join(args.data_dir, "players_normalized.json"), current_players)
    write_json(os.path.join(args.data_dir, "cap_snapshot.json"), cap_snapshot)
    write_json(os.path.join(args.data_dir, "provenance.json"), provenance)

    result_with_provenance = dict(result)
    result_with_provenance["_provenance"] = provenance

    os.makedirs(os.path.dirname(args.pr_title_out) or ".", exist_ok=True)
    with open(args.pr_title_out, "w", encoding="utf-8") as f:
        f.write(build_pr_title(result))

    os.makedirs(os.path.dirname(args.pr_body_out) or ".", exist_ok=True)
    with open(args.pr_body_out, "w", encoding="utf-8") as f:
        f.write(build_pr_body(result_with_provenance))

    print(f"Wrote candidate data files under {args.data_dir}")


if __name__ == "__main__":
    main()
