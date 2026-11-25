# Implementation Report

Run: 2026-11-25 — lineup review: fault only what a manager could have avoided

- The lineup log keeps the day's history (`day_start`, `state`, `gap`).
- `scripts/lineup_review.py` applies the owner's 19-case table and publishes `lineupReview` in the live feed; rules in `config/roster_rules.json`.
- REVIEW tab, LIVE lineup checks and My team show the same faults; the in-page judging and log fetch are gone.
