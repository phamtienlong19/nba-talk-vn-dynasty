# Live league data (matchups, live standings, race impact)

Status: **phase 1 only** (parser + category math, tests). Nothing is fetched on a schedule yet and nothing is shown on the site. The
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
