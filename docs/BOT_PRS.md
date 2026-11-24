# Bot pull requests: tokens, checks and auto-merge

Three scheduled workflows open a PR with data: **Update Yahoo Rosters**, **Update Yahoo Standings**, **Update Player Metadata**. They share
`scripts/bot_pr.sh`. Owner decision 2026-11-24 (CLAUDE.md): each may merge its own PR once its checks are green.

## What makes a PR safe to merge by itself
All of: the run's outcome is READY (or the metadata changed), the path guard proved only that workflow's own data files and the generated page
changed, `./validate.sh` and the tests passed in the run, and (rosters) `automerge_ok` says no ownership change. Anything else stays open for a human.

## The token (`ROSTER_PR_TOKEN`)
A PR opened with the built-in token has its checks held for a maintainer's "Approve and run workflows" click, and nothing is merged.
With the owner's token the author is a person, the checks run by themselves and the PR merges when they pass.

Create it once: GitHub > Settings > Developer settings > Fine-grained tokens > Generate. Resource owner: you; Repository access: **only this
repository**; Permissions: Contents **read and write**, Pull requests **read and write**, Metadata read. Copy the token, then
repository Settings > Secrets and variables > Actions > New repository secret, name `ROSTER_PR_TOKEN`. Tokens expire: set the longest allowed
and note the date; an invalid token falls back to the built-in one with a warning (no merge, a human approves).

Also turn on repository Settings > General > "Allow auto-merge" (optional: without it the helper waits for the PR's checks and merges).

## Failure handling
A failed step opens/updates the "Roster refresh needs attention" issue (rosters). The nightly full-suite run (`nightly-tests.yml`) opens a
`tests-red` issue. The roster run's own gate is validate + the roster/ownership tests, so a UI test cannot stop data refreshes.
