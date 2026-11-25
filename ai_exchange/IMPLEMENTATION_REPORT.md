# Implementation Report

Run: 2026-11-25 — game log: one line per game, whole season for rostered players (plan C phase 5)

- Player card, export and share text: one line per game with aligned columns.
- `scripts/yahoo_player_days.py` + `scripts/backfill_player_log.py` read Yahoo's public one-day player list; each day is checked against the team pages; `player_days.json` on `stats-data`.
- The stats workflow runs the fill after the team-page log (max 20 days a run).
