# Future Canonical Data Model

Design-direction schema for the eventual league-management system. Two
entities below are already real and committed
(`data/2026-27/franchises.json`, and `prekeeper_rosters.json` once the
forensic source file is supplied — see `docs/OPEN_RULE_QUESTIONS.md`).
Everything else is direction, not built state — do not assume it exists.

## SEASON
```
seasonId
rulesVersion
status
```

## FRANCHISE
```
franchiseId        -- persistent identity, independent of display name
```
Implemented today as `franchiseId` in `data/2026-27/franchises.json`
(`franchise-01`..`franchise-16`), a software bootstrap identity — not a
claim that the legacy workbook used these IDs.

## MANAGER
```
managerId
displayName
```
Not yet split out. Today's `displayName` strings (e.g. `"Hai | GTA San
Antonio"`) conflate manager and team name losslessly, per Section 6 of
the bootstrap spec — do not aggressively parse them until this entity is
introduced.

## TEAM_SEASON
```
seasonId
franchiseId
teamName
managerId
division
```

## PLAYER
```
playerId
yahooPlayerKey
canonicalName
nbaTeam
eligiblePositions[]
```
Sourced from the Yahoo adapter's normalized output
(`scripts/normalize_yahoo_players.py`) once player identity needs to be
persisted rather than recomputed per refresh.

## PLAYER_MARKET_VALUE
```
season
playerId
oRank
capDollars
source
effectiveAt
sourceLeagueKey
```
Sourced from `scripts/fetch_yahoo_draft_analysis.py` /
`normalize_yahoo_players.py`. See `docs/YAHOO_DATA_SOURCE.md` for the
verified field mapping.

## ROSTER_OWNERSHIP
```
season
franchiseId
playerId
slot/status
```
Implemented today as `data/2026-27/prekeeper_rosters.json` (pending the
forensic source file), keyed by `playerName` rather than `playerId` —
Yahoo identity linkage happens later, only when a reliable name→
`playerKey` match exists (Section 3A of the bootstrap spec: never invent
Yahoo player IDs during import).

## DRAFT_ASSET
```
season
round
originalFranchiseId
currentFranchiseId
pickNumber/status
```

## TRANSACTION
```
transactionId
type
timestamp
effectiveDate
status
approvedBy
```

## TRANSACTION_LEG
```
transactionId
franchiseId
assetType
assetId
direction
```

## CAP_SNAPSHOT
```
season
franchiseId
checkpoint
salary
floor
ceiling
status
yahooSourceTimestamp
```

## COMPLIANCE_EVENT
```
type
franchiseId
season
severity
evidence
commissionerDecision
```
Deliberately carries `commissionerDecision` as a first-class field rather
than a computed verdict — see `docs/RULE_AUTOMATION_MATRIX.md`.

## RULESET
```
version
effectiveSeason
```
Rules change over time (Section 38 of the bootstrap spec) — keeper count,
roster slots, playoff count, lottery participant set/weights, the Rank
3/4 draft bonus, the cap formula, the Yahoo source league key, tank
penalties, and trade windows have all changed historically or may again.
A `rulesVersion` is never overwritten in place; new versions are added,
old ones preserved.

## Ownership vs. market-value provenance (critical distinction)

```
FORENSIC teams.md snapshot  →  who owns which player (ROSTER_OWNERSHIP)
Yahoo public adapter        →  current player metadata / cap dollars (PLAYER_MARKET_VALUE)
```

Never overwrite ownership merely because Yahoo metadata changed, and
never overwrite current Yahoo metadata with a stale forensic-snapshot
value (Section 3A).
