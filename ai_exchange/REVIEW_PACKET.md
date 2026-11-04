# Review Packet

Generated: 2026-11-04T08:25:58Z

## Task
Active Task

## Status
READY_FOR_REVIEW

## Git
Branch: feat/season-schedule
Commit: 1027fe9
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
 data/2026-27/rosters/index.json                    |   11 +-
 .../rosters/snapshots/RS-2026-11-04-1ef07fff.json  | 1211 ++++++++++++++++++++
 index.html                                         |  388 ++++++-
 scripts/live.css                                   |    4 +
 scripts/live_app.js                                |   12 +-
 scripts/what_if.css                                |    2 +
 scripts/what_if_app.js                             |   21 +-
 tests/_phone.py                                    |   39 +
 tests/test_consistency.py                          |   55 +
 tests/test_export.py                               |   25 +-
 tests/test_keeper_board.py                         |    9 +
 tests/test_live_tab.py                             |   12 +-
 tests/test_my_team.py                              |   82 ++
 tests/test_phone.py                                |   42 +
 tests/test_player_card.py                          |   79 ++
 tests/test_scenario_rendering.py                   |    9 +-
 tests/test_trade_sketch.py                         |  131 +++
 tests/test_update_yahoo_standings.py               |    2 +-
 18 files changed, 2073 insertions(+), 61 deletions(-)
```

## Validation
- site validation: PASS
- tests: PASS (FAILED: HTTP_404: https://basketball.fantasysports.yahoo.com/nba/85092/matchup?date=totals&week=3&mid1=13 answered 404 (the previous feed stays up))
- Yahoo refresh: last local snapshot: draft_analysis_2026-10-05T032730Z.json
- live HTTP: OK

## Canonical State
Roster baseline: 16 franchises, 232 assignments
Cap snapshot: 131-178
Yahoo source timestamp: 2026-10-05T03:27:30Z

## Files Changed
- data/2026-27/rosters/index.json
- data/2026-27/rosters/snapshots/RS-2026-11-04-1ef07fff.json
- index.html
- scripts/live.css
- scripts/live_app.js
- scripts/what_if.css
- scripts/what_if_app.js
- tests/_phone.py
- tests/test_consistency.py
- tests/test_export.py
- tests/test_keeper_board.py
- tests/test_live_tab.py
- tests/test_my_team.py
- tests/test_phone.py
- tests/test_player_card.py
- tests/test_scenario_rendering.py
- tests/test_trade_sketch.py
- tests/test_update_yahoo_standings.py

## Issues
- New manual workflow `Update Yahoo Rosters` (`.github/workflows/update-yahoo-rosters.yml`), authorised by the owner on 2026-10-20 (this replaces the earlier "no Yahoo credentials in Actions" rule for this one workflow). Setup, run and failure guide: `docs/YAHOO_ROSTER_WORKFLOW.md`.
- It has NOT been run on GitHub yet (it needs the `YAHOO_STORAGE_STATE` secret and two repo settings). Logic is tested locally; see the PR for exactly what was and was not exercised.
- Lineup-slot moves (bench <-> active) are treated as "no material change": 102 players moved on 2026-10-20 alone, they affect nothing, and a PR per lineup change would be noise. IL moves and status changes are material.
- Live cross-check on 2026-10-20: no metadata drift, no ineligible slots, IL labels intact, payroll matches. Flags for the commissioner: Porziņģis (BN), Strus (Util) and Harris (PF) are listed Out but not on IL; DHA is short at PG; HCMC, TT and Thịnh have 6 single-position players.

## Decisions Required

- Set the secret and repo settings (docs/YAHOO_ROSTER_WORKFLOW.md), then run the workflow once from main.

## Suggested Next Step
Open/update the PR from `feat/season-schedule` if not already done, then request human/ChatGPT review of this packet.
