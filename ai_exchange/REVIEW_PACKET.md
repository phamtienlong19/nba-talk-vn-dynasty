# Review Packet

Generated: 2026-11-25T06:35:32Z

## Task
Active Task

## Status
READY_FOR_REVIEW

## Git
Branch: feat/commissioner-tab
Commit: 51c291e
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
 .github/workflows/claude-code-review.yml           |    7 +-
 .github/workflows/heal-generated-conflicts.yml     |   41 +
 .github/workflows/nightly-tests.yml                |   49 +
 .github/workflows/pages.yml                        |   78 ++
 .github/workflows/update-live-data.yml             |    9 +
 .github/workflows/update-player-metadata.yml       |   93 ++
 .github/workflows/update-player-stats.yml          |   66 ++
 .github/workflows/update-roster-feed.yml           |   49 +
 .github/workflows/update-yahoo-rosters.yml         |   54 +-
 .github/workflows/update-yahoo-standings.yml       |   26 +-
 .github/workflows/validate.yml                     |   13 +-
 .gitignore                                         |    5 +
 CLAUDE.md                                          |   19 +-
 ai_exchange/IMPLEMENTATION_REPORT.md               |   11 +-
 ai_exchange/REVIEW_PACKET.md                       |  388 ++++--
 config/draft_lottery_rules.json                    |   25 +-
 config/roster_rules.json                           |    6 +-
 config/trade_rules.json                            |   14 +-
 data/2026-27/rosters/index.json                    |  299 ++++-
 .../rosters/snapshots/RS-2026-11-04-184c2108.json  | 1210 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-04-1ef07fff.json  | 1211 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-04-7e61e063.json  | 1211 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-12-614214db.json  | 1217 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-12-ad71628e.json  | 1215 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-12-b3828230.json  | 1217 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-13-23177149.json  | 1218 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-13-23f6e967.json  | 1213 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-13-5d065593.json  | 1211 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-14-e9b206e3.json  | 1211 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-16-03ecae9d.json  | 1205 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-17-303bdce1.json  | 1228 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-17-99384f16.json  | 1225 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-18-1b9a25b4.json  | 1226 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-18-2d342ecb.json  | 1219 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-18-bab745b3.json  | 1223 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-18-fd4cfea1.json  | 1226 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-19-5110b05d.json  | 1216 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-19-b1a98eb3.json  | 1229 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-19-eefb1e1a.json  | 1229 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-20-54817660.json  | 1232 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-20-99eb538e.json  | 1222 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-21-098a4b52.json  | 1235 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-21-3213642f.json  | 1240 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-21-3a5d4979.json  | 1236 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-21-7e3b8480.json  | 1238 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-22-0d569ede.json  | 1244 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-22-18f8c5ec.json  | 1247 ++++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-22-329a8b3f.json  | 1244 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-22-53eab6b8.json  | 1240 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-24-b5997500.json  | 1229 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-24-d8e95c25.json  | 1230 +++++++++++++++++++
 .../rosters/snapshots/RS-2026-11-25-e9bdd027.json  | 1231 +++++++++++++++++++
 data/2026-27/schedule.json                         |  587 +++++++++
 data/2026-27/season_transactions.json              |   94 ++
 data/2026-27/standings/index.json                  |   56 +-
 .../snapshots/ST-20261112T090500Z-9cb975d0.json    |  271 +++++
 .../snapshots/ST-20261116T091000Z-c455f86a.json    |  271 +++++
 .../snapshots/ST-20261118T090300Z-253f5a7c.json    |  271 +++++
 .../snapshots/ST-20261119T090200Z-538e0359.json    |  271 +++++
 .../snapshots/ST-20261120T090300Z-f7e95ebc.json    |  271 +++++
 .../snapshots/ST-20261124T090200Z-4e82f571.json    |  271 +++++
 data/2026-27/unlisted_players.json                 |   16 +
 data/2026-27/violations.json                       |   25 +
 data/yahoo/player_registry.json                    |  216 ++--
 data/yahoo/player_status.json                      |  164 ++-
 docs/BOT_PRS.md                                    |   23 +
 docs/HEALING_CONFLICTS.md                          |   25 +
 docs/LEAGUE_RULES_MODEL.md                         |   11 +
 docs/LEAGUE_STATE_MODEL.md                         |    9 +
 docs/LIVE_DATA.md                                  |   73 ++
 docs/SEASON_STATE_MODEL.md                         |    2 +-
 docs/YAHOO_DATA_SOURCE.md                          |    2 +-
 docs/YAHOO_ROSTER_WORKFLOW.md                      |    2 +-
 index.html                                         |  677 +++++++++--
 scripts/bot_pr.sh                                  |   44 +
 scripts/build_league_state.py                      |    4 +-
 scripts/build_live_feed.py                         |   12 +-
 scripts/build_roster_feed.py                       |   95 ++
 scripts/build_site.py                              |   44 +
 scripts/handoff.sh                                 |   28 +-
 scripts/heal_open_prs.sh                           |   31 +
 scripts/lineup_log.py                              |  153 +++
 scripts/live.css                                   |   24 +
 scripts/live_app.js                                |   84 +-
 scripts/live_days.py                               |   51 +-
 scripts/live_feed_loop.sh                          |   15 +
 scripts/live_page.py                               |   26 +-
 scripts/lottery_order.py                           |    4 +-
 scripts/player_log.py                              |   67 ++
 scripts/refresh_card_positions.py                  |   68 ++
 scripts/resolve_generated_conflicts.py             |   48 +
 scripts/roster_feed_loop.sh                        |   29 +
 scripts/run_tests.py                               |  270 +++++
 scripts/season_state.py                            |   27 +
 scripts/trade_checker.py                           |   27 +-
 scripts/update_player_log.py                       |   74 ++
 scripts/update_yahoo_matchups.py                   |   34 +
 scripts/update_yahoo_player_stats.py               |   81 ++
 scripts/update_yahoo_rosters.py                    |   11 +-
 scripts/update_yahoo_standings.py                  |    5 +-
 scripts/violations.py                              |   61 +
 scripts/what_if.css                                |    2 +
 scripts/what_if.py                                 |    2 +-
 scripts/what_if_app.js                             |   21 +-
 scripts/yahoo_player_stats.py                      |   84 ++
 scripts/yahoo_schedule.py                          |   65 +
 scripts/yahoo_teamday.py                           |    7 +-
 sync-after-merge.sh                                |   17 +-
 tests/_drive.py                                    |   47 +
 tests/_phone.py                                    |   41 +
 tests/_proposed.py                                 |    4 +-
 tests/_site.py                                     |   19 +
 tests/fixtures/yahoo/players/last7_free.html       |   47 +
 tests/fixtures/yahoo/players/season_2024_free.html |   47 +
 .../fixtures/yahoo/players/season_2026_taken.html  |   47 +
 tests/test_bot_prs.py                              |   42 +
 tests/test_build_site.py                           |   49 +
 tests/test_card_positions.py                       |   40 +
 tests/test_consistency.py                          |   55 +
 tests/test_export.py                               |   50 +-
 tests/test_fa_draft_pool.py                        |    4 +-
 tests/test_final_keeper_freeze.py                  |    4 +-
 tests/test_il_state.py                             |   93 ++
 tests/test_keeper_board.py                         |   35 +-
 tests/test_keeper_overrides.py                     |    4 +-
 tests/test_league_state_builders.py                |    6 +-
 tests/test_league_state_data.py                    |   14 +-
 tests/test_lineup_log.py                           |  110 ++
 tests/test_live_moves.py                           |   63 +
 tests/test_live_tab.py                             |   79 +-
 tests/test_lottery_eligibility.py                  |    5 +-
 tests/test_lottery_order.py                        |   10 +-
 tests/test_lottery_sim.py                          |   10 +-
 tests/test_my_team.py                              |   67 ++
 tests/test_official_cap_policy.py                  |    4 +-
 tests/test_phone.py                                |   44 +
 tests/test_player_card.py                          |  127 ++
 tests/test_player_log.py                           |  114 ++
 tests/test_player_metadata_workflow.py             |   37 +
 tests/test_player_stats.py                         |  138 +++
 tests/test_qol.py                                  |   23 +-
 tests/test_refresh_player_metadata.py              |    8 +-
 tests/test_refresh_team_cap_summary.py             |    4 +-
 tests/test_resolve_generated_conflicts.py          |   91 ++
 tests/test_roster_feed.py                          |  174 +++
 tests/test_run_tests.py                            |  110 ++
 tests/test_scenario_rendering.py                   |  101 +-
 tests/test_schedule.py                             |  143 +++
 tests/test_season_ops.py                           |   22 +-
 tests/test_seattle_keeper_ceiling.py               |    4 +-
 tests/test_trade_checker.py                        |   52 +-
 tests/test_trade_sketch.py                         |  117 ++
 tests/test_update_yahoo_rosters.py                 |   61 +-
 tests/test_update_yahoo_standings.py               |   11 +-
 tests/test_violations.py                           |   93 ++
 tests/test_what_if.py                              |    4 +-
 tests/test_yahoo_rosters.py                        |   16 +-
 tests/test_yahoo_roto_tool.py                      |   57 +
 tests/test_yahoo_top300_export.py                  |    4 +-
 tools/yahoo-roto/README.md                         |   40 +
 tools/yahoo-roto/leagues.json                      |    4 +
 tools/yahoo-roto/report.html                       |  118 ++
 tools/yahoo-roto/roto-live.yml                     |   71 ++
 tools/yahoo-roto/tests/test_yahoo_roto.py          |  184 +++
 tools/yahoo-roto/yahoo_roto.py                     |  571 +++++++++
 165 files changed, 49760 insertions(+), 682 deletions(-)
```

## Validation
- site validation: PASS
- tests: PASS (full run, 986 ran, 2 skipped, at 51c291e with uncommitted changes)
- Yahoo refresh: last local snapshot: draft_analysis_2026-10-05T032730Z.json
- live HTTP: OK

## Canonical State
Roster baseline: 16 franchises, 232 assignments
Cap snapshot: 131-178
Yahoo source timestamp: 2026-10-05T03:27:30Z

## Files Changed
- .github/workflows/claude-code-review.yml
- .github/workflows/heal-generated-conflicts.yml
- .github/workflows/nightly-tests.yml
- .github/workflows/pages.yml
- .github/workflows/update-live-data.yml
- .github/workflows/update-player-metadata.yml
- .github/workflows/update-player-stats.yml
- .github/workflows/update-roster-feed.yml
- .github/workflows/update-yahoo-rosters.yml
- .github/workflows/update-yahoo-standings.yml
- .github/workflows/validate.yml
- .gitignore
- CLAUDE.md
- ai_exchange/IMPLEMENTATION_REPORT.md
- ai_exchange/REVIEW_PACKET.md
- config/draft_lottery_rules.json
- config/roster_rules.json
- config/trade_rules.json
- data/2026-27/rosters/index.json
- data/2026-27/rosters/snapshots/RS-2026-11-04-184c2108.json
- data/2026-27/rosters/snapshots/RS-2026-11-04-1ef07fff.json
- data/2026-27/rosters/snapshots/RS-2026-11-04-7e61e063.json
- data/2026-27/rosters/snapshots/RS-2026-11-12-614214db.json
- data/2026-27/rosters/snapshots/RS-2026-11-12-ad71628e.json
- data/2026-27/rosters/snapshots/RS-2026-11-12-b3828230.json
- data/2026-27/rosters/snapshots/RS-2026-11-13-23177149.json
- data/2026-27/rosters/snapshots/RS-2026-11-13-23f6e967.json
- data/2026-27/rosters/snapshots/RS-2026-11-13-5d065593.json
- data/2026-27/rosters/snapshots/RS-2026-11-14-e9b206e3.json
- data/2026-27/rosters/snapshots/RS-2026-11-16-03ecae9d.json
- data/2026-27/rosters/snapshots/RS-2026-11-17-303bdce1.json
- data/2026-27/rosters/snapshots/RS-2026-11-17-99384f16.json
- data/2026-27/rosters/snapshots/RS-2026-11-18-1b9a25b4.json
- data/2026-27/rosters/snapshots/RS-2026-11-18-2d342ecb.json
- data/2026-27/rosters/snapshots/RS-2026-11-18-bab745b3.json
- data/2026-27/rosters/snapshots/RS-2026-11-18-fd4cfea1.json
- data/2026-27/rosters/snapshots/RS-2026-11-19-5110b05d.json
- data/2026-27/rosters/snapshots/RS-2026-11-19-b1a98eb3.json
- data/2026-27/rosters/snapshots/RS-2026-11-19-eefb1e1a.json
- data/2026-27/rosters/snapshots/RS-2026-11-20-54817660.json
- data/2026-27/rosters/snapshots/RS-2026-11-20-99eb538e.json
- data/2026-27/rosters/snapshots/RS-2026-11-21-098a4b52.json
- data/2026-27/rosters/snapshots/RS-2026-11-21-3213642f.json
- data/2026-27/rosters/snapshots/RS-2026-11-21-3a5d4979.json
- data/2026-27/rosters/snapshots/RS-2026-11-21-7e3b8480.json
- data/2026-27/rosters/snapshots/RS-2026-11-22-0d569ede.json
- data/2026-27/rosters/snapshots/RS-2026-11-22-18f8c5ec.json
- data/2026-27/rosters/snapshots/RS-2026-11-22-329a8b3f.json
- data/2026-27/rosters/snapshots/RS-2026-11-22-53eab6b8.json
- data/2026-27/rosters/snapshots/RS-2026-11-24-b5997500.json
- data/2026-27/rosters/snapshots/RS-2026-11-24-d8e95c25.json
- data/2026-27/rosters/snapshots/RS-2026-11-25-e9bdd027.json
- data/2026-27/schedule.json
- data/2026-27/season_transactions.json
- data/2026-27/standings/index.json
- data/2026-27/standings/snapshots/ST-20261112T090500Z-9cb975d0.json
- data/2026-27/standings/snapshots/ST-20261116T091000Z-c455f86a.json
- data/2026-27/standings/snapshots/ST-20261118T090300Z-253f5a7c.json
- data/2026-27/standings/snapshots/ST-20261119T090200Z-538e0359.json
- data/2026-27/standings/snapshots/ST-20261120T090300Z-f7e95ebc.json
- data/2026-27/standings/snapshots/ST-20261124T090200Z-4e82f571.json
- data/2026-27/unlisted_players.json
- data/2026-27/violations.json
- data/yahoo/player_registry.json
- data/yahoo/player_status.json
- docs/BOT_PRS.md
- docs/HEALING_CONFLICTS.md
- docs/LEAGUE_RULES_MODEL.md
- docs/LEAGUE_STATE_MODEL.md
- docs/LIVE_DATA.md
- docs/SEASON_STATE_MODEL.md
- docs/YAHOO_DATA_SOURCE.md
- docs/YAHOO_ROSTER_WORKFLOW.md
- index.html
- scripts/bot_pr.sh
- scripts/build_league_state.py
- scripts/build_live_feed.py
- scripts/build_roster_feed.py
- scripts/build_site.py
- scripts/handoff.sh
- scripts/heal_open_prs.sh
- scripts/lineup_log.py
- scripts/live.css
- scripts/live_app.js
- scripts/live_days.py
- scripts/live_feed_loop.sh
- scripts/live_page.py
- scripts/lottery_order.py
- scripts/player_log.py
- scripts/refresh_card_positions.py
- scripts/resolve_generated_conflicts.py
- scripts/roster_feed_loop.sh
- scripts/run_tests.py
- scripts/season_state.py
- scripts/trade_checker.py
- scripts/update_player_log.py
- scripts/update_yahoo_matchups.py
- scripts/update_yahoo_player_stats.py
- scripts/update_yahoo_rosters.py
- scripts/update_yahoo_standings.py
- scripts/violations.py
- scripts/what_if.css
- scripts/what_if.py
- scripts/what_if_app.js
- scripts/yahoo_player_stats.py
- scripts/yahoo_schedule.py
- scripts/yahoo_teamday.py
- sync-after-merge.sh
- tests/_drive.py
- tests/_phone.py
- tests/_proposed.py
- tests/_site.py
- tests/fixtures/yahoo/players/last7_free.html
- tests/fixtures/yahoo/players/season_2024_free.html
- tests/fixtures/yahoo/players/season_2026_taken.html
- tests/test_bot_prs.py
- tests/test_build_site.py
- tests/test_card_positions.py
- tests/test_consistency.py
- tests/test_export.py
- tests/test_fa_draft_pool.py
- tests/test_final_keeper_freeze.py
- tests/test_il_state.py
- tests/test_keeper_board.py
- tests/test_keeper_overrides.py
- tests/test_league_state_builders.py
- tests/test_league_state_data.py
- tests/test_lineup_log.py
- tests/test_live_moves.py
- tests/test_live_tab.py
- tests/test_lottery_eligibility.py
- tests/test_lottery_order.py
- tests/test_lottery_sim.py
- tests/test_my_team.py
- tests/test_official_cap_policy.py
- tests/test_phone.py
- tests/test_player_card.py
- tests/test_player_log.py
- tests/test_player_metadata_workflow.py
- tests/test_player_stats.py
- tests/test_qol.py
- tests/test_refresh_player_metadata.py
- tests/test_refresh_team_cap_summary.py
- tests/test_resolve_generated_conflicts.py
- tests/test_roster_feed.py
- tests/test_run_tests.py
- tests/test_scenario_rendering.py
- tests/test_schedule.py
- tests/test_season_ops.py
- tests/test_seattle_keeper_ceiling.py
- tests/test_trade_checker.py
- tests/test_trade_sketch.py
- tests/test_update_yahoo_rosters.py
- tests/test_update_yahoo_standings.py
- tests/test_violations.py
- tests/test_what_if.py
- tests/test_yahoo_rosters.py
- tests/test_yahoo_roto_tool.py
- tests/test_yahoo_top300_export.py
- tools/yahoo-roto/README.md
- tools/yahoo-roto/leagues.json
- tools/yahoo-roto/report.html
- tools/yahoo-roto/roto-live.yml
- tools/yahoo-roto/tests/test_yahoo_roto.py
- tools/yahoo-roto/yahoo_roto.py

## Issues
- New manual workflow `Update Yahoo Rosters` (`.github/workflows/update-yahoo-rosters.yml`), authorised by the owner on 2026-10-20 (this replaces the earlier "no Yahoo credentials in Actions" rule for this one workflow). Setup, run and failure guide: `docs/YAHOO_ROSTER_WORKFLOW.md`.
- It has NOT been run on GitHub yet (it needs the `YAHOO_STORAGE_STATE` secret and two repo settings). Logic is tested locally; see the PR for exactly what was and was not exercised.
- Lineup-slot moves (bench <-> active) are treated as "no material change": 102 players moved on 2026-10-20 alone, they affect nothing, and a PR per lineup change would be noise. IL moves and status changes are material.
- Live cross-check on 2026-10-20: no metadata drift, no ineligible slots, IL labels intact, payroll matches. Flags for the commissioner: Porziņģis (BN), Strus (Util) and Harris (PF) are listed Out but not on IL; DHA is short at PG; HCMC, TT and Thịnh have 6 single-position players.

## Decisions Required

- Set the secret and repo settings (docs/YAHOO_ROSTER_WORKFLOW.md), then run the workflow once from main.

## Suggested Next Step
Open/update the PR from `feat/commissioner-tab` if not already done, then request human/ChatGPT review of this packet.
