# Implementation Report

Run: 2026-09-16 — Final workflow optimization
(`NBA_Talk_VN_Dynasty_Final_Workflow_Optimization.md`, direct request,
not GitHub-Issue-driven).

## What changed

- **Task inbox**: GitHub Issues are now the documented canonical task
  spec (`CLAUDE.md` "Task inbox"); `tasks/ACTIVE.md`/`tasks/README.md`
  switched to a lightweight generated-pointer template.
- **`./work-issue.sh <N>`**: fetches an open issue via `gh`, derives a
  `fix|feat|chore/issue-N-<slug>` branch (`scripts/issue_workflow.py`),
  refuses a dirty tree / closed issue / unrelated branch collision,
  writes the lightweight `tasks/ACTIVE.md` pointer + `working.*` in
  `ai_exchange/CURRENT_STATE.json`, then launches
  `claude -p --permission-mode auto` with a minimal prompt (falls back
  to printing the one-line command if `claude` isn't non-interactive-
  capable).
- **`./sync-after-merge.sh [PR]`**: requires the PR to be MERGED, pulls
  main, archives the completed task pointer to `tasks/archive/`, resets
  `tasks/ACTIVE.md`, refreshes `CURRENT_STATE.json` + the
  deployment-freshness marker, re-validates, regenerates the review
  packet, offers to delete the local branch, and reports Pages
  freshness.
- **Deployment freshness** (`docs/DEPLOYMENT_FRESHNESS.md`): a public
  `build.json` `{"commit","generatedAt"}` fingerprint, compared
  local-vs-live (`scripts/deployment_freshness.py`) rather than against
  a not-yet-known future commit SHA. Wired into `publish.sh` and
  `sync-after-merge.sh`.
- **`CURRENT_STATE.json` schema**: split into `deployed` (main) /
  `working` (current branch/issue/PR) / `canonicalState` (cap,
  roster baseline, Yahoo refresh) to remove the old ambiguous top-level
  branch/commit fields.
- **`status.sh`**: rewritten to the one-screen field set from the spec
  (deployed main, live fingerprint, working branch, active issue, PR,
  CI, validation, Yahoo snapshot, published cap, roster baseline,
  public URL).
- **`scripts/handoff.sh`**: reads the new state schema; Deployment
  section now reports fingerprint FRESH/STALE, not just HTTP 200;
  Issues/Decisions Required sections splice in
  `ai_exchange/REVIEW_NOTES.md` when present instead of hardcoding
  `(none)`.
- **`.github/ISSUE_TEMPLATE/correction.yml`**: short, phone-friendly
  correction template; blank issues remain allowed (default, untouched).
- **Labels**: added `data-correction`, `workflow`, `human-decision`
  (`bug`, `enhancement` already existed).
- **Not done, deliberately**: no Claude hooks added (no concrete
  deterministic failure mode identified that scripts/CI don't already
  cover); no Claude skills added (workflow is project-specific, belongs
  in `CLAUDE.md`/repo scripts/CI per the source file's own item 13).

## Tests added

`tests/test_issue_workflow.py`, `tests/test_deployment_freshness.py` —
pure-function unit tests (branch naming/slugging, marker matching,
freshness retry logic including "HTTP-200-but-wrong-fingerprint must not
pass").

`tests/test_work_issue.py`, `tests/test_sync_after_merge.py` — run the
real scripts against a throwaway git repo with fake `gh`/`claude` on
PATH (`tests/_workflow_test_utils.py`); no live network, GitHub auth, or
Claude invocation. Cover: missing/invalid issue number, dirty tree,
closed/nonexistent issue, branch-collision refusal, successful pointer
generation, idempotent rerun; unmerged-PR rejection, merged-PR sync
(state refresh, task archiving, marker refresh), rerun-is-a-near-noop.

Writing these against the real scripts (not just descriptions) caught
three real bugs before they shipped: `set -e`+`pipefail` aborting
`work-issue.sh` on an intentional no-match `grep` instead of reaching
the custom error message; an unconditional `git commit` failing on a
branch-reuse rerun with nothing new to stage; and a `build.json`
self-reference loop where anchoring the marker to "current HEAD" meant
every `sync-after-merge.sh` run invalidated its own marker one commit
later (fixed by anchoring to the PR's actual merge commit instead).

## Validation

- `./validate.sh` — PASS
- `python3 -m unittest discover -s tests` — 58 tests, PASS
