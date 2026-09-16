# League Rules Model

Summarized from `local_sources/Dynasty-Rule-Oct-2025.docx` (Vietnamese,
local-only) plus this project's direct current instructions, which take
precedence on any conflict (see `docs/OPEN_RULE_QUESTIONS.md` for the one
place that mattered: lottery ticket allocation). Historical enforcement
examples and named tank-violator records from the DOCX are intentionally
**not** reproduced here (Section 28 of the bootstrap spec) — only the
mechanism is described.

## League structure

- 16 teams, 2 divisions, head-to-head weekly, 9 categories.
- 8-team playoffs (final week finishes one week before the regular season
  ends). Division winner qualifies; seeding is by overall record; no
  playoff reseeding; H2H is the playoff tiebreaker.
- A team is locked after its own final week; adds/claims after lock are
  reverted.
- Max 7 adds/week. Yahoo's Can't Cut List applies.
- Waiver/trade review: 2-day pending period.
- Trade deadline: around All-Star week.
- Trade veto: league + commissioners vote; veto requires ≥7/16 team
  votes; an uninvolved commissioner may cast one additional vote.

## Roster / keepers (2025–26 onward)

- 9 keepers, 15 total roster spots.
- Active (8 slots): PG, SG, G, SF, PF, F, C, FC.
- Plus 3 Bench, 2 IL, 2 IL+.
- The whole roster, including IL/IL+, carries into the offseason for
  keeper selection.

## Roster / anti-tank governance (deterministic parts)

- Max 5 long-term-injured players (IL, or GTD with a >2-week-out signal).
- Minimum 2 tagged players per position (min 3 for a 2-position combo,
  e.g. needing a 3rd SF/PF-tagged player if only 2 exist).
- Max 5 single-position-only players roster-wide (max 4 in the active
  roster); combo-position tags (e.g. PG+PG/SG+SG) raise the cap to 7.
- A team already over these thresholds may not trade for or add players
  that would worsen the same concentration.
- Coaches must move a newly long-term-injured player to IL within 2 days
  of the injury tag, and must return a healthy IL player to the active
  roster within 1 game of clearance.
- Active-roster players must have real NOW value, keeper potential, or a
  bad contract >$5 (salary-cheat value) — not N/A filler; commissioner
  judges edge cases (e.g. a low-impact 25-minute role player may be asked
  to be dropped).
- Prospect/young-player keep exceptions: max 1 not-yet-rotation
  (<10 min) top-10 rookie, plus max 2 young players with unstable minutes
  (<20 min) total including that rookie. "Young/prospect" means a
  rookie/sophomore/3rd-year player inside roughly the top 10–15 (rookie),
  top 5–10 (sophomore), or top 3–5 (3rd year) picks of their draft class,
  or per commissioner judgment.
- Salary-based drop restrictions: players valued ≥$20 (or top-50
  preseason rank) may never be dropped; players valued $10–19 face
  restricted drops subject to commissioner/league review (via current
  average ranking, above/below top 100).

## AFK / lineup-integrity rules

- AFK trigger: 2+ days, or 3+ players, misset in a week. A smaller
  misset (2 players) still counts if they're stars (top-50 XRank or
  commissioner judgment), or if the pattern repeats across consecutive
  weeks. Benching a star, or intentionally starting a long-term-injured
  (IL) player, also counts as misset.
- If both sides of a matchup forget to set a lineup, only the side with
  more (and higher-ranked) players benched is flagged — unless a
  commissioner-approved compensating benching applies (a team that
  detects blatant tanking by an opponent may bench a matching quantity
  and quality of players without being flagged as AFK itself).
- Playoff teams are never charged Tank Violator points for AFK.

## Tank allowance (late-season)

- In the final 3 weeks of the regular season (roughly from All-Star
  week), a team may intentionally lose. Limits: max 1/4 of that week's
  games benched (excluding Out/IL), and at most 1 game bench for a
  player averaging rank 50 or better (season, L30, or XRank). A team
  actively tanking may not go below a 2-7 category-loss margin (to avoid
  distorting the playoff race); streaming bad players to intentionally
  lose strong categories is the documented alternative to raw benching.
  Violating these tank conditions itself counts as an AFK instance.

## Tank Violator penalty ladder (mechanism, not historical data)

No warnings under the current model. Penalties escalate by points, applied
in order from the 16-seed toward the 8-seed (worst draft position first):

| Points | Effect |
|---|---|
| 1 | +5W to record before Lottery, for teams in the out-of-PO/lottery-ball group (capped at the last lottery-eligible slot). |
| 2 | +10W (same group/cap); a team inside the PO group may be moved up 1 seed slot. |
| 3 | Same as 2, plus: after the lottery result, draft position moves back 1 slot. |
| 4 | Fixed placement at the end of its group (lottery group → pick 8 of that group; PO/lottery group → pick 12). |
| 5+ | Round 1 pick becomes the last pick of Round 1 (16th). |

## Trade rules

- Cooldown: a traded-for player must be held ≥2 weeks (≥4 weeks for a
  top-32 preseason-ranked player).
- Total Value = `[Value NOW + (Value FUTURE × 3)] / 4`, where FUTURE
  spans roughly the next 3 seasons.
- Ordinary in-season trades: NOW-value gap should stay under ~30%.
- Trade Tank: NOW-value gap may widen to ~30–50%; only for teams that
  are mathematically out of playoff contention (Games Back vs. seed 8
  exceeding weeks-remaining-to-PO); one sell-NOW/buy-FUTURE trade per
  eligible tanker; must occur ≥2 weeks before the trade deadline;
  O4S/serious injury changes how NOW/FUTURE are read for that player.
- Trade evaluation (fairness, tank-intent, injury discounting) is
  **commissioner review**, not an automatic approval — see
  `docs/RULE_AUTOMATION_MATRIX.md`.

## Pre-draft trade window

- After keeper declaration, before the draft: each team may make up to 1
  trade (may involve 2+ teams), often to create cap space.
- This is the only window where the **current year's** Round 1 pick may
  be traded (future Round 1 picks are not implied tradeable here).
- Admin/league veto still applies. Final roster-size constraints still
  apply. Teams may finalize/trim their keeper list before the draft.

## Salary cap application

Applies at keeper declaration, draft, and trade.

- $0 players are treated as minimum-value/vet-min; always draftable/
  tradeable even at a full cap.
- Keeper: max 9 keepers; may not exceed the cap ceiling at declaration.
- Draft: teams self-monitor; at a full cap, only $0 (or below-cap)
  players may be added. Under the floor, Round 1 allows rookie/no-salary
  flexibility, but Round 2+ forces drafting above the team's own
  lowest-salaried player; a second consecutive under-cap season forces
  drafting the highest-salaried available player.
- In-season adds may temporarily push a team outside the cap band; trades
  must move a team toward the permitted range, not away from it.

## Cap violation ladder (trade-time)

| Violation size | Effect |
|---|---|
| < $5 | Trade-restricted for 2 weeks; repeat violation adds ±$3 to future cap allowance through next season's draft. |
| > $5 | Trade-restricted for 1 month; ±$5 to future cap allowance through next season's draft. |
| Near trade deadline | Restriction extends through next season's draft regardless of size. |

Undercap checkpoints: Post-Draft and Post-Trade-Deadline. Violating both
checkpoints in one season: +5W penalty (unless demonstrable cap
improvement occurred). A 2nd consecutive violating season: lose
add/drop rights in the first week of playoffs (if qualified) and 1st
Round pick drops one slot next season. A 3rd consecutive season: lose
add/drop rights through all of playoffs, and Round 1 pick is fixed to
the end of its group (PO or Lottery) next season.

## Lottery / draft order (current 2026–27 model)

Lottery mechanics themselves are owned by `nba-talk-vn-lottery` — this
project only consumes a final export. Current parameters (per this
project's direct instructions, which take precedence over the DOCX's
older/evolving numbers — see `docs/OPEN_RULE_QUESTIONS.md`):

- 12 teams participate, covering regular-season ranks 16→5.
- Ticket allocation (rank 16 → rank 5): `16,16,15,15,14,13,12,11,2,2,2,2`
  — 120 total combinations.
- Pick 1.02 is resolved first, then 1.01. The prior winner remains
  eligible for 1.01; if the same team wins both, it keeps its choice of
  pick and the other pick is redrawn.
- Round 2 and Round 3 use plain inverse regular-season standings — no
  lottery, no Rank 3/4 bonus.
- Regular-season Rank 3 and Rank 4 do not enter the lottery. After 1.01
  and 1.02 resolve, Rank 3 takes the earliest remaining slot in the
  Rank 3–8 Round-1 block, then Rank 4 takes the next earliest — i.e.
  they occupy the first two positions left after removing the lottery
  winners from that block. Their exact slot shifts depending on whether
  lottery winners came from ranks 5–8.

The DOCX describes an earlier/transitional model (a 2024-25-era 8-ball
combination scheme, `21-21-19-19-16-12-8-3`, and various proposed
alternate-format contingencies if tanking became severe, e.g. dropping to
6-team or 4-team playoffs). Those are historical/contingency context, not
the current authoritative numbers.
