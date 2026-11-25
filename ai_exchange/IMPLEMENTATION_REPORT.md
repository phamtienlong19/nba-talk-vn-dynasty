# Implementation Report

Run: 2026-11-25 — LIVE tab reduced to lineups and checks (plan C phase 4)

- LIVE shows one lineup card per team with current-slot flags, the week's roster changes and the lineup checks; export of current lineups.
- Removed: scores, standings, playoff picture, projected order, roto, raw stats, all-play, schedule, the TEAMS tab's live order and My team's score / rank / next opponents.
- The feed no longer builds them and reads only the current week (plus closed days). `live_standings.py` and `live_roto.js` deleted; `roto.py` kept for `tools/yahoo-roto`.
- The live workflow now restarts on changes to the lineup scripts and `config/roster_rules.json`.
