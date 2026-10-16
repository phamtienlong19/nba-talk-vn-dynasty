# Roster refresh (commissioner workflow)

Keeps the current-season rosters (layer B, `docs/SEASON_STATE_MODEL.md`) in step
with Yahoo. Local, standard library, Git/PR based — no backend.

## Steps

```bash
# 1. start from the current rosters (or paste Yahoo's rosters into the same columns)
python3 scripts/import_rosters.py export /tmp/rosters.csv
# 2. edit /tmp/rosters.csv to match Yahoo today, then review the diff (writes nothing)
python3 scripts/import_rosters.py diff /tmp/rosters.csv \
    --verified-at 2026-11-02T15:00:00Z --source "Yahoo league rosters, checked by <name>"
# 3. commit only after reviewing
python3 scripts/import_rosters.py commit /tmp/rosters.csv --verified-at ... --source ... --reviewed
# 4. publish
python3 scripts/build_league_state.py embed && python3 scripts/what_if.py embed && ./validate.sh
# then open a PR as usual

python3 scripts/import_rosters.py status     # current snapshot + history
python3 scripts/import_rosters.py rollback   # point back to the previous snapshot (files are kept)
```

## Input

CSV header `team,player_key,player_id,player_name,slot` (one row per rostered
player, all 16 teams):

```csv
team,player_key,player_id,player_name,slot
Bsy,478.p.10094,10094,Victor Wembanyama,C
Bsy,,10290,Stephon Castle,BN
Thịnh,478.p.5352,,Nikola Jokić,IL
DonTrick,provisional:dailyn-swain,,Dailyn Swain,BN
```

- `team`: the Yahoo team key once `rosters/team_map.json` has them, else any alias
  there (short name, team name, display name).
- Player identity: `player_key`, else `player_id` (game 478 is assumed), else an
  entry in `rosters/player_aliases.json`, else a unique exact name (reported as a
  warning). Unknown players **block** the commit.
- `slot`: PG SG G SF PF F C FC Util BN IL IL+ (blank = unknown).
- JSON form: `{"teams":[{"team": "...", "players":[{"playerKey"|"playerId", "name", "slot"}]}]}`.
- `docs/examples/roster_snapshot_example.csv` is a complete export of the current
  rosters (192 rows) to use as a template.

## What the diff shows

| Section | Meaning |
|---|---|
| ADDED / DROPPED / CHANGED TEAM | ownership changes (affect payroll) |
| IL MOVE | into / out of IL or IL+ (payroll unchanged: the top 9 salaries count, IL or not) |
| LINEUP ONLY | slot change between active / bench positions |
| TRANSACTION | a COMPLETED in-season trade dated before this snapshot: must be reflected |

## Safety rules

Blocking: unmatched team or player, a player on two teams, a team with no rows,
an unknown slot, a snapshot not newer than the current one, identical content to
an earlier import, a completed trade the snapshot does not reflect, or a commit
without `--reviewed`. Over 15 players on a team is a warning. Every committed
snapshot stays in `data/2026-27/rosters/snapshots/`; `index.json` records each
commit and rollback.

## Players Yahoo does not list yet

Six drafted rookies are provisional (`data/2026-27/provisional_players.json`):
Dailyn Swain, Bennett Stirtz, Hannes Steinbach, Sergio de Larrea, Cameron Carr,
Nate Ament. When Yahoo lists one, an import row with the Yahoo key and the same
name is reported as `PROVISIONAL_LINK_CANDIDATE`; after checking, run

```bash
python3 scripts/import_rosters.py link-provisional provisional:dailyn-swain 478.p.<id>
```

This records the Yahoo key on the provisional entry. The internal identity, the
draft event, the rookie flag and the frozen $0 draft salary do not change, so no
second player appears and the 19-rookie count holds. Linking refuses a Yahoo key
that already has its own frozen identity or is linked elsewhere.

A free agent added in-season who is not in the frozen 2026-27 player table (the
600-player registry + provisional) blocks the import until the commissioner adds
an explicit entry with a salary; nothing is guessed.
