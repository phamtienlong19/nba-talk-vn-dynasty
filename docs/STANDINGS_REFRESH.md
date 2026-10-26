# Standings refresh (commissioner workflow)

Yahoo declined the Fantasy API application, so standings are read from the public page the league already shows, with no API and no
sign-in. Standings are **display only**: they never change rosters, salaries, Trade Lab, draft results or transaction history.
Rosters and standings are separate pipelines (own files, snapshots, timestamps, reports, error states); one routine runs both.

## Weekly routine (one capture, one command)

Anonymous fetch (works today, see "Access" below):

```bash
python3 scripts/update_yahoo_standings.py --engine http            # dry run: report only, nothing authoritative written
python3 scripts/update_yahoo_standings.py --engine http --apply    # commit the snapshot and regenerate the page
```

Or from a browser, if Yahoo ever blocks the plain fetch: open
`https://basketball.fantasysports.yahoo.com/nba/85092?lhst=stand`, save the page as HTML, then

```bash
python3 scripts/update_yahoo_standings.py --input ~/Downloads/<saved>.html [--apply]
```

`--input` also takes a normalized capture JSON (`schema_version` 1, the format of `tests/fixtures/yahoo/NBA_Talk_Dynasty_Standings_2026-10-26.json`).
Then open the PR (`git checkout -b data/standings-<date>`, commit `data/2026-27/standings/` and `index.html`). To refresh rosters the
same day: `python3 scripts/update_yahoo_rosters.py` (see `docs/ROSTER_REFRESH.md`). Check both with `./validate.sh` and
`python3 -m unittest discover -s tests`.

The page is read as data: nothing in it is executed. Columns are found by header name (Rank, Team, W-L-T, Pct, Div, GB, Last Week,
Waiver, Moves), teams by Yahoo team id from their links (ids are 1-9, 11-17; not contiguous), divisions from the East/West headings.

## Outcomes

| Outcome | Meaning | Writes |
|---|---|---|
| READY | valid, newer than the published snapshot | with `--apply`: new snapshot + index; previous kept |
| NO_CHANGE | same Yahoo update already published (any day, any source: HTML, JSON, fetch) | nothing |
| STALE | older Yahoo update than the published one | nothing (restore: `--allow-historical-restore --reason "..."`) |
| CONFLICT | same Yahoo update time but different standings | nothing; needs a commissioner's review |
| FAILED | a validation error, login/consent page, changed columns, bad timestamp | nothing; published standings untouched |

Exit code 0 for READY and NO_CHANGE, 1 otherwise. A failed update leaves the last verified standings on the page, labelled with the
Yahoo update date they were verified at.

**Validation (any failure rejects the whole snapshot):** 16 unique teams all mapped to franchises; ranks 1-16 once each; non-negative W-L-T;
Pct consistent with the record (Yahoo rounding); divisions East/West with 8 each; league wins = losses; a readable update time. Warnings
only: Pct order vs rank, GB vs formula, a team changing division.

**Time.** Yahoo prints no year (`Mon Oct 26 03:00pm +07`, or `04:00am EDT` when fetched without a session: the same moment). The year comes
from the configured fantasy season in `config/yahoo_league.json` and the weekday must match the date. `sourceUpdatedAt` (Yahoo's update,
UTC) and `capturedAt` (when we looked) are separate. **Identity** of an update is its source time + standings content; capture time,
names, **waiver priority and moves** are excluded because the last two change all week with every add/drop (observed live on 2026-10-26).

**Data.** `data/2026-27/standings/index.json` (current pointer + history) and `snapshots/ST-<UTC>-<digest>.json`. Nulls are preserved
(GB for the leaders, moves `-`), never turned into zeros. Yahoo's own rank / tie order is kept.

## Access (investigated 2026-10-26)

A plain GET of the standings URL, no cookies, returned the full table and update time (HTTP 200, ~1 MB), and the importer produced
NO_CHANGE against the published snapshot. `robots.txt` disallows only upper-case `/NBA/` style paths, not `/nba/85092`. This works only
while the league stays publicly viewable; if it goes private the fetch fails visibly (login page rejected) and the saved-HTML path remains.
`.github/workflows/update-yahoo-standings.yml` runs this fetch **manually** (no schedule): it opens a PR, never merges, and uses no session
or secret. A schedule is deliberately not enabled until the fetch has proved stable over several weeks. Session-cookie automation is not used.

## Reverse order and lottery groundwork

The team cards and projected order show **provisional reverse-standings order** (worst Yahoo rank first). `scripts/lottery_order.py` returns data
only: tickets per rank from `config/draft_lottery_rules.json`, eligibility from `scripts/lottery_eligibility.py`, everything labelled
provisional. It draws nothing and assigns no pick. Not the final order.

## Open league-rule questions (not decided here)

1. How the rank 3/4 reward applies in rounds 2 and 3, and the exact slot it takes in round 1.
2. Whether under-cap / tanking penalties change draft position, and by how much.
3. Any head-to-head tie-break beyond Yahoo's printed rank (ties such as ranks 15/16 at 1-7-1 currently follow Yahoo).
4. The lottery format for the 2027 draft beyond the configured ticket table.
