# Live league data (lineups, lineup checks, official weekly results)

The site shows current lineups, roster changes and lineup checks, refreshed every few minutes. Display-only; it never touches rosters, salaries, the
Trade Lab, the draft or the ledger. The LIVE tab's scores, standings, projected order, roto, all-play and schedule views were removed on 2026-11-25
(owner: the tab is for lineups and rule checks).

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
equal records.

## Official weekly results (phase 2)

`data/2026-27/matchups/week-NN.json` holds each **finished** week: the 8 pairings, both teams' totals, Yahoo's printed category wins and
our computed result. `python3 scripts/update_yahoo_matchups.py [--apply]` walks the pairings of every finished week not yet stored (8
requests a week, 1.5 s apart) and stores only weeks before the current one whose categories are all decided and equal Yahoo's printed
scores. A stored week is never overwritten: a different capture is a CONFLICT (Yahoo stat corrections need a human).

Golden check (2026-11-02): summed weeks 1-2 equal Yahoo's published standings for all 16 teams
(`tests/fixtures/yahoo/standings_2026-11-02_after_week2.json`). Official standings are weekly: Yahoo's page updates after a week closes.

## Live feed and LIVE tab

- `scripts/build_live_feed.py` builds `live.json`: week in progress, every team's roster rows (slot, status, today's game, games left, day and week
  lines), starters' games left, the week's roster changes (`moves`) and the closed days' checks (`lineupChecks`); the loop adds `lineupReview`.
  No scores, standings or projections. `.github/workflows/update-live-data.yml` runs `scripts/live_feed_loop.sh` (a build and publish every 4 min in
  game hours, every 15 min otherwise, ~115 min per run; each run queues the next) and force-pushes one orphan commit to the `live-data` branch. It
  never touches main or `data/`.
- The page (`scripts/live_page.py embed`; `scripts/live_app.js`) fetches that file every 2 min while visible, shows its age in Bangkok time and flags one
  older than 30 min. Without a feed it shows no lineups and points to the TEAMS tab.
- One card per team (mine first, then teams with something to check). Row flags are facts about the current slots, not rulings: **OUT IN LINEUP** (a
  starting slot, listed out, game today), **EMPTY**, **IL !** (on IL, not IL-eligible). The judgement of what a manager could have avoided is the
  lineup review below.

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
scores), `d`/`dm`/`dfg`/`dft`/`ds` (that day's line, minutes, made/attempted, slot). The player card shows them. The first build after a deploy fetches every closed day of the week (up to ~100 requests, once).

## Roto math
`scripts/roto.py` (roto points and all-play) is no longer shown on the site; it stays as the reference that `tools/yahoo-roto` is tested against,
with the owner's week-2 package (`tests/fixtures/roto_week2_package.json`).

## Season schedule (`data/2026-27/schedule.json`)

`python3 scripts/update_yahoo_matchups.py --schedule [--apply]` keeps the head-to-head pairings of the 17 regular-season weeks as plain
pairs of Yahoo team ids (no stats, no ownership). Finished weeks come from the stored results, other weeks from one matchup-page walk
each (8 requests, 1.5 s apart); a week already kept is never walked again. The playoff weeks (18-20) are seeded from the final
standings and Yahoo lists no opponent for them yet, so they are not stored. Display data only.

## Player averages (`stats-data` branch, `player_stats.json`)

`.github/workflows/update-player-stats.yml` runs `scripts/update_yahoo_player_stats.py` once a day (09:40 UTC, after Yahoo's day rolls
over): about 55 read-only anonymous GETs, 1.5 s apart, of the public player list (`players?status=T&stat1=<window>&count=<offset>`,
25 players a page) for six windows: this season (`S_AS_2026`), last 7 / 14 / 30 days (`S_AL7/14/30`) and the two previous seasons
(`S_AS_2025`, `S_AS_2024`). Taken players only. The result is ONE file force-pushed as an orphan commit to the `stats-data` branch; it never
touches main or `data/`. A failure (or fewer than 150 players in the season window) keeps the previous file. The player card fetches it once
and shows a plain "Averages per game" table (no colours, ranks or verdicts); a missing file or a player with no games just hides the section.
Windows with no games print dashes, stored as null. The 14- and 30-day windows are identical until the season is 30 days old.

## Day-by-day game log (`stats-data` branch, `player_log.json`)

The same workflow (`update-player-stats.yml`, daily 09:40 UTC) also runs `scripts/update_player_log.py`: for every closed day of the season
it reads each team's page for that day (`yahoo_teamday`, `?date=`; one request per team per day, 1.5 s apart) and keeps one compact line per
player who played: date, slot, opponent, minutes, FGM/A, FTM/A, 3PM, PTS, REB, AST, STL, BLK, TO and the Yahoo team id. The first run walks
the whole season (about 10 minutes, at most 45 days a run); after that only new days are fetched. A day that fails is skipped and retried
next run, never invented; the previous file stays unless something new was captured. Only rostered players appear (team pages), so a free
agent has no log. Minutes are kept as Yahoo shows them (some pages give 36:07, others 36). The file goes to the `stats-data` branch with
`player_stats.json` as one orphan commit; it never touches main or `data/`.

The player card shows the last 10 games as plain lines (`13-7-1-1-1` = PTS-REB-AST-STL-BLK, `5/7 FG`, `2 3PM`, `1/2 FT`, `3 TO`), newest
first, with "Show all"; the feed's current day is added on top until the file has it. No totals anywhere. Display data only.

## Roster changes and departed players (live feed `moves`)

Each closed day's rosters are compared with the day before (`live_days.moves_between`): who was added and who was dropped, by team and
date, plus today against the last closed day. The latest closed day's rosters are kept in `playerWeek.last` as the baseline; a feed
built before this existed is backfilled once from the day cache. A player whose slot reads `--` on the week-totals page (dropped or
traded away, still counted in the totals) is not shown in the lineup and is not a roster member for today's comparison. Facts only: nothing here says whether a move was good, legal or disputed.

## Keeping the feed continuous (2026-11-13)

GitHub's cron is best-effort and was dropping most of this workflow's triggers: runs started 6-8 hours apart and the feed was fresh about
30% of the time. Each run now queues its own successor with `workflow_dispatch` as its first step (it waits in the `update-live-data`
concurrency group until the current run ends), so the loop no longer depends on the cron; the cron stays as a backstop. The roster workflow
has its own concurrency group and does not block or delay the feed.

## Roster feed (`roster-data/rosters.json`)

Yahoo's CURRENT rosters (slot, injury status, NBA team per player) for the 16 teams, rebuilt about every 5 minutes by
`update-roster-feed.yml` (`scripts/build_roster_feed.py`, `scripts/roster_feed_loop.sh`) and force-pushed as one orphan commit to the `roster-data`
branch, like the live feed. Anonymous read-only GETs, the same parser as the audited import. Schema `roster-feed/1`: `asOf`, `digest`, `complete`,
`teams{franchiseId: {teamId, name, asOf, players[{k, n, s, st?, t?}]}}`. A team whose page failed keeps its previous entry with its own older `asOf`;
the page reports the oldest team's time as the feed's age.

The page (`NBA_ROSTERS` in `index.html`) overlays slots and statuses on players already on a team and lists adds / drops / trades that Yahoo shows
and the verified rosters do not yet have ("N moves on Yahoo not yet in the verified rosters"). A provisional identity counts as the same player as his
Yahoo id. It never changes ownership, cap, keepers or the trade checker: a roster change becomes official only through the audited PR
(`update-yahoo-rosters.yml`). The roster label shows "ROSTERS hh:mm · N MIN AGO", warns when the feed is old, and falls back to the verified
snapshot's date when it is more than 3 hours old or cannot be fetched. A page opened from disk never fetches it.

## IL states and the lineup log (evidence, never a verdict)

**IL states** (`season_state.il_state`, mirrored by `ilKind` on the page): a player in an IL slot is `injured` (Yahoo lists him Out / INJ / OFS, or no status and the
registry still shows the IL token), `healthy_on_il` (an ineligible status P / Q / GTD / DTD (Doubtful is IL-eligible per the league settings), or no status and the registry says he is not IL-eligible) or
`unverified` (no registry entry, or an unknown status code). The page shows three different chips ("IL", an amber "IL !", a grey "IL ?") and a per-team
"N injured · N not IL-eligible" count. The page never calls such a player healthy (a Questionable player may well be hurt): `healthy_on_il` is only the internal name, kept because lineup-log records use it. Team rows carry `ie` (1 / 0, the registry's IL token; absent when unknown). The registry refreshes every 4 hours.

**Lineup log** (`scripts/lineup_log.py`, called by `scripts/live_feed_loop.sh` after every build): a Yahoo lineup locks per player at tip-off, so a status that
changes afterwards used to erase the proof of what counted. For every player whose game turns live or final the loop appends one lock record (slot, status,
registry IL token, IL state, flags `healthy_on_il` / `out_starter` / `star_benched`) to `<Pacific game date>.jsonl` on the **append-only `lineup-log`
branch** (ordinary commits, never force-pushed; the live feed branch is force-pushed and keeps no history), plus one `first_tip` snapshot of every team's
lineup per day. A player is recorded once per day and an existing line is never rewritten. Precision is the polling interval (4 minutes in game hours).
Tank intent, AFK verdicts and points stay with the commissioner (`data/2026-27/violations.json`).

## Commissioner review (the REVIEW tab, `#commissioner`)

One compiled list per team plus league items, built in the page (`cmData` / `cmRender` in `index.html`); it writes nothing and rules on nothing. Every item says
when its fact was read.

| Item | Source | Time shown |
|---|---|---|
| Recorded violations | `data/2026-27/violations.json` | recorded by the commissioner |
| Flags at lineup lock | `lineup-log` branch, one file per US game day, last 7 days (more on demand) | capture time, and whether the game was on or over |
| Week lineup checks (rule count) | live feed `lineupChecks` (closed days) | feed time |
| IL not eligible / unverified, IL and roster size | rosters in the page: the roster feed when loaded, else the verified snapshot | that read's time |
| Payroll over / under, roster rules | verified snapshot (build time) | snapshot time |
| Under-floor checkpoint findings | `data/` checkpoints | checkpoint date |
| Trades waiting, cooldowns, Yahoo changes not yet verified, unlinked player ids, unset violation points | page data and roster feed | |

## Lineup review (`scripts/lineup_review.py`)

The live loop runs it after the lineup log and puts the result in `live.json` as `lineupReview`; the REVIEW tab, the LIVE lineup checks and My team show it.
Owner rulings 2026-11-25; the numbers live in `config/roster_rules.json` (`lineupReview`). Status = as shown 1 hour before tip; slot = as it stood at lock.
**fault** counts toward the weekly rule (2 days, 3 players or 2 stars), **il** is an injured-list rule item, **watch** is shown only, **cleared** is only counted.

| # | Situation | Outcome |
|---|---|---|
| 1 | Starter healthy, uncertain, or without a game | nothing |
| 2 | Starter listed Out later than the hour | cleared |
| 3 | Out starter with a game; a healthy bench player with a game could cover | fault |
| 4 / 5 | Out starter, no cover, IL slot free: out more than 2 days / 2 days or less | il / watch |
| 6 | Out starter, no cover, IL full (or NA / SUSP) | cleared |
| 7 / 8 | Empty starting slot with / without cover | fault / cleared |
| 9 | Healthy top-50 benched who could start without benching another top-50 | fault |
| 10 / 11 | Top-50 benched with no such slot / uncertain or first game back | cleared |
| 12 / 13 | Other Out player off IL with a slot free: more than 2 days / within 2 days | il / watch |
| 14 | On IL as Out, INJ, OFS or Doubtful | nothing |
| 15 | On IL as Q / GTD / DTD, not played | watch |
| 16 / 17 | On IL, cleared: first game since / after that | watch / fault |
| 18 | On IL as NA / SUSP, or eligibility unknown | watch |
| 19 | No read of the lineup an hour before tip (gap, old data) | watch, "unconfirmed" |

One bench player covers one gap, and healthy starters may be rearranged to make room. A player picked up inside the hour is not judged. An open IL slot is used by
one Out player (the longest out). Not automated: playoff teams are not charged, the late-season tank allowance, both sides forgetting or compensating benching,
and long versus short injuries. The tip is taken from the first read showing the game on, so it is up to a few minutes late; Out streaks start no earlier than
the first logged day.

**Lineup-log history records:** `day_start` (every rostered player at the day's first read), `state` (each later change of team, slot, status or having a game;
`slot: null` = left the roster) and `gap` (more than 30 minutes unread). With the lock records they answer what stood one hour before a tip-off.
