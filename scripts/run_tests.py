#!/usr/bin/env python3
"""Run the tests in parallel (stdlib only). `python3 -m unittest discover -s tests` still works; this is the same tests, several at a time.

    python3 scripts/run_tests.py                      every test
    python3 scripts/run_tests.py test_il_state        only these test files (or file.Class / file.Class.test_name)
    python3 scripts/run_tests.py --changed            only what the diff against origin/main (plus uncommitted work) can reach
    python3 scripts/run_tests.py --changed --list     show that selection without running it

Each test class runs in its own process; at most --chrome of the classes that drive headless Chrome run at once (too many at once is where
page tests become flaky). A failed Chrome class is run once more, alone, after the others; if that passes, the summary says so by name. The
served page is built once and shared (NBA_TEST_SITE, read by tests/_site.py). Only failures are printed.

--changed follows file references backwards: a test is selected when it names a changed file, or names something that does (imports, script and
workflow names, config file names). Anything it cannot follow (data/, an unreferenced file) runs everything. It can still miss a cross-cutting
break, so a new PR gets one full run, and CI always runs everything."""
import argparse
import concurrent.futures as cf
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
TESTS = os.path.join(ROOT, "tests")
LAST_RUN = os.path.join("ai_exchange", ".last_test_run")          # git-ignored; scripts/handoff.sh reports it
TIMINGS = os.path.join("ai_exchange", ".test_timings.json")       # git-ignored; slowest classes start first next time
CHROME = re.compile(r"_chrome\b|_chrome_run|\bdrive_page\b|\b_phone\b|\b_drive\b")
# Files that no test can depend on unless one names them: a change to one selects only the tests that mention it (possibly none).
DOC_LIKE = re.compile(r"\.md$|^docs/|^ai_exchange/|^tasks/|^\.gitignore$")
GRAPH_DIRS = ("scripts", "tests", "config", ".github", "tools")


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout


def changed_files(root=ROOT, base="origin/main"):
    out = set(_git(root, "diff", "--name-only", base + "...HEAD").split("\n"))
    out |= set(_git(root, "diff", "--name-only", "HEAD").split("\n"))
    out |= set(_git(root, "ls-files", "--others", "--exclude-standard").split("\n"))
    return sorted(f for f in out if f)


def _graph_files(root):
    """Every file that can pull another one into a test, as {repo path: text}."""
    found = {}
    for d in GRAPH_DIRS:
        for base, dirs, names in os.walk(os.path.join(root, d)):
            dirs[:] = [x for x in dirs if x not in ("__pycache__", "node_modules", "fixtures")]
            for n in names:
                if n.endswith((".py", ".sh", ".yml", ".js", ".json")):
                    found[os.path.relpath(os.path.join(base, n), root)] = None
    for n in os.listdir(root):
        if n.endswith(".sh"):
            found[n] = None
    for rel in found:
        with open(os.path.join(root, rel), encoding="utf-8", errors="replace") as f:
            found[rel] = f.read()
    return found


def _reference(path):
    """A pattern that matches a mention of `path` in another file."""
    name = os.path.basename(path)
    parts = [re.escape(name)]
    if name.endswith(".py"):
        stem = re.escape(name[:-3])
        parts.append(r"(?:^|\n)[ \t]*(?:from[ \t]+%s\b|import[ \t]+(?:[\w.]+(?:[ \t]+as[ \t]+\w+)?[ \t]*,[ \t]*)*%s\b)" % (stem, stem))
    return re.compile("|".join(parts))


def is_test(path):
    return os.path.dirname(path) == "tests" and os.path.basename(path).startswith("test_") and path.endswith(".py")


def select(changed, root=ROOT):
    """(test module names, reason). None instead of the names means: run everything."""
    files = _graph_files(root)
    picked = set()
    for path in changed:
        if path.startswith("data/"):
            return None, path + " is data: any test may read it"
        reached, todo = {path}, [path]
        while todo:
            ref = _reference(todo.pop())
            for other, text in files.items():
                if other not in reached and ref.search(text):
                    reached.add(other)
                    todo.append(other)
        tests = {os.path.basename(p)[:-3] for p in reached if is_test(p) and os.path.isfile(os.path.join(root, p))}
        if not tests and not DOC_LIKE.search(path):
            return None, path + ": no test refers to it"
        picked |= tests
    return sorted(picked), "%d changed file(s)" % len(changed)


def list_tests(names):
    """{unit: [test ids]} where a unit is module.Class, or the whole file when its tests come from somewhere else (a load_tests that pulls in
    another folder's tests cannot be addressed by class name). A module that fails to import stays a unit, so the error is reported."""
    names = list(names) or sorted(n[:-3] for n in os.listdir(TESTS) if n.startswith("test_") and n.endswith(".py"))
    code = ("import json,sys,unittest\nsys.path.insert(0,'.')\nL=unittest.TestLoader()\n"
            "def walk(x):\n"
            "    for t in x:\n"
            "        if isinstance(t, unittest.TestSuite): yield from walk(t)\n"
            "        else: yield t.id()\n"
            "out=[[n, i] for n in sys.argv[1:] for i in walk(L.loadTestsFromName(n))]\n"
            "print('\\nIDS '+json.dumps(out))\n")
    p = subprocess.run([sys.executable, "-c", code, *names], cwd=TESTS, capture_output=True, text=True, env=_env())
    line = next((l for l in reversed(p.stdout.split("\n")) if l.startswith("IDS ")), None)
    if p.returncode or line is None:
        sys.exit("could not list the tests:\n" + p.stderr)
    found = json.loads(line[4:])
    foreign = {name for name, test_id in found if not test_id.startswith(name.split(".")[0] + ".")}
    units = {}
    for name, test_id in found:
        units.setdefault(name if name in foreign else test_id.rsplit(".", 1)[0], []).append(test_id)
    return units


def _env():
    return dict(os.environ, PYTHONWARNINGS=os.environ.get("PYTHONWARNINGS", "ignore::ResourceWarning"))


def run_unit(unit, ids, names):
    # a hand-picked single test stays a single test; otherwise the whole class (or file) runs in one process (setUpClass once)
    target = ids if any(n.count(".") >= 2 for n in names) else [unit]
    t = time.time()
    p = subprocess.run([sys.executable, "-m", "unittest", *target], cwd=TESTS, capture_output=True, text=True, env=_env())
    ran = re.findall(r"^Ran (\d+) test", p.stderr, re.M)
    skipped = re.findall(r"skipped=(\d+)", p.stderr)
    return {"unit": unit, "ok": p.returncode == 0, "ran": int(ran[-1]) if ran else 0, "skipped": int(skipped[-1]) if skipped else 0,
            "secs": time.time() - t, "out": p.stdout[-4000:] + p.stderr}


def schedule(units, chrome_units, jobs, chrome_jobs, cost, run):
    """Run every unit, longest first, with at most `jobs` at once and at most `chrome_jobs` of the Chrome ones. Yields results as they finish."""
    waiting = sorted(units, key=lambda u: -cost.get(u, 0))
    running = {}
    with cf.ThreadPoolExecutor(max_workers=jobs) as pool:
        while waiting or running:
            for u in list(waiting):
                if len(running) >= jobs:
                    break
                if u in chrome_units and sum(1 for x in running.values() if x in chrome_units) >= chrome_jobs:
                    continue
                waiting.remove(u)
                running[pool.submit(run, u)] = u
            done, _ = cf.wait(running, return_when=cf.FIRST_COMPLETED)
            for f in done:
                del running[f]
                yield f.result()


def run_all(units, chrome, jobs, chrome_jobs, cost, run):
    """schedule(), then one lone retry for each failed Chrome unit (a loaded machine can stall a page). Returns (results, names that needed it)."""
    results, retry = [], []
    for r in schedule(units, chrome, jobs, chrome_jobs, cost, run):
        if not r["ok"] and r["unit"] in chrome:
            retry.append(r["unit"])
        else:
            results.append(r)
    flaky = []
    for u in retry:
        r = run(u)
        results.append(r)
        if r["ok"]:
            flaky.append(u)
    return results, flaky


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="*", help="test files, classes or tests (default: all)")
    ap.add_argument("--changed", action="store_true", help="only tests the current diff can reach")
    ap.add_argument("--base", default="origin/main", help="what --changed compares with")
    ap.add_argument("--list", action="store_true", help="print the selection and stop")
    cpus = os.cpu_count() or 2
    ap.add_argument("-j", "--jobs", type=int, default=max(1, cpus - 1))
    ap.add_argument("--chrome", type=int, default=0, help="Chrome test classes at once (default: min(4, jobs))")
    a = ap.parse_args(argv)
    names = [os.path.basename(n)[:-3] if n.endswith(".py") else n for n in a.names]
    mode = "named" if names else "full"
    if a.changed:
        if names:
            ap.error("--changed and test names are exclusive")
        changed = changed_files(base=a.base)
        picked, why = select(changed)
        if picked is None:
            print("--changed: running everything (%s)" % why)
        else:
            mode = "changed"
            print("--changed: %s -> %d test file(s)" % (why, len(picked)))
            if a.list:
                print("\n".join(picked))
            if not picked:
                return 0
            names = picked
    if a.list:
        if not a.changed:
            print("\n".join(sorted(list_tests(names))))
        return 0

    start = time.time()
    site = tempfile.mkdtemp(prefix="nba-site-")
    try:
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_site.py"), "--out", site], check=True, stdout=subprocess.DEVNULL)
        os.environ["NBA_TEST_SITE"] = site
        units = list_tests(names)
        expected = sum(len(v) for v in units.values())
        chrome = set()
        for u in units:
            path = os.path.join(TESTS, u.split(".")[0] + ".py")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    if CHROME.search(f.read()):
                        chrome.add(u)
        timings = _read_json(os.path.join(ROOT, TIMINGS))
        cost = {u: timings.get(u, (5.0 if u in chrome else 0.1) * len(units[u])) for u in units}
        ran = skipped = 0
        failed = []
        results, flaky = run_all(units, chrome, a.jobs, a.chrome or min(4, a.jobs), cost, lambda u: run_unit(u, units[u], names))
        for r in results:
            ran += r["ran"]
            skipped += r["skipped"]
            timings[r["unit"]] = round(r["secs"], 2)
            if not r["ok"]:
                failed.append(r["unit"])
                print("=" * 70 + "\nFAILED " + r["unit"] + "\n" + r["out"], flush=True)
    finally:
        shutil.rmtree(site, True)

    # a class that is skipped as a whole (no Chrome) reports no test as run, so only a shortfall without skips is suspicious
    short = ran < expected and not skipped and not failed
    ok = not failed and not short
    summary = "%s: %d of %d tests ran, %d skipped, %d failing group(s), %.0fs (-j %d)" % (
        "OK" if ok else "FAILED", ran, expected, skipped, len(failed), time.time() - start, a.jobs)
    if failed:
        summary += "\nfailing: " + " ".join(sorted(failed))
    if flaky:
        summary += "\nfailed under load, passed when run alone: " + " ".join(sorted(flaky))
    if short:
        summary += "\nfewer tests ran than were listed"
    print(summary)
    try:
        head = _git(ROOT, "rev-parse", "--short", "HEAD").strip()
        dirty = bool(_git(ROOT, "status", "--porcelain").strip())
        os.makedirs(os.path.join(ROOT, "ai_exchange"), exist_ok=True)
        with open(os.path.join(ROOT, TIMINGS), "w", encoding="utf-8") as f:
            json.dump(timings, f, indent=0, sort_keys=True)
        with open(os.path.join(ROOT, LAST_RUN), "w", encoding="utf-8") as f:
            json.dump({"result": "PASS" if ok else "FAIL", "mode": mode, "ran": ran, "skipped": skipped, "head": head, "dirty": dirty}, f)
    except (OSError, subprocess.CalledProcessError):
        pass                                                      # bookkeeping only
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
