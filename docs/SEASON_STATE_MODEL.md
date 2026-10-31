# Season state model (2026–27 regular season)

Three layers; code in `scripts/season_state.py`.

| Layer | What | Source | Changes? |
|---|---|---|---|
| **A. Historical official** | keeper freeze + pre-draft trades + 48-pick draft | `keeper_freeze.json`, `trades.json`, `draft_state.json` → `league_state.resolve`; checkpoint `snapshots/POST_DRAFT.json` | Never (POST_DRAFT is refused if a rebuild would differ) |
| **B. Current season** | verified rosters + completed in-season trades | latest `rosters/snapshots/*` (via `rosters/index.json`) + COMPLETED rows of `season_transactions.json` dated after it | Each verified import / completed trade |
| **C. Trade Lab scenario** | B + ticked proposals | PROPOSED / AGREED rows of `season_transactions.json` | Never written; computed per combination |

The page's default ("OFFICIAL") view is layer B. Team-card rows: own draftees keep the draft chip (filled
purple `R · pick` for rookies); players acquired in a completed in-season trade get a blue bar and ⇄ tag; a
Trade Lab scenario acquisition gets an amber bar; a rookie acquired by trade keeps the purple name with an outlined
`R` chip (drafted by another team). Team cards show movement
against the post-draft roster; the Draft Archive and Picks pages show layer A.

## In-season ledger

`season_transactions.json` (not `trades.json`: the pre-draft ledger is replayed
before draft events, so an in-season trade of a drafted player cannot live
there). Statuses PROPOSED / AGREED / COMPLETED / VOID. A COMPLETED trade applies
once on top of the current snapshot while its `effectiveAt` is after the
snapshot's `verifiedAt`; a later verified snapshot already contains it (and the
importer refuses a snapshot that does not). A COMPLETED trade whose sender does
not own the asset fails loudly.

Current rows: `TXN-2026-001` CrazyCat ↔ HCMC, Morez Johnson Jr. ↔ Zion Williamson (COMPLETED);
`PROP-2026-001` Bsy ↔ sup fam and `PROP-2026-002` Bsy ↔ Thịnh (both COMPLETED, approved 2026-10-17 per the league
owner; promoted in place with a `statusHistory`, dated to the 2026-10-18 report; no Yahoo time or id supplied). Bsy ↔ Thịnh
is recorded in the only ownership-consistent direction (Bsy sends Wembanyama + Tyson): the approval did not state the
direction, and "Bsy receives Wembanyama + Tyson" cannot execute because Bsy already owns them. `PROP-2026-003` Long con ↔ Thịnh (Anunoby, Jarrett Allen, Porziņģis for Clingan, Robert Williams III, Cason Wallace) is COMPLETED, confirmed official by the league owner on 2026-10-31 (dated to the report; the 10-31 snapshot still shows the pre-trade rosters, so it applies on top until Yahoo shows it). No proposals are pending. `TRADE-F-AMEND` in
`trades.json` is VOID / WITHDRAWN, superseded by `TXN-2026-001`; `TRADE-F` and the
2.07 selection are unchanged.

## Salaries

`salary_freeze.json` — 2026-27 salaries frozen when the draft completed (registry
+ provisional, with a digest). `player_cap` reads it first, so a Yahoo refresh
never changes payroll. **Payroll = the top 9 salaries on the roster, IL / IL+
included** (league owner, 2026-10-16; `config/cap_policy.json` `payrollCounting`).
Players beyond the top 9 are greyed out and do not count. This applies to layers
B and C and to checkpoint findings (re-derived from each checkpoint's frozen
ownership); layer A keeps the all-player totals recorded at the time. The draft-night 12-player count is not enforced; the
importer only warns above the 15 roster spots.

## Page navigation (tabs)

The page shows one view at a time: **TEAMS** (1–8 and 9–16 together), **CAP**, **TRADE LAB**, **DRAFT**. The active tab is in the
URL hash (`#cap`, `#trade-lab`, `#draft`, `#draft/r2`), so links and the browser's back button work; the old anchors
(`#rosters-a`, `#rosters-b`, `#draft-order`) still land on the right tab. The Draft Archive has a tab per round (ALL ROUNDS /
ROUND 1 / 2 / 3; the default is all three side by side on wide screens and Round 1 on narrow ones). Tabs only toggle a CSS class
(`tab-off` / `sub-off`): every section stays in the page, nothing is generated differently, and printing shows everything.
What-If keeps its own mode switch (clicking a tab leaves it). On phones the top bar is two rows so all four tabs stay reachable.

## Team-card display rules

- **Healthy payroll.** The counted payroll (top 9 frozen salaries of everyone, IL included) is unchanged. "Healthy" is that
  figure minus the counted salaries of *injured* players: an IL / IL+ slot **or** a long-term Yahoo status (Out, INJ, OFS) even if
  the manager has not moved the player to IL (`season_state.injured_keys`, `config/roster_rules.json`).
- **Which nine are shown as counted.** Salary decides, with ties at the ninth salary resolved for the healthy player
  (`season_state.rank_roster`): an injured $0 player is never the counted one just because of name order. The payroll number is
  identical either way; only the display, and the IL group's "N counted", change.
- **Not-counted rows** are not faded (a fade also dims status chips): names keep full contrast, the salary sits in a dashed
  outline, and a divider labels the group.
- **Colour roles.** Status = solid fill, white text, white halo (P green, Q blue, D orange, INJ red with an inner ring, OUT red,
  OFS ink, NA charcoal). Where a player came from (trade, scenario, own draft) = a thin edge bar and an *outlined* tag, never a
  tinted row. Rookies stay purple. NA (not active, no NBA team) also gets a hatched row and a NO TEAM marker.

## Roster checks (anti-tank limits)

`season_state.roster_checks` reports the countable limits from the dynasty rules
(`config/roster_rules.json`, citing `LEAGUE_RULES_MODEL.md`) on every team card,
as evidence for the commissioner; it never labels a team as tanking. Injured players
(below) do not count toward the positional checks: they cannot contribute (owner, 2026-10-19).

| Chip | Counts | Levels |
|---|---|---|
| injured | IL / IL+ slots + players Yahoo lists Out (`O`, `INJ`) off IL; max 5 | at 5 = watch, over 5 = over |
| single-pos | healthy players who can play only one position; max 5 (7 with combo tags) | 6–7 = watch (combo exception is a judgment), > 7 = over |
| positions ✓ / short PG … | healthy players who can play each of PG, SG, SF, PF, C; min 2 | below = over |
| short G / short F | healthy players who can play either position of a two-position combo (G = PG/SG, F = SF/PF); min 3 | below = over |
| lineup | whether the healthy roster fills every Yahoo lineup slot on a full game day | any empty slot = over |

Player status comes from the verified roster snapshot (Yahoo's codes as observed;
it never affects ownership or payroll). Cards show it as a chip left of the name:
P green, Q / GTD / DTD blue, D orange, INJ red, OUT solid red, OFS / SUSP ink; an IL
player without a status shows IL. Not automated: when combo tags lift the single-position cap to 7, the "max 4 single-position in the active
roster" lineup rule, injury duration, IL-return timing, and trades that would
worsen a concentration.

## Trade-time cap rule (in-season)

Dynasty-Rule-Oct-2025 "Trade trong mùa": adds/drops may leave the band, trades
must move a team toward 131–178. `league_state.in_season_cap_checks`:
`CAP_TRADE_LEAVES_BAND` (out of band and not moving toward it — the trade is
reversible; ladder under $5 / over $5 / exactly $5 → commissioner) or
`CAP_STILL_OUTSIDE_BAND` (outside but moving toward: allowed). Roster count is not
checked in-season.

## Cap checkpoints

`cap_checkpoints.json`: POST_DRAFT (2026-10-14, `snapshots/POST_DRAFT.json`) and
POST_TRADE_DEADLINE (date pending, All-Star week). Findings are derived from the
checkpoint snapshots (`season_state.checkpoint_findings`), so a recorded
under-floor finding stays even if payroll later improves. Status
`FINDING_RECORDED` → `REPEAT_UNDER_FLOOR_REVIEW` when the deadline checkpoint is
also under the floor; the +5W penalty (unless payroll improved via trade or claim)
is applied only as a recorded `commissionerDecisions` entry, never automatically.

DonTrick: 123 counted (top 9) at the post-draft checkpoint, floor 131 → **8 short**. Finding
recorded, no penalty.

To record the deadline checkpoint: after the deadline, commit a verified roster
snapshot (`docs/ROSTER_REFRESH.md`), then
`python3 scripts/season_state.py record-checkpoint POST_TRADE_DEADLINE --date YYYY-MM-DD`
(freezes every team's current payroll; refuses to re-record).

## Search and "my team" (page navigation)

- Top bar: **Search** (`/` or Ctrl/Cmd-K) finds teams, rostered players and free agents (accent-insensitive); a pick jumps to the team card / player row on the Teams tab. Rookies keep their purple name plus an `R · slot` tag.
- **My team** (★ button, remembered in the browser's localStorage only) is one tap away and is marked everywhere a chip names it: Teams, Cap, Draft pick rows/chips, Trade Lab cards/folds/compare, What-If and scenario views. Marker is ink-navy (double frame + star badge), deliberately not gold/green/red, which carry status/trade meaning. See `markMine` in `index.html`.
- Mobile: the tab row and search stay pinned while scrolling; only the Official/Scenario/What-If switch folds away.

## Trade checker

`scripts/trade_checker.py` `check_proposal(si, state, moves, now)` returns per-rule rows `{rule, team, level (ok/info/review/blocked), source, reason}` and an overall `LEGAL` / `COMMISSIONER REVIEW` / `BLOCKED`. It reads the current-season state and never writes. The page embeds `trade` (rules, roster limits, preseason top-32, acquisition dates) and runs a port of the same logic; `tests/test_scenario_rendering.py` compares the two on every 1-for-1 swap.
