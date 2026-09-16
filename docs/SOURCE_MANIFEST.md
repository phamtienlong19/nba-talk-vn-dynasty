# Source Manifest

Provenance record for the source artifacts this project was bootstrapped
from. Raw files themselves are **not** committed to this public repository
(see `.gitignore` / `local_sources/`); this manifest is the public record
that they exist and what role each one plays.

## 1. Public board HTML (canonical Phase A source)

- **Original filename requested:** `nba_talk_vn_dynasty_announcement_compact_hybrid35_fonts(2).html`
- **Actual filename found:** `nba_talk_vn_dynasty_announcement_compact_hybrid35_fonts.html` (no `(2)` suffix existed on this machine; it was the only file matching this name, dated 2026-09-16, the most recent Dynasty board HTML in Downloads)
- **SHA-256:** `3d2ecac8f0657c0d43d15d80a85a6f435c30b9840e07911f7e960b374801d41f`
- **Size:** 91,638 bytes
- **Role:** Canonical current public board. Sanitized (local `@font-face`/woff refs stripped) and published as `index.html`.
- **Source location:** `~/Downloads/` (copied to `local_sources/`, gitignored)
- **Status:** local-only source; sanitized derivative (`index.html`) is public.

## 2. League rules reference (DOCX)

- **Original filename requested:** `Dynasty-Rule-Oct-2025(3).docx`
- **Actual filename found:** `Dynasty-Rule-Oct-2025.docx` (no `(3)` suffix existed; only one file with this name, dated 2025-09-10)
- **SHA-256:** `500d70d34bfbcc13438c98ac7decd395ed31c33600dca3e0abccb90569b88384`
- **Size:** 39,860 bytes
- **Role:** Comprehensive league-rules reference (Vietnamese). Mix of active rules, historical examples, and named historical tank-violator enforcement notes. Used to author `docs/LEAGUE_RULES_MODEL.md`, `docs/RULE_AUTOMATION_MATRIX.md`, and portions of `docs/OPEN_RULE_QUESTIONS.md`.
- **Source location:** `~/Downloads/` (copied to `local_sources/`, gitignored)
- **Status:** local-only. Contains named enforcement history not reproduced in the public repo.

## 3. Legacy cap workbook (XLSX)

- **Original filename requested:** `Dynasty Cap Space 2026.xlsx`
- **Actual filename found:** exact match, dated 2026-09-16
- **SHA-256:** `4c44456c3eda4b527982370bff2108d4d30201906e28e994d5d0fd9fa0e03de2`
- **Size:** 71,088 bytes
- **Role:** Legacy operating model (player table, cap-band formulas, manual rosters, draft/trade log). Contains sheets `2025-2026` and `2024-2025`. Not edited; used only to document the replacement architecture in `docs/LEGACY_XLSX_REPLACEMENT.md`.
- **Source location:** `~/Downloads/` (copied to `local_sources/`, gitignored)
- **Status:** local-only. Contains operational league data (rosters, salaries) not otherwise public.

## 4. Forensic pre-keeper roster snapshot (Markdown)

- **Original filename requested:** `nba_talk_vn_dynasty_forensic_state_2026-08-20(6).md`
- **Actual filename found:** **NOT FOUND.** An exhaustive search of `~/Downloads` (including nested `Downloads/Downloads` and archive subfolders) found no file matching `*forensic_state_2026-08-20*` in any form.
- **Role (intended):** Canonical source for the 16-team order, display names, and the 232-assignment pre-keeper roster ownership baseline (Section 2 `teams.md` block).
- **Status:** **BLOCKED.** See `docs/OPEN_RULE_QUESTIONS.md`. `data/2026-27/franchises.json` was still built directly from the canonical team order given explicitly in this project's bootstrap spec (no forensic file needed for that part). `data/2026-27/prekeeper_rosters.json` (the 232 player-to-team assignments) could **not** be built — fabricating player names would violate the source-fidelity requirement. `scripts/import_forensic_rosters.py` is complete and ready to run once the real file is supplied to `local_sources/`.
