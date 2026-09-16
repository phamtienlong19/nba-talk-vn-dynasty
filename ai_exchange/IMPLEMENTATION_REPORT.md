# Implementation Report

Bootstrap run: 2026-09-16.

## Phase A — public board (complete)

- Canonical source: `nba_talk_vn_dynasty_announcement_compact_hybrid35_fonts.html`
  (found in `~/Downloads`, no `(2)` suffix existed — see
  `docs/SOURCE_MANIFEST.md`).
- Sanitized (stripped 4 local Yahoo `@font-face`/`.woff2` declarations,
  which were confirmed unused dead CSS — no `.yicon` class references
  exist in the markup) and published as `index.html`.
- Verified: valid UTF-8, `<!doctype html>`, viewport meta present, all 4
  nav anchors (`draft-order`, `rosters-a`, `draft-pool`, `cap`) present,
  no `/mnt/data`, `file://`, `localhost`, or `assets/fonts` references, no
  `.woff`/`.woff2` references.
- Repo `nba-talk-vn-dynasty` created public under `phamtienlong19`, pushed
  to `main`, GitHub Pages enabled (branch `main`, folder `/`).

## Phase B — lightweight foundation (mostly complete, one blocker)

### Yahoo source adapter — working, verified live

- `scripts/fetch_yahoo_draft_analysis.py` fetched the live public
  endpoint on 2026-09-16: HTTP 200, 300 players, all with unique O-Rank
  1–300.
- `scripts/normalize_yahoo_players.py` normalizes using field paths
  **verified against the real response**, not guessed (see
  `docs/YAHOO_DATA_SOURCE.md`).
- Determined conclusively that `projected_auction_value` (not
  `average_auction_cost`) is the authoritative cap-dollar field: it
  reproduces the published R1–R9 (51.0625 ... 0.0), benchmark
  (152.5625), and cap range (130/175) **exactly** when recomputed live.
- `./refresh-yahoo.sh` runs the full fetch → normalize → cap-model →
  compare pipeline and reported `Status: MATCH` on 2026-09-16.

### Cap model — pure function, fully tested

- `scripts/cap_model.py` has no hardcoded R1–R9; `tests/test_cap_model.py`
  encodes the regression snapshot as a constructed fixture (16
  identical-valued players per band). 6/6 tests pass, including
  structural rejection tests (missing rank, duplicate rank, insufficient
  count) and an order-independence check.

### Roster baseline — RESOLVED, source file supplied by user

`nba_talk_vn_dynasty_forensic_state_2026-08-20(6).md` did not exist
anywhere on this machine at bootstrap time (exhaustive search of
`~/Downloads`, including nested/archived subfolders — see
`docs/SOURCE_MANIFEST.md`). The user subsequently placed the file
directly into `local_sources/` as
`nba_talk_vn_dynasty_forensic_state_2026-08-20.md`.

What was done:

- `data/2026-27/franchises.json` — built directly from the canonical
  16-team order given explicitly in the bootstrap spec. Verified: 16
  franchises, exact canonical order, stable `franchise-01`..`franchise-16`
  IDs.
- `scripts/import_forensic_rosters.py` — run against the supplied file.
  Parses only the Section-2 `teams.md` code block, hard-fails on wrong
  team order, wrong per-team counts, wrong total (≠232), duplicate
  ownership, or detected drift into projected-keeper/cut/FA-pool/
  infographic sections. Output: 232 assignments across 16 franchises.
- `data/2026-27/prekeeper_rosters.json` — generated and committed with
  the full 232-assignment pre-keeper ownership baseline.
- `tests/test_roster_baseline.py` — all 7 tests pass: franchise count,
  canonical order, stable IDs, total assignment count (232), no
  duplicate ownership, exact per-franchise counts
  (`15,15,14,15,13,14,13,15,13,15,15,15,15,15,15,15`), and all 8 anchor
  ownership facts (Wembanyama → franchise-01, Giannis → franchise-03,
  Karl-Anthony Towns → franchise-04, Luka Dončić → franchise-09, Cooper
  Flagg → franchise-12, Shai Gilgeous-Alexander → franchise-13, Nikola
  Jokić → franchise-11, Donovan Mitchell → franchise-16).

### Docs — complete

All of `docs/SOURCE_MANIFEST.md`, `docs/OPEN_RULE_QUESTIONS.md`,
`docs/LEAGUE_RULES_MODEL.md` (summarized from the full DOCX, read in
its entirety), `docs/RULE_AUTOMATION_MATRIX.md`,
`docs/LEGACY_XLSX_REPLACEMENT.md`, `docs/DATA_MODEL.md`,
`docs/CAP_MODEL.md`, `docs/YAHOO_DATA_SOURCE.md`, and
`docs/PRODUCT_SCOPE.md` were written. Historical named tank-violator
enforcement records from the DOCX were deliberately not reproduced
(local-only source, per Section 28).

## Not done / out of scope (by design)

- Lottery randomness, allocation protocol, ceremony — owned by
  `nba-talk-vn-lottery`, never touched.
- Any transaction ledger, generated-board pipeline, commissioner UI,
  Yahoo OAuth, or rule-enforcement automation — explicitly future-phase
  per `docs/PRODUCT_SCOPE.md` and Section 51 (do not overengineer).
