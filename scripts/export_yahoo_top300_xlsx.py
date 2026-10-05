#!/usr/bin/env python3
"""Generate the commissioner XLSX from the generated Yahoo Top 300 Markdown.

The workbook is derived ONLY from exports/yahoo_top300_proj_dollar_rank.md
(see scripts/export_yahoo_top300.py) so there is a single commissioner-
facing tabular interpretation. Re-verifies MD/XLSX parity after writing
and fails loudly on any divergence. Requires openpyxl.

Usage:
    python3 scripts/export_yahoo_top300_xlsx.py [in.md] [out.xlsx]
"""
from __future__ import annotations

import datetime
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_yahoo_top300 import (  # noqa: E402
    DEFAULT_OUT as DEFAULT_MD, EXPECTED_ROWS, parse_markdown,
)

DEFAULT_XLSX = os.path.join(os.path.dirname(DEFAULT_MD), "yahoo_top300_proj_dollar_rank.xlsx")
SHEET = "Yahoo Top 300"
TITLE = "Yahoo Top 300 — Projected $ / Rank"
HEADERS = ("Player", "Proj $", "Rank")
FIRST_DATA_ROW = 4

FIXED_DATETIME = datetime.datetime(1980, 1, 1)
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)

MODIFIED_RE = re.compile(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)")

PURPLE_TITLE = "5F01D1"
DARK_HEADER = "111827"
BAR_PURPLE = "7E22CE"
STRIPE = "F5F3FF"


def read_sheet_rows(path: str) -> list:
    from openpyxl import load_workbook
    wb = load_workbook(path)
    try:
        ws = wb[SHEET]
        out = []
        for r in range(FIRST_DATA_ROW, ws.max_row + 1):
            out.append((ws.cell(r, 1).value, ws.cell(r, 2).value, ws.cell(r, 3).value))
        return out
    finally:
        wb.close()


def build_workbook(rows, out_path: str) -> None:
    from openpyxl import Workbook
    from openpyxl.formatting.rule import DataBarRule
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET

    ws.merge_cells("A1:C1")
    ws["A1"] = TITLE
    ws["A1"].font = Font(bold=True, size=16, color="FFFFFF")
    ws["A1"].fill = PatternFill("solid", fgColor=PURPLE_TITLE)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    for col, head in enumerate(HEADERS, start=1):
        c = ws.cell(3, col, head)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=DARK_HEADER)
        c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[3].height = 22

    stripe = PatternFill("solid", fgColor=STRIPE)
    for i, (name, dollars, rank) in enumerate(rows):
        r = FIRST_DATA_ROW + i
        ws.cell(r, 1, name)
        ws.cell(r, 2, dollars).number_format = "0"
        ws.cell(r, 3, rank).number_format = "0"
        for col in (2, 3):
            ws.cell(r, col).alignment = Alignment(horizontal="center")
        if i % 2 == 1:
            for col in (1, 2, 3):
                ws.cell(r, col).fill = stripe

    last = FIRST_DATA_ROW + len(rows) - 1
    ws.conditional_formatting.add(
        f"B{FIRST_DATA_ROW}:B{last}",
        DataBarRule(start_type="min", end_type="max", color=BAR_PURPLE),
    )
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 11
    ws.column_dimensions["C"].width = 9
    ws.freeze_panes = f"A{FIRST_DATA_ROW}"
    ws.auto_filter.ref = f"A3:C{last}"

    # Fixed workbook metadata (never the current time or the environment).
    wb.properties.created = FIXED_DATETIME
    wb.properties.modified = FIXED_DATETIME
    wb.properties.creator = "nba-talk-vn-dynasty"
    wb.properties.lastModifiedBy = "nba-talk-vn-dynasty"

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    raw = out_path + ".raw.tmp"
    tmp = out_path + ".tmp"
    try:
        wb.save(raw)
        canonicalize_xlsx(raw, tmp)
        os.replace(tmp, out_path)
    finally:
        for leftover in (raw, tmp):
            if os.path.exists(leftover):
                os.remove(leftover)


def canonicalize_xlsx(src: str, dst: str) -> None:
    """Rewrite an XLSX (ZIP) so identical content gives identical bytes:
    members in a fixed order, every ZipInfo.date_time pinned to ZIP_EPOCH,
    one fixed compression method/level and fixed attributes. XML payloads are
    copied byte-for-byte."""
    with zipfile.ZipFile(src) as zin:
        # [Content_Types].xml first (as Excel writes it), rest alphabetical.
        names = sorted(zin.namelist(), key=lambda n: (n != "[Content_Types].xml", n))
        payloads = [(n, zin.read(n)) for n in names]
    # openpyxl's save() unconditionally stamps dcterms:modified with the
    # current time (openpyxl/writer/excel.py), so pinning
    # wb.properties.modified beforehand isn't enough: rewrite that one value
    # in docProps/core.xml. Every other payload is copied byte-for-byte.
    pinned = FIXED_DATETIME.strftime("%Y-%m-%dT%H:%M:%SZ").encode()
    payloads = [
        (n, MODIFIED_RE.sub(rb"\g<1>" + pinned + rb"\g<2>", d) if n == "docProps/core.xml" else d)
        for n, d in payloads
    ]
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
        for name, data in payloads:
            info = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # fixed regardless of the platform that wrote it
            info.external_attr = 0o600 << 16
            info.flag_bits = 0
            zout.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def export_xlsx(md_path: str = DEFAULT_MD, out_path: str = DEFAULT_XLSX) -> list:
    with open(md_path, encoding="utf-8") as f:
        rows = parse_markdown(f.read())
    if len(rows) != EXPECTED_ROWS:
        raise ValueError(f"{md_path}: expected {EXPECTED_ROWS} rows, parsed {len(rows)}")
    build_workbook(rows, out_path)
    actual = read_sheet_rows(out_path)
    if actual != rows:
        raise ValueError("XLSX diverges from Markdown after write -- refusing to keep it")
    return rows


def main():
    md_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MD
    out_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_XLSX
    rows = export_xlsx(md_path, out_path)
    print(f"Wrote {len(rows)} rows -> {out_path} (parity with {md_path} verified)")


if __name__ == "__main__":
    main()
