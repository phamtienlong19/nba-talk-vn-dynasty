import os
import sys
import tempfile
import unittest
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import export_yahoo_top300 as md_export  # noqa: E402
import export_yahoo_top300_xlsx as xlsx_export  # noqa: E402
from cap_model import compute_cap_model  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
FIXTURE_MD = os.path.join(os.path.dirname(__file__), "fixtures", "yahoo_top300_2026-10-04.md")
EXPORT_MD = os.path.join(REPO_ROOT, "exports", "yahoo_top300_proj_dollar_rank.md")
EXPORT_XLSX = os.path.join(REPO_ROOT, "exports", "yahoo_top300_proj_dollar_rank.xlsx")


def _fixture_rows():
    with open(FIXTURE_MD, encoding="utf-8") as f:
        return md_export.parse_markdown(f.read())


def _players_from_rows(rows):
    # Shuffle-ish order (reverse) so the exporter's own ordering is what's tested.
    return [{"name": n, "capDollars": float(d), "oRank": r} for n, d, r in reversed(rows)]


class TestMarkdownExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_rows = _fixture_rows()
        cls.players = _players_from_rows(cls.fixture_rows)

    def test_fixture_has_300_rows(self):
        self.assertEqual(len(self.fixture_rows), 300)

    def test_render_matches_the_reference_format_byte_for_byte(self):
        rows = md_export.build_rows(self.players)
        with open(FIXTURE_MD, encoding="utf-8") as f:
            self.assertEqual(md_export.render_markdown(rows), f.read())

    def test_header_and_order(self):
        text = md_export.render_markdown(md_export.build_rows(self.players))
        lines = text.splitlines()
        self.assertEqual(lines[0], "# Yahoo Top 300 — Projected $ / Rank")
        self.assertEqual(lines[2:4], ["| Player | Proj $ | Rank |", "|---|---:|---:|"])
        rows = md_export.parse_markdown(text)
        self.assertEqual(rows, sorted(rows, key=lambda r: (-r[1], r[2])))

    def test_deterministic(self):
        a = md_export.render_markdown(md_export.build_rows(self.players))
        b = md_export.render_markdown(md_export.build_rows(list(reversed(self.players))))
        self.assertEqual(a, b)

    def test_unicode_names_preserved(self):
        names = {r[0] for r in self.fixture_rows}
        for n in ("Nikola Jokić", "Luka Dončić", "Alperen Şengün", "Kristaps Porziņģis"):
            self.assertIn(n, names)

    def test_rejects_wrong_row_count_duplicates_and_rank_gaps(self):
        with self.assertRaises(md_export.ExportError):
            md_export.build_rows(self.players[:-1])
        dup = [dict(p) for p in self.players]
        dup[0]["name"] = dup[1]["name"]
        with self.assertRaises(md_export.ExportError):
            md_export.build_rows(dup)
        gap = [dict(p) for p in self.players]
        gap[0]["oRank"] = 999
        with self.assertRaises(md_export.ExportError):
            md_export.build_rows(gap)


class TestXlsxParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.xlsx = os.path.join(cls.tmp.name, "t.xlsx")
        warnings.simplefilter("ignore")
        cls.md_rows = xlsx_export.export_xlsx(FIXTURE_MD, cls.xlsx)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _sheet_rows(self):
        return xlsx_export.read_sheet_rows(self.xlsx)

    def test_row_count_and_parity_with_markdown(self):
        rows = self._sheet_rows()
        self.assertEqual(len(rows), 300)
        for (xp, xd, xr), (mp, md, mr) in zip(rows, self.md_rows):
            self.assertEqual(xp, mp)
            self.assertEqual(xd, md)
            self.assertEqual(xr, mr)

    def test_first_middle_last_rows(self):
        rows = self._sheet_rows()
        self.assertEqual(rows[0], ("Nikola Jokić", 61, 1))
        self.assertEqual(rows[149], self.md_rows[149])
        self.assertEqual(rows[-1], ("Caris LeVert", 0, 300))

    def test_unique_players_and_rank_coverage(self):
        rows = self._sheet_rows()
        self.assertEqual(len({r[0] for r in rows}), 300)
        self.assertEqual(sorted(r[2] for r in rows), list(range(1, 301)))

    def test_numbers_are_numeric_and_unicode_survives(self):
        for _, dollars, rank in self._sheet_rows():
            self.assertIsInstance(dollars, int)
            self.assertIsInstance(rank, int)
        names = {r[0] for r in self._sheet_rows()}
        self.assertIn("Alperen Şengün", names)
        self.assertIn("Kristaps Porziņģis", names)

    def test_layout_matches_commissioner_workbook(self):
        from openpyxl import load_workbook
        wb = load_workbook(self.xlsx)
        self.assertEqual(wb.sheetnames, ["Yahoo Top 300"])
        ws = wb["Yahoo Top 300"]
        self.assertEqual([str(r) for r in ws.merged_cells.ranges], ["A1:C1"])
        self.assertEqual(ws["A1"].value, "Yahoo Top 300 — Projected $ / Rank")
        self.assertIsNone(ws["A2"].value)
        self.assertEqual([ws.cell(3, c).value for c in (1, 2, 3)], ["Player", "Proj $", "Rank"])
        self.assertEqual(ws["A4"].value, "Nikola Jokić")
        self.assertEqual(ws["A303"].value, "Caris LeVert")
        self.assertEqual(ws.freeze_panes, "A4")
        self.assertEqual(len(ws.conditional_formatting), 1)
        wb.close()

    def test_regeneration_replaces_a_stale_workbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = os.path.join(tmp, "out.xlsx")
            stale_md = os.path.join(tmp, "stale.md")
            rows = list(self.md_rows)
            rows[0] = ("Stale Player", 99, 1)
            with open(stale_md, "w", encoding="utf-8") as f:
                f.write(md_export.render_markdown(rows))
            xlsx_export.export_xlsx(stale_md, stale)
            self.assertEqual(xlsx_export.read_sheet_rows(stale)[0][0], "Stale Player")
            xlsx_export.export_xlsx(FIXTURE_MD, stale)
            fresh = xlsx_export.read_sheet_rows(stale)
            self.assertEqual(fresh[0], ("Nikola Jokić", 61, 1))
            self.assertNotIn("Stale Player", [r[0] for r in fresh])

    def test_workbook_is_byte_stable_for_identical_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = os.path.join(tmp, "a.xlsx"), os.path.join(tmp, "b.xlsx")
            xlsx_export.export_xlsx(FIXTURE_MD, a)
            xlsx_export.export_xlsx(FIXTURE_MD, b)
            with open(a, "rb") as fa, open(b, "rb") as fb:
                self.assertEqual(fa.read(), fb.read())

    def test_divergence_between_md_and_xlsx_is_detected(self):
        from openpyxl import load_workbook
        wb = load_workbook(self.xlsx)
        wb["Yahoo Top 300"]["B4"] = 1
        tampered = os.path.join(self.tmp.name, "tampered.xlsx")
        wb.save(tampered)
        self.assertNotEqual(xlsx_export.read_sheet_rows(tampered), self.md_rows)


class TestCommittedExportArtifacts(unittest.TestCase):
    """The committed exports/ files must agree with each other: the XLSX is
    derived from the MD and may never silently diverge from it."""

    def test_committed_md_and_xlsx_agree_exactly(self):
        warnings.simplefilter("ignore")
        with open(EXPORT_MD, encoding="utf-8") as f:
            md_rows = md_export.parse_markdown(f.read())
        self.assertEqual(len(md_rows), 300)
        self.assertEqual(xlsx_export.read_sheet_rows(EXPORT_XLSX), md_rows)
        self.assertEqual(len({r[0] for r in md_rows}), 300)
        self.assertEqual(sorted(r[2] for r in md_rows), list(range(1, 301)))

    def test_board_links_the_stable_xlsx_and_md_paths(self):
        with open(os.path.join(REPO_ROOT, "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn('href="exports/yahoo_top300_proj_dollar_rank.xlsx"', html)
        self.assertIn('href="exports/yahoo_top300_proj_dollar_rank.md"', html)


class TestCapModelIndependence(unittest.TestCase):
    def test_cap_benchmark_is_unaffected_by_the_exported_rank_column(self):
        rows = _fixture_rows()
        players = [{"capDollars": d, "oRank": r} for _, d, r in rows]
        scrambled = [{"capDollars": d, "oRank": 1000 + i} for i, (_, d, _) in enumerate(rows)]
        # Same dollars, completely different Rank column -> same cap result.
        self.assertEqual(compute_cap_model(players)["top144Sum"],
                         compute_cap_model(scrambled)["top144Sum"])

    def test_cap_scripts_do_not_import_the_export(self):
        with open(os.path.join(REPO_ROOT, "scripts", "cap_model.py"), encoding="utf-8") as f:
            self.assertNotIn("export_yahoo_top300", f.read())


if __name__ == "__main__":
    unittest.main()
