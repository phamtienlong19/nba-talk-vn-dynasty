# Review Packet

Generated: 2026-09-16T10:33:15Z

## Task
Issue 5: Cosmetic Change to Samsung Sans Font

## Status
READY_FOR_REVIEW

## Git
Branch: claude/issue-5-20260916-1030
Commit: 2b1a18e
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
- Issue #5 asks to apply the Samsung Sans font (attached as
  `samsung-sans-4.zip`) to `index.html`, with real `@font-face` webfont
  loading rather than a cosmetic `font-family` name swap.
- The attachment (verified via `.issue-context/manifest.json`, sha256
  `b4cd9bc6...9d8b09a`, three re-uploads all identical) contains exactly
  five files: `SamsungSans-{Thin,Light,Regular,Medium,Bold}.ttf`. No
  condensed weight, no italic, no README, no LICENSE file.
- Font `name`-table metadata (extracted from all 5 files) shows
  copyright `© 2013 Samsung Electronics Co., Ltd.`, typeface produced by
  Dalton Maag Ltd, no license description, no license URL, no SIL Open
  Font License or comparable grant anywhere in the binaries or the
  archive.
- Samsung Sans is Samsung's proprietary corporate/brand typeface. With
  no license text shipped in the attachment and no embedded license
  grant, there is no basis to conclude public redistribution or
  web-embedding (committing the `.ttf` files into a public repo /
  serving them from GitHub Pages) is permitted.
- Per the issue's own instruction and `CLAUDE.md`'s human-decision
  boundary, this session did **not** commit the font binaries and did
  **not** wire up `@font-face` against them. `index.html` is unchanged
  from `main` (still `"Yahoo Sans"` / `"Yahoo Sans Cond"`) — a
  name-only rename was explicitly rejected in the issue as insufficient,
  and implementing real `@font-face` requires binaries this session is
  not authorized to publish.

## Decisions Required

- Human: confirm whether Samsung Sans may be legally redistributed and
  served from this repo's public GitHub Pages site (e.g. an internal
  Samsung font license, a purchased web-font license, or written
  permission). If confirmed, re-open/re-trigger with that confirmation
  and, ideally, any accompanying license file so it can be committed
  alongside the fonts for provenance.
- If licensing cannot be confirmed, decide whether to source a
  similarly-styled font under a redistributable license (e.g. an
  SIL-OFL geometric sans) instead of Samsung Sans, or drop this issue.
- Separately, note the attachment has no condensed-weight font — any
  future implementation should map the five available weights
  (Thin/Light/Regular/Medium/Bold) directly onto both the current
  regular and condensed usage sites in `index.html`, rather than
  inventing a "Samsung Sans Cond" family that doesn't exist in the
  attachment.

## Suggested Next Step
Open/update the PR from `claude/issue-5-20260916-1030` if not already done, then request human/ChatGPT review of this packet.
