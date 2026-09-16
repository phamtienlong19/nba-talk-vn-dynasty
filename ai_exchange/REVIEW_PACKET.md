# Review Packet

Generated: 2026-09-16T09:12:09Z

## Task
Issue 11: Fix sync-after-merge tests timing out

## Status
READY_FOR_REVIEW

## Git
Branch: claude/issue-11-20260916-0903
Commit: 1edac69
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
 ai_exchange/CURRENT_STATE.json |  2 +-
 ai_exchange/REVIEW_NOTES.md    | 38 +++++++++++---------
 sync-after-merge.sh            | 23 ++++++++++--
 tasks/ACTIVE.md                |  4 +--
 tests/_workflow_test_utils.py  | 49 ++++++++++++++++++++++++++
 tests/test_sync_after_merge.py | 80 ++++++++++++++++++++++++++++++++++++++----
 6 files changed, 168 insertions(+), 28 deletions(-)
```

## Validation
- site validation: PASS
- tests: PASS (OK)
- Yahoo refresh: not run this session
- live HTTP: OK

## Canonical State
Roster baseline: 16 franchises, 232 assignments
Cap snapshot: 130-175
Yahoo source timestamp: 2026-09-16T03:20:25Z

## Files Changed
- ai_exchange/CURRENT_STATE.json
- ai_exchange/REVIEW_NOTES.md
- sync-after-merge.sh
- tasks/ACTIVE.md
- tests/_workflow_test_utils.py
- tests/test_sync_after_merge.py

## Issues
- Confirmed root cause (per issue #11 follow-up): `sync-after-merge.sh`
  unconditionally ran `./validate.sh`, the full `python3 -m unittest
  discover -s tests`, and `./handoff.sh` (which itself runs that same
  `unittest discover` a second time, see `scripts/handoff.sh`) with no
  test-mode seam. `tests/test_sync_after_merge.py` exercises
  `sync-after-merge.sh` end-to-end as a subprocess, so this path was
  liable to recursively re-run the outer suite that is already executing
  the test.
- Fix: `sync-after-merge.sh` now reads
  `SYNC_AFTER_MERGE_VALIDATE_CMD` / `SYNC_AFTER_MERGE_TEST_CMD` /
  `SYNC_AFTER_MERGE_HANDOFF_CMD` overrides (defaulting to the real
  `./validate.sh`, `python3 -m unittest discover -s tests`, and
  `./handoff.sh` in production — unchanged). `tests/_workflow_test_utils.py`
  injects deterministic fakes for all three by default, logging each
  invocation to `$FAKE_CALL_LOG` so tests can assert the step actually ran.
  The two previously timing-out tests now assert the fakes were invoked.
  A new regression test
  (`test_real_test_command_stays_scoped_and_does_not_recurse`) runs with
  the production defaults (no fakes) inside the isolated fixture repo and
  asserts the internal test run discovers only its own single smoke test —
  never the real outer suite.

## Decisions Required

- (none)

## Suggested Next Step
Open/update the PR from `claude/issue-11-20260916-0903` if not already done, then request human/ChatGPT review of this packet.
