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
  projected reverse order). `.github/workflows/update-live-data.yml` runs `scripts/live_feed_loop.sh` (a build and publish every 4 min in game hours, every 15 min otherwise, for ~115 min per run; an hourly-ish cron starts the next run, which queues behind the current one). GitHub's cron alone is too unreliable for a 5-minute cadence: scheduled runs start tens of minutes late or not at all. The page polls every 2 min while visible, bypassing the 5-min raw-file cache with a per-minute query, and flags a feed older than 30 min, hourly
  otherwise, plus the Yahoo day/waiver rollover at 08:00 and 07:00 UTC) and force-pushes it as one orphan commit to the `live-data`
  branch. It never touches main or `data/`.
- The page (`scripts/live_page.py embed` -> LIVE block in index.html) fetches
  `raw.githubusercontent.com/<repo>/live-data/live.json` (5-minute cache), shows its age in Bangkok time, flags a feed older than 75 min and
  falls back to the embedded official finished weeks. The Teams tab gets a `LIVE ↓` order option once a feed has loaded.
- Not in this phase: the Draft tab's lottery on the projected order, and the lineup-integrity evidence panel.

## Fetching notes (2026-11-03)
- Yahoo's no-week matchup page (`/matchup`) and the in-progress week's default view (`Live`) do not contain the category table
  for an anonymous client. The feed therefore reads `matchup?date=totals&week=N&mid1=T`, which has the same table for finished
  and in-progress weeks, and derives the current week from `seasonStartMonday` (Pacific) in `config/yahoo_league.json`.
- A failed parse names the URL, final URL, size and page title in the error.

## Lineup-integrity evidence (built: `scripts/live_lineups.py`, the LINEUP CHECKS card, visible to everyone)
Counts what `docs/LEAGUE_RULES_MODEL.md` ("AFK / lineup-integrity") already counts as a misset, from the day-closed `date=` lineup of each
finished Yahoo day. Neutral wording, evidence for review, never a verdict. A "misset" day for a team is any of:
1. **A healthy bench or IL-eligible player with a game, and a star (top-50 O-Rank) left on the bench** (benching a star).
2. **A starting slot held by a player who is Out (O/INJ/SUSP/NA) while a healthy bench player with a game that day is eligible for that
   slot** (position eligibility from the player's positions; Util takes anyone). The slot is wasted although a replacement was on the bench.
3. **An empty starting slot while an eligible, healthy bench player had a game.**
4. A long-term-injured (IL-status) player started on purpose.
Per week the panel shows the days and players affected against the rule's thresholds (2+ days or 3+ players; 2 players if stars) and, in the
last three weeks, the bench-games share against the late-season allowance. Caveat shown with the evidence: a status is what Yahoo showed at
capture time, so a late scratch after the lineup locked looks like an Out starter; the commissioner decides.

## Games left (built)
`scripts/live_schedule.py` reads the NBA teams playing on each remaining day of the week from Yahoo's own future-day roster pages (a game time
and opponent appear for every player whose team plays), from as few pairings as it takes to see all 30 teams. A day is fetched once and kept in
`schedule-cache.json` on the runner (reused for 12 h by the looping run; a fresh run fetches again, about 25 requests once). A player's `gl` is
today's game if it has not finished plus every later day his NBA team plays; a side's `gamesLeft` sums its starting lineup, leaving out
players whose status is out. A day Yahoo cannot serve is left out and the feed sets `gamesLeftComplete: false` (the page shows "~").

Built as designed with these details: a closed day is captured once (8 requests) from the `date=` pages and carried in the feed's
`lineupChecks.byDate`; the looping run reads the last published feed (`--previous live.json`) so a new run does not capture those days
again. An out starter counts only when his status is out, his team had a game and he recorded nothing. A star is top 50 by Yahoo's
preseason O-Rank (`data/yahoo/player_registry.json`), the stand-in for the rule's XRank. The card lists only teams with something found,
flags the ones at the rule's count (2+ days, 3+ players or 2 stars in the week) and says nothing more: the commissioner decides.

## Day view, minutes and made/attempted (built)
The matchup page has only percentages per player, so day-level data comes from Yahoo's team page for one day
(`/nba/<league>/<team>?date=YYYY-MM-DD&stat1=S&stat2=D`, `scripts/yahoo_teamday.py`): slot that day, minutes, FGM/A, FTM/A and the counting
stats, 16 requests per day. `scripts/live_days.py` captures each closed day once (lineup evidence and the starters' week made/attempted, carried
in the feed as `lineupChecks.byDate` and `playerWeek` and reused through `--previous`; a runner-local `--day-cache` serves the day shown) and
the latest day with a started game fresh on every build. Feed fields: per player `wfg`/`wft` (week made/attempted, starting days only, as Yahoo
scores), `d`/`dm`/`dfg`/`dft`/`ds` (that day's line, minutes, made/attempted, slot); per matchup `day` (the starters' category inputs and
winners for that day, our arithmetic, not Yahoo's score). The page's Week totals / Day switch changes the category rows, the score and the rosters
together and labels the card WEEK TOTALS or DAY. The first build after a deploy fetches every closed day of the week (up to ~100 requests, once).

## Roto, raw stats and all-play (built, week in progress)
The LIVE tab has a view strip `Matchups | Roto | Raw stats | All-play`, shown once the week has numbers. They are descriptive only (the league is
head-to-head; the standings are W-L-T) and are computed on the page from the feed's `matchups[].teams[].stats` of all 16 teams, so they refresh with the
feed and add no Yahoo requests. Roto: each category ranks the 16 teams, 16 points for the best, 1 for the worst (fewer turnovers is better), level
teams share the average (two at the bottom score 1.5); total = roto score, rank = competition rank. All-play: each team against every other,
category by category. `scripts/roto.py` is the reference, `scripts/live_roto.js` the page's port, and `tests/test_roto.py` holds both to the
owner's week-2 report package (`tests/fixtures/roto_week2_package.json`: stats and expected points, totals, ranks and every all-play cell).
Yahoo corrects stats after a week closes (the stored week 2 differs from the package by five single-unit numbers), so roto points are as of the feed.

## Quality-of-life pass on the LIVE tab (2026-11-03)
Found by an adversarial review and fixed together: the tall sticky left column now scrolls inside itself (its lower cards were unreachable); a
refresh keeps each table's sideways scroll and the focused cell; the all-play detail sits above the matrix and scrolls into view; one tab stop in
the matrix with arrow keys; sortable roto / raw-stats columns that also reorder the matrix; closest matchups first after mine; "Day N of 7" and a
fewer-turnovers note on the roto views; a phone list (team picker, 48px rows) instead of the 16 x 16 matrix; Standings as a pane on narrow screens
(they used to sit above the matchups); roto, raw stats and all-play records in the export hub; text no smaller than 10.5px except the ribbon, and the
faint grey darkened to 4.6:1 on white (test-enforced). The last pane chosen is remembered in `localStorage` (per device; no shareable URL, because
the site's own router owns the hash and query). Not done: a roto-rank trend since yesterday (needs a daily history in the feed).

## Season schedule (`data/2026-27/schedule.json`)

`python3 scripts/update_yahoo_matchups.py --schedule [--apply]` keeps the head-to-head pairings of the 17 regular-season weeks as plain
pairs of Yahoo team ids (no stats, no ownership). Finished weeks come from the stored results, other weeks from one matchup-page walk
each (8 requests, 1.5 s apart); a week already kept is never walked again. The playoff weeks (18-20) are seeded from the final
standings and Yahoo lists no opponent for them yet, so they are not stored and the LIVE Schedule pane shows "seeded". Display data only.

## Player averages (`stats-data` branch, `player_stats.json`)

`.github/workflows/update-player-stats.yml` runs `scripts/update_yahoo_player_stats.py` once a day (09:40 UTC, after Yahoo's day rolls
over): about 55 read-only anonymous GETs, 1.5 s apart, of the public player list (`players?status=T&stat1=<window>&count=<offset>`,
25 players a page) for six windows: this season (`S_AS_2026`), last 7 / 14 / 30 days (`S_AL7/14/30`) and the two previous seasons
(`S_AS_2025`, `S_AS_2024`). Taken players only. The result is ONE file force-pushed as an orphan commit to the `stats-data` branch; it never
touches main or `data/`. A failure (or fewer than 150 players in the season window) keeps the previous file. The player card fetches it once
and shows a plain "Averages per game" table (no colours, ranks or verdicts); a missing file or a player with no games just hides the section.
Windows with no games print dashes, stored as null. The 14- and 30-day windows are identical until the season is 30 days old.

## Roster changes and departed players (live feed `moves`)

Each closed day's rosters are compared with the day before (`live_days.moves_between`): who was added and who was dropped, by team and
date, plus today against the last closed day. The latest closed day's rosters are kept in `playerWeek.last` as the baseline; a feed
built before this existed is backfilled once from the day cache. A player whose slot reads `--` on the week-totals page (dropped or
traded away, still counted in the totals) is listed apart on the matchup card as "Left this roster" and is not a roster member for
today's comparison. Facts only: nothing here says whether a move was good, legal or disputed.

## Keeping the feed continuous (2026-11-13)

GitHub's cron is best-effort and was dropping most of this workflow's triggers: runs started 6-8 hours apart and the feed was fresh about
30% of the time. Each run now queues its own successor with `workflow_dispatch` as its first step (it waits in the `update-live-data`
concurrency group until the current run ends), so the loop no longer depends on the cron; the cron stays as a backstop. The roster workflow
has its own concurrency group and does not block or delay the feed.
