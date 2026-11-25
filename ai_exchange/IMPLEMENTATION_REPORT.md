# Fix: "my team" highlight waited for a drawn frame

`main`'s macOS check failed on 2026-11-24 and again on 2026-11-25 (after roster PR #248) on
`test_my_team_is_highlighted_across_cap_draft_and_synthetic_views`; the roster data was not the cause.

- Cause: `scheduleMine` re-applied the highlight on `requestAnimationFrame`, which headless Chrome may not fire before the test reads the page.
- Fix: it uses a 16 ms timer (`index.html`).
- Test: now disables animation frames, so it fails every time if the highlight depends on one again (reproduced the CI failure locally before the fix).
- Run: `test_scenario_rendering` (58 tests, 2 skipped) and `./validate.sh`. Full suite left to CI.
