# Review Packet

Generated: 2026-09-16T08:37:54Z

## Task
Issue 11: Fix sync-after-merge tests timing out

## Status
READY_FOR_REVIEW

## Git
Branch: claude/issue-11-20260916-0824
Commit: 4e72cbe
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
- Could not reproduce the reported 30s timeout in this sandbox (network
  calls require explicit approval here and `PUBLIC_URL` is empty in the
  test fixture, so `deployment_freshness.py check` was never reached).
  The fix removes the dependency on that incidental empty-URL skip
  regardless: `sync-after-merge.sh` now threads a
  `DEPLOYMENT_FRESHNESS_FETCH_CMD` override into
  `scripts/deployment_freshness.py check --fetch-cmd`, defaulting to the
  real HTTP fetch in production and to an injected offline fetcher in
  tests. A new test
  (`test_deployment_freshness_check_is_deterministic_when_public_url_set`)
  configures a non-empty `publicUrl` and asserts the check actually runs
  and returns `FRESH` fast via the injected fetcher, proving the seam
  works end-to-end rather than merely being skipped.

## Decisions Required

- Please confirm this addresses the timeout as observed in your
  environment (e.g. re-run CI on this branch) since it could not be
  reproduced locally.

## Suggested Next Step
Open/update the PR from `claude/issue-11-20260916-0824` if not already done, then request human/ChatGPT review of this packet.
