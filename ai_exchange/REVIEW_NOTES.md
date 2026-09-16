# Review Notes

Read by `./handoff.sh` and spliced into `ai_exchange/REVIEW_PACKET.md`'s
"Issues"/"Decisions Required" sections. Overwrite freely per task — this
file isn't meant to accumulate history (Git already has that).

## Issues

(none)

## Decisions Required

- `work-issue.sh` launches Claude Code with `claude -p --permission-mode
  auto`. `auto` mirrors this repo's normal interactive working mode
  (proceed without stopping for routine tool approvals, but still able
  to decline/stop on a genuinely blocking decision) rather than
  `bypassPermissions`/`--dangerously-skip-permissions`, which Claude
  Code's own `--help` discourages for anything touching the network
  (this invocation does: `git push`, `gh pr create`). If a different
  permission posture is wanted for unattended runs, that's a one-line
  change in `work-issue.sh`.
- `ai_exchange/ARTIFACT_MANIFEST.json` was left untouched: there's no
  established regeneration tooling for it (it wasn't produced by any
  script in this bootstrap), and hand-maintaining hashes for every file
  this pass touched risked getting it wrong. Flagging in case it's
  expected to stay in sync.
