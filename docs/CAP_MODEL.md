# Cap Model

Pure calculation, implemented in `scripts/cap_model.py` (Python standard
library only, no hardcoded R1–R9 — those are regression expectations, not
part of the formula).

## Inputs

An iterable of player rows, each with:

```
oRank        int, Yahoo O-Rank, 1-based, unique
capDollars   number, projected cap dollars ($0 valid)
```

Ranks 1–144 must all be present exactly once. Row order is irrelevant.

## Calculation

```
R1 = mean(capDollars for oRank in 1..16)
R2 = mean(capDollars for oRank in 17..32)
R3 = mean(capDollars for oRank in 33..48)
R4 = mean(capDollars for oRank in 49..64)
R5 = mean(capDollars for oRank in 65..80)
R6 = mean(capDollars for oRank in 81..96)
R7 = mean(capDollars for oRank in 97..112)
R8 = mean(capDollars for oRank in 113..128)
R9 = mean(capDollars for oRank in 129..144)

benchmark   = R1 + R2 + ... + R9
rawFloor    = benchmark * 0.85
rawCeiling  = benchmark * 1.15
roundedFloor   = round(rawFloor)    # nearest whole dollar
roundedCeiling = round(rawCeiling)  # nearest whole dollar
```

Rounding uses Python's `round()` (round-half-to-even on exact .5 ties,
which do not occur in the current verified data — no tie-breaking policy
has been needed in practice).

## Current verified regression snapshot

`tests/test_cap_model.py` encodes a fixed regression fixture (16
identical-valued players per band, since a band of 16 identical values
has that value as its mean — a legitimate construction, not a
reverse-engineered shortcut), plus structural tests: insufficient
rankings rejected, duplicate rank rejected, missing rank rejected, row
order doesn't matter, $0 accepted. That fixture is independent of the
published board and does not need updating when the board's snapshot
changes.

## Published board snapshot history

| Promoted | League refresh timestamp | Floor / Ceiling |
|---|---|---|
| 2026-09-16 (original migration) | 2026-09-16 (live-matched) | 130 / 175 |
| 2026-09-18 | 2026-09-18T01:43:50Z | **131 / 177** (current) |

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
