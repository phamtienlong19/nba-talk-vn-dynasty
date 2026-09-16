# Legacy XLSX Replacement

`Dynasty Cap Space 2026.xlsx` (local-only, not committed — see
`docs/SOURCE_MANIFEST.md`) is the league's current operating model. It
contains two season tabs (`2025-2026`, `2024-2025`) and demonstrates:

- a player table (historically hand-entered ranks + salary values);
- nine 16-player rank bands, each averaged;
- a benchmark (sum of the nine band averages) and a ±15% cap range;
- per-team roster sections where player names are typed in by hand;
- `VLOOKUP`-style formulas resolving a roster name against the player
  table to pull its salary;
- per-team salary totals (sum of resolved player salaries);
- manually maintained draft/trade log sections that update pick
  ownership and evolving cap totals over the season.

**The formulas are not the problem.** `scripts/cap_model.py` reimplements
the band/benchmark/±15% formula faithfully (see `docs/CAP_MODEL.md`) and
it is correct, useful, and worth keeping. The problem is that a
spreadsheet's cells are forced to simultaneously act as database, user
interface, transaction ledger, calculation engine, and historical record
— so every trade, draft pick, or ranking update requires a human to find
the right cell and retype reality into it, with no ledger of *why* a cell
changed.

## Legacy flow

```
Yahoo public data
    ↓ manually copied / retyped
spreadsheet player table
    ↓
manual roster names (typed into each team's section)
    ↓
VLOOKUP (name → salary)
    ↓
SUM / band formulas (team cap, R1-R9, benchmark, range)
    ↓
manual draft + trade log edits
    ↓
XLSX state ("truth" lives in cells)
```

## Target flow

```
Yahoo public Draft Analysis adapter
    ↓ (scripts/fetch_yahoo_draft_analysis.py + normalize_yahoo_players.py)
normalized Players + market values (identity, NBA team, positions, O-Rank, capDollars)
    +
canonical ownership / transactions
    ↓ (data/2026-27/franchises.json, prekeeper_rosters.json today;
       a transaction ledger later — see docs/DATA_MODEL.md)
derived rosters
    ↓
cap engine (scripts/cap_model.py — same formula, pure function over canonical data)
    ↓
compliance engine (future — docs/RULE_AUTOMATION_MATRIX.md)
    ↓
generated public board
    ↓
same stable GitHub Pages URL
```

Concretely, this bootstrap already replaces two of the legacy workbook's
manual-entry surfaces:

1. **Player ranks/salaries** no longer need retyping from Yahoo into a
   spreadsheet — `./refresh-yahoo.sh` fetches and normalizes them
   directly, and `scripts/cap_model.py` recomputes the exact same
   band/benchmark/±15% formula the workbook used.
2. **Team roster ownership** has a source-derived starting point
   (`data/2026-27/franchises.json`; `prekeeper_rosters.json` pending the
   forensic source file, see `docs/OPEN_RULE_QUESTIONS.md`) instead of
   living only in hand-typed spreadsheet cells.

What is **not** replaced yet: the draft/trade log (still nothing but this
doc's design direction — see `docs/DATA_MODEL.md`'s `TRANSACTION` /
`TRANSACTION_LEG` entities), and the generated-board step (`index.html`
is still the hand-authored HTML snapshot, not yet generated from the JSON
data — see `docs/PRODUCT_SCOPE.md`, V2).
