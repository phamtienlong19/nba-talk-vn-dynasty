## Issues

- `rosters/team_map.json` now maps all 16 Yahoo team ids to franchises (each matched by team-name prefix and by every Yahoo-listed player belonging to that franchise). Please confirm.
- The 2026-10-19 Yahoo capture is NOT imported. It blocks on Jayden Quaintance (sup fam, 478.p.10594), who is not in the frozen 2026-27 salary table, and shows 6 provisional rookies now listed under Yahoo ids (link-provisional candidates), 17 Yahoo-only players and 3 players only on our rosters (Risacher, Will Riley, Santi Aldama).
- Yahoo's keeper-salary label for RJ Barrett is 5; the frozen salary is 0. Not changed.

## Decisions Required

- Salary entry for Jayden Quaintance before the first Yahoo import.
- Whether to link the 6 provisional rookies to their Yahoo ids (`import_rosters.py link-provisional`).
