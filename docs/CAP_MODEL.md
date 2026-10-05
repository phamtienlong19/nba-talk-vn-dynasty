# Cap Model

Pure calculation, implemented in `scripts/cap_model.py` (Python standard
library only, no hardcoded R1–R9 — those are regression expectations, not
part of the formula).

## Inputs

An iterable of player rows, each with:

```
capDollars   number, Yahoo projected auction value ($0 valid)
oRank        int, Yahoo O-Rank, unique (tie-break only)
```

At least 144 players. Row order is irrelevant.

## Calculation

The benchmark simulates a Yahoo salary-cap draft, so it uses **salary-draft
order — never O-Rank order**. (O-Rank is not salary order: e.g. a $5 player
at O-Rank 123 is drafted ahead of a $4 player at O-Rank 97.)

```
order      = players sorted by capDollars DESC, then oRank ASC (tie-break only)
top144     = first 144 of that order            # 9 buckets x 16
R1..R9     = mean(capDollars) of each consecutive group of 16 in `order`
benchmark  = sum(top144 capDollars) / 16        # == R1 + ... + R9
rawFloor   = benchmark * 0.85
rawCeiling = benchmark * 1.15
roundedFloor / roundedCeiling = round(raw...)   # nearest whole dollar
```

Yahoo O-Rank stays valid for display and for FA/DRAFT within-CAP-tier
relevance; it must not define the cap buckets.

## Current verified regression snapshot

`tests/test_cap_model.py` asserts, from the frozen fixture
`tests/fixtures/yahoo_top300_2026-10-04.md` (nothing hardcoded in
`cap_model.py`): top-144 sum 2468 → benchmark 154.25 → raw 131.1125 /
177.3875 → formula **131 / 177** (official band 131 / 178, see below). It also asserts the salary-order regression
(O-Rank 97 / $4 vs. O-Rank 123 / $5 → the $5 player is placed first).

## Published board snapshot history

| Promoted | League refresh timestamp | Floor / Ceiling |
|---|---|---|
| 2026-09-16 (original migration) | 2026-09-16 (live-matched) | 130 / 175 |
| 2026-09-18 | 2026-09-18T01:43:50Z | 131 / 177 (historical formula band; the corrected salary-order model reproduces it on the 2026-10-05 snapshot — the earlier O-Rank-bucket model had wrongly reported 130 / 176 and 153.25 / 153.4375) |
| 2026-10-05 | 2026-10-05T03:27:30Z | **131 / 178 official** (formula 131 / 177; commissioner ceiling override) |

The 2026-09-18 promotion (formula-only; historical) is recorded in `ai_exchange/CURRENT_STATE.json`
(`canonicalState.lastYahooRefresh`), including the human-review flags it
surfaced (one team over the new ceiling; an NBA-team swap worth a sanity
check). See `docs/YAHOO_DATA_SOURCE.md` for why `projected_auction_value`
is the authoritative `capDollars` field.

## Official band vs. formula band

The formula result and the league's **official operating band** are separate
things (`config/cap_policy.json`, `scripts/cap_model.py:apply_cap_policy`):

| Field | 2026-27 value | Meaning |
|---|---|---|
| `rawFloor` / `rawCeiling` | 131.1125 / 177.3875 | formula, unrounded |
| `formulaFloor` / `formulaCeiling` | 131 / 177 | formula, rounded |
| `officialFloor` / `officialCeiling` | **131 / 178** | commissioner policy |
| `ceilingOverride` | true | official ≠ formula |
| `approvedFormulaFloor` / `approvedFormulaCeiling` | 131 / 177 | formula result the official band was approved against |

The 178 ceiling is a governance decision (commissioner confirmed after the R9
review), not a claim that 177.3875 rounds to 178. `cap_model.py`'s math is not
bent to produce it. The board, CAP page, team totals and
`ai_exchange/CURRENT_STATE.json` (`capFloor`/`capCeiling`) show the official
band. A Yahoo refresh only updates market inputs: it reports whether the live
formula band still equals the approved one and never rewrites the official band
— changing it means editing `config/cap_policy.json` (a human decision).

## Governance

A live Yahoo recalculation that **differs** from the published snapshot
is not applied automatically. `./refresh-yahoo.sh` reports both values
side by side (`CURRENT BOARD SNAPSHOT` vs. `LIVE YAHOO RECALCULATION`,
`MATCH` or `CHANGED`) and leaves `index.html` untouched either way. A
commissioner-controlled season refresh decides when a new snapshot
becomes authoritative (see `docs/PRODUCT_SCOPE.md`, V1.1).
