# WHAT IF / GIẢ ĐỊNH (post-freeze lens)

Optional, read-only. It never changes league governance or any official record.

| State | Keepers | Salaries | Band |
|---|---|---|---|
| OFFICIAL | frozen | frozen (Yahoo registry the freeze was priced from) | `config/cap_policy.json` |
| WHAT IF — SAME KEEPERS (A) | identical to frozen | dated snapshot | recomputed (`cap_model.py`) |
| WHAT IF — REDO CUTS (B) | projected | dated snapshot | recomputed |

**Inputs:** `data/2026-27/keeper_freeze.json` + `prekeeper_rosters.json` (eligible roster) + `data/what_if/snapshots/<id>/`
(`players.json`, `snapshot.json`) + `config/what_if_assumptions.json`. Salary field is `projected_auction_value`
(never `average_auction_cost`); players missing from the snapshot are $0 and flagged `∅`.
Snapshot meta keeps three dates apart: `effectiveDate` (hypothetical), `fileAcquiredAt`, and Yahoo's own metadata.

**Add a snapshot:** `python3 scripts/what_if.py import "<draft_analysis.json>" --id YYYY-MM-DD --effective YYYY-MM-DD`
then `python3 scripts/what_if.py embed` (rewrites only the `WHATIF` block of `index.html`; a selector appears when >1 snapshot exists).

**Scenario B method (deterministic, explainable):** keep official picks unless the new ceiling is broken; then choose the
fewest-change legal set — never dropping a ≥$20 player, avoiding $10–19 drops (commissioner review), tie-broken by
Yahoo/dynasty value then name. Equally minimal fixes are listed, never hidden. The floor is not a keeper-declaration test.
Optional swaps (`DOMINATES`, `RANK_FLIP`) are flagged, never applied. Not enforced (no data): prospect-minutes exceptions,
positional tag minimums, IL cap treatment.

**FA 60:** same `build_fa_draft_pool` pipeline run three times — official; snapshot prices + official keepers (MARKET effect);
snapshot prices + projected keepers (adds KEEPER effect). Changes are attributed to the stage that caused them.
Manual swaps in the UI recompute cap/compliance only and live in page memory.

Official board JS gets only the mode button/banner hooks; the What-If page is `<section id="what-if">` and its cards are
`<article>` so Scenario Mode's `section.team-card` rewriter can never touch them.
