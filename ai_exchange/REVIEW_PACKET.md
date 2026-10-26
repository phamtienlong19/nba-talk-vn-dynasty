# Review Packet

Generated: 2026-10-26T14:39:42Z

## Task
Active Task

## Status
READY_FOR_REVIEW

## Git
Branch: feat/standings-refresh
Commit: aea67b9
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
 config/yahoo_league.json                           |   4 +-
 data/2026-27/standings/index.json                  |  25 +
 .../snapshots/ST-20261020T032209Z-49219eef.json}   |  94 ++--
 .../snapshots/ST-20261026T080000Z-3dab0aad.json    | 271 ++++++++++
 index.html                                         |   2 +-
 scripts/build_league_state.py                      |  15 +-
 scripts/update_yahoo_standings.py                  | 213 ++++++++
 scripts/yahoo_rosters.py                           |  95 +---
 scripts/yahoo_standings.py                         | 435 ++++++++++++++++
 .../NBA_Talk_Dynasty_Standings_2026-10-26.json     | 252 +++++++++
 .../yahoo_standings_2026-10-26_real_sanitized.html | 416 +++++++++++++++
 tests/test_update_yahoo_standings.py               | 571 +++++++++++++++++++++
 tests/test_yahoo_rosters.py                        |  88 +---
 13 files changed, 2259 insertions(+), 222 deletions(-)
```

## Validation
- site validation: PASS
- tests: PASS (keeper freeze is LOCKED -- baseline not regenerated (immutable).)
- Yahoo refresh: not run this session
- live HTTP: OK

## Canonical State
Roster baseline: 16 franchises, 232 assignments
Cap snapshot: 131-178
Yahoo source timestamp: 2026-10-05T03:27:30Z

## Files Changed
- config/yahoo_league.json
- data/2026-27/standings/index.json
- data/2026-27/standings/snapshots/ST-20261020T032209Z-49219eef.json
- data/2026-27/standings/snapshots/ST-20261026T080000Z-3dab0aad.json
- index.html
- scripts/build_league_state.py
- scripts/update_yahoo_standings.py
- scripts/yahoo_rosters.py
- scripts/yahoo_standings.py
- tests/fixtures/yahoo/NBA_Talk_Dynasty_Standings_2026-10-26.json
- tests/fixtures/yahoo/yahoo_standings_2026-10-26_real_sanitized.html
- tests/test_update_yahoo_standings.py
- tests/test_yahoo_rosters.py

## Issues
- New manual workflow `Update Yahoo Rosters` (`.github/workflows/update-yahoo-rosters.yml`), authorised by the owner on 2026-10-20 (this replaces the earlier "no Yahoo credentials in Actions" rule for this one workflow). Setup, run and failure guide: `docs/YAHOO_ROSTER_WORKFLOW.md`.
- It has NOT been run on GitHub yet (it needs the `YAHOO_STORAGE_STATE` secret and two repo settings). Logic is tested locally; see the PR for exactly what was and was not exercised.
- Lineup-slot moves (bench <-> active) are treated as "no material change": 102 players moved on 2026-10-20 alone, they affect nothing, and a PR per lineup change would be noise. IL moves and status changes are material.
- Live cross-check on 2026-10-20: no metadata drift, no ineligible slots, IL labels intact, payroll matches. Flags for the commissioner: Porziņģis (BN), Strus (Util) and Harris (PF) are listed Out but not on IL; DHA is short at PG; HCMC, TT and Thịnh have 6 single-position players.

## Decisions Required

- Set the secret and repo settings (docs/YAHOO_ROSTER_WORKFLOW.md), then run the workflow once from main.

## Suggested Next Step
Open/update the PR from `feat/standings-refresh` if not already done, then request human/ChatGPT review of this packet.
