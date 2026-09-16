# tasks/

`tasks/ACTIVE.md` holds the one current implementation/review objective
for this repo. When it's done, either move it to `tasks/archive/` or
just let the merged PR / Git history stand as the record — don't keep
both a long archive and a full Git history saying the same thing.

Rules for task files:

- Keep them concise: roughly 0.5–3 KB. Not a 50 KB prompt.
- Reference canonical docs/data (`docs/`, `data/`, `ai_exchange/`)
  instead of restating the project. Durable rules belong in
  `CLAUDE.md` and `docs/`, not copied into every task.
- One active task at a time. If new work comes in before the current
  one is done, decide whether it supersedes or queues — don't silently
  stack objectives in one file.

## `ACTIVE.md` template

```markdown
# Task

## Objective
What outcome must exist.

## Why
Why this matters now.

## Inputs
Canonical files/sources to read.

## Constraints
Things that must not change.

## Acceptance Criteria
Concrete checks.

## Validation
Commands/tests to run.

## Delivery
Branch / PR / deployment expectations.

## Decision Required
Human decisions still unresolved, if any.
```
