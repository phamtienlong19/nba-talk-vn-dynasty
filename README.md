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

## Report a correction / start work on an issue

GitHub Issues are the canonical task inbox (use the "Correction / feedback"
template, or a blank issue). To implement one:

```bash
./work-issue.sh <issue-number>
```

Prepares a task branch + `tasks/ACTIVE.md` pointer and launches Claude
Code to implement it, validate, and open a PR (`Closes #N`, never
auto-merged). After a human merges the PR on GitHub:

```bash
./sync-after-merge.sh <PR-number>
```

Normalizes local/repo state (archives the completed task pointer, resets
`tasks/ACTIVE.md`, refreshes `ai_exchange/CURRENT_STATE.json` and the
deployment-freshness marker). See `CLAUDE.md` for the full workflow.

## Refresh Yahoo player/cap data (read-only, does not touch the board)

```bash
./refresh-yahoo.sh
```

Fetches Yahoo's public Draft Analysis endpoint, normalizes it, recomputes
the current R1–R9 / benchmark / cap-range formula, and reports whether the
formula band still equals the one the official band was approved against
(`config/cap_policy.json`; official 2026-27 band **131–178**, formula 131–177 —
the refresh never changes the official band). Never modifies
`index.html` automatically — see `docs/CAP_MODEL.md` and
`docs/YAHOO_DATA_SOURCE.md`.

The "Yahoo Ranking Refresh" GitHub Actions workflow (`workflow_dispatch`)
runs this same refresh in CI. When it reports `CHANGED`, it goes further
than the local script: `./promote-yahoo-refresh.sh` mechanically
regenerates the keeper board's Yahoo-sourced display fields (position/NBA
team/cap, never which players are kept) and the FA/DRAFT 60 pool, then
opens/updates exactly one PR (branch `automation/yahoo-refresh`) carrying
the refreshed `data/yahoo/` snapshot and both regenerations together.
Merging that PR is the human promotion approval — no separate issue/PR
follows. On `MATCH`, no PR is touched.

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

## Yahoo Top 300 commissioner export (generated)

`./refresh-yahoo.sh` (and the CHANGED-refresh PR) regenerates, in order:
normalized Yahoo snapshot → `exports/yahoo_top300_proj_dollar_rank.md`
(`scripts/export_yahoo_top300.py`) → `exports/yahoo_top300_proj_dollar_rank.xlsx`
(`scripts/export_yahoo_top300_xlsx.py`, derived from the Markdown, parity
re-checked on write; needs `pip install -r requirements.txt`). Both are linked
from the board's CAP page at stable paths. They are reference material only —
the cap model never reads them, and they contain pure Yahoo data (no cap policy, keeper, or dynasty content).

## League state: keepers, trades, picks (pre-draft layer)

`data/2026-27/` holds the OFFICIAL keeper freeze (**locked**), 48
stable pick ids, the structured trade ledger (Trades A–D are seeded as
`PROPOSED`, never official) and the draft ledger. The page's **TRADE LAB**,
**PICKS** and **OFFICIAL / SCENARIO** switch are generated from it by the
engine; see `docs/LEAGUE_STATE_MODEL.md`.

## What If (post-freeze, optional)

Top-bar **WHAT IF** (`?mode=whatif`) reprices the frozen keepers with a dated Yahoo snapshot and projects alternative keeper/cut sets and a hypothetical FA 60. Read-only; see `docs/WHAT_IF_MODE.md`.
