import io
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import materialize_issue_context as mic


class IssueContextTests(unittest.TestCase):
    def test_extract_attachment_urls(self):
        text = """
        [doc](https://github.com/user-attachments/files/123/test.docx)
        https://github.com/user-attachments/assets/abc/screenshot.png
        https://example.com/not-allowed.pdf
        """
        urls = mic.extract_attachment_urls(text)
        self.assertEqual(len(urls), 2)
        self.assertTrue(all(u.startswith("https://github.com/user-attachments/") for u in urls))

    def test_trusted_associations(self):
        for assoc in ("OWNER", "MEMBER", "COLLABORATOR"):
            self.assertTrue(mic.association_is_trusted(assoc))
        for assoc in ("CONTRIBUTOR", "NONE", "FIRST_TIME_CONTRIBUTOR", None):
            self.assertFalse(mic.association_is_trusted(assoc))

    def test_zip_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            z = td / "bad.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("../escape.txt", "bad")
            with self.assertRaises(ValueError):
                mic.safe_extract_zip(z, td / "out")

    def test_zip_symlink_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            z = td / "link.zip"
            info = zipfile.ZipInfo("link.txt")
            info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr(info, "target")
            report = mic.safe_extract_zip(z, td / "out")
            self.assertEqual(report["extracted"], [])
            self.assertEqual(report["skipped"][0]["reason"], "symlink")

    def test_nested_zip_not_extracted(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            z = td / "outer.zip"
            with zipfile.ZipFile(z, "w") as zf:
                zf.writestr("notes.txt", "hello")
                zf.writestr("inner.zip", b"PK")
            report = mic.safe_extract_zip(z, td / "out")
            self.assertIn("notes.txt", report["extracted"])
            self.assertTrue(any(x["reason"] == "nested archive not extracted" for x in report["skipped"]))

    def test_docx_text_extraction(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            docx = td / "sample.docx"
            xml = """<?xml version="1.0" encoding="UTF-8"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
              <w:body>
                <w:p><w:r><w:t>Hello</w:t></w:r></w:p>
                <w:p><w:r><w:t>World</w:t></w:r></w:p>
              </w:body>
            </w:document>"""
            with zipfile.ZipFile(docx, "w") as zf:
                zf.writestr("word/document.xml", xml)
            out = td / "sample.txt"
            mic.extract_docx(docx, out)
            self.assertEqual(out.read_text().strip(), "Hello\nWorld")

    def test_untrusted_issue_body_is_not_collected(self):
        event = {
            "repository": {"full_name": "owner/repo"},
            "issue": {
                "number": 1,
                "author_association": "NONE",
                "user": {"login": "stranger"},
                "body": "https://github.com/user-attachments/files/1/evil.zip",
                "html_url": "https://github.com/owner/repo/issues/1",
            },
        }
        sources, _ = mic.collect_trusted_sources(event, token=None)
        self.assertEqual(sources, [])


if __name__ == "__main__":
    unittest.main()
