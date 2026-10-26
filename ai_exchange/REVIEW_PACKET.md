# Review Packet

Generated: 2026-10-26T14:59:21Z

## Task
Active Task

## Status
READY_FOR_REVIEW

## Git
Branch: feat/lottery-sim
Commit: 66f35d6
Base: main
Working tree: dirty

## GitHub
Repository: https://github.com/phamtienlong19/nba-talk-vn-dynasty
GitHub CLI: available
PR: https://github.com/phamtienlong19/nba-talk-vn-dynasty/pull/91 (OPEN)
CI: Claude Code Review: completed/success

## Deployment
Public URL: https://phamtienlong19.github.io/nba-talk-vn-dynasty/
HTTP: OK
Fingerprint: FRESH

## Changes
```
 .github/workflows/update-yahoo-standings.yml       |  82 +++
 ai_exchange/REVIEW_PACKET.md                       |  53 +-
 config/yahoo_league.json                           |   4 +-
 data/2026-27/standings/index.json                  |  25 +
 .../snapshots/ST-20261020T032209Z-7c49a8e0.json}   |  94 ++--
 .../snapshots/ST-20261026T080000Z-775801c1.json    | 271 ++++++++++
 docs/GOVERNANCE_ROADMAP.md                         |   5 +-
 docs/ROSTER_REFRESH.md                             |  11 +-
 docs/STANDINGS_REFRESH.md                          |  75 +++
 index.html                                         |  65 ++-
 scripts/build_league_state.py                      |  24 +-
 scripts/lottery_order.py                           |  56 ++
 scripts/update_yahoo_standings.py                  | 213 ++++++++
 scripts/yahoo_rosters.py                           |  95 +---
 scripts/yahoo_standings.py                         | 445 ++++++++++++++++
 .../NBA_Talk_Dynasty_Standings_2026-10-26.json     | 252 +++++++++
 tests/fixtures/yahoo/README.md                     |   7 +
 .../yahoo_standings_2026-10-26_real_sanitized.html | 416 +++++++++++++++
 tests/test_lottery_order.py                        |  60 +++
 tests/test_lottery_sim.py                          |  60 +++
 tests/test_scenario_rendering.py                   |  53 +-
 tests/test_update_yahoo_standings.py               | 588 +++++++++++++++++++++
 tests/test_yahoo_rosters.py                        |  90 +---
 23 files changed, 2792 insertions(+), 252 deletions(-)
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
- .github/workflows/update-yahoo-standings.yml
- ai_exchange/REVIEW_PACKET.md
- config/yahoo_league.json
- data/2026-27/standings/index.json
- data/2026-27/standings/snapshots/ST-20261020T032209Z-7c49a8e0.json
- data/2026-27/standings/snapshots/ST-20261026T080000Z-775801c1.json
- docs/GOVERNANCE_ROADMAP.md
- docs/ROSTER_REFRESH.md
- docs/STANDINGS_REFRESH.md
- index.html
- scripts/build_league_state.py
- scripts/lottery_order.py
- scripts/update_yahoo_standings.py
- scripts/yahoo_rosters.py
- scripts/yahoo_standings.py
- tests/fixtures/yahoo/NBA_Talk_Dynasty_Standings_2026-10-26.json
- tests/fixtures/yahoo/README.md
- tests/fixtures/yahoo/yahoo_standings_2026-10-26_real_sanitized.html
- tests/test_lottery_order.py
- tests/test_lottery_sim.py
- tests/test_scenario_rendering.py
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
Open/update the PR from `feat/lottery-sim` if not already done, then request human/ChatGPT review of this packet.
