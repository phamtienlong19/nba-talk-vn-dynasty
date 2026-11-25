# Implementation Report

Run: 2026-11-25 — faster test runs (plan D)

- `scripts/run_tests.py` (stdlib): tests in parallel, at most 4 Chrome classes at once, one lone retry for a failed Chrome class (named in the summary), the page built once. Local full run about 2 min (plain discover: 428 s measured on this machine).
- `--changed` follows file references backwards from the diff; data and unreferenced files run everything. Core scripts and `index.html` still reach about 60 of 76 files; naming test files is the fast path for small fixes.
- `handoff.sh` reports the last recorded run instead of re-running the suite (`--run-tests` to run it).
- PR checks use the runner (`-j 4 --chrome 2`); nightly stays on plain discover. CLAUDE.md "Test effort" says how much to run when.
