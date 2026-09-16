# Rule Automation Matrix

Classifies each rule area from `docs/LEAGUE_RULES_MODEL.md` by how much of
it can be safely automated versus requiring human judgment. None of this
is implemented yet (Section 4 of the bootstrap spec) — this is a design
reference for future phases (`docs/PRODUCT_SCOPE.md`).

Categories:

- **AUTOMATABLE** — deterministic given canonical data; no judgment call.
- **PARTIALLY_AUTOMATABLE** — can compute evidence/flags automatically,
  but a human still confirms or overrides the conclusion.
- **COMMISSIONER_REVIEW** — inherently a judgment call; software should
  surface evidence, never auto-decide.
- **MANUAL_GOVERNANCE** — process/social rule, not really a data problem
  (e.g. team-transfer approval criteria).

| Rule area | Classification | Notes |
|---|---|---|
| Roster count / keeper count (≤9 keepers, 15 spots) | AUTOMATABLE | Pure counting against canonical roster state. |
| Salary totals vs. cap floor/ceiling | AUTOMATABLE | Pure sum + `cap_model.py` bands, given canonical ownership + Yahoo cap dollars. |
| Draft/trade pick ownership | AUTOMATABLE | Ledger lookup once a transaction system exists. |
| Trade cooldown windows (2 wk / 4 wk top-32) | AUTOMATABLE | Date arithmetic from the transaction ledger. |
| Cap checkpoints (Post-Draft, Post-Trade-Deadline) existence/timing | AUTOMATABLE | Calendar-driven, no judgment. |
| Number of long-term-injured players (given real injury-status data) | AUTOMATABLE | Requires a reliable injury-status feed; otherwise partial (see below). |
| Positional concentration (max single-position, combo caps) | PARTIALLY_AUTOMATABLE | Countable from eligible positions, but "combo" tag interactions and edge cases benefit from a human sanity check before penalizing. |
| Minimum position coverage (2–3 tagged players per slot) | PARTIALLY_AUTOMATABLE | Same as above. |
| Healthy player left on IL past clearance | PARTIALLY_AUTOMATABLE | Needs a real "cleared to play" signal, which is not always clean/timely in public data. |
| Playing-time / rotation thresholds (20 min active, prospect exceptions) | PARTIALLY_AUTOMATABLE | Minutes data is available, but the prospect/rookie exception depends on draft-class judgment. |
| Cap direction during a trade (must move toward the band) | PARTIALLY_AUTOMATABLE | Arithmetic is automatable; whether the *intent* was compliant (vs. a violation needing penalty) is commissioner-adjacent. |
| Salary-based drop restrictions (≥$20 never-drop, $10–19 restricted) | PARTIALLY_AUTOMATABLE | The $20 floor is a hard rule; the $10–19 band explicitly defers to "ave ranking + commissioner/league review." |
| AFK detection (missed lineup days/players) | PARTIALLY_AUTOMATABLE | Countable from lineup logs, but star-player identification (top-50 XRank "or commissioner judgment"), compensating-benching exceptions, and multi-week pattern matching need human confirmation. |
| Tank-window benching limits (max 1/4 games, rank-50 game cap) | PARTIALLY_AUTOMATABLE | Countable, but whether a loss margin or streaming choice was "intentional tanking" vs. legitimate strategy is judgment. |
| Trade fairness / Total Value balance | COMMISSIONER_REVIEW | The formula is a starting estimate; FUTURE-value projection, O4S discounting, and "is this obviously lopsided" are explicitly judgment-based in the source rules. |
| Trade Tank eligibility and fairness | COMMISSIONER_REVIEW | Games-back eligibility is computable, but approving the trade's fairness is not. |
| Whether a role player has legitimate current value | COMMISSIONER_REVIEW | Explicitly named in the source rules as commissioner-evaluated. |
| Whether roster construction is "obvious tanking" | COMMISSIONER_REVIEW | Same. |
| Whether benching was strategically legitimate (vs. tanking) | COMMISSIONER_REVIEW | Same; includes the compensating-benching carve-out. |
| Prospect/young-player keep exceptions | COMMISSIONER_REVIEW | Draft-class judgment ("top 10 per commiss") is explicit in the source rules. |
| Team-transfer approval (new owner vetting) | MANUAL_GOVERNANCE | Social/reputational criteria across other NBA Talk leagues; not a data problem. |
| Tank Violator point assignment | COMMISSIONER_REVIEW | The ladder's *effects* are deterministic once points are assigned (see LEAGUE_RULES_MODEL.md), but assigning the points themselves is a human review of AFK/tank evidence each week. |

## Design principle

Software should compute and surface evidence (counts, flags, historical
comparisons) for every `PARTIALLY_AUTOMATABLE` and `COMMISSIONER_REVIEW`
row — never silently convert a judgment call into a boolean gate. See
Section 37 of the bootstrap spec and `docs/DATA_MODEL.md`'s
`COMPLIANCE_EVENT` entity, which is designed to record
`commissionerDecision` explicitly rather than assume one.
