# Yahoo Public Draft Analysis — Source Adapter

Authoritative source for current player metadata (identity, NBA team,
position eligibility, O-Rank, cap dollars). **Not** a source of this
league's actual roster ownership — see `docs/DATA_MODEL.md` and Section 36
of the bootstrap spec for that distinction.

## Endpoint

```
https://pub-api-ro.fantasysports.yahoo.com/fantasy/v2/league/478.l.public;out=settings/players;position=ALL;start=0;count=300;sort=projected_cost;search=;out=auction_values,ranks;ranks=o-rank;out=expert_ranks;expert_ranks.rank_type=projected_season_remaining/draft_analysis;cut_types=diamond;slices=last7days?format=json_f
```

League key `478.l.public` and the URL live in `config/yahoo_source.json`,
not hardcoded into scripts — only the adapter should need updating if
Yahoo changes the endpoint or league key.

No OAuth/credentials required; this is a public read-only endpoint.

## Fetch verified: 2026-09-16

`./refresh-yahoo.sh` (via `scripts/fetch_yahoo_draft_analysis.py`) was run
against the live endpoint on 2026-09-16. Result: HTTP 200, 1,220,491 bytes,
300 players returned, all with unique O-Rank values 1–300.

Note: the resolved league (`league_key: "478.l.101"`, name `"101 League"`)
is Yahoo's generic public league behind the `478.l.public` alias — it is
**not** the actual NBA Talk VN Dynasty private league. This is expected
and correct: the public endpoint's only job here is public player/rank/cap
metadata, never this league's private ownership data.

## Verified response shape (`format=json_f`, flattened)

```
fantasy_content.league.league_key      "478.l.101"
fantasy_content.league.players         list[ { "player": {...} } ], 300 entries
```

Per-player fields actually present in the response and used by the
normalizer (`scripts/normalize_yahoo_players.py`):

| Normalized field     | Yahoo response path                                                              | Example (Victor Wembanyama) |
|-----------------------|-----------------------------------------------------------------------------------|------------------------------|
| `playerId`            | `player.player_id`                                                               | `"10094"` |
| `playerKey`           | `player.player_key`                                                              | `"478.p.10094"` |
| `name`                | `player.name.full`                                                               | `"Victor Wembanyama"` |
| `nbaTeam`             | `player.editorial_team_abbr`                                                     | `"SAS"` |
| `eligiblePositions`   | `[p.position for p in player.eligible_positions]`                                | `["C", "Util"]` |
| `oRank`               | `player.player_ranks[].player_rank.rank_value` where `rank_type == "OR"`, as int | `1` |
| `capDollars`          | `player.projected_auction_value`, as float                                      | `61.0` |
| `auctionValue`        | `player.average_auction_cost`, as float (reference only, not used by cap model) | `70.0` |
| `expertRanks`         | `player.player_ranks` (raw, preserved as-is)                                    | — |

## Which field is the authoritative cap-dollar input — verified, not guessed

Yahoo returns **two** plausible cap-dollar fields per player:

- `projected_auction_value` — Yahoo's forward-looking price for the
  *next* draft.
- `average_auction_cost` (same value as `draft_analysis.average_cost`) —
  the observed average cost across actual completed drafts in the field
  (this public league's `draft_status` is `"postdraft"`).

These diverge meaningfully (e.g. for rank-1 Wembanyama: `61` vs. `70`).

**Decision: `projected_auction_value` is the authoritative cap-dollar
field.** Verified by recomputing the league's cap model
(`scripts/cap_model.py`) over the full live 2026-09-16 snapshot using each
candidate field:

| Field | R1 | R2 | R3 | ... | Benchmark | Floor/Ceiling |
|---|---|---|---|---|---|---|
| `average_auction_cost` | 58.25 | 29.06 | 13.13 | ... | 117.375 | 100 / 135 |
| **`projected_auction_value`** | **51.0625** | **32.25** | **24.4375** | ... | **152.5625** | **130 / 175** |

`projected_auction_value` reproduces the currently published R1–R9 band
averages, benchmark (152.5625), and cap range (130/175) **exactly** — see
`docs/CAP_MODEL.md`. This is conclusive, not a coincidence: it is the
field the league's cap model was actually built against.

## Normalization decisions

- Players missing an `"OR"`-type rank, or with an unparseable
  `projected_auction_value`, are **skipped** (not coerced to 0/null) and
  counted in a `skipped` list; `normalize_yahoo_players.py` prints a
  warning to stderr when this happens. In the verified 2026-09-16 fetch,
  0 of 300 players were skipped.
- `expertRanks` is preserved as the raw `player_ranks` array rather than
  flattened further, since only the `"OR"` rank is currently load-bearing
  for the cap model — future rule versions may need other rank types
  without a normalizer change.
- Unicode names (e.g. "Nikola Jokić", "Luka Dončić") pass through
  untouched; verified both in the live fetch and in
  `tests/test_yahoo_normalization.py`.

## Failure behavior

`scripts/fetch_yahoo_draft_analysis.py` fails loudly (non-zero exit,
message on stderr) on: network/HTTP errors, non-JSON responses, or a
response missing `fantasy_content.league.players`. It does not fall back
to HTML scraping or guess at a different shape.

## Raw snapshot storage

Raw fetched snapshots are written to `local_data/yahoo/` (gitignored) as
`draft_analysis_<UTC timestamp>.json`. They are never committed. The
derived normalized snapshot (`local_data/yahoo/players_normalized.json`)
is also local-only in every run of `./refresh-yahoo.sh` itself (Section
14's small derived cap snapshot is committed, but only via the workflow
below, never directly by the script).

## Networked CI refresh + committed candidate snapshot

The Claude issue-agent sandbox cannot reach Yahoo's endpoint (no
interactive network approval in a non-interactive run) or the GitHub
Actions artifact API. `.github/workflows/yahoo-refresh.yml`
(`workflow_dispatch`) is the permanent bridge: it runs on a normal
GitHub-hosted runner, executes this same `./refresh-yahoo.sh` unchanged,
then:

- **MATCH** (live result equals the published floor/ceiling
  `./refresh-yahoo.sh` compares against — currently 130/175): no repo
  changes, just a job summary.
- **CHANGED**: commits the verified snapshot to branch
  `automation/yahoo-refresh` (`data/yahoo/players_normalized.json`,
  `cap_snapshot.json`, `provenance.json` — see `../data/README.md`) and
  opens/updates one PR against `main` (`scripts/prepare_yahoo_data_pr.py`
  builds the candidate files and PR text from the refresh's own output;
  it does not re-derive anything).

**Merging that PR is the human promotion approval** — Git itself, not an
Actions artifact, is the handoff to the offline issue-agent, which reads
`data/yahoo/` straight off `main` with no network access. The workflow
never merges its own PR and never touches `index.html` or keeper/roster
state; the intended next step after a human merges the data PR is a
normal GitHub Issue ("Propagate canonical Yahoo refresh through
cap/keeper/site state") for that propagation work.

## Why CI does not use live network

`tests/test_yahoo_normalization.py` uses a synthetic fixture shaped
exactly like the verified real response (see table above), so the
normalizer's field-mapping logic is tested deterministically without
depending on Yahoo's availability, rate limits, or day-to-day data churn.
Live refresh is an explicit operator action (`./refresh-yahoo.sh`), never
a CI dependency.

## Running a refresh

```bash
./refresh-yahoo.sh
```

Fetches the live endpoint, normalizes it, recomputes R1–R9/benchmark/
floor/ceiling, and prints a `MATCH` / `CHANGED` comparison against the
currently published board snapshot (130–175). It never modifies
`index.html` automatically.
