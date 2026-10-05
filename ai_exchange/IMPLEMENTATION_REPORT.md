# Implementation Report

Run: 2026-10-05 — cap model salary-order fix + Yahoo Top-300 export

- `scripts/cap_model.py`: players ordered by projected $ DESC (O-Rank ASC
  tie-break), top 144 / 16 → benchmark 154.25, band 131/177 (was O-Rank
  buckets → 153.25–153.44, 130/176). Regression fixture + A/B salary-order
  test in `tests/test_cap_model.py`.
- Propagation: Seattle re-solved at 177 (Porziņģis in, Davion Mitchell out →
  $177/177); team totals/floor-ceiling pills now refreshed by
  `refresh_team_cap_summary.py` (pills included); FA/DRAFT 60 rebuilt.
- FA/DRAFT ranking: Yahoo O-Rank dominant within a CAP tier, dynasty an
  upward-only 0.15 bonus, conservative proxy only for Yahoo-missing curated
  prospects, no forced prospect slots (Paul Reed only). Rui Hachimura
  regression added; aggressive-proxy test removed.
- Export: `scripts/export_yahoo_top300.py` → `exports/*.md` →
  `scripts/export_yahoo_top300_xlsx.py` → `exports/*.xlsx`; linked on the CAP
  page; wired into `refresh-yahoo.sh` / `promote-yahoo-refresh.sh`;
  `requirements.txt` + CI installs openpyxl.

Not changed: league rules; keeper selections other than Seattle's; the
under-floor teams (commissioner decisions).
