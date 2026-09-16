#!/usr/bin/env python3
"""Validate index.html and repo hygiene before publishing.

Standard library only. Exits non-zero with messages on stderr on any
failure.
"""
from __future__ import annotations

import os
import re
import sys

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")

REQUIRED_ANCHORS = ["draft-order", "rosters-a", "draft-pool", "cap"]
REQUIRED_NAV_LABELS = ["DRAFT", "KEEPERS", "FA 60", "CAP"]
FORBIDDEN_SUBSTRINGS = ["/mnt/data", "file://", "localhost", "assets/fonts"]
FORBIDDEN_EXTENSIONS = (".woff", ".woff2")


def fail(msg: str, errors: list):
    errors.append(msg)


def validate_index_html(path: str, errors: list):
    if not os.path.exists(path):
        fail(f"{path} does not exist", errors)
        return

    with open(path, "rb") as f:
        raw = f.read()

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        fail(f"{path} is not valid UTF-8: {e}", errors)
        return

    lowered = text.lower()

    if "<!doctype html" not in lowered:
        fail(f"{path} missing <!doctype html>", errors)

    if 'name="viewport"' not in lowered:
        fail(f"{path} missing viewport meta tag", errors)

    for anchor in REQUIRED_ANCHORS:
        if f'id="{anchor}"' not in text:
            fail(f"{path} missing expected anchor id=\"{anchor}\"", errors)

    for label in REQUIRED_NAV_LABELS:
        if label not in text:
            fail(f"{path} missing expected nav label \"{label}\"", errors)

    for bad in FORBIDDEN_SUBSTRINGS:
        if bad in text:
            fail(f"{path} contains forbidden reference: \"{bad}\"", errors)

    for ext in FORBIDDEN_EXTENSIONS:
        if ext in lowered:
            fail(f"{path} contains forbidden font runtime reference: \"{ext}\"", errors)


def validate_repo_files(errors: list):
    for required in ["README.md", "publish.sh"]:
        if not os.path.exists(os.path.join(REPO_ROOT, required)):
            fail(f"missing required file: {required}", errors)


def validate_no_font_binaries(errors: list):
    for dirpath, _dirnames, filenames in os.walk(REPO_ROOT):
        if "/.git" in dirpath or "/local_sources" in dirpath or "/local_data" in dirpath:
            continue
        for name in filenames:
            if name.lower().endswith((".woff", ".woff2")):
                fail(
                    f"proprietary font binary tracked in repo: "
                    f"{os.path.relpath(os.path.join(dirpath, name), REPO_ROOT)}",
                    errors,
                )


def main():
    errors = []
    validate_index_html(os.path.join(REPO_ROOT, "index.html"), errors)
    validate_repo_files(errors)
    validate_no_font_binaries(errors)

    if errors:
        print("VALIDATION FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    print("VALIDATION OK")


if __name__ == "__main__":
    main()
