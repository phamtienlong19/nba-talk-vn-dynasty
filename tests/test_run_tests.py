"""scripts/run_tests.py: what --changed selects, how classes are scheduled, and what handoff.sh says about a run."""
import os
import sys
import tempfile
import threading
import time
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import run_tests as rt  # noqa: E402


def _repo(files):
    d = tempfile.TemporaryDirectory()
    for rel, text in dict({"scripts/.keep": "", "tests/.keep": ""}, **files).items():
        path = os.path.join(d.name, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return d


class TestSelect(unittest.TestCase):
    FILES = {
        "config/zz_rules.json": "{}",
        "scripts/zz_base.py": "RULES = 'zz_rules.json'\n",
        "scripts/zz_page.py": "import os, zz_base\n",
        "scripts/zz_other.py": "X = 1\n",
        "scripts/zz_lonely.py": "X = 1\n",
        "tests/_zz_help.py": "import zz_page  # noqa\n",
        "tests/test_zz_page.py": "import _zz_help\n",
        "tests/test_zz_base.py": "def f():\n    from zz_base import RULES\n",
        "tests/test_zz_other.py": "import zz_other as zz\n",
        "docs/ZZ.md": "text",
    }

    def pick(self, *changed):
        with _repo(self.FILES) as d:
            return rt.select(list(changed), d)[0]

    def test_a_change_reaches_the_tests_that_depend_on_it_through_imports_helpers_and_config_names(self):
        self.assertEqual(self.pick("config/zz_rules.json"), ["test_zz_base", "test_zz_page"])
        self.assertEqual(self.pick("scripts/zz_page.py"), ["test_zz_page"])
        self.assertEqual(self.pick("scripts/zz_other.py"), ["test_zz_other"])

    def test_a_changed_test_selects_itself(self):
        self.assertEqual(self.pick("tests/test_zz_other.py"), ["test_zz_other"])

    def test_data_and_unreferenced_files_run_everything(self):
        self.assertIsNone(self.pick("data/2026-27/rosters/index.json"))
        self.assertIsNone(self.pick("scripts/zz_lonely.py"))
        self.assertIsNone(self.pick("scripts/zz_other.py", "something.bin"))

    def test_an_unmentioned_document_needs_no_test(self):
        self.assertEqual(self.pick("docs/ZZ.md"), [])
        self.assertEqual(self.pick("docs/ZZ.md", "scripts/zz_other.py"), ["test_zz_other"])

    def test_the_real_repo_follows_a_rules_file_and_the_page(self):
        picked = rt.select(["config/trade_rules.json"], ROOT)[0]
        self.assertIn("test_trade_checker", picked)
        picked = rt.select(["index.html"], ROOT)[0]
        self.assertTrue({"test_scenario_rendering", "test_il_state", "test_export"} <= set(picked), picked)


class TestSchedule(unittest.TestCase):
    def test_every_unit_runs_once_and_chrome_stays_under_its_cap(self):
        units = ["c%d" % i for i in range(6)] + ["p%d" % i for i in range(6)]
        chrome, live, peak, lock = {u for u in units if u[0] == "c"}, [], [0, 0], threading.Lock()

        def run(u):
            with lock:
                live.append(u)
                peak[0] = max(peak[0], len(live))
                peak[1] = max(peak[1], len([x for x in live if x in chrome]))
            time.sleep(0.02)
            with lock:
                live.remove(u)
            return {"unit": u, "ok": True}

        got = [r["unit"] for r in rt.schedule(units, chrome, 4, 2, {}, run)]
        self.assertEqual(sorted(got), sorted(units))
        self.assertLessEqual(peak[0], 4)
        self.assertLessEqual(peak[1], 2)

    def test_only_a_failed_chrome_unit_is_retried_and_a_pass_on_retry_is_named(self):
        calls = []

        def run(u):
            calls.append(u)
            ok = u == "ok" or (u == "flaky" and calls.count(u) > 1)
            return {"unit": u, "ok": ok}

        results, flaky = rt.run_all(["ok", "flaky", "broken", "plain"], {"flaky", "broken"}, 2, 2, {}, run)
        self.assertEqual(flaky, ["flaky"])
        self.assertEqual({r["unit"]: r["ok"] for r in results}, {"ok": True, "flaky": True, "broken": False, "plain": False})
        self.assertEqual({u: calls.count(u) for u in set(calls)}, {"ok": 1, "flaky": 2, "broken": 2, "plain": 1})


class TestHandoff(unittest.TestCase):
    def test_handoff_does_not_run_the_suite_unless_asked(self):
        with open(os.path.join(ROOT, "scripts", "handoff.sh"), encoding="utf-8") as f:
            sh = f.read()
        self.assertNotIn("unittest discover", sh)
        self.assertIn('if [ "$RUN_TESTS" = 1 ]; then\n  python3 scripts/run_tests.py', sh)
        self.assertIn(rt.LAST_RUN.replace(os.sep, "/"), sh)


if __name__ == "__main__":
    unittest.main()
