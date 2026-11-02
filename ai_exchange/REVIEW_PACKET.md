# Review Packet

Generated: 2026-11-02T16:23:01Z

## Task
Active Task

## Status
READY_FOR_REVIEW

## Git
Branch: feat/live-tab
Commit: 1351473
Base: main
Working tree: dirty

## GitHub
Repository: https://github.com/phamtienlong19/nba-talk-vn-dynasty
GitHub CLI: available
PR: https://github.com/phamtienlong19/nba-talk-vn-dynasty/pull/117 (OPEN)
CI: Claude Code Review: completed/success

## Deployment
Public URL: https://phamtienlong19.github.io/nba-talk-vn-dynasty/
HTTP: OK
Fingerprint: FRESH

## Changes
```
 .github/workflows/update-live-data.yml             |   55 +
 ai_exchange/REVIEW_PACKET.md                       |  108 +-
 config/yahoo_league.json                           |   20 +-
 data/2026-27/matchups/week-01.json                 |  556 +++++++++
 data/2026-27/matchups/week-02.json                 |  556 +++++++++
 data/2026-27/rosters/index.json                    |   29 +-
 .../rosters/snapshots/RS-2026-11-01-cd3eaa64.json  | 1217 ++++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-02-8964cc4c.json  | 1212 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-02-b17bd5ac.json  | 1206 +++++++++++++++++++
 docs/LIVE_DATA.md                                  |   66 ++
 docs/PROJECT_CONTEXT.md                            |   90 ++
 docs/WHAT_IF_MODE.md                               |    4 +
 index.html                                         |  367 +++++-
 scripts/build_live_feed.py                         |  125 ++
 scripts/live.css                                   |   50 +
 scripts/live_app.js                                |  140 +++
 scripts/live_page.py                               |  116 ++
 scripts/live_standings.py                          |  145 +++
 scripts/stress_roster_tests.py                     |    2 +-
 scripts/update_yahoo_matchups.py                   |   99 ++
 scripts/update_yahoo_rosters.py                    |    2 +-
 scripts/update_yahoo_standings.py                  |    2 +-
 scripts/what_if.css                                |   43 +
 scripts/what_if_app.js                             |   75 +-
 scripts/yahoo_matchups.py                          |  406 +++++++
 .../yahoo/matchups/week1_mid11_header.html         |    4 +
 .../yahoo/matchups/week1_mid13_header.html         |    4 +
 .../fixtures/yahoo/matchups/week1_mid1_header.html |    4 +
 .../fixtures/yahoo/matchups/week1_mid2_header.html |    4 +
 .../fixtures/yahoo/matchups/week1_mid4_header.html |    4 +
 .../fixtures/yahoo/matchups/week1_mid5_header.html |    4 +
 .../fixtures/yahoo/matchups/week1_mid7_header.html |    4 +
 tests/fixtures/yahoo/matchups/week1_mid8_full.html |    5 +
 .../fixtures/yahoo/matchups/week1_mid8_header.html |    4 +
 .../week2_mid16_mid4_date2026-11-01_full.html      |    5 +
 .../matchups/week3_mid8_not_started_full.html      |    5 +
 .../yahoo/standings_2026-11-02_after_week2.json    |  181 +++
 tests/test_export.py                               |   23 +
 tests/test_keeper_board.py                         |    8 +-
 tests/test_live_feed.py                            |  132 +++
 tests/test_live_standings.py                       |  192 +++
 tests/test_live_tab.py                             |  127 ++
 tests/test_yahoo_matchups.py                       |  150 +++
 43 files changed, 7416 insertions(+), 135 deletions(-)
```

## Validation
- site validation: PASS
- tests: PASS (FAILED: HTTP_404: https://basketball.fantasysports.yahoo.com/nba/85092/matchup?week=3&mid1=13 answered 404 (the previous feed stays up))
- Yahoo refresh: last local snapshot: draft_analysis_2026-10-05T032730Z.json
- live HTTP: OK

## Canonical State
Roster baseline: 16 franchises, 232 assignments
Cap snapshot: 131-178
Yahoo source timestamp: 2026-10-05T03:27:30Z

## Files Changed
- .github/workflows/update-live-data.yml
- ai_exchange/REVIEW_PACKET.md
- config/yahoo_league.json
- data/2026-27/matchups/week-01.json
- data/2026-27/matchups/week-02.json
- data/2026-27/rosters/index.json
- data/2026-27/rosters/snapshots/RS-2026-11-01-cd3eaa64.json
- data/2026-27/rosters/snapshots/RS-2026-11-02-8964cc4c.json
- data/2026-27/rosters/snapshots/RS-2026-11-02-b17bd5ac.json
- docs/LIVE_DATA.md
- docs/PROJECT_CONTEXT.md
- docs/WHAT_IF_MODE.md
- index.html
- scripts/build_live_feed.py
- scripts/live.css
- scripts/live_app.js
- scripts/live_page.py
- scripts/live_standings.py
- scripts/stress_roster_tests.py
- scripts/update_yahoo_matchups.py
- scripts/update_yahoo_rosters.py
- scripts/update_yahoo_standings.py
- scripts/what_if.css
- scripts/what_if_app.js
- scripts/yahoo_matchups.py
- tests/fixtures/yahoo/matchups/week1_mid11_header.html
- tests/fixtures/yahoo/matchups/week1_mid13_header.html
- tests/fixtures/yahoo/matchups/week1_mid1_header.html
- tests/fixtures/yahoo/matchups/week1_mid2_header.html
- tests/fixtures/yahoo/matchups/week1_mid4_header.html
- tests/fixtures/yahoo/matchups/week1_mid5_header.html
- tests/fixtures/yahoo/matchups/week1_mid7_header.html
- tests/fixtures/yahoo/matchups/week1_mid8_full.html
- tests/fixtures/yahoo/matchups/week1_mid8_header.html
- tests/fixtures/yahoo/matchups/week2_mid16_mid4_date2026-11-01_full.html
- tests/fixtures/yahoo/matchups/week3_mid8_not_started_full.html
- tests/fixtures/yahoo/standings_2026-11-02_after_week2.json
- tests/test_export.py
- tests/test_keeper_board.py
- tests/test_live_feed.py
- tests/test_live_standings.py
- tests/test_live_tab.py
- tests/test_yahoo_matchups.py

## Issues
- New manual workflow `Update Yahoo Rosters` (`.github/workflows/update-yahoo-rosters.yml`), authorised by the owner on 2026-10-20 (this replaces the earlier "no Yahoo credentials in Actions" rule for this one workflow). Setup, run and failure guide: `docs/YAHOO_ROSTER_WORKFLOW.md`.
- It has NOT been run on GitHub yet (it needs the `YAHOO_STORAGE_STATE` secret and two repo settings). Logic is tested locally; see the PR for exactly what was and was not exercised.
- Lineup-slot moves (bench <-> active) are treated as "no material change": 102 players moved on 2026-10-20 alone, they affect nothing, and a PR per lineup change would be noise. IL moves and status changes are material.
- Live cross-check on 2026-10-20: no metadata drift, no ineligible slots, IL labels intact, payroll matches. Flags for the commissioner: Porziņģis (BN), Strus (Util) and Harris (PF) are listed Out but not on IL; DHA is short at PG; HCMC, TT and Thịnh have 6 single-position players.

## Decisions Required

- Set the secret and repo settings (docs/YAHOO_ROSTER_WORKFLOW.md), then run the workflow once from main.

## Suggested Next Step
Open/update the PR from `feat/live-tab` if not already done, then request human/ChatGPT review of this packet.
