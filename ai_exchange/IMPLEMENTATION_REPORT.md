# Implementation Report

Run: 2026-09-16 — Issue #2, "Double Check Team Name and Rosters' Cap Numbers".

## Fixed

- **John Collins cap.** Published board showed `1` (The Silver Seekers'
  roster row and both cap-total displays); live Yahoo
  `projected_auction_value` (verified via `./refresh-yahoo.sh`,
  `local_data/yahoo/draft_analysis_2026-09-16T045439Z.json`) is `0`.
  Corrected the player row and recomputed the team's cap total/ROOM in
  both the team card and the CAP page summary card:
  `153/175, 22 ROOM` → `152/175, 23 ROOM`.
- **Outdated rookie flags.** Nique Clifford, Tre Johnson, and Dylan
  Cardwell were shown `rookie-row`/`R` in the draft pool. Confirmed via
  web search that all three are 2025 NBA draft class (Clifford: Kings
  1st rd; Johnson: Wizards #6 overall; Cardwell: Kings UDFA
  two-way/standard) — second-year players for the 2026-27 season the
  board covers, not rookies. Reclassified as `FA` (no fantasy-league cut
  source is recorded for them, so `src-cut` with a team code would be a
  guess).

## Checked, not changed (surfaced for human review)

- **Minor per-player cap drift.** A full audit script compared every
  roster/pool cap value in `index.html` against a fresh
  `./refresh-yahoo.sh` pull. Six other players (Jaime Jaquez Jr., Peyton
  Watson, Josh Hart, Ayo Dosunmu, Kristaps Porziņģis, Andrew Wiggins)
  differ by ±1 from today's live snapshot even though the aggregate
  floor/ceiling still MATCH (130/175). This is ordinary day-to-day
  market movement in Yahoo's `projected_auction_value`, not a baking
  error, so it was not bulk-applied — CLAUDE.md reserves promoting a
  changed Yahoo snapshot to a human decision.
- **Team identity-tag/name mismatches** between the forensic-canonical
  `data/2026-27/franchises.json` (authoritative for team
  identities/order per `CLAUDE.md`) and the currently published
  `index.html`:
  - franchise-01: canonical `Hai` vs board `Bsy`.
  - franchise-07: canonical has no team name at all (`Maxfixe`) vs
    board `Maxfixe | Poop for Coop` — likely a gap in the forensic
    source rather than a board error, but not resolved here.
  - franchise-09: canonical `M. Jordat` vs board `Đạt`.

  These aren't verifiable from data already in the repo — the forensic
  snapshot is dated 2026-08-20 and the public board 2026-09-16, so
  either could be the stale one. Left both sources untouched; recorded
  as `Decision Required` in `tasks/ACTIVE.md`.

## Validation

- `./validate.sh` — PASS
- `python3 -m unittest discover -s tests` — 19 tests, PASS
- `./refresh-yahoo.sh` — live floor/ceiling MATCH (130/175)
