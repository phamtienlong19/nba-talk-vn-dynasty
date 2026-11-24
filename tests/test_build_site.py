import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


class TestBuildSite(unittest.TestCase):
    def test_the_build_reproduces_the_committed_page_byte_for_byte_and_never_touches_the_source(self):
        """The repository still commits the embedded blocks, so building them again must change nothing. This equivalence is what allows the
        blocks to be dropped from git later (plan A piece 3): the served page will then be exactly what this builds."""
        src = os.path.join(ROOT, "index.html")
        before = open(src, "rb").read()
        with tempfile.TemporaryDirectory() as d:
            out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_site.py"), "--out", d], capture_output=True, text=True, check=True).stdout.strip()
            self.assertEqual(open(out, "rb").read(), before)
            self.assertTrue(os.path.exists(os.path.join(d, "build.json")))
            self.assertTrue(os.path.exists(os.path.join(d, "exports", "yahoo_top300_proj_dollar_rank.xlsx")))
        self.assertEqual(open(src, "rb").read(), before)

    def test_the_build_fills_blocks_that_are_missing_from_the_source(self):
        """With empty data blocks in the source (what git will hold after piece 3c) the build still produces the full page."""
        import re
        src = open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
        want = src
        stripped = re.sub(r'(<script type="application/json" id="(?:league-data|whatif-data|live-data)">)[^\n]*?(</script>)', r"\1{}\2", src)
        self.assertNotEqual(stripped, src)
        with tempfile.TemporaryDirectory() as d:
            tmp_root = os.path.join(d, "x")
            os.makedirs(tmp_root)
            # build from a stripped copy: point the embedders at it directly
            p = os.path.join(tmp_root, "index.html")
            open(p, "w", encoding="utf-8").write(stripped)
            env = dict(os.environ, NBA_INDEX_HTML=p)
            for script, arg in (("build_league_state.py", "embed"), ("what_if.py", "embed"), ("live_page.py", "embed")):
                subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script), arg], check=True, env=env, capture_output=True)
            self.assertEqual(open(p, encoding="utf-8").read(), want)


if __name__ == "__main__":
    unittest.main()
