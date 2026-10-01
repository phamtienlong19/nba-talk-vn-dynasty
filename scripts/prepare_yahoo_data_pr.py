#!/usr/bin/env python3
"""Materialize the committed Yahoo data-PR candidate files + PR text.

Consumes outputs already produced earlier in the pipeline -- no
re-fetching, no re-deriving cap/ranking numbers, no re-deriving the
keeper-board/FA-draft-pool regeneration status. Writes exactly three
tracked files under a data directory (default data/yahoo/):

    players_normalized.json  -- verified normalized Yahoo snapshot, copied
                                 as-is from the refresh's local output
    cap_snapshot.json        -- the refresh's own cap-model output, minus
                                 the local/gitignored raw-snapshot path
    provenance.json          -- source, fetch timestamp, workflow run
                                 identity, player count, derived floor/
                                 ceiling, and board-regeneration counters

...plus two plain-text files (PR title, PR body markdown) the calling
script passes straight to `gh pr create`/`gh pr edit`.

This is the single candidate-PR model: one PR carries the refreshed
Yahoo snapshot AND the mechanical keeper-board/FA-draft-pool
regeneration together (see promote-yahoo-refresh.sh). It does not ask
for a second issue or a second PR -- merging this one PR is the whole
human approval step.

Standard library only.

Usage:
    python3 scripts/prepare_yahoo_data_pr.py \
        --result artifacts/yahoo-refresh/yahoo-refresh-result.json \
        --current-players local_data/yahoo/players_normalized.json \
        --cap-snapshot local_data/yahoo/cap_snapshot_latest.json \
        --data-dir data/yahoo \
        --pr-title-out artifacts/yahoo-refresh/pr_title.txt \
        --pr-body-out artifacts/yahoo-refresh/pr_body.md \
        --run-id "$GITHUB_RUN_ID" \
        --run-attempt "$GITHUB_RUN_ATTEMPT" \
        --repository "$GITHUB_REPOSITORY" \
        --server-url "$GITHUB_SERVER_URL" \
        [--keeper-board-stats artifacts/yahoo-refresh/keeper_board_stats.json] \
        [--test-status PASS]
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


def build_provenance(
    result, current_players, run_id, run_attempt, repository, server_url,
    keeper_board_updates, fa_draft_pool_rebuilt, test_status,
):
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
        "keeperBoardPlayerRowsUpdated": keeper_board_updates,
        "faDraftPoolRebuilt": fa_draft_pool_rebuilt,
        "testStatus": test_status,
    }


def build_pr_title(result):
    fetched_at = result.get("fetchedAt") or ""
    date = fetched_at.split("T", 1)[0] if "T" in fetched_at else fetched_at
    return f"data: refresh Yahoo rankings — {date}" if date else "data: refresh Yahoo rankings"


def build_pr_body(result, keeper_board_updates, test_status):
    previous, current = result["previous"], result["current"]
    changes = result.get("rankingChanges") or []
    provenance = result.get("_provenance") or {}

    lines = [
        f"**Yahoo source:** `{result['source']}`",
        f"**Fetch timestamp:** {result.get('fetchedAt', 'unknown')}",
        "",
        f"**Old floor / ceiling:** {previous['floor']} / {previous['ceiling']}",
        f"**New floor / ceiling:** {current['floor']} / {current['ceiling']}",
        "",
        "## Yahoo ranking-change summary",
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

    lines += [
        "",
        "## Board regeneration status",
        "",
        f"- Keeper board: {keeper_board_updates} kept-player row(s) had their "
        "Yahoo-sourced position/NBA team/cap display mechanically refreshed. "
        "No roster membership (which players are kept) was changed.",
        f"- FA/DRAFT 60 pool: mechanically rebuilt by "
        "`scripts/build_fa_draft_pool.py` from this snapshot.",
        "",
        "## Tests",
        "",
        f"- Full suite + `./validate.sh`: **{test_status}** (hard gate run "
        "inside the refresh workflow before this PR was opened/updated; "
        "GITHUB_TOKEN-authored pushes/PRs do not auto-trigger this repo's "
        "own CI, so re-run checks manually on this PR if you want a second, "
        "independent confirmation).",
        "",
        "## Workflow run provenance",
        "",
        f"- Run: {provenance.get('workflowRunUrl') or 'n/a'}",
        f"- Normalized players: {provenance.get('normalizedPlayerCount', 'n/a')}",
        "",
        "---",
        "",
        "This is the single candidate PR for this refresh: it carries the "
        "refreshed `data/yahoo/` snapshot, the mechanically-refreshed "
        "keeper-board display fields, and the rebuilt FA/DRAFT 60 pool "
        "together. No discretionary keeper selection (which players are "
        "kept/cut) was changed. **Merging this PR is the full human "
        "promotion approval — no further issue or PR is needed.**",
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
    parser.add_argument("--keeper-board-stats", default=None)
    parser.add_argument("--test-status", default="UNKNOWN")
    args = parser.parse_args()

    result = load_json(args.result)
    current_players = load_json(args.current_players)
    cap_snapshot = dict(load_json(args.cap_snapshot))
    cap_snapshot.pop("rawSnapshot", None)  # local/gitignored temp-file path, not meaningful once committed

    keeper_board_updates = 0
    if args.keeper_board_stats and os.path.isfile(args.keeper_board_stats):
        keeper_board_updates = load_json(args.keeper_board_stats).get("keptPlayerRowsUpdated", 0)

    provenance = build_provenance(
        result, current_players, args.run_id, args.run_attempt, args.repository, args.server_url,
        keeper_board_updates=keeper_board_updates, fa_draft_pool_rebuilt=True,
        test_status=args.test_status,
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
        f.write(build_pr_body(
            result_with_provenance, keeper_board_updates, args.test_status,
        ))

    print(f"Wrote candidate data files under {args.data_dir}")


if __name__ == "__main__":
    main()
