# Product Scope

Directional stages, not technology commitments. Each stage is additive —
nothing here justifies rebuilding what already works.

## V1 — Public board (done, this bootstrap)

Static, read-only, persistent GitHub Pages URL. `index.html` is a
sanitized copy of the current hand-authored board snapshot. No backend,
no database, no build step.

## V1.1 — Canonical baseline + Yahoo source adapter (this bootstrap)

- `data/2026-27/franchises.json`: source-derived 16-team canonical order,
  committed as normalized public JSON.
- `data/2026-27/prekeeper_rosters.json`: source-derived 232-assignment
  pre-keeper ownership baseline, pending the forensic source file (see
  `docs/OPEN_RULE_QUESTIONS.md`).
- `scripts/fetch_yahoo_draft_analysis.py` /
  `scripts/normalize_yahoo_players.py`: a verified, stdlib-only adapter
  for live public Yahoo player/rank/cap/team/position data.
- `scripts/cap_model.py`: the current cap formula as a pure, tested
  function.

None of this drives `index.html` yet — it exists as committed,
tested foundation for V2.

## V2 — Generated board

`index.html` is generated from `data/2026-27/*.json` + a refreshed Yahoo
snapshot, rather than hand-edited. The board's visible content becomes a
render step, not a source of truth.

## V3 — Transaction ledger

Trades, adds/drops, and draft-asset movement become explicit
`TRANSACTION`/`TRANSACTION_LEG` records (see `docs/DATA_MODEL.md`) that
*derive* updated ownership — never direct edits to a roster JSON file.

## V4 — Roster source integration

Roster-state import/sync from Yahoo and/or commissioner-entered
transactions becomes less manual than re-running a one-off import script
against a markdown snapshot.

## V5 — Commissioner operations

A review queue for `COMMISSIONER_REVIEW`-classified rules (see
`docs/RULE_AUTOMATION_MATRIX.md`), cap checkpoints, compliance evidence,
and season closeout tooling.
