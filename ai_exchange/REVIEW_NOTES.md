# Review Notes

Read by `./handoff.sh` and spliced into `ai_exchange/REVIEW_PACKET.md`'s
"Issues"/"Decisions Required" sections. Overwrite freely per task — this
file isn't meant to accumulate history (Git already has that).

## Issues

- This session could not execute `./validate.sh`,
  `python3 -m unittest discover -s tests`, or `./handoff.sh` — the Bash
  tool's permission mode required an approval not available in this
  non-interactive run for anything beyond a small allowlist (git, ls,
  grep, cat, wc, `python3 --version`). `ai_exchange/REVIEW_PACKET.md`
  still reflects the previous task (PR #4) and was not regenerated.
  Please run those three commands locally/in CI before merging.

## Decisions Required

- Issue #5 attaches a `samsung-sans-4.zip` font-file bundle
  (GitHub user-attachment). This session's network access also required
  an approval it couldn't obtain, so the actual Samsung Sans font
  binaries were not downloaded or embedded via `@font-face`. Only the
  CSS `font-family` names were swapped from `"Yahoo Sans"`/
  `"Yahoo Sans Cond"` to `"Samsung Sans"`/`"Samsung Sans Cond"`, matching
  the pre-existing pattern of referencing a font by name with a system
  fallback rather than self-hosting it. A human (or an agent with
  network/file-download access) should confirm whether the attached
  files should be committed under a static asset path (e.g.
  `assets/fonts/`) with real `@font-face` declarations for the font to
  actually render as Samsung Sans on non-Samsung devices.
