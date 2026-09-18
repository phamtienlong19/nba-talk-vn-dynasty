# data/

Public, league-facing canonical state, committed as normalized JSON.

- `2026-27/franchises.json` — the 16-team canonical order and display
  names for the 2026-27 season.
- `2026-27/prekeeper_rosters.json` — the 232-assignment pre-keeper roster
  ownership baseline for 2026-27 (pending import — see
  `../docs/OPEN_RULE_QUESTIONS.md`).
- `yahoo/players_normalized.json`, `yahoo/cap_snapshot.json`,
  `yahoo/provenance.json` — the last Yahoo-verified player snapshot, its
  derived cap model, and fetch provenance. Written only by a human
  merging the `automation/yahoo-refresh` PR opened by
  `.github/workflows/yahoo-refresh.yml` — see
  `../docs/YAHOO_DATA_SOURCE.md` ("Committed candidate snapshot"). Never
  hand-edited; never written directly to `main` by CI.

These are not yet wired into `index.html` (see `../docs/PRODUCT_SCOPE.md`,
V2) but are the committed migration seed for the future canonical data
model (`../docs/DATA_MODEL.md`).
