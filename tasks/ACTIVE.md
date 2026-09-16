# Task — V1 Post-Bootstrap Acceptance Audit

## Objective

Verify that the deployed V1 public league board and its automation
foundation are trustworthy enough to freeze before any V2
generated-board or transaction work begins. Do not add features.

## Why

The initial bootstrap created the public site, canonical roster
baseline, Yahoo adapter, cap model, validation, CI, and update
automation. Before expanding scope, prove that these pieces work and
that source-of-truth boundaries were respected.

## Inputs

Read: `CLAUDE.md`, `ai_exchange/CURRENT_STATE.json`,
`ai_exchange/IMPLEMENTATION_REPORT.md`,
`ai_exchange/ARTIFACT_MANIFEST.json`,
`data/2026-27/franchises.json`, `data/2026-27/prekeeper_rosters.json`,
`docs/`, `config/yahoo_source.json`, `publish.sh`, `refresh-yahoo.sh`,
`validate.sh`, `status.sh`, `scripts/`, `tests/`.

## Constraints

Do not redesign the board; change league rules; change canonical
ownership without proven bootstrap corruption; promote a changed
Yahoo cap snapshot automatically; implement trades; implement
generated-board V2; add a database/backend; touch
`nba-talk-vn-lottery`.

## Acceptance Criteria

- **Deployment**: repo public, `main` pushed, Pages enabled, live URL
  returns success and contains `NBA TALK VN DYNASTY` plus the four
  section anchors, no local filesystem/font dependencies.
- **Source separation**: forensic snapshot supplied
  Team/order/pre-keeper ownership only; old forensic `178` cap not
  authoritative; projected keeper tables not imported as canonical
  ownership; Yahoo supplies current metadata/cap fields; raw
  DOCX/XLSX/forensic Markdown not public-tracked.
- **Roster baseline**: 16 franchises, canonical order,
  `franchise-01`..`franchise-16`, 232 assignments, no duplicate
  ownership, per-team counts
  `15,15,14,15,13,14,13,15,13,15,15,15,15,15,15,15`; anchor
  spot-checks (Wembanyama→franchise-01, Giannis→franchise-03,
  Towns→franchise-04, Dončić→franchise-09, Jokić→franchise-11,
  Flagg→franchise-12, SGA→franchise-13, Mitchell→franchise-16).
- **Yahoo adapter**: refresh runs, normalized samples contain
  id/name/team/positions/O-Rank/cap $, raw response gitignored, CI
  does not depend on live Yahoo network.
- **Cap model**: regression tests pass against the published snapshot
  (R1 51.0625 … R9 0.0000, benchmark 152.5625, raw floor 129.678125,
  raw ceiling 175.446875, rounded 130/175). If live Yahoo differs,
  report separately — do not auto-promote.
- **Publish automation**: `./publish.sh` sanitizes, validates before
  replacement, fails without corrupting `index.html`, commits/pushes
  only valid state.
- **Repo hygiene**: no tracked proprietary fonts, raw Yahoo snapshots,
  raw DOCX/XLSX/forensic Markdown, secrets/tokens, `/mnt/data`,
  `file://`, or machine-specific absolute paths in runtime files.
- **CI**: latest validation passes (site validation, roster-baseline,
  cap, Yahoo normalization fixture tests).

## Validation

```bash
./validate.sh
python3 -m unittest discover -s tests
./status.sh
git status
git log --oneline -5
git remote -v
```

Also inspect GitHub Pages / CI with `gh` if available.

## Delivery

Do not deploy feature changes. Fix only proven bootstrap defects
required for acceptance. Update `ai_exchange/CURRENT_STATE.json`,
`ai_exchange/IMPLEMENTATION_REPORT.md`,
`ai_exchange/ARTIFACT_MANIFEST.json`, `ai_exchange/REVIEW_PACKET.md`.
Open/update a PR from the task branch if appropriate.

## Decision Required

Final verdict: `V1_ACCEPTED` / `V1_ACCEPTED_WITH_MINOR_ISSUES` /
`BLOCKED`.
