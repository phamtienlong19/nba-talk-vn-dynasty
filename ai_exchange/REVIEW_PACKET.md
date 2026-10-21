# Review Packet

Generated: 2026-10-21T01:53:18Z

## Task
Active Task

## Status
READY_FOR_REVIEW

## Git
Branch: fix/tests-not-pinned-to-live-roster
Commit: fce8af4
Base: main
Working tree: dirty

## GitHub
Repository: https://github.com/phamtienlong19/nba-talk-vn-dynasty
GitHub CLI: available
PR: none
CI: no runs found for this branch

## Deployment
Public URL: https://phamtienlong19.github.io/nba-talk-vn-dynasty/
HTTP: OK
Fingerprint: FRESH

## Changes
```
 tests/test_final_keeper_freeze.py |  5 ++-
 tests/test_league_state_data.py   |  6 ++-
 tests/test_scenario_rendering.py  | 80 ++++++++++++++++++++++-----------------
 tests/test_season_ops.py          | 39 +++++++++++--------
 tests/test_yahoo_rosters.py       | 69 +++++++++++++++++++++------------
 5 files changed, 121 insertions(+), 78 deletions(-)
```

## Validation
- site validation: PASS
- tests: PASS (keeper freeze is LOCKED -- baseline not regenerated (immutable).)
- Yahoo refresh: last local snapshot: draft_analysis_2026-10-05T032730Z.json
- live HTTP: OK

## Canonical State
Roster baseline: 16 franchises, 232 assignments
Cap snapshot: 131-178
Yahoo source timestamp: 2026-10-05T03:27:30Z

## Files Changed
- tests/test_final_keeper_freeze.py
- tests/test_league_state_data.py
- tests/test_scenario_rendering.py
- tests/test_season_ops.py
- tests/test_yahoo_rosters.py

## Issues
- New manual workflow `Update Yahoo Rosters` (`.github/workflows/update-yahoo-rosters.yml`), authorised by the owner on 2026-10-20 (this replaces the earlier "no Yahoo credentials in Actions" rule for this one workflow). Setup, run and failure guide: `docs/YAHOO_ROSTER_WORKFLOW.md`.
- It has NOT been run on GitHub yet (it needs the `YAHOO_STORAGE_STATE` secret and two repo settings). Logic is tested locally; see the PR for exactly what was and was not exercised.
- Lineup-slot moves (bench <-> active) are treated as "no material change": 102 players moved on 2026-10-20 alone, they affect nothing, and a PR per lineup change would be noise. IL moves and status changes are material.
- Live cross-check on 2026-10-20: no metadata drift, no ineligible slots, IL labels intact, payroll matches. Flags for the commissioner: Porziņģis (BN), Strus (Util) and Harris (PF) are listed Out but not on IL; DHA is short at PG; HCMC, TT and Thịnh have 6 single-position players.

## Decisions Required

- Set the secret and repo settings (docs/YAHOO_ROSTER_WORKFLOW.md), then run the workflow once from main.

## Suggested Next Step
Open/update the PR from `fix/tests-not-pinned-to-live-roster` if not already done, then request human/ChatGPT review of this packet.
