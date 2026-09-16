# Deployment Freshness

HTTP 200 on the public URL only proves the site is *reachable*, not that
GitHub Pages is serving the *latest* pushed revision (Pages caching/build
lag can leave a stale page returning 200 for a while).

## Marker

A small public file, `build.json` (served alongside `index.html`), records
the commit its content was generated against:

```json
{ "commit": "<sha>", "generatedAt": "<iso timestamp>" }
```

## Why compare local-vs-live instead of "live vs. current HEAD"

`build.json` cannot record its own commit SHA (unknown until after it's
committed), so it always records the commit *before* the small commit that
carries it. Rather than chase that one-commit lag, freshness is verified by
comparing the **live** `build.json` against the **local, already-committed**
`build.json` byte-for-byte on the `commit` field
(`scripts/deployment_freshness.py`). If they match, Pages is serving at
least that push — no future-commit prediction required.

## Who writes the marker

- `./publish.sh` — writes/commits `build.json` right after the content
  commit, using that commit's real SHA (now known).
- `./sync-after-merge.sh` — after pulling a merged PR, refreshes
  `build.json` to match the merge commit if a PR touched `index.html`
  directly (not via `publish.sh`) and left the marker stale.

## Checking freshness

```bash
python3 scripts/deployment_freshness.py check <public-url> --local-path build.json
```

Exits 0 only on an exact commit match; a bare HTTP 200 with a missing or
mismatched marker is treated as **not fresh**.
