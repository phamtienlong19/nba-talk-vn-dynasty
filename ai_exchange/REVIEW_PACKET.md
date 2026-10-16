# Review Packet

Generated: 2026-10-16T02:29:56Z

## Task
Active Task

## Status
READY_FOR_REVIEW

## Git
Branch: feat/season-ops
Commit: 15c3d1b
Base: main
Working tree: dirty

## GitHub
Repository: https://github.com/phamtienlong19/nba-talk-vn-dynasty
GitHub CLI: available
PR: none
CI: no runs found for this branch

## Deployment
Public URL: https://phamtienlong19.github.io/nba-talk-vn-dynasty/
HTTP: OK
Fingerprint: FRESH

## Changes
```

```

## Validation
- site validation: PASS
- tests: PASS (keeper freeze is LOCKED -- baseline not regenerated (immutable).)
- Yahoo refresh: last local snapshot: draft_analysis_2026-10-05T032730Z.json
- live HTTP: OK

## Canonical State
Roster baseline: 16 franchises, 232 assignments
Cap snapshot: 131-178
Yahoo source timestamp: 2026-10-05T03:27:30Z

## Files Changed
(none)

## Issues
- PROP-2026-002 (Bsy ↔ Thịnh) was described with the direction reversed; it is staged in the only ownership-consistent direction (Bsy sends Wembanyama + Tyson) and flagged `DISCREPANCY_FLAGGED`. Confirm with the teams.
- PROP-2026-002 alone puts Bsy at 179 (> 178): `CAP_TRADE_LEAVES_BAND`, under-$5 ladder. Together with PROP-2026-001 Bsy ends at 176 (legal).
- TXN-2026-001 effective date is the report date (2026-10-16); the exact Yahoo processing time was not supplied.
- The 16 Yahoo team keys and the league key are unknown (no authenticated data in the repo); `rosters/team_map.json` has nulls.

## Decisions Required

- Confirm PROP-2026-002 direction before it moves past PROPOSED.
- Commissioner: does IL / IL+ salary count toward the cap? (currently counted; flagged in OPEN_RULE_QUESTIONS).
- Commissioner: provide the league id; decide whether to apply for Yahoo Fantasy API access (docs/YAHOO_API_FEASIBILITY.md).

## Suggested Next Step
Open/update the PR from `feat/season-ops` if not already done, then request human/ChatGPT review of this packet.
