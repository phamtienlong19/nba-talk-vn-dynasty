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

**Baseline note:** What If models the keeper deadline, so its OFFICIAL side is the locked keeper freeze (pre-trade). It does not apply the later official pre-draft trades.

## KEEPERS view (your own ranking and keeper plan)

A simulator for next season: pick a team, re-rank players the way you expect them to be ranked, tick up to 9 keepers. Never
official, never written to league data.

- **Salary rule (owner, 2026-10-30):** a player's keeper salary is the salary at his **actual descending rank** (Yahoo projected $
  sorted high to low, ties by O-Rank), not his O-Rank (e.g. Sandro Mamukelashvili: $3 at O-Rank 139, but position 116 by $).
  The table is stored in `config/keeper_salary_by_rank.json`, built by `python3 scripts/keeper_rank_salary.py` from
  `data/yahoo/players_normalized.json`. Regenerate and commit it when the Yahoo snapshot is refreshed; a test skips (with a
  reminder) when the committed table is older than `data/yahoo/provenance.json`. Ranks past the paid ranks are $0.
- **Re-ranking:** a rank number (or ▲/▼) *pins* the player at exactly that league-wide rank; everyone else keeps Yahoo's order.
  If two edits want the same rank, the later one wins and the earlier slides down one.
- **Checks:** payroll of the kept players against the **official** band (`config/cap_policy.json`; ceiling is the declaration
  test, the floor is shown only), at most `keeperMax` keepers, and for every unkept player the existing drop thresholds
  ($20+ cannot be dropped without the commissioner, $10-19 needs review). Flags appear once a keeper is chosen.
- **Memory across sessions:** the URL (`&team=&keep=&rk=`) and this browser's localStorage (`nbaTalkVN.keeperBoard`). *Copy my
  link* moves a plan to another device or the group chat. No backend, no PR.
- Rosters are the latest verified snapshot (trades applied). Drafted rookies are not special-cased.
