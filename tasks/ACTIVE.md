# Active Task

No active GitHub Issue. Direct human-requested fix, not issue-backed.
Branch: fix/cap-model-salary-order-and-yahoo-export (PR #26)
Generated: 2026-10-05T00:00:00Z

## Task

PR #26 final correction pass: official cap 131–178 (formula 131–177) kept
separate in `config/cap_policy.json`; keeper overrides (Kratos: Wiggins in /
Queta out; DHA: Poeltl in / Kuminga out; Seattle: Porziņģis in / Davion out);
FA/DRAFT 60 rebuilt as a CAP-then-65/35 Yahoo/dynasty hybrid over a
cuts + Yahoo + dynasty-consensus universe. Details live in
`ai_exchange/CURRENT_STATE.json` (`canonicalState.capPolicy`,
`canonicalState.capModelSalaryOrderFix`) and `docs/CAP_MODEL.md`.

## Status

Implementation complete; tests + `./validate.sh` pass. PR #26 updated.
