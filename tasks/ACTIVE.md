# Active Task

No active GitHub Issue. Direct human-requested fix, not issue-backed.
Branch: fix/cap-model-salary-order-and-yahoo-export
Generated: 2026-10-05T00:00:00Z

## Task

Cap model bug (O-Rank buckets instead of projected-$ draft order) →
corrected band 131/177, Seattle keeper recheck, Yahoo-dominant FA/DRAFT 60
ranking, and the generated Yahoo Top-300 MD/XLSX commissioner export. Details
live in `ai_exchange/CURRENT_STATE.json`
(`canonicalState.capModelSalaryOrderFix`, `canonicalState.yahooTop300Export`)
and `docs/CAP_MODEL.md` — not restated here.

## Status

Implementation complete; tests + `./validate.sh` pass. PR pending review.
