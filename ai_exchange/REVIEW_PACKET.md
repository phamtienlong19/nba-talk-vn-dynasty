# Review Packet

Generated: 2026-10-19T15:15:02Z

## Task
Active Task

## Status
READY_FOR_REVIEW

## Git
Branch: feat/yahoo-roster-acquisition
Commit: 60eef8c
Base: main
Working tree: dirty

## GitHub
Repository: https://github.com/phamtienlong19/nba-talk-vn-dynasty
GitHub CLI: available
PR: https://github.com/phamtienlong19/nba-talk-vn-dynasty/pull/59 (OPEN)
CI: Claude Code Review: completed/success

## Deployment
Public URL: https://phamtienlong19.github.io/nba-talk-vn-dynasty/
HTTP: OK
Fingerprint: FRESH

## Changes
```
 ai_exchange/CURRENT_STATE.json                     |    7 +-
 ai_exchange/REVIEW_NOTES.md                        |   10 +-
 ai_exchange/REVIEW_PACKET.md                       |  156 +-
 config/cap_policy.json                             |    6 +
 config/yahoo_league.json                           |    8 +
 data/2026-27/rosters/index.json                    |   11 +-
 .../rosters/snapshots/RS-2026-10-19-878cd6e3.json  | 1079 +++++++++++
 data/2026-27/rosters/team_map.json                 |  115 +-
 data/2026-27/unlisted_players.json                 |   14 +
 docs/ROSTER_REFRESH.md                             |   95 +-
 docs/YAHOO_API_FEASIBILITY.md                      |    9 +
 index.html                                         |  176 +-
 scripts/build_league_state.py                      |   52 +-
 scripts/import_rosters.py                          |   56 +-
 scripts/league_state.py                            |   31 +-
 scripts/season_state.py                            |   35 +-
 scripts/what_if.py                                 |    6 +-
 scripts/yahoo_rosters.py                           |  631 ++++++
 tasks/ACTIVE.md                                    |    6 +-
 tests/fixtures/yahoo/observation_2026-10-19.json   | 2003 ++++++++++++++++++++
 tests/fixtures/yahoo/team16_2026-10-19.html        |  316 +++
 tests/fixtures/yahoo/team2_2026-10-19.html         |  190 ++
 tests/fixtures/yahoo/team8_2026-10-19.html         |  232 +++
 tests/test_fa_draft_pool.py                        |    2 +-
 tests/test_final_keeper_freeze.py                  |    2 +-
 tests/test_league_state_builders.py                |    6 +-
 tests/test_league_state_data.py                    |   10 +-
 tests/test_scenario_rendering.py                   |   56 +-
 tests/test_season_ops.py                           |   98 +-
 tests/test_yahoo_rosters.py                        |  616 ++++++
 30 files changed, 5766 insertions(+), 268 deletions(-)
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
- ai_exchange/CURRENT_STATE.json
- ai_exchange/REVIEW_NOTES.md
- ai_exchange/REVIEW_PACKET.md
- config/cap_policy.json
- config/yahoo_league.json
- data/2026-27/rosters/index.json
- data/2026-27/rosters/snapshots/RS-2026-10-19-878cd6e3.json
- data/2026-27/rosters/team_map.json
- data/2026-27/unlisted_players.json
- docs/ROSTER_REFRESH.md
- docs/YAHOO_API_FEASIBILITY.md
- index.html
- scripts/build_league_state.py
- scripts/import_rosters.py
- scripts/league_state.py
- scripts/season_state.py
- scripts/what_if.py
- scripts/yahoo_rosters.py
- tasks/ACTIVE.md
- tests/fixtures/yahoo/observation_2026-10-19.json
- tests/fixtures/yahoo/team16_2026-10-19.html
- tests/fixtures/yahoo/team2_2026-10-19.html
- tests/fixtures/yahoo/team8_2026-10-19.html
- tests/test_fa_draft_pool.py
- tests/test_final_keeper_freeze.py
- tests/test_league_state_builders.py
- tests/test_league_state_data.py
- tests/test_scenario_rendering.py
- tests/test_season_ops.py
- tests/test_yahoo_rosters.py

## Issues
- `rosters/team_map.json` maps all 16 Yahoo team ids to franchises (name prefix + every Yahoo-listed player on that team belongs to that franchise). Please confirm.
- First Yahoo import committed (RS-2026-10-19-878cd6e3): 18 players added, 3 dropped (Risacher, Will Riley, Santi Aldama); payroll unchanged everywhere. Jayden Quaintance recorded at $0 under the owner's 2026-10-19 rule.
- The 6 provisional rookies are still provisional (Yahoo ids appear as link candidates); not linked.
- Yahoo's keeper-salary label for RJ Barrett is 5; the frozen salary is 0. Not changed.

- Team names now follow Yahoo (2026-10-19, `rosters/team_map.json` `name`): e.g. Bsy → Bulls Dynasty, sup fam → Crashed for Caleb, CrazyCat → Damageeeee, Maxfixe → Maxfixe, LC → Long con dynasty. The locked keeper freeze and franchises.json keep the old names as history.

- Roster checks (anti-tank limits, `config/roster_rules.json`) now show on every card as evidence: today DHA is short at PG (1 healthy, min 2); HCMC and TT have 6 and DonTrick, Thịnh and sup fam 7 single-position players (inside the 7 combo exception -> review). Nothing is labelled tanking.
- Second Yahoo import RS-2026-10-19-83f0a0bb (15:11Z): no roster change; adds Yahoo player status (O/Q/P) to the snapshot.

## Decisions Required

- Whether the single-position combo exception applies to HCMC, TT, DonTrick, Thịnh, sup fam.

- Whether to link the 6 provisional rookies to their Yahoo ids (`import_rosters.py link-provisional`).

## Suggested Next Step
Open/update the PR from `feat/yahoo-roster-acquisition` if not already done, then request human/ChatGPT review of this packet.
