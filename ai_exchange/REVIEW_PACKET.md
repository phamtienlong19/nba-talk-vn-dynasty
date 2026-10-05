# Review Packet

Generated: 2026-10-05T04:05:37Z

## Task
Active Task

## Status
READY_FOR_REVIEW

## Git
Branch: fix/cap-model-salary-order-and-yahoo-export
Commit: 066319c
Base: main
Working tree: clean

## GitHub
Repository: https://github.com/phamtienlong19/nba-talk-vn-dynasty
GitHub CLI: available
PR: https://github.com/phamtienlong19/nba-talk-vn-dynasty/pull/26 (OPEN)
CI: Claude Code Review: in_progress/

## Deployment
Public URL: https://phamtienlong19.github.io/nba-talk-vn-dynasty/
HTTP: OK
Fingerprint: FRESH

## Changes
```
 .github/workflows/validate.yml                 |    3 +
 .github/workflows/yahoo-refresh.yml            |    8 +
 README.md                                      |   17 +-
 ai_exchange/CURRENT_STATE.json                 |   71 +-
 ai_exchange/IMPLEMENTATION_REPORT.md           |   55 +-
 ai_exchange/REVIEW_PACKET.md                   |  128 +-
 config/cap_policy.json                         |    9 +
 data/dynasty/consensus.json                    | 6605 +++++++++++++++++++++
 data/dynasty/draft_classes.json                |   22 +
 data/dynasty/sources/allaccess_categories.json | 3159 ++++++++++
 data/dynasty/sources/dynatyze.json             |  447 ++
 data/dynasty/sources/hashtagbasketball.json    | 2361 ++++++++
 data/dynasty/sources/nbcsports_rookies.json    |  281 +
 data/dynasty/sources/rotowire.json             |  509 ++
 data/yahoo/cap_snapshot.json                   |   30 +
 data/yahoo/players_normalized.json             | 7462 ++++++++++++++++++++++++
 data/yahoo/provenance.json                     |   15 +
 docs/CAP_MODEL.md                              |   76 +-
 docs/YAHOO_DATA_SOURCE.md                      |   11 +-
 exports/yahoo_top300_proj_dollar_rank.md       |  304 +
 exports/yahoo_top300_proj_dollar_rank.xlsx     |  Bin 0 -> 13118 bytes
 index.html                                     |  172 +-
 promote-yahoo-refresh.sh                       |   19 +-
 refresh-yahoo.sh                               |   60 +-
 requirements.txt                               |    1 +
 scripts/build_dynasty_consensus.py             |  189 +
 scripts/build_fa_draft_pool.py                 |  423 +-
 scripts/build_yahoo_refresh_result.py          |   66 +-
 scripts/cap_model.py                           |  120 +-
 scripts/export_yahoo_top300.py                 |  101 +
 scripts/export_yahoo_top300_xlsx.py            |  126 +
 scripts/normalize_yahoo_players.py             |    5 +-
 scripts/prepare_yahoo_data_pr.py               |    8 +-
 scripts/refresh_keeper_board_display.py        |  134 +-
 scripts/refresh_team_cap_summary.py            |  168 +
 scripts/write_yahoo_job_summary.py             |    7 +-
 tasks/ACTIVE.md                                |   23 +-
 tests/_yahoo_promote_test_utils.py             |   11 +
 tests/fixtures/yahoo_top300_2026-10-04.md      |  304 +
 tests/test_build_dynasty_consensus.py          |  161 +
 tests/test_build_yahoo_refresh_result.py       |   70 +
 tests/test_cap_model.py                        |  136 +-
 tests/test_fa_draft_pool.py                    |  333 +-
 tests/test_keeper_overrides.py                 |   82 +
 tests/test_official_cap_policy.py              |   87 +
 tests/test_promote_yahoo_refresh.py            |    2 +-
 tests/test_refresh_keeper_board_display.py     |  146 +-
 tests/test_refresh_team_cap_summary.py         |  158 +
 tests/test_refresh_yahoo_published_baseline.py |  107 +-
 tests/test_seattle_keeper_ceiling.py           |   59 +
 tests/test_yahoo_top300_export.py              |  218 +
 51 files changed, 24485 insertions(+), 584 deletions(-)
```

## Validation
- site validation: PASS
- tests: PASS (OK)
- Yahoo refresh: last local snapshot: draft_analysis_2026-10-05T032730Z.json
- live HTTP: OK

## Canonical State
Roster baseline: 16 franchises, 232 assignments
Cap snapshot: 131-178
Yahoo source timestamp: 2026-10-05T03:27:30Z

## Files Changed
- .github/workflows/validate.yml
- .github/workflows/yahoo-refresh.yml
- README.md
- ai_exchange/CURRENT_STATE.json
- ai_exchange/IMPLEMENTATION_REPORT.md
- ai_exchange/REVIEW_PACKET.md
- config/cap_policy.json
- data/dynasty/consensus.json
- data/dynasty/draft_classes.json
- data/dynasty/sources/allaccess_categories.json
- data/dynasty/sources/dynatyze.json
- data/dynasty/sources/hashtagbasketball.json
- data/dynasty/sources/nbcsports_rookies.json
- data/dynasty/sources/rotowire.json
- data/yahoo/cap_snapshot.json
- data/yahoo/players_normalized.json
- data/yahoo/provenance.json
- docs/CAP_MODEL.md
- docs/YAHOO_DATA_SOURCE.md
- exports/yahoo_top300_proj_dollar_rank.md
- exports/yahoo_top300_proj_dollar_rank.xlsx
- index.html
- promote-yahoo-refresh.sh
- refresh-yahoo.sh
- requirements.txt
- scripts/build_dynasty_consensus.py
- scripts/build_fa_draft_pool.py
- scripts/build_yahoo_refresh_result.py
- scripts/cap_model.py
- scripts/export_yahoo_top300.py
- scripts/export_yahoo_top300_xlsx.py
- scripts/normalize_yahoo_players.py
- scripts/prepare_yahoo_data_pr.py
- scripts/refresh_keeper_board_display.py
- scripts/refresh_team_cap_summary.py
- scripts/write_yahoo_job_summary.py
- tasks/ACTIVE.md
- tests/_yahoo_promote_test_utils.py
- tests/fixtures/yahoo_top300_2026-10-04.md
- tests/test_build_dynasty_consensus.py
- tests/test_build_yahoo_refresh_result.py
- tests/test_cap_model.py
- tests/test_fa_draft_pool.py
- tests/test_keeper_overrides.py
- tests/test_official_cap_policy.py
- tests/test_promote_yahoo_refresh.py
- tests/test_refresh_keeper_board_display.py
- tests/test_refresh_team_cap_summary.py
- tests/test_refresh_yahoo_published_baseline.py
- tests/test_seattle_keeper_ceiling.py
- tests/test_yahoo_top300_export.py

## Issues
None. Visual review (desktop + mobile) was run this session via headless
Playwright screenshots — see `ai_exchange/IMPLEMENTATION_REPORT.md`.

## Decisions Required

- Cameron Carr and Labaron Philon Jr. were reviewed per the correction
  pack's instruction but do not clear the CAP-first top 60 naturally
  (no Yahoo rank, $0 cap, no forced-inclusion guarantee for these two
  specifically) -- excluded. Flagging in case the owner wants either
  force-included the way the other 16 curated names are; that's a one-line
  change to `GUARANTEED_NAMES` in `scripts/build_fa_draft_pool.py`.

## Suggested Next Step
Open/update the PR from `fix/cap-model-salary-order-and-yahoo-export` if not already done, then request human/ChatGPT review of this packet.
