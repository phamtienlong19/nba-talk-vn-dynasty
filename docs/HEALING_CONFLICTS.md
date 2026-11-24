# Healing generated-block conflicts

`index.html` carries one-line generated JSON blocks (`league-data`, `whatif-data`, `live ...`) derived from `data/` and `config/` by
`scripts/build_league_state.py`, `what_if.py` and `live_page.py`. Every roster, standings and player-metadata refresh regenerates them, and the roster
refresh merges every few hours, so any other open PR that regenerates them conflicts again within hours. Until 2026-11-18 each of these was resolved
by hand (take main's `index.html`, re-run the embeds, validate, push).

**Heal Generated Conflicts** (`.github/workflows/heal-generated-conflicts.yml`, `scripts/heal_open_prs.sh`) does exactly that, automatically:

- Runs after every push to `main`, hourly as a backstop (GitHub computes mergeability lazily), and on demand.
- For each open **same-repo** PR that GitHub reports as CONFLICTING: merge `main` into its branch. If the only conflicts are the generated one-line data
  blocks of `index.html` (`scripts/resolve_generated_conflicts.py` checks every hunk), take main's line, re-run the four embeds, run `./validate.sh`,
  push the merge to the **PR branch**, start `validate.yml` on it (pushes made with the built-in token do not start PR checks), and comment on the PR.
- **Anything else is left for a human**: a real conflict in any other file or in hand-edited markup, a failed embed or validation, or a refused push
  (for example when main changed a workflow file, which the built-in token may not push).
- It never pushes to `main` and never merges. The data in the blocks is re-derived, never hand-written, so nothing is decided by this.

Limit: it fixes the conflict, not the cause. Two PRs that both regenerate the blocks still collide each time the other merges; the workflow heals the
second one right after the first merges.

## After plan A piece 3c (2026-11)
`index.html` in git no longer carries the three generated data lines (`league-data`, `whatif-data`, `live-data`): they are `{}` and
`scripts/build_site.py` embeds them from `data/` when the site is built and deployed (`.github/workflows/pages.yml`). Bot PRs therefore stop
touching `index.html`, and this healer only has old PR branches (still carrying full blocks) to fix: it takes main's `{}` and no longer
re-embeds. Tests read the built page through `tests/_site.py`.
