# Implementation Report

Run: 2026-09-16 — Issue #5 (Samsung Sans replaced with open-font system)

## What changed

- **`index.html`**: removed every `"Yahoo Sans"` / `"Yahoo Sans Cond"`
  reference (Samsung Sans was never committed — blocked earlier on
  licensing, see Git history). Added a Google Fonts `<link>` for
  **Inter** (400/500/600/700/800) and **Roboto Mono** (500/600/700).
  No font binaries committed.
- **Inter** applied to all UI text: body, topbar/nav, headings, team
  identity (`.title`, `.brand`, `.team-name`), player/pool names,
  section labels, tags/chips.
- **Roboto Mono** applied only to numeric/data elements: cap totals
  (`.cap-total`, `.cap-num`), salary values (`.cap`, `.pool-cap`),
  gap/room text (`.gap-big`, `.cap-gap`), pick numbers (`.pick-slot`),
  ranks (`.pool-rank`, `.yahoo-rank`), the team seed badge
  (`.team-index`), and the unused legacy matrix cap column (`.mcap`).
  No condensed family was invented — the old `"...Cond"` stack is gone.
- **Font weights**: replaced the old ad-hoc 650–950 scale (tuned for a
  condensed display face) with the issue's suggested scale — Inter
  400 body / 500–600 labels, nav, player rows / 700–800 headings and
  team identity; Roboto Mono 500–700 for numeric emphasis.
- **Mobile overflow mitigation**: `"Yahoo Sans"/"Yahoo Sans Cond"`
  never matched an installed font, so the page always silently
  rendered on the Arial/Helvetica fallback already baked into each
  stack — this is the first time a real, distinct typeface renders.
  Roboto Mono's average digit advance (~0.6em) is measurably wider
  than Arial's (~0.556em); the tightest spot is the `"NN TO FLOOR"` /
  `"NN ROOM"` strings (`.gap-big`, `.cap-gap`) inside fixed ~108–132px
  grid columns on the 680px breakpoint. Added `letter-spacing:-.02em`
  to both to offset the width increase without changing box
  dimensions (layout preserved). No other numeric field was close
  enough to its container width to need the same treatment.
- Colors, grid layout, responsiveness breakpoints, and all league data
  are unchanged.

## Not done / limitation

- Could not render the page in a real browser in this session to
  visually confirm the mobile-overflow mitigation (no headless
  browser/screenshot tooling available under this session's
  non-interactive tool allowlist). The fix above is a calculated
  estimate, not a verified screenshot. See `REVIEW_NOTES.md`.

## Validation

- `./validate.sh`: PASS
- `python3 -m unittest discover -s tests`: 68 tests, PASS
- `./handoff.sh`: regenerated `REVIEW_PACKET.md`
