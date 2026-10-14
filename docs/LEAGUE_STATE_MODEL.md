# League state model (pre-draft layer)

Operational state under the board. The board's FA/DRAFT 60 stays a
*recommendation*; this layer answers "who owns what right now".

```
CURRENT OFFICIAL STATE = OFFICIAL KEEPER FREEZE + OFFICIAL TRADES + DRAFT EVENTS
SCENARIO STATE         = CURRENT OFFICIAL STATE + SELECTED PROPOSED/AGREED TRADES
```

Engine: `scripts/league_state.py` (pure, stdlib). Builder / embedder:
`scripts/build_league_state.py`. Player universe: `scripts/build_player_registry.py`.

## Files (`data/2026-27/` unless noted)

| File | Role |
|---|---|
| `keeper_freeze.json` | per-team keeper `playerKey`s. `status`: `locked` — the OFFICIAL keeper freeze (final declarations, 2026-10-07): `lockedAt`, `lockDigest`, and a `checkpoint` (official band 131–178, per-team keeper cap / room / status, provenance). `baseline` refuses to overwrite a locked freeze; `projected` is only the pre-declaration state |
| `picks.json` | 48 stable pick ids (`2026-R1-03`), `originalOwner` (never overwritten), plus `historicalTransfers` (already-completed last-season swaps, replayed into the baseline and tagged `historical`). Current owner is derived |
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

## Processed pre-draft trades (2026-10-13)

TRADE-A..F were promoted to `OFFICIAL` as one batch (`execution.batch = 2026-10-13-pre-draft`), replayed once in `order`
(dependencies first) over the locked freeze + historical pick swaps. Nothing is stored as a result, so rebuilds cannot
double-apply; an official trade that fails validation raises `StateError` instead of being dropped. `resolve(..., "SCENARIO")`
refuses to select an OFFICIAL trade. Pre-trade state: `snapshots/KEEPER_FREEZE.json`; post-trade checkpoint:
`snapshots/PRE_DRAFT_LOCK.json`. `audit_official()` reconciles ownership/caps and reports rule violations (roster > 9,
pre-draft trade limit) without correcting them. `build_league_state.py sync-ledger` keeps the first-page draft-order
ledger (current owner + `VIA <original>`) in step with the official state.

## Live draft (from 2026-10-14)

`data/2026-27/draft_results.json` is the commissioner-confirmed record; `scripts/import_draft_results.py` resolves names
against the Yahoo player master and appends `DRAFT_PICK` events to `draft_state.json` idempotently (rejects contradictions,
repeat players, out-of-order results and held picks). The selecting franchise is the CURRENT owner in the post-trade pick
ledger. Roster, cap, availability, pick completion and the on-the-clock cursor are derived. `draft_state.holds` blocks recording
a pick whose ownership is unresolved until the transaction it waits on is decided: 2.07 is held on `TRADE-F-AMEND`
(CrazyCat ↔ HCMC amendment: 2.07 CrazyCat → HCMC, Derik Queen HCMC → CrazyCat), staged as PROPOSED + `pendingConfirmation`.
Confirm = set its status to `OFFICIAL` (a correction replayed once, not a re-run of TRADE-F). The commissioner has since **released** the 2.07 hold (`released: true`) so CrazyCat's selection (Morez Johnson Jr.) is recorded for the current owner. The amendment stays PROPOSED; if confirmed it moves only the 2.07 pick's recorded owner (to HCMC) and Derik Queen — Morez stays with CrazyCat, as if that part of the trade never happened. Such differences are listed in `state.draftConflicts` (the selector must have held the pick earlier in its trade history; any other mismatch still fails). Drafted players Yahoo does not list yet live in `data/2026-27/provisional_players.json` (key `provisional:*`, cap 0, flagged); once Yahoo adds them, re-key the draft events and delete the entry. `sync-ledger` renders the
Draft Order status strip (on the clock / latest / counts / holds) and per-pick selections; the FA/DRAFT 60 excludes drafted players.
