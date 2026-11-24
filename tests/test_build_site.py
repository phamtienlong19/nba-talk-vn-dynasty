import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


class TestBuildSite(unittest.TestCase):
    def test_git_holds_empty_data_blocks_and_the_build_fills_them(self):
        """The generated data lines are not committed (they are what made every two data PRs conflict in index.html); the build embeds them."""
        import json
        import re
        src_path = os.path.join(ROOT, "index.html")
        with open(src_path, "rb") as f:
            before = f.read()
        src = before.decode("utf-8")
        for block in ("league-data", "whatif-data", "live-data"):
            m = re.search(r'<script type="application/json" id="%s">([^\n]*?)</script>' % block, src)
            self.assertIsNotNone(m, block)
            self.assertEqual(m.group(1), "{}", block + " must be empty in git; it is embedded by scripts/build_site.py")
        self.assertLess(len(src), 800000)                                      # a committed data line alone is ~190 KB
        with tempfile.TemporaryDirectory() as d:
            out = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_site.py"), "--out", d], capture_output=True, text=True, check=True).stdout.strip()
            with open(out, encoding="utf-8") as f:
                built = f.read()
            for block, key in (("league-data", "season"), ("whatif-data", "order"), ("live-data", "liveUrl")):
                m = re.search(r'<script type="application/json" id="%s">(.*?)</script>' % block, built, re.S)
                self.assertIn(key, json.loads(m.group(1)), block)
            self.assertTrue(os.path.exists(os.path.join(d, "build.json")))
            self.assertTrue(os.path.exists(os.path.join(d, "exports", "yahoo_top300_proj_dollar_rank.xlsx")))
        with open(src_path, "rb") as f:
            self.assertEqual(f.read(), before)                                 # the build never touches the source

    def test_the_deploy_workflow_is_a_noop_until_pages_is_switched_and_cannot_run_from_a_pr(self):
        wf = open(os.path.join(ROOT, ".github", "workflows", "pages.yml"), encoding="utf-8").read()
        self.assertIn("build_type", wf)
        self.assertEqual(wf.count("if: steps.mode.outputs.build_type == 'workflow'"), 5)   # every build step after the check is guarded
        self.assertIn("if: needs.build.outputs.build_type == 'workflow'", wf)              # and the deploy job only runs when Pages is set to Actions
        self.assertIn("python3 scripts/build_site.py", wf)
        self.assertNotIn("pull_request", wf)                                                # a PR never deploys
        self.assertIn("schedule:", wf)                                                      # bot merges do not start the push trigger
        roster = open(os.path.join(ROOT, ".github", "workflows", "update-yahoo-rosters.yml"), encoding="utf-8").read()
        self.assertIn("gh workflow run pages.yml", roster)


if __name__ == "__main__":
    unittest.main()
