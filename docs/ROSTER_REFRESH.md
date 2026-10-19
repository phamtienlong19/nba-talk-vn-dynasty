# Roster refresh (commissioner workflow)

Keeps the current-season rosters (layer B, `docs/SEASON_STATE_MODEL.md`) in step
with Yahoo. Local, standard library, Git/PR based — no backend.

## Yahoo acquisition (read-only, recommended)

`scripts/yahoo_rosters.py` fetches the 16 Yahoo team pages of league 85092
(team ids 1–9, 11–17; there is no team 10), validates them and reports the
differences. It writes **only** a staged observation under `local_data/yahoo_observations/`
(gitignored); official rosters change only through the reviewed import below.

```bash
python3 scripts/yahoo_rosters.py fetch                  # all teams → validate → save observation → report
python3 scripts/yahoo_rosters.py fetch --team 8         # one team (PARTIAL: diagnostic only, never importable)
python3 scripts/yahoo_rosters.py import-json capture.json   # a capture made with the DevTools script below
python3 scripts/yahoo_rosters.py validate local_data/yahoo_observations/OBS-….json
python3 scripts/yahoo_rosters.py diff     local_data/yahoo_observations/OBS-….json
# official change = the existing reviewed import, fed the observation file unchanged:
python3 scripts/import_rosters.py diff   local_data/yahoo_observations/OBS-….json --verified-at <capturedAt> --source "<source>"
python3 scripts/import_rosters.py commit local_data/yahoo_observations/OBS-….json --verified-at … --source … --reviewed
```

- **Engines.** `--engine http` (default) is a plain GET with no cookies: the
  league's team pages are publicly viewable (checked 2026-10-19). If Yahoo makes
  them private, use `--engine browser`: run `yahoo_rosters.py login` once (a
  visible Chromium on an isolated profile at
  `~/.config/nba-talk-vn-dynasty/yahoo-browser-profile`, override with
  `NBA_TALK_YAHOO_PROFILE`; needs `pip install playwright && python3 -m playwright install chromium`).
  Either way only GET requests are sent; nothing is clicked or submitted. A
  sign-in page, consent wall, HTTP error or a page for the wrong team fails that
  team clearly; login is never worked around.
- **Validation.** A full observation needs all 16 teams, a non-empty roster per
  team, numeric Yahoo ids, known slots and each player on one team. Roster size
  is **not** checked (in-season counts vary). A failed or partial capture is not
  saved as a baseline.
- **Identity.** Yahoo id → `478.p.<id>` (the game key is checked against the
  frozen salary table) → registry / provisional identity, via the importer.
  Teams resolve by `yahooTeamKey` (`478.l.85092.t.<id>`) in
  `rosters/team_map.json`; Yahoo team names change and are kept only as aliases.
- **Report.** Versus the current season state: ON YAHOO ONLY, OURS ONLY, OTHER
  TEAM (labelled when it matches a not-completed proposal), IL MOVE, LINEUP ONLY,
  and each recorded in-season trade as reflected or not; versus the previous full
  observation: added / removed / changed team / slot changes. These are observed
  differences — nothing is classified as a trade and no transaction is created.
  A payroll preview applies the existing top-9 frozen-salary rule (IL included);
  players missing from the frozen salary table are listed and block the import.
  Yahoo's "Keeper Salary" label is shown only as evidence when it differs from
  the frozen salary; `salary_freeze.json` is never changed.
- **IL.** IL / IL+ is a lineup slot. IL players are owned roster members, stay
  in observations, snapshots and team cards (IL tag), and compete for the nine
  counted salaries like anyone else. A BN↔IL move changes neither ownership nor
  payroll.

**Manual capture (Chrome DevTools).** On any page of the league, logged in,
paste into the console; it GETs the 16 team pages and downloads `capture.json`
for `import-json`:

```js
(async () => {
  const ids = [1,2,3,4,5,6,7,8,9,11,12,13,14,15,16,17], teams = [];
  for (const id of ids) {
    const doc = new DOMParser().parseFromString(await (await fetch(`/nba/85092/${id}`)).text(), "text/html");
    const t = doc.querySelector("table#statTable0");
    if (!t) throw new Error(`team ${id}: no roster table (signed out?)`);
    teams.push({teamId: id, teamName: doc.title.replace(/^.* - Dynasty - /, "").replace(/ \| Fantasy Basketball.*$/, ""),
      players: [...t.querySelectorAll("tbody tr")].map(tr => {
        const a = tr.querySelector('a.name[href*="/nba/players/"]'); if (!a) return null;
        const pl = tr.querySelector(".pos-label"), inj = tr.querySelector(".F-injury");
        return {playerId: a.href.match(/players\/(\d+)/)[1], name: a.textContent.trim(),
                slot: pl && (pl.dataset.pos || pl.textContent.trim()), injury: inj ? inj.textContent.trim() : null};
      }).filter(Boolean)});
    await new Promise(r => setTimeout(r, 1000));
  }
  const blob = new Blob([JSON.stringify({capturedAt: new Date().toISOString(), leagueId: "85092", teams})], {type: "application/json"});
  Object.assign(document.createElement("a"), {href: URL.createObjectURL(blob), download: "capture.json"}).click();
})();
```

`import-json` also accepts `{"<teamId>": [players]}` and a flat list of players
carrying `teamId`.

**Scheduling (not set up).** The fetch is safe to run unattended because it
never changes official data. A future local macOS job would be a LaunchAgent
running `python3 scripts/yahoo_rosters.py fetch` from the repo directory. Do not
run it from GitHub Actions and never put Yahoo credentials in a workflow.

## Manual steps (spreadsheet / CSV)

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
