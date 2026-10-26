# Yahoo fixtures

## Standings fixtures

- `yahoo_standings_2026-10-26_real_sanitized.html`: the real `#standingstable` and update time of league 85092, saved on 2026-10-26 with scripts, ads and unrelated page material removed by the owner. No other edits.
- `NBA_Talk_Dynasty_Standings_2026-10-26.json`: the normalized capture of the same page; the tests assert the parser's output equals it field by field.
- Malformed variants are built inside the tests by mutating the real HTML (labelled MUTATION), never stored as fixtures.
