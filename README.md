# NBA Talk VN Dynasty

Public URL: **https://phamtienlong19.github.io/nba-talk-vn-dynasty/**

Public, read-only league reference board for the NBA Talk VN Dynasty
fantasy league. Sections:

- **Draft Order**
- **Keepers**
- **FA / Draft Pool**
- **Cap**

This is a separate project from `nba-talk-vn-lottery` — no runtime
dependency between the two. This site stays usable if the Lottery
application is offline.

## Update the board

```bash
./publish.sh ~/Downloads/new-board.html
```

Sanitizes (strips local Yahoo `@font-face`/`.woff` refs, rejects
`/mnt/data`, `file://`, `localhost`), validates, and — if valid — commits
and pushes as the new `index.html`.

## Refresh Yahoo player/cap data (read-only, does not touch the board)

```bash
./refresh-yahoo.sh
```

Fetches Yahoo's public Draft Analysis endpoint, normalizes it, recomputes
the current R1–R9 / benchmark / cap-range formula, and reports whether it
still matches the published board's `130–175` cap range. Never modifies
`index.html` automatically — see `docs/CAP_MODEL.md` and
`docs/YAHOO_DATA_SOURCE.md`.

## Architecture today

Static GitHub Pages. `index.html`, JSON data files, Python-standard-library
scripts, Bash, Git. No framework, no backend, no database.

## Architecture direction

```
Yahoo public Draft Analysis (player id, name, NBA team, positions, O-Rank, cap $)
        +
canonical pre-keeper ownership baseline (16 teams / 232 assignments,
sourced from the 2026-08-20 forensic roster snapshot)
        ↓
canonical transactions / ownership
        ↓
deterministic rules (cap, roster, pick ownership, cooldowns, compliance evidence)
        ↓
generated public league board
        ↓
same stable GitHub Pages URL
```

The legacy system being replaced is `Dynasty Cap Space 2026.xlsx`
(local-only, not committed to this public repo — see
`docs/SOURCE_MANIFEST.md`). Its formulas are correct and are preserved
(`scripts/cap_model.py`); what's being replaced is spreadsheet cells
acting as database + UI + ledger + calculation engine all at once. See
`docs/LEGACY_XLSX_REPLACEMENT.md`.

## Docs

- [`docs/PRODUCT_SCOPE.md`](docs/PRODUCT_SCOPE.md) — staged migration plan
- [`docs/DATA_MODEL.md`](docs/DATA_MODEL.md) — future canonical entities
- [`docs/CAP_MODEL.md`](docs/CAP_MODEL.md) — cap formula + regression snapshot
- [`docs/YAHOO_DATA_SOURCE.md`](docs/YAHOO_DATA_SOURCE.md) — verified Yahoo field mapping
- [`docs/LEAGUE_RULES_MODEL.md`](docs/LEAGUE_RULES_MODEL.md) — current rules, summarized
- [`docs/RULE_AUTOMATION_MATRIX.md`](docs/RULE_AUTOMATION_MATRIX.md) — what can/can't be automated
- [`docs/LEGACY_XLSX_REPLACEMENT.md`](docs/LEGACY_XLSX_REPLACEMENT.md) — legacy vs. target flow
- [`docs/SOURCE_MANIFEST.md`](docs/SOURCE_MANIFEST.md) — source file provenance
- [`docs/OPEN_RULE_QUESTIONS.md`](docs/OPEN_RULE_QUESTIONS.md) — unresolved gaps, including a blocked source file

## Development

```bash
./validate.sh                          # site validation
python3 -m unittest discover -s tests -v  # cap model, Yahoo normalization, roster baseline
./status.sh                            # current project state
```
