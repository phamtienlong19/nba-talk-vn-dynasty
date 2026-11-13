# yahoo-roto

Roto standings for any **publicly viewable** Yahoo fantasy league, from its league id. One file, Python 3 standard library only, read-only, no sign-in.
It does not depend on the rest of this repository; copy `yahoo_roto.py` anywhere.

```bash
python3 yahoo_roto.py 85092                     # season roto, every week that has stats
python3 yahoo_roto.py 85092 --week 3            # one week
python3 yahoo_roto.py 85092 --through 3 --json  # weeks 1-3, as JSON
python3 yahoo_roto.py 85092 --cache .cache      # reruns re-use fetched pages (finished weeks never change)
```

What it reads (anonymous GETs, one per 1.5 s): the league's public settings (scoring type, scoring categories), the standings page (teams) and each
week's matchup page in its "totals" view (category totals; one page covers two teams). Season roto adds the weekly totals; each category ranks the
teams worst = 1 point ... best = number of teams, ties share the average place, fewer is better for TO / PF. Percentages come from the summed makes and
attempts. Roto is derived here, not a Yahoo number.

## Limits (stated, not hidden)
- The league must be viewable without a login. A private or unknown league id is reported as such; the tool never signs in and cannot read it.
- Head-to-head leagues only (weekly matchup pages). A roto-scoring league has no weekly pages; it is refused, not guessed.
- Counting categories (PTS, REB, 3PTM, TO ...) and made/attempted percentages (FG%, FT%) are computed; ratio categories (ERA, WHIP ...) are listed and skipped.
- Verified against one league (NBA, 9 categories): its week-1 roto equals this repo's own tested roto for all 16 teams. Other leagues and `--sport` values
  other than nba are untested.
- The current week may be in progress; use `--through N` to stop at a finished week.

Tests (no network): `python3 -m unittest discover -s tests` from this folder, also run by the repo's suite.
