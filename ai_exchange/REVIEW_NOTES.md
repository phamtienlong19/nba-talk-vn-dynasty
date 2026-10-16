## Issues

- Payroll now counts the top 9 salaries per roster, IL included (league owner, 2026-10-16). Current-season changes: CrazyCat 147→145, LC 162→161, DonTrick 124→123; DonTrick's post-draft shortfall is 8. Draft-night history keeps all-player totals.

- PROP-2026-002 (Bsy ↔ Thịnh) was described with the direction reversed; it is staged in the only ownership-consistent direction (Bsy sends Wembanyama + Tyson) and flagged `DISCREPANCY_FLAGGED`. Confirm with the teams.
- PROP-2026-002 alone puts Bsy at 179 (> 178): `CAP_TRADE_LEAVES_BAND`, under-$5 ladder. Together with PROP-2026-001 Bsy ends at 176 (legal).
- TXN-2026-001 effective date is the report date (2026-10-16); the exact Yahoo processing time was not supplied.
- The 16 Yahoo team keys and the league key are unknown (no authenticated data in the repo); `rosters/team_map.json` has nulls.

## Decisions Required

- Confirm PROP-2026-002 direction before it moves past PROPOSED.
- Commissioner: provide the league id; decide whether to apply for Yahoo Fantasy API access (docs/YAHOO_API_FEASIBILITY.md).
