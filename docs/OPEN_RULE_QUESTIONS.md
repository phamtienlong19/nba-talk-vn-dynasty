# Open Rule Questions / Known Gaps

Recorded per the source-precedence policy: unresolved conflicts or gaps are
written down here rather than silently guessed. This does not block the
Phase A public-board deployment.

## 1. RESOLVED: forensic pre-keeper roster snapshot file was supplied

The file was originally not found anywhere on this machine (searched
`~/Downloads` exhaustively, including nested/archived subfolders). The
user subsequently placed it directly into `local_sources/` as
`nba_talk_vn_dynasty_forensic_state_2026-08-20.md` (unsuffixed — see
item 2 below on filename suffixes generally).

- `python3 scripts/import_forensic_rosters.py "local_sources/nba_talk_vn_dynasty_forensic_state_2026-08-20.md"`
  ran successfully: 232 pre-keeper assignments across 16 franchises,
  parsed from the canonical Section 2 `teams.md` block only.
- `data/2026-27/prekeeper_rosters.json` is now committed with the full
  232-assignment baseline.
- All roster-baseline regression tests pass, including the 16-franchise
  canonical order, exact per-team counts
  (`15,15,14,15,13,14,13,15,13,15,15,15,15,15,15,15`), no duplicate
  ownership, and all 8 anchor ownership facts (Wembanyama →
  franchise-01, Giannis → franchise-03, etc.).

## 2. Source filenames lacked the exact requested parenthetical suffixes

The bootstrap spec named `...(2).html`, `...(3).docx`, and
`...(6).md` exactly. On this machine, only unsuffixed versions of the
HTML and DOCX existed (each the sole file with that base name, most
recent by timestamp), and the XLSX matched exactly. Per the "inspect
timestamps and content" instruction, the unsuffixed files were treated as
current and used. See `docs/SOURCE_MANIFEST.md` for exact hashes.

## 3. Lottery ticket allocation: DOCX vs. this prompt's current numbers

`Dynasty-Rule-Oct-2025.docx` describes an evolving lottery model (a
2024-25-era 8-ball/12-team allocation `21-21-19-19-16-12-8-3`, and a
transitional note about adding tickets for ranks 8-7-6-5 with a "current
year" allocation `20-19-18-18-15-12-9-5-1-1-1-1`). This project's
bootstrap spec (Section 19) gives a different, more specific current
allocation: 12 teams, ranks 16→5, tickets
`16,16,15,15,14,13,12,11,2,2,2,2` (total 120).

**Resolution applied:** per source precedence (direct current prompt
instructions outrank the DOCX), `16,16,15,15,14,13,12,11,2,2,2,2` is
treated as the current 2026-27 authoritative allocation in
`docs/LEAGUE_RULES_MODEL.md`. The DOCX numbers are documented there only
as historical/evolutionary context. Lottery execution itself is out of
scope for this project (owned by `nba-talk-vn-lottery`).

## 4. Historical tank-violator names in the DOCX

The DOCX contains a dated (Jan 21, 2025) list of named tank-violator
findings for the 2024-2025 season. Per Section 28 of the bootstrap spec,
these are **not** reproduced in this public repository or its docs —
they remain local-only in `local_sources/Dynasty-Rule-Oct-2025.docx`.
`docs/RULE_AUTOMATION_MATRIX.md` and `docs/LEAGUE_RULES_MODEL.md`
describe the penalty *mechanism* generically, without naming teams/owners
or reproducing the 2024-25 enforcement log.

## 5. Live Yahoo recalculation vs. published board snapshot

Live fetch on 2026-09-16 against `478.l.public` reproduced the published
band averages and 130/175 cap range **exactly** using
`projected_auction_value` as the cap-dollar field (see
`docs/YAHOO_DATA_SOURCE.md`). No open question here today, but noting it
per Section 15's reporting requirement: `./refresh-yahoo.sh` will report
`MATCH` until Yahoo's live projections drift from the currently published
snapshot, at which point a commissioner decision is needed before
re-publishing a new cap range.
