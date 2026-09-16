# Review Notes

Read by `./handoff.sh` and spliced into `ai_exchange/REVIEW_PACKET.md`'s
"Issues"/"Decisions Required" sections. Overwrite freely per task — this
file isn't meant to accumulate history (Git already has that).

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
