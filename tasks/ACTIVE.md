# Task — Double Check Team Name and Rosters' Cap Numbers (Issue #2)

## Objective

Verify and correct clear, confirmable errors in the published board
(`index.html`): player cap-dollar values and rookie-status flags in the
draft pool. Surface anything ambiguous for human decision instead of
guessing.

## Why

GitHub Issue #2: John Collins is shown with a nonzero cap but likely
has none; Nique Clifford, Tre Johnson, and Dylan Cardwell are flagged
`rookie-row`/`R` in the draft pool but are 2025 draft class (second
season by 2026-27), no longer rookies.

## Inputs

`index.html`, `local_data/yahoo/players_normalized.json` (live Yahoo
refresh via `./refresh-yahoo.sh`), `docs/YAHOO_DATA_SOURCE.md`,
`data/2026-27/franchises.json`.

## Constraints

Do not bulk-repromote every player's cap number from a fresh Yahoo
pull (normal day-to-day market drift, not an error) — only fix the
specifically-confirmed defect. Do not resolve team
identity-tag/name discrepancies between `data/2026-27/franchises.json`
and `index.html` autonomously; report them.

## Acceptance Criteria

- John Collins' cap corrected to match live Yahoo
  `projected_auction_value` (0), including team cap-total/ROOM in both
  the team card and the CAP page summary card.
- Nique Clifford, Tre Johnson, Dylan Cardwell no longer flagged as
  rookies in the draft pool (verified 2025 draft class via web
  search — second-year players for the 2026-27 season).
- `./validate.sh` and `python3 -m unittest discover -s tests` pass.
- Findings not auto-fixed (minor cap drift on other players; team
  identity-tag mismatches for franchise-01, 07, 09) are written up for
  human review, not silently changed.

## Validation

```bash
./validate.sh
python3 -m unittest discover -s tests
```

## Delivery

Branch off `main`, PR with `Closes #2`, not merged.

## Decision Required

Which source wins for franchise-01 identity ("Hai" vs board's "Bsy"),
franchise-07's missing team name in canonical data ("Maxfixe" vs
board's "Maxfixe | Poop for Coop"), and franchise-09 identity
("M. Jordat" vs board's "Đạt").
