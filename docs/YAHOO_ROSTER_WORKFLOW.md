# Update Yahoo Rosters (GitHub Actions)

Manual workflow `.github/workflows/update-yahoo-rosters.yml`. A thin wrapper (`scripts/update_yahoo_rosters.py`) around code
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
| `READY` | only adds, drops, IL moves and status changes | a **draft PR** with the snapshot and regenerated site, and the report as its description |
| `CONFLICT` | needs a human: a player on a different team than ours (not a recorded completed trade), a completed trade Yahoo does not show, any import-blocking problem | the report only; **canonical data is not modified**; the run shows a warning |
| `NO_CHANGE` | Yahoo matches the verified snapshot, or only lineup slots moved (bench ↔ active) | no PR, but the **compliance checks still run**: the report lists any anti-tank, IL and roster findings (a count, plus a run annotation), so a no-change run doubles as a weekly check |
| `FAILED` | see step 2 | the report says why and how to fix it |

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
   Actions to create and approve pull requests* (the workflow only opens a draft PR; it never approves or merges).
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

## Run it

Actions → **Update Yahoo Rosters** → *Run workflow* (branch `main`; engine `browser`; leave *Open a draft PR* ticked), or:

```bash
gh workflow run "Update Yahoo Rosters" --ref main -f engine=browser -f open_pr=true
gh run watch
```

From any other branch, or with *Open a draft PR* unticked, it is a dry run: the report only. Runs are serialized
(`concurrency`), time out after 25 minutes, and a roster update can only touch `data/2026-27/rosters/`,
`data/2026-27/unlisted_players.json` and the generated `index.html` (checked before the PR is created).

**Review and merge the draft PR yourself.** The workflow already ran `./validate.sh` and the full test suite before opening it,
and the repository's `validate` check runs on the PR too (verified on the first real run). The automated Claude Code Review is
skipped for these PRs (`automation/yahoo-rosters-*` branches): the action refuses PRs opened by a bot, and the content is
generated roster data that this report already summarises.

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
