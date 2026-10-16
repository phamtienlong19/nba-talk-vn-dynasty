#!/usr/bin/env python3
"""Rebuild draft-board-example.zip from examples/draft-board (deterministic: sorted names, fixed timestamps).
   python3 docs/guides/downloads/build_zip.py
Only the fictional example goes in. Nothing else from the repository."""
import os, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "examples", "draft-board")
OUT = os.path.join(HERE, "draft-board-example.zip")
TOP = "draft-board-example"
files = []
for root, _, names in os.walk(SRC):
    for n in names:
        if n.startswith(".") or n.endswith((".pyc", ".DS_Store")): continue
        files.append(os.path.join(root, n))
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(files):
        rel = os.path.relpath(f, SRC).replace(os.sep, "/")
        info = zipfile.ZipInfo(TOP + "/" + rel, date_time=(2026, 10, 16, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        with open(f, "rb") as fh: z.writestr(info, fh.read())
print("wrote", OUT, len(files), "files")
