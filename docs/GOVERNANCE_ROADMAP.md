# Governance roadmap (owner direction, 2026-10-19)

Purpose: digitise league governance (chuyển đổi số). The tool **flags what a manager cannot do, and why** — it never
suggests what to do. Managers negotiate in group chat and DMs; they come to the tool for context on their own team and
for rule checks. Fairness, tank intent and penalties stay commissioner judgment (`CLAUDE.md`).

## Out of scope (owner decisions)
- NOW/FUTURE trade values and any value-gap meter (too subjective).
- Roster intelligence: positional-need maps, injury impact, waiver ideas.
- Auto-balancer, "who should I trade with", or any recommendation. Neutral context (every team's cap room and band
  status) is fine; ranking or advising is not.
- Recording proposals or veto votes: approval is outsourced to the group chat / commissioner. No new storage.

## Build order
1. **Trade checker** (essential). Input: a proposal (teams, players, picks) in Trade Lab. Output: a verdict per rule with
   the rule's source and a plain "blocked because…" reason, then one overall status: `LEGAL` / `BLOCKED` /
   `COMMISSIONER REVIEW`. Never "good" or "fair". Shareable link = URL state only (Trade Lab already supports
   `?mode=scenario&trades=`; extend it to ad-hoc proposals). No storage.
2. **"My team" landing view**, phone-first: counted + healthy payroll, room to the band, what the manager cannot drop,
   cooldowns, restrictions, checkpoint status, pick ownership.
3. **Lottery / standings display built as configuration.** The NBA changes its lottery in 2027; how this league adopts it
   is undecided (expected: relegation-style zone, limits on top-3 picks for the worst teams, no consecutive No.1s). Model
   odds table, zone, exclusions and no-consecutive rule as config; show the current model as "2026–27 model". Do NOT guess
   the 2027 rules.
4. **Ranking board with live keeper-salary math** (offseason): a manager re-ranks players, keeper salaries move with the
   ranking, payroll / band room / legality update live. Client-side only, saved in the browser, never written to official
   data. Needs the exact rank→keeper-salary function confirmed against `docs/CAP_MODEL.md` and how the league actually sets it.

## Trade checker rules (source: `docs/LEAGUE_RULES_MODEL.md`)
| Rule | Check | Level |
|---|---|---|
| Cap direction | each team ends closer to the 131–178 band (existing `league_state.in_season_cap_checks`, top-9 frozen salaries) | blocked |
| Violation ladder | under $5: trade-restricted 2 weeks; over $5: 1 month; near the deadline: through next draft; repeat adds ±$3 / ±$5 allowance | restriction shown |
| Cooldown | a traded-for player is held ≥2 weeks; ≥4 weeks if top-32 in the **preseason Yahoo O-Rank** (owner decision). Countdown from the completed trade's `effectiveAt` in `season_transactions.json` | blocked |
| Anti-tank limits | trade may not worsen an already-over concentration (`season_state.roster_checks`: injured >5, single-position, coverage, combos, lineup) | blocked / review |
| Trade Tank | eligibility only: games back vs seed 8 > weeks remaining, one sell-NOW/buy-FUTURE trade per eligible team, ≥2 weeks before the deadline (needs live standings: `yahoo_rosters.py standings`) | eligibility flag |
| Salary-drop restrictions | $20+ players can never be dropped; $10–19 need review (drop checker, same view) | blocked / review |
| Pending period | 2-day review window, shown as information (approval itself is outsourced) | info |
| Process / fairness | always commissioner review; never automated | review |

Open data questions to resolve while building: which snapshot is the "preseason O-Rank" (candidates:
`data/yahoo/player_registry.json` `oRank` as of its fetch date, or `data/what_if/snapshots/2026-10-08`); trade dates in the
ledger are report dates, not Yahoo timestamps, so cooldown countdowns must say "from the recorded date".

## Conventions
Follow `CLAUDE.md` (fresh branch from latest `main`, read-only on canonical data, tests + `./validate.sh`, PR, never
merge). Reuse `season_state.py`, `league_state.py`, Trade Lab and `roster_checks`; do not build a second cap calculator.
Keep internal notes off the public page. Use rules from the config files (`config/roster_rules.json`,
`config/cap_policy.json`), not hard-coded numbers.
