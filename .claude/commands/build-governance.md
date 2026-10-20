---
description: Build the next governance feature (trade checker, my-team view, lottery config, ranking board) per docs/GOVERNANCE_ROADMAP.md
argument-hint: "[trade-checker | my-team | lottery | ranking-board]  (default: next unbuilt item in order)"
---

Continue the NBA Talk VN Dynasty governance roadmap. Feature requested: $ARGUMENTS (if empty, take the first item in the
build order that is not yet built).

1. Read, in order: `CLAUDE.md`, `docs/GOVERNANCE_ROADMAP.md` (the owner's direction — it is binding), `ai_exchange/CURRENT_STATE.json`,
   `docs/SEASON_STATE_MODEL.md`, `docs/LEAGUE_RULES_MODEL.md`, and the memory note `product-direction-governance-not-advice` if present.
2. Check prerequisites: `git fetch`, confirm PR "Yahoo roster acquisition … team cards" (#59) is merged into `origin/main`
   (it provides `roster_checks`, player status, standings, `config/roster_rules.json`). If it is not merged, say so and stop.
3. Work in a fresh branch from the latest `origin/main`, preferably in a `git worktree`. Never stack on another feature
   branch and never touch uncommitted edits in the main working tree.
4. Principle (do not violate): the tool **flags what a manager cannot do and why**; it never recommends, ranks, or judges
   fairness. No NOW/FUTURE values, no roster intelligence, no recording of proposals or votes, no new storage for approvals.
5. For the first run of a feature: write a short spec (rules table, inputs, outputs, edge cases) into the PR description or
   `docs/`, list any open data questions from the roadmap, and ask the owner only where a rule is genuinely undefined.
   Do not guess league rules or the 2027 lottery.
6. Implement with the existing engine (`season_state`, `league_state`, Trade Lab, `roster_checks`, `config/*.json`), keep it
   phone-first and visually consistent with the cards (Inter / Roboto Mono, quiet chips: grey ok, amber review, red blocked),
   put numbers in config not code, and regenerate generated files (`build_league_state.py embed`, `what_if.py embed`,
   `./handoff.sh`) instead of hand-editing them.
7. Tests: unit tests for every rule (pass, block, boundary), a rendered-page test for the UI, a test that nothing official
   changes, then the full suite and `./validate.sh`.
8. Open a PR against `main`, report what was tested with real data vs fixtures, and do not merge.
