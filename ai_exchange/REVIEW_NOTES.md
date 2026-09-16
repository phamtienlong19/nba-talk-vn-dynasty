# Review Notes

Read by `./handoff.sh` and spliced into `ai_exchange/REVIEW_PACKET.md`'s
"Issues"/"Decisions Required" sections. Overwrite freely per task — this
file isn't meant to accumulate history (Git already has that).

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
