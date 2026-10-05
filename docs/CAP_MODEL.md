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
177.3875 → **131 / 177**. It also asserts the salary-order regression
(O-Rank 97 / $4 vs. O-Rank 123 / $5 → the $5 player is placed first).

## Published board snapshot history

| Promoted | League refresh timestamp | Floor / Ceiling |
|---|---|---|
| 2026-09-16 (original migration) | 2026-09-16 (live-matched) | 130 / 175 |
| 2026-09-18 | 2026-09-18T01:43:50Z | **131 / 177** (current; the corrected salary-order model reproduces it on the 2026-10-05 snapshot — the earlier O-Rank-bucket model had wrongly reported 130 / 176 and 153.25 / 153.4375) |

The 2026-09-18 promotion is recorded in `ai_exchange/CURRENT_STATE.json`
(`canonicalState.lastYahooRefresh`), including the human-review flags it
surfaced (one team over the new ceiling; an NBA-team swap worth a sanity
check). See `docs/YAHOO_DATA_SOURCE.md` for why `projected_auction_value`
is the authoritative `capDollars` field.

## Governance

A live Yahoo recalculation that **differs** from the published snapshot
is not applied automatically. `./refresh-yahoo.sh` reports both values
side by side (`CURRENT BOARD SNAPSHOT` vs. `LIVE YAHOO RECALCULATION`,
`MATCH` or `CHANGED`) and leaves `index.html` untouched either way. A
commissioner-controlled season refresh decides when a new snapshot
becomes authoritative (see `docs/PRODUCT_SCOPE.md`, V1.1).
