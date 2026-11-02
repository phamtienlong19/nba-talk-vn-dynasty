# Live league data (matchups, live standings, race impact)

Status: **phases 1-2** (parser, category math, official weekly results, standings math; tests). Nothing is fetched on a schedule yet and nothing is shown on the site. The
full plan (live JSON off `main`, LIVE tab, lineup-integrity evidence) is phased as: parser → official weekly results → live feed and
tab → evidence panel. Display-only; never touches rosters, salaries, the Trade Lab, the draft or the ledger.

## What a Yahoo matchup page gives (public, no sign-in; checked 2026-11-02 on league 85092)

`/nba/<league>/matchup?week=N&mid1=<teamId>` (optional `&date=YYYY-MM-DD`). One page = one matchup, both teams. Pairings are not
listed anywhere else (`/scoreboard` and a team schedule page are 404), so a week is learned by walking team ids (8 requests: fetch
the lowest unseen id, read both teams from the header table, mark both seen).

- **Header table** (`Team FGM/A* FG% FTM/A* FT% 3PTM PTS REB AST ST BLK TO <wins>`): the week's totals for both teams. The last cell is
  Yahoo's printed count of categories won. Winning cells carry the `Bg-selected` class. A week that has not started prints `-/-` and `-`
  (stored as null) with 0 wins.
- **Roster table**: both teams side by side, one row per slot: slot (`PG SG G SF PF F C FC Util BN IL`, or `--`), player, Yahoo player id,
  `NBA - POS,POS`, injury flag (`O`, `Q`, ...), game text (`W, 124-112 vs LAC` or a start time) and the 9 stat cells.
- **`date=`** changes only the roster table (that day's slot and stat line); the totals are the whole week for any date.
- **`--` slot**: in the default view of a finished week, players who contributed stats that week but are no longer on the roster
  (dropped / traded away) show `--`. With an explicit `date=` there are none.
- The week selector lists weeks 1-20.

## Validation (`scripts/yahoo_matchups.py`)

Yahoo's own numbers are the reference: our category math (FG%/FT% from made ÷ attempted, fewer turnovers wins, ties counted) must
reproduce the printed category wins and the highlighted cells; a week with no stats must print 0 wins. Tests (`tests/test_yahoo_matchups.py`)
use trimmed copies of real pages: all eight week-1 matchups reproduce Yahoo's scores, and their summed results equal the published
2026-10-26 standings (week 1 is the whole of that snapshot).

## Not yet verified
Mid-week behaviour during live games, how often Yahoo tolerates requests, week start/end dates, and Yahoo's tie-break order for
equal records (live standings will show ties as ties rather than guess).

## Official weekly results (phase 2)

`data/2026-27/matchups/week-NN.json` holds each **finished** week: the 8 pairings, both teams' totals, Yahoo's printed category wins and
our computed result. `python3 scripts/update_yahoo_matchups.py [--apply]` walks the pairings of every finished week not yet stored (8
requests a week, 1.5 s apart) and stores only weeks before the current one whose categories are all decided and equal Yahoo's printed
scores. A stored week is never overwritten: a different capture is a CONFLICT (Yahoo stat corrections need a human).

Golden check (2026-11-02): summed weeks 1-2 equal Yahoo's published standings for all 16 teams
(`tests/fixtures/yahoo/standings_2026-11-02_after_week2.json`). Official standings are weekly: Yahoo's page updates after a week closes.

## Standings math (`scripts/live_standings.py`)

- Record from weekly results; a tie counts half (7-1-1 = .833). Games back is measured from the **division leader** (Yahoo prints "-" for
  both division leaders).
- Live table = official records + the week in progress (only categories already decided), always labelled PROVISIONAL, with rank movement.
- **Ties:** equal records share a rank and are marked tied. Yahoo's regular-season tiebreaker is not in its settings, and its order inside
  ties (3-way at 10-8, two 9-8-1, two 7-11) matches neither head-to-head nor total points, so none is invented. Re-check at each official
  update.
- **Playoffs** (Yahoo settings, 2026-11-02): 8 teams, weeks 18-20, regular season weeks 1-17, no reseeding, division winners advance but
  seeding is by overall record. `playoff_picture` reserves one spot per division leader, fills the rest by record, and marks teams level
  with the last spot "bubble" and tied division leaders "divisionTie".
- `projected_snapshot` feeds `scripts/lottery_order.py` (ties ordered by the official order as a stand-in, listed in `tiedRanks`).

## Live feed and LIVE tab (phase 3)

- `scripts/build_live_feed.py` builds `live.json` (week in progress: scores, rosters, standings if the week ended now, playoff picture,
  projected reverse order). `.github/workflows/update-live-data.yml` runs it on a UTC schedule (every 15 min in game hours, hourly
  otherwise, plus the Yahoo day/waiver rollover at 08:00 and 07:00 UTC) and force-pushes it as one orphan commit to the `live-data`
  branch. It never touches main or `data/`.
- The page (`scripts/live_page.py embed` -> LIVE block in index.html) fetches
  `raw.githubusercontent.com/<repo>/live-data/live.json` (5-minute cache), shows its age in Bangkok time, flags a feed older than 75 min and
  falls back to the embedded official finished weeks. The Teams tab gets a `LIVE ↓` order option once a feed has loaded.
- Not in this phase: the Draft tab's lottery on the projected order, and the lineup-integrity evidence panel.
