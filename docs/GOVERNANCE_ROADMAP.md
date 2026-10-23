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

## Status
- **Trade checker: built** (Trade Lab → "Check a trade"; `scripts/trade_checker.py`, numbers in `config/trade_rules.json`, page port tested against Python). Decisions of 2026-10-21: the cooldown restricts re-trading the acquired player (14 days, 28 if preseason top-32 O-Rank); proposals are built ad hoc in the browser and shared by URL (`?check=playerKey~toTeam,...`), nothing stored; the violation ladder is displayed only (no memory of past violations); anti-tank = blocked only when a limit is already over and the trade worsens it, review when the trade takes a team over, info at the limit. Players only (in-season trades move no picks). Now the **Trade Machine**: 2-6 teams, post-trade rosters with the card styling, per-team summary (gets / sends / drops, payroll meter, check marks), a 15-roster-spot rule (Yahoo makes a team over the limit drop players, so the machine lets you pick drops and checks them against the drop rule: 20+ never, 10-19 review; it never suggests who to drop). No dollar signs anywhere in the tool: payroll is plain points. Also modelled (2026-10-21): **draft picks** (next season's R1-R3 only; 1st-round locked in-season; 2nd/3rd only inside a Trade Tank trade, at least 2 weeks before the deadline; nothing further ahead; source: the original rules document, para on Trade Tank and the pre-draft window); **Yahoo slot peculiarities** (9 lineup + 3 bench + 3 IL = 15; incoming players never land on IL; only injured players can be moved to IL, so a team at 12 players outside IL needs a drop or an IL move first); **trade deadline** (Feb 18, 2027) and Trade Tank cutoff (Feb 4); **drop rule** = paid 20+ OR preseason top 50 never; 10-19 restricted (commissioner decides by current ranking, top 100). Settings are recorded in `docs/YAHOO_LEAGUE_SETTINGS.md`. **Share image** (Trade Machine): draws the proposal onto a canvas (no libraries): headline + verdict, one card per team (gets / sends with counterpart pills, payroll before to after on the band meter, roster size, the rules' flags in words), dated; preview with Share (phone share sheet) / Copy image / Save. Nothing is stored or uploaded. Not checked: Trade Tank eligibility (needs standings), bans from past cap violations, NOW/FUTURE value (out of scope by owner decision). Not evaluated: Trade Tank eligibility (needs live standings), the trade deadline (date unset), salary-drop restrictions.

## Build order
1. **Trade checker** (essential). Input: a proposal (teams, players, picks) in Trade Lab. Output: a verdict per rule with
   the rule's source and a plain "blocked because…" reason, then one overall status: `LEGAL` / `BLOCKED` /
   `COMMISSIONER REVIEW`. Never "good" or "fair". Shareable link = URL state only (Trade Lab already supports
   `?mode=scenario&trades=`; extend it to ad-hoc proposals). No storage.
2. **"My team" landing view**, phone-first: counted + healthy payroll, room to the band, what the manager cannot drop,
   cooldowns, restrictions, checkpoint status, pick ownership.
3. **Lottery / standings display built as configuration.** Top-of-draft eligibility is now recorded
   (`config/draft_lottery_rules.json`, `scripts/lottery_eligibility.py`; commissioner rules of 2026-10-20: no top 2 twice in
   a row, one No. 1 per 3-year span). The display should flag, per team, "cannot pick 1st / 1st or 2nd in <year>" with the
   reason, and recompute after each draft. Decided: eligibility follows the lottery-time holder; an ineligible draw result is
   redrawn; the 2027 ball allocation is unchanged. Remaining: The NBA changes its lottery in 2027; how this league adopts it
   is undecided (expected: relegation-style zone, limits on top-3 picks for the worst teams, no consecutive No.1s). Model
   odds table, zone, exclusions and no-consecutive rule as config; show the current model as "2026–27 model". The ball allocation is unchanged
   for 2027 (see Backlog).
4. **Ranking board with live keeper-salary math** (offseason): a manager re-ranks players, keeper salaries move with the
   ranking, payroll / band room / legality update live. Client-side only, saved in the browser, never written to official
   data. Needs the exact rank→keeper-salary function confirmed against `docs/CAP_MODEL.md` and how the league actually sets it.

## Backlog (filed 2026-10-20; not scheduled)

**Lottery simulator on live standings** (inspired by Tankathon's draft-lottery simulator that tanking-franchise fans use).
- **What:** a page that takes the live Yahoo standings, orders teams worst to best (`standings_view` already provides this once
  games are played) into the projected pre-lottery order, shows each team's odds for each slot, and lets a manager press "Sim
  lottery" to draw one outcome, or run many sims for a probability table. Reset returns to the live order.
- **Rules it must apply:** the league's lottery parameters (above); the top-of-draft eligibility from `config/draft_lottery_rules.json` / `scripts/lottery_eligibility.py` (no
  top 2 twice in a row, one No. 1 per 3 years; ineligible teams show as such); and the owner's rule that a draw landing on
  an ineligible team is **redrawn**.
- **Settled:** the ball allocation is the same for 2027 as for 2026-27 (owner, 2026-10-20) and is recorded as data
  (`lottery` in `config/draft_lottery_rules.json`: 12 teams, tickets 16,16,15,15,14,13,12,11,2,2,2,2 = 120, draw 1.02 then
  1.01, rank 3/4 bonus, rounds 2-3 plain inverse standings). Read it from config; never hard-code it.
- **Open before building:** how ties in the standings are broken (H2H, per the league rules); how the "same team wins both
  picks" clause interacts with the redraw rule.
- **Governance, not advice:** it shows odds and eligibility; it never says who should tank or trade.
- **Reuse:** `standings_view` (live order), `lottery_eligibility.eligibility`, the card/chip styling. Client-side simulation;
  nothing is written to official data. The actual official lottery stays in the separate `nba-talk-vn-lottery` repo.

**Other planned or possible work, in rough priority:**
- Ranking board with live keeper-salary math (offseason; per-manager, browser-only) and, later, a keeper planner.
- Statuses for free agents in the available-players list (the 600-player status table `data/yahoo/player_status.json` exists;
  only rostered players show a status today).
- Local scheduled refresh on the owner's Mac (a LaunchAgent running `yahoo_rosters.py fetch`, `standings` and
  `refresh_player_metadata.py`); never GitHub Actions with Yahoo credentials.
- Link the six provisional rookies to their Yahoo ids (`import_rosters.py link-provisional`) once the commissioner agrees.
- Decide whether Jaylen Martin and Kylor Kelley (on Yahoo, not in the registry) should join the player registry.
- Roster-check refinements not yet automated: the "max 4 single-position in the active lineup" rule, injury duration,
  IL-return timing, and "trades may not worsen a concentration" (part of the trade checker).

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
