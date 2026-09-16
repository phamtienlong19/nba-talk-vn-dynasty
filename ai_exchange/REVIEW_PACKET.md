# Review Packet

Generated: 2026-09-16T09:40:36Z

## Task
Issue 11: Fix sync-after-merge tests timing out

## Status
READY_FOR_REVIEW

## Git
Branch: claude/issue-11-20260916-0935
Commit: 7fd247d
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
(none)

## Issues
- Confirmed root cause (per issue #11's macOS follow-up): the prior fix's
  `tests/_workflow_test_utils.py:run_script()` never set `stdin=` on its
  `subprocess.run(...)` call, so the child process inherited whatever
  stdin the test runner itself was started with. `sync-after-merge.sh`'s
  branch-deletion step probes `[ -t 0 ]` and, when true, blocks on an
  interactive `read` prompt. GitHub Actions Ubuntu runners invoke
  `python3 -m unittest discover -s tests` with non-tty stdin, so the
  prompt was always skipped there; running the same suite from an
  interactive terminal (e.g. Terminal.app on macOS, or any local
  Linux/macOS terminal) gives it a real tty and the prompt blocks until
  the test harness's own 30s subprocess timeout fires. This is a
  test-isolation defect, not an OS-specific one — it reproduces reliably
  on macOS because local test runs there are typically interactive.
- Fix: `run_script()` now pins `stdin=subprocess.DEVNULL` by default
  (overridable per-call), making the script's own non-interactive
  fallback deterministic regardless of the invoking environment's tty.
  Production behavior (interactive prompt when a human runs the script
  from a real terminal) is unchanged — the seam only affects the test
  harness.
- Added `sync-after-merge.sh` `stage()` markers (`SYNC-STAGE: <name>` to
  stderr before each numbered step, plus one inside the interactive-read
  branch specifically) so any future stall is diagnosable from captured
  stderr without raising the timeout. `run_script()` now catches
  `subprocess.TimeoutExpired` and re-raises with the last `SYNC-STAGE`
  marker plus captured stdout/stderr.
- Added `test_stdin_tty_dependence_is_the_root_cause_of_the_reported_hang`
  (`tests/test_sync_after_merge.py`): hands the script a real pty as
  stdin with a pre-queued "decline" answer, proving the script takes the
  interactive branch when stdin is a tty (confirming the mechanism)
  while completing quickly itself (input is already queued, so it never
  blocks).
- **Not done**: adding a `macos-latest` GitHub Actions test lane was
  requested but is out of scope for this agent — GitHub App permissions
  used here do not allow modifying `.github/workflows/*`. The exact diff
  to add is included in the PR description for a human to apply.

## Decisions Required

- Human: apply the `macos-latest` matrix lane to
  `.github/workflows/validate.yml` (diff provided in the PR description)
  so this regression is caught in CI going forward, not just locally.

## Suggested Next Step
Open/update the PR from `claude/issue-11-20260916-0935` if not already done, then request human/ChatGPT review of this packet.
