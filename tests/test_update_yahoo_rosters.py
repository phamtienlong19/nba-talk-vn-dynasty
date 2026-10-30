"""Update Yahoo Rosters workflow logic (scripts/update_yahoo_rosters.py + .github/workflows/update-yahoo-rosters.yml).

No test touches the network or a real Yahoo session. Data tests use a private copy of data/2026-27 pinned to the draft-night
snapshot (TempData), the real 2026-10-19 capture as the Yahoo side, and a fetcher that renders it as team pages."""
import copy
import io
import json
import os
import re
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))
import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402
import update_yahoo_rosters as up  # noqa: E402
import yahoo_rosters as yr  # noqa: E402
from test_season_ops import TempData  # noqa: E402
from test_yahoo_rosters import LOGIN_PAGE, REFERENCE  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "update-yahoo-rosters.yml")
JOKIC, MILLER = "478.p.5352", "478.p.10084"


def reference():
    with open(REFERENCE, encoding="utf-8") as f:
        return json.load(f)


class PageFetcher:
    """Serves each team page rendered from an observation (slot, status, NBA team and positions included)."""
    method = "fake"

    def __init__(self, obs, overrides=None):
        self.obs, self.overrides, self.urls = obs, overrides or {}, []

    def get(self, url):
        self.urls.append(url)
        tid = int(url.rstrip("/").split("/")[-1])
        if tid in self.overrides:
            return self.overrides[tid]
        t = next((t for t in self.obs["teams"] if t["teamId"] == tid), None)
        if t is None:
            return 503, url, ""
        rows = ""
        for p in t["players"]:
            inj = (f'<span class="ysf-player-status Nowrap F-injury Fz-xxs"><span title="{p["injury"]}">{p["injury"]}</span></span>'
                   if p.get("injury") else "")
            meta = f'<span class="D-b"><span class="Fz-xxs">{p.get("nbaTeam", "")} - {p.get("positions", "")}</span></span>' if p.get("positions") else ""
            rows += (f'<tr><td><span class="pos-label" data-pos="{p["slot"]}">{p["slot"]}</span></td><td>'
                     f'<a class="Nowrap name F-link" href="https://sports.yahoo.com/nba/players/{p["playerId"]}">{p["name"]}</a>{inj}{meta}</td></tr>')
        return 200, url, (f'<html><head><title>NBA Talk VN - Dynasty - {t["teamName"]} | Fantasy Basketball | Yahoo! Sports</title>'
                          f'<link rel="canonical" href="https://basketball.fantasysports.yahoo.com/nba/85092/{tid}" /></head>'
                          f'<body><table id="statTable0"><tbody>{rows}</tbody></table></body></html>')

    def close(self):
        pass


def team(obs, tid):
    return next(t for t in obs["teams"] if t["teamId"] == tid)


def move(obs, pid, to_team):
    o = copy.deepcopy(obs)
    for t in o["teams"]:
        hit = [p for p in t["players"] if p["playerId"] == pid]
        if hit:
            t["players"].remove(hit[0])
            team(o, to_team)["players"].append(hit[0])
    return o


class RunCase(unittest.TestCase):
    cfg = yr.load_config()

    clock = 0

    def run_update(self, td, obs, apply=False, overrides=None, out=None):
        out = out or os.path.join(td.root, "out")
        RunCase.clock += 1                                               # every run is one minute later than the last
        now = f"2026-10-20T14:{RunCase.clock % 60:02d}:00Z" if RunCase.clock < 60 else "2026-10-20T15:00:00Z"
        return up.run(self.cfg, PageFetcher(obs, overrides), out, data_dir=td.dir, apply=apply, delay=0, now=now), out

    def snapshot_files(self, td):
        return sorted(os.listdir(os.path.join(td.dir, "rosters", "snapshots")))


class TestOutcomes(RunCase):
    def test_ready_applies_a_reviewed_snapshot_and_nothing_else(self):
        with TempData() as td:
            before = up.protected_files(td.dir)
            res, out = self.run_update(td, reference(), apply=True)
            self.assertEqual((res["outcome"], res["exit"]), ("READY", 0))
            after = up.protected_files(td.dir)
            self.assertEqual({k: v for k, v in after.items() if k in before}, before)           # frozen salaries, ledger, history untouched
            self.assertEqual(len(self.snapshot_files(td)), 2)                                    # draft-night + the new one
            si = td.si()
            self.assertEqual(si["rosterSnapshot"]["kind"], "VERIFIED_IMPORT")
            cur = ss.season_state(si)
            self.assertEqual(cur["playerOwner"][MILLER], "franchise-01")                         # the IL pickup is owned
            self.assertEqual(cur["slots"][MILLER], "IL")                                         # and keeps its IL label
            self.assertEqual(ls.team_cap(si, cur, "franchise-12"), 144)                          # top 9 over all owned players
            txns = ss._load(os.path.join(td.dir, "season_transactions.json"))["transactions"]
            self.assertEqual([t["txnId"] for t in txns], ["TXN-2026-001", "PROP-2026-001", "PROP-2026-002", "PROP-2026-003"])  # nothing manufactured
            report = res["report"]
            self.assertIn("Jordan Miller → Bsy **[IL]** `O`", report)
            self.assertIn("## Salary-cap effects (top 9 frozen salaries, IL included)", report)
            self.assertRegex(report, r"\| sup fam \| 15 \| 3 \| 144 → 144 \| 144 \| IN_RANGE")
            self.assertTrue(os.path.exists(os.path.join(out, "observation.json")))

    def test_second_run_is_no_change_and_dry_run_modifies_nothing(self):
        with TempData() as td:
            before = up.protected_files(td.dir)
            res, _ = self.run_update(td, reference(), apply=False)                               # dry run
            self.assertEqual(res["outcome"], "READY")
            self.assertEqual(up.protected_files(td.dir), before)
            self.run_update(td, reference(), apply=True)
            res, _ = self.run_update(td, reference(), apply=True)
            self.assertEqual((res["outcome"], res["exit"]), ("NO_CHANGE", 0))
            self.assertEqual(len(self.snapshot_files(td)), 2)                                    # no duplicate import

    def test_lineup_only_changes_are_not_a_roster_update(self):
        with TempData() as td:
            self.run_update(td, reference(), apply=True)
            o = reference()
            for p in team(o, 8)["players"]:
                if p["slot"] == "BN" and p["name"] == "Nikola Jokić":
                    p["slot"] = "Util"                                                           # a daily lineup move
            res, _ = self.run_update(td, o, apply=True)
            self.assertEqual(res["outcome"], "NO_CHANGE")
            self.assertIn("only moved between bench and lineup slots", res["report"])
            self.assertEqual(len(self.snapshot_files(td)), 2)

    def test_no_change_still_reports_compliance_flags(self):
        with TempData() as td:
            self.run_update(td, reference(), apply=True)
            o = reference()
            next(p for p in team(o, 8)["players"] if p["name"] == "Aaron Nesmith")["injury"] = "O"      # Out, in a lineup slot
            self.run_update(td, o, apply=True)                                                           # status change: applied
            res, _ = self.run_update(td, o, apply=True)                                                  # nothing changed since
            self.assertEqual(res["outcome"], "NO_CHANGE")
            rep = res["report"]
            self.assertRegex(rep, r"\*\*Compliance flags on the current rosters: [1-9]\d*\*\*")
            self.assertIn("Aaron Nesmith (team 8) is injured (status O)", rep)                           # injured but not on IL
            self.assertRegex(rep, r"DHA — position coverage: \*\*over\*\* short PG")
            self.assertGreater(res["flags"], 0)
            self.assertNotRegex(rep.lower(), r"tanking|violator")
            self.assertEqual(len(self.snapshot_files(td)), 3)                                            # still no extra snapshot

    def test_flag_count_adds_antitank_and_cross_checks(self):
        dc = {"antiTank": [1, 2], "metadataDrift": [1], "slotIneligible": [], "healthyOnIL": [1], "injuredOffIL": [1, 2, 3],
              "ilLabelsLost": [9], "payrollMismatch": [9]}
        self.assertEqual(up.flag_count(dc), 7)                          # integrity failures are not flags: they fail the run

    def test_il_move_and_status_change_are_material(self):
        with TempData() as td:
            self.run_update(td, reference(), apply=True)
            o = reference()
            for p in team(o, 6)["players"]:
                if p["name"] == "Nic Claxton":
                    p["slot"] = "IL"
            res, _ = self.run_update(td, o, apply=True)
            self.assertEqual(res["outcome"], "READY")
            self.assertIn("IL moves", res["report"])
            o2 = copy.deepcopy(o)
            next(p for p in team(o2, 8)["players"] if p["name"] == "Aaron Nesmith")["injury"] = "O"
            res, _ = self.run_update(td, o2, apply=True)
            self.assertEqual(res["outcome"], "READY")                                            # a status change alone is a change
            self.assertIn("## Status changes", res["report"])

    def test_unexplained_ownership_change_is_a_conflict_and_modifies_nothing(self):
        with TempData() as td:
            before = up.protected_files(td.dir)
            res, out = self.run_update(td, move(reference(), "5352", 16), apply=True)             # Jokić "moves" to sup fam
            self.assertEqual((res["outcome"], res["exit"]), ("CONFLICT", 0))
            self.assertIn("ownership change not in the ledger: Nikola Jokić", res["report"])
            self.assertIn("canonical data NOT modified", res["report"])
            self.assertEqual(up.protected_files(td.dir), before)
            self.assertEqual(len(self.snapshot_files(td)), 1)                                    # no snapshot written
            self.assertEqual(ss._load(os.path.join(td.dir, "rosters", "index.json"))["current"], "snapshots/RS-2026-10-14-DRAFT-NIGHT.json")

    def test_completed_trade_yahoo_does_not_show_is_a_conflict(self):
        with TempData() as td:
            o = move(move(reference(), "10290", 8), "10465", 16)    # Castle back to Bsy, Coward back to sup fam: PROP-2026-001 undone
            res, _ = self.run_update(td, o, apply=True)
            self.assertEqual(res["outcome"], "CONFLICT")
            self.assertIn("PROP-2026-001", res["report"])


class TestFailures(RunCase):
    def failed(self, obs, overrides=None):
        with TempData() as td:
            before = up.protected_files(td.dir)
            res, out = self.run_update(td, obs, apply=True, overrides=overrides)
            self.assertEqual((res["outcome"], res["exit"]), ("FAILED", 1))
            self.assertEqual(up.protected_files(td.dir), before)
            self.assertEqual(len(self.snapshot_files(td)), 1)
            self.assertFalse(os.path.exists(os.path.join(out, "observation.json")))              # a failed capture is not kept
            return res["report"]

    def test_authentication_failure_says_how_to_fix_it(self):
        report = self.failed(reference(), {5: (200, "https://login.yahoo.com/?done=x", LOGIN_PAGE)})
        self.assertIn("FETCH_AUTH_REQUIRED", report)
        self.assertIn("update the YAHOO_STORAGE_STATE secret", report)

    def test_incomplete_roster_set_fails(self):
        o = reference()
        o["teams"] = [t for t in o["teams"] if t["teamId"] != 9]
        report = self.failed(o)
        self.assertIn("INCOMPLETE_CAPTURE", report)

    def test_empty_roster_fails(self):
        o = reference()
        team(o, 9)["players"] = []
        self.assertIn("EMPTY_ROSTER", self.failed(o))

    def test_duplicate_yahoo_player_id_fails(self):
        o = reference()
        team(o, 9)["players"].append(copy.deepcopy(team(o, 8)["players"][0]))
        self.assertIn("DUPLICATE_OWNERSHIP", self.failed(o))

    def test_parse_failure_fails(self):
        self.assertIn("NO_ROSTER_TABLE", self.failed(reference(), {4: (200, "x", "<html><body><table><tr><td>x</td></tr></table></body></html>")}))

    def test_http_error_fails_after_one_retry(self):
        f = PageFetcher(reference(), {7: (503, "u", "")})
        teams, errors = yr.fetch_teams(self.cfg, self.cfg["teamIds"], f, delay=0, sleep=lambda s: None)
        self.assertEqual([(e["teamId"], e["code"], e["attempts"]) for e in errors], [(7, "HTTP_503", 2)])


class TestDoubleChecks(RunCase):
    def report(self, mutate):
        o = reference()
        mutate(o)
        with TempData() as td:
            res, _ = self.run_update(td, o)
            self.assertIn(res["outcome"], ("READY", "CONFLICT"), res["report"][:300])
            return res["report"]

    def test_metadata_drift_and_ineligible_slot_are_reported(self):
        def mutate(o):
            p = next(p for p in team(o, 8)["players"] if p["name"] == "Nikola Jokić")
            p["nbaTeam"], p["positions"] = "LAL", "PG"                 # team moved and eligibility changed on Yahoo
            p["slot"] = "PG"                                           # and a centre sits in the PG slot
        report = self.report(mutate)
        self.assertIn("Nikola Jokić: our data DEN C, Yahoo team page LAL PG", report)
        self.assertNotIn("Nikola Jokić (PG) is in the PG slot", report)    # he is PG-eligible on that page: consistent
        def mutate2(o):
            p = next(p for p in team(o, 8)["players"] if p["name"] == "Nikola Jokić")
            p["slot"] = "PG"                                           # slot ineligible for the page's own positions (C)
        self.assertIn("Nikola Jokić (C) is in the PG slot", self.report(mutate2))

    def test_il_consistency_flags_use_yahoos_il_eligibility(self):
        def mutate(o):
            next(p for p in team(o, 8)["players"] if p["name"] == "Nikola Jokić")["slot"] = "IL"          # healthy star parked on IL
            next(p for p in team(o, 8)["players"] if p["name"] == "Jordan Miller")["injury"] = None      # IL-eligible, no status: still fine
            next(p for p in team(o, 8)["players"] if p["name"] == "Grayson Allen")["injury"] = "OFS"     # out for the season, on the bench
            next(p for p in team(o, 2)["players"] if p["name"] == "Kristaps Porziņģis")["injury"] = None  # IL-eligible, benched, no status
        report = self.report(mutate)
        self.assertIn("Nikola Jokić (team 8) is on IL but Yahoo lists him as neither IL-eligible nor Out/injured", report)
        self.assertNotIn("Jordan Miller (team 8) is on IL", report)
        self.assertIn("Grayson Allen (team 8) is injured (", report)
        self.assertIn("Kristaps Porziņģis (team 2) is injured (IL-eligible per Yahoo) but sits in BN, not IL", report)

    def test_a_player_just_injured_is_not_flagged_when_the_registry_lags(self):
        """The registry's IL eligibility can be a day old: Out on IL is compliant even if it does not list IL yet."""
        def mutate(o):
            p = next(p for p in team(o, 8)["players"] if p["name"] == "Nikola Jokić")
            p["slot"], p["injury"] = "IL", "O"                      # healthy-looking star, registry says not IL-eligible, Yahoo says Out
        self.assertIn("- Parked on IL but not IL-eligible: none", self.report(mutate))

    def test_il_eligible_players_in_il_slots_are_not_flagged(self):
        report = self.report(lambda o: None)
        self.assertIn("- Parked on IL but not IL-eligible: none", report)

    def test_anti_tank_checks_are_reported_without_a_verdict(self):
        report = self.report(lambda o: None)
        self.assertIn("## Anti-tank roster checks (evidence only)", report)
        self.assertRegex(report, r"DHA — position coverage: \*\*over\*\* short PG")
        self.assertNotRegex(report.lower(), r"tanking|violator")

    def test_payroll_counts_il_players_in_the_top_nine(self):
        o = reference()
        with TempData() as td:
            res, _ = self.run_update(td, o, apply=True)
            si = td.si()
            cur = ss.season_state(si)
            for fid in si["franchises"]:
                caps = sorted((ls.player_cap(si, k) for k in ls.team_players(si, cur, fid)), reverse=True)
                self.assertEqual(ls.team_cap(si, cur, fid), sum(caps[:9]))
            il = [k for k, s in cur["slots"].items() if s in ss.SLOTS_IL]
            self.assertEqual(len(il), 15)                                                       # every IL player kept his label
            self.assertTrue(all(k in cur["playerOwner"] for k in il))                            # and is owned


class TestStorageState(unittest.TestCase):
    def write(self, state):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, "state.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump(state, f)
        return p

    def cookie(self, domain=".yahoo.com", expires=None):
        c = {"name": "T", "value": "SECRET-VALUE-NEVER-PRINT", "domain": domain, "path": "/"}
        if expires is not None:
            c["expires"] = expires
        return c

    def test_state_problems(self):
        self.assertTrue(yr.storage_state_problems(None))
        self.assertIn("no browser-state file", yr.storage_state_problems("/nonexistent")[0])
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        bad = os.path.join(d, "bad.json")
        with open(bad, "w") as f:
            f.write("not json")
        self.assertIn("not a valid Playwright storage state", yr.storage_state_problems(bad)[0])
        self.assertIn("no yahoo.com cookies", yr.storage_state_problems(self.write({"cookies": [self.cookie(".example.com")]}))[0])
        self.assertIn("expired", yr.storage_state_problems(self.write({"cookies": [self.cookie(expires=time.time() - 10)]}))[0])
        self.assertEqual(yr.storage_state_problems(self.write({"cookies": [self.cookie(expires=time.time() + 3600)]})), [])
        self.assertEqual(yr.storage_state_problems(self.write({"cookies": [self.cookie()]})), [])        # a session cookie has no expiry

    def test_bad_state_fails_clearly_without_network_and_never_leaks_the_secret(self):
        expired = self.write({"cookies": [self.cookie(expires=time.time() - 10)]})
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out)
        before = up.protected_files(ls.DATA_DIR)
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = up.main(["--engine", "browser", "--storage-state", expired, "--out", out])
        self.assertEqual(rc, 1)
        with open(os.path.join(out, "report.md"), encoding="utf-8") as f:
            report = f.read()
        self.assertIn("AUTH_REQUIRED", report)
        self.assertIn("update the YAHOO_STORAGE_STATE secret", report)
        for text in (report, buf.getvalue()):
            self.assertNotIn("SECRET-VALUE-NEVER-PRINT", text)
        self.assertEqual(up.protected_files(ls.DATA_DIR), before)

    def test_session_problem_is_reported_even_when_playwright_is_not_installed(self):
        """CI installs no Playwright: the missing/expired session must still be the reported reason."""
        saved = {k: sys.modules.get(k) for k in ("playwright", "playwright.sync_api")}
        sys.modules["playwright"] = sys.modules["playwright.sync_api"] = None        # makes `import playwright` raise ImportError
        try:
            with self.assertRaises(yr.FetchError) as e:
                yr.BrowserFetcher(storage_state="/nonexistent")
            self.assertEqual(e.exception.code, "AUTH_REQUIRED")
            self.assertIn("no browser-state file", e.exception.detail)
            valid = self.write({"cookies": [self.cookie()]})
            with self.assertRaises(yr.FetchError) as e:                              # a usable session but no Playwright
                yr.BrowserFetcher(storage_state=valid)
            self.assertEqual(e.exception.code, "NO_PLAYWRIGHT")
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v

    def test_missing_state_fails_before_any_request(self):
        out = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(up.main(["--engine", "browser", "--storage-state", "/nonexistent", "--out", out]), 1)
        with open(os.path.join(out, "report.md"), encoding="utf-8") as f:
            self.assertIn("no browser-state file", f.read())

    def test_outputs_file_gets_single_line_values_only(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        p = os.path.join(d, "out.txt")
        up.write_outputs(p, {"outcome": "READY", "report": "a.md\nINJECTED=1"})
        with open(p, encoding="utf-8") as f:
            self.assertEqual(f.read(), "outcome=READY\nreport=a.md\n")


class TestAutoMergeGuard(unittest.TestCase):
    D = {"changedTeam": [], "added": [1] * 12, "dropped": [1] * 4, "ilMoves": [1] * 5}

    def test_small_free_agent_activity_is_safe(self):
        self.assertTrue(up.automerge_ok("READY", self.D))

    def test_conflicts_ownership_changes_and_wild_swings_wait_for_a_human(self):
        self.assertFalse(up.automerge_ok("CONFLICT", self.D))
        self.assertFalse(up.automerge_ok("NO_CHANGE", self.D))
        self.assertFalse(up.automerge_ok("READY", dict(self.D, changedTeam=[{"player": "x"}])))
        self.assertFalse(up.automerge_ok("READY", dict(self.D, added=[1] * (up.AUTOMERGE_MAX_CHANGES + 1))))     # looks like a broken page


class TestFreshnessPill(unittest.TestCase):
    def test_the_roster_pill_says_how_old_the_snapshot_is_without_changing_its_text(self):
        with open(os.path.join(ROOT, "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn('hrs>=48?Math.floor(hrs/24)+"D OLD":hrs>=12?Math.floor(hrs)+"H OLD":""', html)   # silent under 12h, amber to 48h, red after
        self.assertIn('.roster-verified[data-age]::after{content:" · " attr(data-age)', html)          # CSS adds the age: textContent stays "✓ ROSTERS <date>"


class TestWorkflowFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(WORKFLOW, encoding="utf-8") as f:
            cls.yml = f.read()

    def test_scheduled_and_manual_only_with_a_serialized_least_privilege_job(self):
        self.assertTrue(self.yml.startswith("name: Update Yahoo Rosters"))
        self.assertRegex(self.yml, r"\non:\n  schedule:\n    - cron: \"17 \*/3 \* \* \*\"\n  workflow_dispatch:")
        for trigger in ("pull_request", "push:", "issue_comment", "workflow_run"):
            self.assertNotIn(trigger + "\n", self.yml.split("jobs:")[0].replace("# ", ""), trigger)
        self.assertRegex(self.yml, r"permissions:\n  contents: write\n  pull-requests: write\n  actions: write\n  issues: write\n")
        self.assertIn("ENGINE: ${{ inputs.engine || 'http' }}", self.yml)                          # scheduled runs are anonymous: no Yahoo credentials
        self.assertIn("(github.event_name == 'schedule' || inputs.open_pr) && github.ref == 'refs/heads/main'", self.yml)
        self.assertRegex(self.yml, r"concurrency:\n  group: update-yahoo-rosters\n  cancel-in-progress: false")
        self.assertIn("runs-on: ubuntu-latest", self.yml)
        self.assertIn("timeout-minutes: 25", self.yml)

    def test_never_pushes_to_main_and_only_queues_auto_merge_for_the_safe_class(self):
        for bad in ("--admin", "--squash --admin", "push origin main", "push origin HEAD:main", "--force", "pull_request_target",
                    "gh pr review", "--approve", "/reviews", "pulls/", "/merge"):
            self.assertNotIn(bad, self.yml, bad)                                                    # no merging, no approving a PR review
        approvals = [l for l in self.yml.splitlines() if "approve" in l and not l.lstrip().startswith("#") and "echo" not in l]
        self.assertTrue(all("actions/runs/$id/approve" in l or "Approve" in l or "approve" in l.lower() for l in approvals))
        self.assertEqual([l.strip() for l in self.yml.splitlines() if "/approve" in l],
                         ['if gh api -X POST "repos/$GITHUB_REPOSITORY/actions/runs/$id/approve" --silent; then'])   # the only approval: a held workflow run
        self.assertIn('gh pr create --base main --head "$branch"', self.yml)
        self.assertNotIn("--draft", self.yml)                                                       # opened ready for review (owner, 2026-10-21)
        self.assertIn('git push origin "$branch"', self.yml)
        self.assertIn("github.ref == 'refs/heads/main'", self.yml)                                # PRs only from main

    def test_pr_checks_are_approved_and_stale_roster_prs_superseded(self):
        step = self.yml.split("- name: Open a pull request")[1]
        self.assertIn('select(.conclusion == "action_required")', step)                            # only runs GitHub is holding
        self.assertIn('actions/runs/$id/approve', step)
        self.assertLess(step.index("gh pr create"), step.index("approve"))                         # approve after the PR exists
        self.assertIn('startswith("automation/yahoo-rosters-")', step)                             # only this workflow's own branches
        self.assertIn('gh pr close "$old" --delete-branch --comment "Superseded by #$new_pr', step)
        self.assertEqual(step.count("gh pr merge"), 1)
        self.assertIn('gh pr merge "$new_pr" --auto --squash --delete-branch', step)               # GitHub merges only after the required checks pass
        self.assertIn('if [ "$AUTOMERGE" = "true" ]; then\n            if gh pr merge', step)         # and only for the safe class
        self.assertLess(step.index("actions/runs/$id/approve"), step.index("gh pr merge"))
        guard = self.yml.index("Only roster data and the generated site may have changed")
        self.assertLess(guard, self.yml.index("actions/runs/$id/approve"))                         # approval only after the path guard passed

    def test_secret_handling(self):
        self.assertEqual(self.yml.count("secrets."), 2)                                           # the session and the optional PR token
        self.assertIn("YAHOO_STORAGE_STATE: ${{ secrets.YAHOO_STORAGE_STATE }}", self.yml)
        self.assertIn("ROSTER_PR_TOKEN: ${{ secrets.ROSTER_PR_TOKEN }}", self.yml)
        self.assertNotRegex(self.yml, r"echo[^\n]*\$(ROSTER_PR_TOKEN|GH_TOKEN|DEFAULT_TOKEN)")        # tokens are never echoed
        self.assertIn('GH_TOKEN="$ROSTER_PR_TOKEN" gh api user --silent', self.yml)                # validated first; falls back if invalid
        self.assertIn("::warning title=PR opened by the bot", self.yml)
        self.assertNotIn("git push origin main", self.yml)
        self.assertNotRegex(self.yml, r"echo[^\n]*\$YAHOO_STORAGE_STATE[^_]")                      # never echoed
        self.assertNotIn("set -x", self.yml)
        self.assertIn("umask 077", self.yml)
        self.assertRegex(self.yml, r"Remove the Yahoo session[^\n]*\n\s+if: always\(\)\n\s+run: rm -f")
        up_ = self.yml.split("actions/upload-artifact@v4")[1].split("retention-days")[0]
        self.assertNotIn("state", up_.replace("observation", ""))                                  # the state file is never uploaded
        self.assertIn("report.md", up_)

    def test_only_roster_data_and_site_may_change_and_checks_run_first(self):
        guard = self.yml.index("Only roster data and the generated site may have changed")
        self.assertLess(self.yml.index("./validate.sh"), guard)
        self.assertLess(self.yml.index("python3 -m unittest discover -s tests"), guard)
        self.assertLess(guard, self.yml.index("Open a pull request"))
        self.assertIn("data/2026-27/rosters/", self.yml)

    def test_installs_only_what_the_scraper_needs(self):
        with open(os.path.join(ROOT, "requirements-yahoo-rosters.txt"), encoding="utf-8") as f:
            reqs = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        self.assertEqual(len(reqs), 1)
        self.assertRegex(reqs[0], r"^playwright==\d+\.\d+\.\d+$")                                  # pinned
        self.assertIn("if: env.ENGINE == 'browser'", self.yml)                                    # nothing installed for the http engine
        with open(os.path.join(ROOT, ".gitignore"), encoding="utf-8") as f:
            self.assertIn("/artifacts/", f.read())

    def test_parses_as_yaml_with_the_expected_shape(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        doc = yaml.safe_load(self.yml)
        triggers = doc.get(True, doc.get("on"))                       # YAML 1.1 reads the key `on` as True
        self.assertEqual(sorted(triggers), ["schedule", "workflow_dispatch"])
        self.assertEqual(doc["permissions"], {"contents": "write", "pull-requests": "write", "actions": "write", "issues": "write"})
        self.assertEqual(list(doc["jobs"]), ["update"])
        names = [st.get("name") for st in doc["jobs"]["update"]["steps"]]
        self.assertEqual(names[0], "Checkout")
        self.assertEqual(names[0], "Checkout")
        self.assertEqual(sum(1 for st in doc["jobs"]["update"]["steps"] if st.get("if") == "always()"), 3)  # report, session cleanup, artifact upload
        self.assertEqual(triggers["workflow_dispatch"]["inputs"]["engine"]["options"], ["browser", "http"])
        self.assertEqual(names[-3:], ["Open a pull request", 'Open or refresh the "needs attention" issue',
                                      'Close the "needs attention" issue once the refresh recovers'])
        self.assertEqual(triggers["workflow_dispatch"]["inputs"]["engine"]["default"], "http")

    def test_stress_tool_is_documented_and_never_touches_the_working_tree(self):
        with open(os.path.join(ROOT, "scripts", "stress_roster_tests.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("shutil.copytree(ROOT, copy", src)                                           # works on a temp copy
        self.assertIn('"--apply"', src)
        with open(os.path.join(ROOT, "docs", "YAHOO_ROSTER_WORKFLOW.md"), encoding="utf-8") as f:
            self.assertIn("scripts/stress_roster_tests.py", f.read())

    def test_documented(self):
        with open(os.path.join(ROOT, "docs", "YAHOO_ROSTER_WORKFLOW.md"), encoding="utf-8") as f:
            doc = f.read()
        for needle in ("gh secret set YAHOO_STORAGE_STATE", "export-state", "gh workflow run \"Update Yahoo Rosters\"",
                       "Allow GitHub", "CONFLICT", "NO_CHANGE", "IL included"):
            self.assertIn(needle, doc)


if __name__ == "__main__":
    unittest.main()
