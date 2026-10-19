# Yahoo Fantasy API — roster integration feasibility (2026-10-16)

> **Update 2026-10-19.** League id **85092** (team ids 1–9, 11–17) is now
> known and `rosters/team_map.json` carries every `yahooTeamKey`. The league's
> team pages are publicly viewable, so rosters are acquired read-only from those
> pages by `scripts/yahoo_rosters.py` (plain GET, or an isolated Playwright
> profile if the league becomes private) — see `docs/ROSTER_REFRESH.md`. The API
> route below remains an option; the observation → reviewed import pipeline does
> not change if it is adopted later. The two "not known" bullets and the closing
> paragraph below describe the 2026-10-16 position.

Short answer: **no authenticated access exists today, and Yahoo now gates the
Fantasy API behind a manual application review.** The maintenance release
therefore ships the manual importer (`docs/ROSTER_REFRESH.md`); an API adapter
can write the same snapshot format later without front-end changes.

## What the repository actually has

- The only Yahoo source in the repo is the **public** draft-analysis endpoint
  (`config/yahoo_source.json`: league `478.l.public`, which resolves to
  `478.l.101` "101 League"). That league is **not** NBA Talk VN; it provides
  player identity, positions, O-Rank and cap dollars only (`docs/YAHOO_DATA_SOURCE.md`).
- The NBA 2026–27 **game key is `478`** (every registry `playerKey` is `478.p.<id>`).
- The NBA Talk VN **league key and the 16 team keys are not in the repo or in the
  local sources** (rules DOCX, cap XLSX, forensic snapshot were searched). They
  were not invented. `data/2026-27/rosters/team_map.json` has `leagueKey: null`
  and `yahooTeamKey: null` for all 16 franchises, plus name aliases so the manual
  importer works without them.
- To fill them: open the league in Yahoo — the URL is
  `basketball.fantasysports.yahoo.com/nba/<league_id>/<team_id>` — giving
  `leagueKey = 478.l.<league_id>` and `yahooTeamKey = 478.l.<league_id>.t.<team_id>`.

## Answers

**1. What API access is available now?** None authenticated. The public
read-only draft-analysis endpoint (no OAuth) keeps working for player metadata,
but it cannot see a private league's rosters.

**2. What needs Yahoo approval?** All Fantasy API access. Yahoo's developer
portal now takes applications that are reviewed by the Fantasy team; access is
**read-only by default**; an application must name the product, the data needed,
the user base (it explicitly asks whether use is personal / single-league) and an
expected user count. Incomplete applications are closed without reply. Yahoo
gives no timeline. Developer reports (yfpy issue #84) describe: existing apps
returning HTTP 403 "not authorized" from July 2026; the create-app form no longer
offering a Fantasy permission; approval by email plus a DocuSign agreement;
**a brand-new app** whose Client ID is then submitted; waits of a few weeks to
~80 days; refresh tokens bound to the client. These reports are third-party and
unverified, but consistent. Products must display "Fantasy data provided by Yahoo
Fantasy" with a link.

**3. Can a league member or commissioner authorize read-only access?** Yes, once
the app is approved: OAuth 2.0 authorization-code flow, read scope. Yahoo's
documentation states a user can only retrieve private-league data for leagues
they belong to, so the authorizing account must be a member — the commissioner's
account is the natural choice. One approved app + one member's consent is enough
to read all 16 rosters.

**4. Fetch all 16 rosters by date.** Base `https://fantasysports.yahooapis.com/fantasy/v2`:
- `GET /league/478.l.<id>/teams` → the 16 team keys (one-time, fills `team_map.json`).
- `GET /team/478.l.<id>.t.<n>/roster;date=YYYY-MM-DD` for n = 1..16 (Yahoo: "For
  MLB, NHL, or NBA, you can specify a date"; default is today). Multiple teams can
  be batched through the collection form `/teams;team_keys=…/roster;date=…`.
- `GET /league/478.l.<id>/transactions;types=add,drop,trade` to cross-check
  ownership changes since the last snapshot.

**5. Membership vs daily lineup.** Each roster entry carries `player_key` (the
membership fact) and `selected_position.position` (PG, SG, …, Util, BN, IL, IL+ —
the day's lineup slot). The importer stores both but diffs them separately:
ownership changes (added / dropped / changed team) vs IL moves vs lineup-only slot
changes. A roster pulled on a fixed day (e.g. the weekly lock date) avoids daily
lineup noise.

**6. Where can a refresh token live securely?** Not in the repo and not in the
static site. Options, in order: a GitHub Actions **encrypted secret** on this repo
(client id/secret + refresh token; workflow runs on demand or on a schedule), or
the commissioner's machine (token in the OS keychain, script run locally). Note:
if Yahoo rotates refresh tokens on use, the workflow must write the new token back
— in Actions that needs a token with `secrets:write`, so the local option is
simpler at first.

**7. Publishing a reviewed snapshot to GitHub Pages.** The fetch job writes the
canonical snapshot (same JSON as `import_rosters.py` produces) and runs
`import_rosters.py diff`, then opens a **pull request** with the snapshot plus the
diff as the PR body. The commissioner reviews; merging runs the existing
`build_league_state.py embed` and Pages deploy. Nothing is published without a
human merge, and a blocking diff (unmatched player, team missing, a completed
trade not reflected) fails the job instead of opening a PR.

**8. Best fallback now.** The manual importer: copy the 16 rosters from Yahoo
(or edit the exported template), run `import_rosters.py diff`, review, then
`commit --reviewed`, `build_league_state.py embed`, open a PR. Refresh weekly and
right before trade talks or a cap checkpoint.

## Next steps (human)

1. Commissioner records the league id → fill `leagueKey` / `yahooTeamKey` in
   `data/2026-27/rosters/team_map.json`.
2. Apply at Yahoo (single-league, read-only, under 1,000 users) with a new app;
   wait for approval.
3. Then: a read-only proof of concept that writes a snapshot file and runs
   `import_rosters.py diff` — kept out of the published frontend.

No browser cookies, scraped sessions, exposed tokens or unauthenticated
endpoints are used, and none should be.

Sources: Yahoo Fantasy Sports developer portal (sports.yahoo.com/developer,
/developer/access, /developer/docs), checked 2026-10-16; uberfastman/yfpy issue #84.
