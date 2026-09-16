# Review Notes

Read by `./handoff.sh` and spliced into `ai_exchange/REVIEW_PACKET.md`'s
"Issues"/"Decisions Required" sections. Overwrite freely per task — this
file isn't meant to accumulate history (Git already has that).

## Issues

- Visual/mobile QA for this font change could not be run in this
  session: no headless browser or screenshot tool is available under
  this non-interactive run's tool allowlist (same limitation as the
  first Samsung Sans pass on this issue). The mobile-overflow fix
  (`letter-spacing:-.02em` on `.gap-big`/`.cap-gap`, see
  `IMPLEMENTATION_REPORT.md`) is a calculated estimate based on
  Roboto Mono's vs. Arial's average digit advance width, not a
  verified screenshot.
- Everything else (font swap scope, weight mapping, removing the old
  Yahoo/Samsung Sans references, no proprietary binaries committed)
  was verified directly in `index.html` plus `./validate.sh` and the
  test suite.

## Decisions Required

- None. Please do a quick visual pass (desktop + a ~390px-wide mobile
  view) on the KEEPERS cards and the CAP grid before merging, since
  this session couldn't screenshot it — specifically the `"NN TO
  FLOOR"` / `"NN ROOM"` chips called out above.
