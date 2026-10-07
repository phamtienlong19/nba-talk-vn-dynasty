# League state model (pre-draft layer)

Operational state under the board. The board's FA/DRAFT 60 stays a
*recommendation*; this layer answers "who owns what right now".

```
CURRENT OFFICIAL STATE = KEEPER FREEZE + OFFICIAL TRADES + DRAFT EVENTS
SCENARIO STATE         = CURRENT OFFICIAL STATE + SELECTED PROPOSED/AGREED TRADES
```

Engine: `scripts/league_state.py` (pure, stdlib). Builder / embedder:
`scripts/build_league_state.py`. Player universe: `scripts/build_player_registry.py`.

## Files (`data/2026-27/` unless noted)

| File | Role |
|---|---|
| `keeper_freeze.json` | per-team keeper `playerKey`s. `status`: `projected` (now — taken from the board, **not** frozen) or `locked` (`lock-keepers` adds `lockedAt` + `lockDigest`; `baseline` then refuses to overwrite it) |
| `picks.json` | 48 stable pick ids (`2026-R1-03`), `originalOwner` (never overwritten). Current owner is derived |
| `trades.json` | atomic transactions: `PROPOSED` / `AGREED` / `OFFICIAL` / `VOID`; assets `{type, playerKey\|pickId, from, to}`; `dependsOn`; `order` |
| `draft_state.json` | append-only `DRAFT_PICK` events (empty pre-draft). Roster, availability, cap, pick completion and the draft cursor are derived from them |
| `data/yahoo/player_registry.json` | expanded (600) Yahoo universe, identity = `playerKey`; the only place player metadata/caps live |
| `snapshots/` | (optional) `KEEPER_FREEZE`, `PRE_DRAFT_LOCK`, `POST_DRAFT` checkpoints = input digests + derived ownership/cap, reproducible from the inputs |

Only `OFFICIAL` trades mutate canonical state. Cap is **never stored**: it is
the sum of registry `projectedAuctionValue` over the derived roster; room is
against the official ceiling in `config/cap_policy.json` (178).

## Validation (nothing is silently fixed)

Errors block a trade (not applied): `NOT_OWNED`, `BROKEN_DEPENDENCY`
(declared prerequisite inactive / not applied), `DEPENDENCY_ORDER`,
`DUPLICATE_ASSET`, `UNKNOWN_PLAYER/PICK`, `BAD_PARTICIPANT`,
`PICK_ALREADY_USED`. Warnings never block: `ASSET_COUNT_UNBALANCED`,
`CAP_OVER_CEILING`, `CAP_MOVES_AWAY_FROM_BAND`, `ROSTER_COUNT_ABOVE_9`
(confirm the final roster-size rule), `PRE_DRAFT_TRADE_LIMIT` (rules allow one
trade per team in the window; multiple legs for one team must fold into one
multi-team transaction — commissioner confirmation). Duplicate player/pick
ownership is rejected at load (`StateError`).

## Page

`scripts/build_league_state.py embed` computes every combination of the
selectable trades with the engine and embeds the results in `index.html`
(`#league-data`). The page only looks them up — it never re-implements the
engine. Surfaces: global OFFICIAL / SCENARIO switch + unmistakable banner,
TRADE LAB (scenarios · folded team impact · official vs scenario), PICKS
(current vs original owner, tap for history), per-team scenario strips,
scenario cap on the CAP page, and a searchable ALL AVAILABLE panel on the
FA/DRAFT page. Dynasty rank is never exposed in the operational data.
`?mode=scenario&trades=TRADE-A,TRADE-B` opens a scenario directly.

## Scenario rendering (one truth)

In SCENARIO mode a team card is rendered entirely from the derived scenario
state: roster rows (sent players removed, received players tagged IN, reusing
the board's own rows), cap total and status, player count and pick list all
come from the same `team_report` object. The official baseline is secondary
(`OFFICIAL 144 · DELTA −13`). "View movement" only explains the change; the
CUTS list is relabelled KEEPER-FREEZE CUTS and never rewritten by trades.
Constraint states (not trade quality): UNDER FLOOR, AT FLOOR, IN RANGE,
NEAR CEILING (room ≤ 4, the board's existing convention), AT CEILING, OVER CEILING.

## Commands

```bash
python3 scripts/build_player_registry.py           # fetch 600-player registry
python3 scripts/build_league_state.py baseline     # projected keepers + picks from the board
python3 scripts/build_league_state.py lock-keepers # freeze the keeper baseline (immutable)
python3 scripts/build_league_state.py embed        # refresh page data
```

## Deferred (next patch)

Pick timer, on-the-clock flow, draft confirm / undo, live ticker, Messenger
copy, shared realtime backend, draft-order chips showing "via", snapshot UI.
