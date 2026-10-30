# Update Yahoo Rosters (GitHub Actions)

Scheduled (every 3 hours, anonymous `http` engine, no Yahoo credentials) and manual workflow `.github/workflows/update-yahoo-rosters.yml`. A thin wrapper (`scripts/update_yahoo_rosters.py`) around code
that already exists: the read-only fetcher and validator (`scripts/yahoo_rosters.py`), the reconciliation, and the reviewed
importer (`scripts/import_rosters.py`). It adds no scraper and no ownership model.

## What a run does

1. Reads league **85092**, team ids 1–9 and 11–17 (GET only; no clicks, no forms).
2. **Fails** (red run, nothing written) on a sign-in/consent page, an expired session, an incomplete or empty roster, a
   duplicate Yahoo player id, a team that is not the one requested, a parse failure, or an unmapped team.
3. Reconciles the capture with the official state exactly as `import_rosters.py diff` does, plus cross-checks (below).
4. Decides:

| Outcome | Meaning | What you get |
|---|---|---|
| `READY` | only adds, drops, IL moves and status changes | a **pull request** with the snapshot and regenerated site, and the report as its description. If only free-agent adds / drops, IL moves and statuses changed (and no more than 40 of them), it is queued to **auto-merge** once its checks pass; otherwise it waits for you |
| `CONFLICT` | needs a human: a player on a different team than ours (not a recorded completed trade), a completed trade Yahoo does not show, any import-blocking problem | the report only; **canonical data is not modified**; the run shows a warning and a **GitHub issue** (label `roster-refresh`) is opened, then closed by the first run that recovers |
| `NO_CHANGE` | Yahoo matches the verified snapshot, or only lineup slots moved (bench ↔ active) | no PR, but the **compliance checks still run**: the report lists any anti-tank, IL and roster findings (a count, plus a run annotation), so a no-change run doubles as a weekly check |
| `FAILED` | see step 2 | the report says why and how to fix it, plus the same issue |

An unexplained ownership change is always a `CONFLICT`: record the trade in `data/2026-27/season_transactions.json`
first (a human decision), then run again. The workflow never creates a transaction and never overrides history.

## The report

Adds, removals, ownership changes, **IL moves** (IL labels are kept: `[IL]` plus Yahoo's status such as `O` / `Q`),
status changes, **salary-cap effects** per team (counted payroll before → after, healthy payroll, band), the anti-tank
roster checks on the proposed rosters, the recorded transactions, and unresolved discrepancies. Payroll is the existing rule:
the top nine frozen salaries over **all** owned players, IL included; frozen salaries are never written (checked by file hash
before and after). Cross-checks: team and position eligibility vs our data, players in a lineup slot they are not eligible
for, players parked on IL that Yahoo lists as neither IL-eligible nor Out, injured players (IL-eligible per Yahoo, or Out) not on IL, IL labels preserved, and an independent top-9 payroll
recomputation.

## One-time setup

1. **Repository settings** → Actions → General → Workflow permissions: *Read and write permissions* and tick *Allow GitHub
   Actions to create and approve pull requests* (the workflow only opens a PR; it never approves or merges).
2. **Sign in locally** (needs Python and Playwright: `pip install -r requirements-yahoo-rosters.txt && python3 -m playwright install chromium`):
   ```bash
   python3 scripts/yahoo_rosters.py login          # a browser opens; sign in to Yahoo, then close the window
   python3 scripts/yahoo_rosters.py export-state   # writes ~/.config/nba-talk-vn-dynasty/yahoo-storage-state.json (mode 600)
   ```
3. **Store it as a secret** named `YAHOO_STORAGE_STATE` (the command reads the file; nothing is printed):
   ```bash
   gh secret set YAHOO_STORAGE_STATE < ~/.config/nba-talk-vn-dynasty/yahoo-storage-state.json
   rm ~/.config/nba-talk-vn-dynasty/yahoo-storage-state.json     # optional: the secret now holds it
   ```
   (Or: Settings → Secrets and variables → Actions → New repository secret → paste the file's contents.)

The file is a signed-in Yahoo session: treat it like a password. It stays outside the repository, is written to a temp file
with mode 600 on the runner, never printed, never uploaded (only `report.md` and `observation.json` are), and is deleted at
the end of every run. Use a Yahoo account that is a league member and nothing more. The workflow runs only when someone with
write access dispatches it; fork pull requests cannot reach the secret.

If Yahoo's team pages are public (they were on 2026-10-19) you do not need the secret: run with `engine = http`. Yahoo may
treat GitHub's datacenter addresses differently from yours, which is why the signed-in `browser` engine is the default.

## Schedule and auto-merge

- `schedule: "17 */3 * * *"` runs the workflow with `engine=http` and *Open a PR* on. A `NO_CHANGE` run is silent. The site's roster pill
  turns amber after 12 h and red after 48 h without a newer snapshot, so a stalled schedule is visible to everyone.
- **Auto-merge** is requested with `gh pr merge --auto --squash` only when `automerge_ok` (`scripts/update_yahoo_rosters.py`) says so:
  outcome `READY`, no ownership change, and at most 40 adds + drops + IL moves in one capture (a bigger swing looks like a broken
  Yahoo page). The path guard (only roster data and the generated page changed) and `./validate.sh` + the unit tests have already
  passed in the run. GitHub merges only after the repository's required checks are green.
- **Never auto-merged** (a human decides): any `CONFLICT`, any ownership change, trades, standings, cap-snapshot promotion, anything
  touching files outside the roster data. A bad merge is reverted with a normal `git revert` PR.
- **One-time repository settings** (the workflow cannot change these): Settings → General → *Allow auto-merge*; Settings → Branches →
  protect `main` and require the `validate` status check, otherwise auto-merge has nothing to wait for and merges at once.
  Keep `ROSTER_PR_TOKEN` valid (90-day expiry) so the PR's checks run without an approval click.

## Run it

Actions → **Update Yahoo Rosters** → *Run workflow* (branch `main`; engine `http` is the default and needs no secret; `browser` needs `YAHOO_STORAGE_STATE`; leave *Open a PR* ticked), or:

```bash
gh workflow run "Update Yahoo Rosters" --ref main -f engine=browser -f open_pr=true
gh run watch
```

From any other branch, or with *Open a PR* unticked, it is a dry run: the report only. Runs are serialized
(`concurrency`), time out after 25 minutes, and a roster update can only touch `data/2026-27/rosters/`,
`data/2026-27/unlisted_players.json` and the generated `index.html` (checked before the PR is created).

**Review and merge the PR yourself.** The workflow already ran `./validate.sh` and the full test suite before opening it, and
the repository's `validate` check runs on the PR too. The automated Claude Code Review is skipped for these PRs
(`automation/yahoo-rosters-*` branches): the action refuses PRs opened by a bot, and the content is generated roster data
that the report already summarises. The PR is opened **ready for review** (not a draft), so you can merge it straight away.

### Checks and approvals: what happens on every run

Every run that opens a PR does three things afterwards, so you never have to click anything to get a mergeable PR:

1. **Supersedes older roster PRs.** Any other open PR from an `automation/yahoo-rosters-*` branch (for example one a previous
   run left open) is closed with a pointer to the new one, and its branch is deleted. Only this workflow's own branches are
   touched.
2. **Approves the new PR's checks.** GitHub holds the checks of a PR opened by the built-in `github-actions` bot until a
   maintainer approves them (`action_required`). The workflow approves them itself, which is safe because it has just verified
   that the PR changes only roster data and the generated page (so no workflow or script in it differs from `main`). The
   job summary lists each run it approved.
3. **Opens the PR ready for review**, never as a draft, and never merges it.

If the approval step cannot approve (a warning appears in the run), the fallback below makes the PR author you, which
needs no approval at all.

### Recommended: open the PR as yourself (the guaranteed route)

PRs authored by a person are never held for approval. Give the workflow a token of yours and the PR is authored by you:

1. GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token.
   Resource owner: you; **Only select repositories** → this repository; permissions: **Contents: Read and write**,
   **Pull requests: Read and write** and **Actions: Read and write** (Metadata read is added automatically); expiration 90 days.
2. Store it: `gh secret set ROSTER_PR_TOKEN` (paste the token when prompted), or Settings → Secrets and variables → Actions.

The workflow checks the token before using it. If it is missing or expired, it falls back to the built-in token and prints a
warning (the PR still opens; its checks just wait for the approval click). The token is used only to open the PR; the workflow
cannot merge, approve, or push to `main` with it (the branch it pushes is always `automation/yahoo-rosters-*`).
Renew the token when it expires and run `gh secret set ROSTER_PR_TOKEN` again.

## When it fails

| Message | Fix |
|---|---|
| *Yahoo session missing* | set the `YAHOO_STORAGE_STATE` secret (above), or run with `engine = http` |
| `AUTH_REQUIRED` / *every Yahoo cookie … has expired* | Yahoo ended the session: repeat steps 2–3 |
| `CONSENT_REQUIRED` | sign in once in the login browser, accept the prompt, export again |
| `NO_ROSTER_TABLE` | Yahoo changed its page layout: the parser needs updating (nothing was written) |
| `INCOMPLETE_CAPTURE` / `EMPTY_ROSTER` / `DUPLICATE_OWNERSHIP` | Yahoo returned a partial or inconsistent page set: run again; if it repeats, open the artifact |

## Tests must not pin the current roster

The workflow runs the full suite on the regenerated site before it opens a PR. A test that hard-codes a detail of today's
rosters (a player count, "X is on team Y", a team's cap) fails on the first real roster change and blocks every later update
PR. Write expectations from the engine for the current snapshot (`season_state`, `season_view`, `roster_checks`), or run on
the frozen draft-night baseline with `TempData` / `draft_night()` and impose the situation you need.

`python3 scripts/stress_roster_tests.py [SEED ...]` checks this: each seed applies a random roster change (drops, pickups, IL
moves, status changes) as a new verified snapshot **in a temporary copy of the repository**, regenerates the site and runs the
whole suite. Run it after adding tests that read the live data; every failure is a test that pins today's roster.
