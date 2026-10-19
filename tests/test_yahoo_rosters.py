"""Read-only Yahoo roster acquisition (scripts/yahoo_rosters.py): parsing, normalization, validation, reconciliation,
governance (nothing official changes without the reviewed import) and IL invariants (owned = all rostered players;
counted payroll = the nine highest frozen salaries, IL included; IL is a lineup slot, kept and shown).

The HTML fixtures are trimmed copies of real public Yahoo team pages fetched 2026-10-19; the reference observation is
the full 16-team capture taken the same day. No test touches the network."""
import copy
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, os.path.dirname(__file__))
import import_rosters as ir  # noqa: E402
import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402
import yahoo_rosters as yr  # noqa: E402
from test_season_ops import TempData, export_rows  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "yahoo")
REFERENCE = os.path.join(FIX, "observation_2026-10-19.json")
BSY, THINH, SUP, QUAN = "franchise-01", "franchise-11", "franchise-12", "franchise-13"
JOKIC, MILLER = "478.p.5352", "478.p.10084"


def page(team):
    with open(os.path.join(FIX, f"team{team}_2026-10-19.html"), encoding="utf-8") as f:
        return f.read()


def reference():
    with open(REFERENCE, encoding="utf-8") as f:
        return json.load(f)


def tree_digest(path):
    h = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(path)):
        dirs.sort()
        for name in sorted(files):
            p = os.path.join(root, name)
            h.update(p.encode())
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()


LOGIN_PAGE = ('<html><head><title>Yahoo</title></head><body><form id="login-username-form">'
              '<input name="username" id="login-username"></form></body></html>')
CONSENT_PAGE = '<html><head><title>Yahoo is part of the Yahoo family of brands</title></head><body>collectConsent consent</body></html>'
EMPTY_TABLE = ('<html><head><title>NBA Talk VN - Dynasty - X | Fantasy Basketball</title>'
               '<link rel="canonical" href="https://basketball.fantasysports.yahoo.com/nba/85092/5" /></head>'
               '<body><table id="statTable0"><tbody><tr class="empty-position"><td><span class="pos-label" data-pos="PG">PG</span>'
               '</td><td></td></tr></tbody></table></body></html>')


class FakeFetcher:
    """Serves fixture pages by team id; `pages` overrides specific teams."""
    method = "fake"

    def __init__(self, pages=None, status=None):
        self.pages, self.status, self.urls = pages or {}, status or {}, []

    def get(self, url):
        self.urls.append(url)
        tid = int(url.rstrip("/").split("/")[-1])
        if tid in self.status:
            return self.status[tid], url, ""
        if tid in self.pages:
            return 200, url, self.pages[tid]
        # rebuild a page for any team from the reference observation (same markup as the real fixture rows)
        t = next(t for t in reference()["teams"] if t["teamId"] == tid)
        rows = "".join(f'<tr><td><span class="pos-label" data-pos="{p["slot"]}">{p["slot"]}</span></td><td>'
                       f'<a class="Nowrap name F-link" href="https://sports.yahoo.com/nba/players/{p["playerId"]}">{p["name"]}</a>'
                       f'</td></tr>' for p in t["players"])
        return 200, url, (f'<html><head><title>NBA Talk VN - Dynasty - {t["teamName"]} | Fantasy Basketball | Yahoo! Sports</title>'
                          f'<link rel="canonical" href="https://basketball.fantasysports.yahoo.com/nba/85092/{tid}" /></head>'
                          f'<body><table id="statTable0"><tbody>{rows}</tbody></table></body></html>')

    def close(self):
        pass


class TestParser(unittest.TestCase):
    def test_real_page_team_8(self):
        t = yr.parse_team_page(page(8), 8, "85092")
        self.assertEqual(t["teamName"], "Hai | Bulls Dynasty")
        by = {p["name"]: p for p in t["players"]}
        for n in ("Nikola Jokić", "Joan Beringer", "Cedric Coward"):
            self.assertIn(n, by)                                          # observed on team 8 on 2026-10-19
        self.assertEqual(by["Nikola Jokić"]["playerId"], "5352")
        self.assertEqual((by["Nikola Jokić"]["nbaTeam"], by["Nikola Jokić"]["positions"]), ("DEN", "C"))
        self.assertEqual(by["Nikola Jokić"]["keeperSalary"], 61)          # evidence only; never written anywhere
        miller = by["Jordan Miller"]
        self.assertEqual((miller["slot"], miller["injury"], miller["injuryTitle"]), ("IL", "O", "Out"))
        self.assertEqual(len({p["playerId"] for p in t["players"]}), len(t["players"]))

    def test_real_page_team_16_and_lineup_slots(self):
        t = yr.parse_team_page(page(16), 16, "85092")
        names = [p["name"] for p in t["players"]]
        self.assertIn("Caleb Wilson", names)
        self.assertIn("Amen Thompson", names)
        self.assertEqual(sum(1 for p in t["players"] if p["slot"] == "IL"), 3)
        self.assertNotIn(None, [p["playerId"] for p in t["players"]])     # empty lineup slots are not players
        thinh = yr.parse_team_page(page(2), 2, "85092")
        self.assertEqual([p["slot"] for p in thinh["players"]][:9], ["PG", "SG", "G", "SF", "PF", "F", "C", "FC", "Util"])

    def test_wrong_team_login_consent_and_malformed_pages_fail_clearly(self):
        with self.assertRaises(yr.FetchError) as e:
            yr.parse_team_page(page(8), 9, "85092")
        self.assertEqual(e.exception.code, "WRONG_TEAM")
        with self.assertRaises(yr.FetchError) as e:
            yr.parse_team_page(LOGIN_PAGE, 8, "85092", "https://login.yahoo.com/?done=x")
        self.assertEqual(e.exception.code, "AUTH_REQUIRED")
        with self.assertRaises(yr.FetchError) as e:
            yr.parse_team_page(LOGIN_PAGE, 8, "85092")                    # sign-in form without a redirect URL
        self.assertEqual(e.exception.code, "AUTH_REQUIRED")
        with self.assertRaises(yr.FetchError) as e:
            yr.parse_team_page(CONSENT_PAGE, 8, "85092")
        self.assertEqual(e.exception.code, "CONSENT_REQUIRED")
        with self.assertRaises(yr.FetchError) as e:
            yr.parse_team_page("<html><body><table><tr><td>x</td></tr></table>", 8, "85092")
        self.assertEqual(e.exception.code, "NO_ROSTER_TABLE")
        self.assertEqual(yr.parse_team_page(EMPTY_TABLE, 5, "85092")["players"], [])   # parsed, then rejected by validation


class TestNormalization(unittest.TestCase):
    cfg = yr.load_config()

    def test_keys_use_the_repository_game_key(self):
        si = ss.load_season(ls.load_inputs())
        yr.check_game_key(si, self.cfg)                                   # 478, from the frozen salary table
        bad = dict(self.cfg, gameKey="466")
        with self.assertRaises(ValueError):
            yr.check_game_key(si, bad)
        obs = yr.make_observation(self.cfg, [yr.parse_team_page(page(8), 8, "85092")], "2026-10-19T13:00:00Z", "http")
        self.assertEqual(obs["teams"][0]["teamKey"], "478.l.85092.t.8")
        self.assertEqual({p["playerKey"] for p in obs["teams"][0]["players"]} >= {JOKIC}, True)
        self.assertEqual(obs["scope"], "PARTIAL")

    def test_digest_ignores_order_and_scope_needs_every_team(self):
        teams = reference()["teams"]
        a = yr.make_observation(self.cfg, teams, "2026-10-19T13:00:00Z", "http")
        b = yr.make_observation(self.cfg, list(reversed(copy.deepcopy(teams))), "2026-10-19T13:00:00Z", "http")
        self.assertEqual((a["digest"], a["scope"]), (b["digest"], "FULL"))

    def test_manual_capture_shapes(self):
        ref = reference()
        list_shape = {"capturedAt": "2026-10-19T13:47:00Z", "leagueId": "85092",
                      "teams": [{"teamId": t["teamId"], "teamName": t["teamName"],
                                 "players": [{"playerId": p["playerId"], "name": p["name"], "slot": p["slot"]} for p in t["players"]]}
                                for t in ref["teams"]]}
        dict_shape = {str(t["teamId"]): [{"id": int(p["playerId"]), "name": p["name"], "position": p["slot"]} for p in t["players"]]
                      for t in ref["teams"]}
        flat_shape = [{"teamId": t["teamId"], "playerId": p["playerId"], "name": p["name"], "slot": p["slot"]}
                      for t in ref["teams"] for p in t["players"]]
        digests = set()
        for shape in (list_shape, dict_shape, flat_shape):
            raw = yr.normalize_manual(shape, self.cfg)
            obs = yr.make_observation(self.cfg, raw["teams"], "2026-10-19T13:47:00Z", "manual-devtools")
            self.assertEqual(yr.validate_observation(obs, self.cfg)["blocking"], [])
            digests.add(obs["digest"])
        self.assertEqual(digests, {ref["digest"]})                         # same rosters whatever the shape
        with self.assertRaises(ValueError):
            yr.normalize_manual(dict(list_shape, leagueId="12345"), self.cfg)

    def test_identity_resolution_keeps_provisional_records(self):
        si = ss.load_season(ls.load_inputs())
        rec = yr.reconcile(si, reference())
        snap = rec["snapshot"]
        owners = ss.snapshot_owner(snap)
        self.assertEqual(owners[JOKIC], BSY)                               # Yahoo id -> canonical registry key
        cands = [w for w in rec["report"]["warnings"] if w["code"] == "PROVISIONAL_LINK_CANDIDATE"]
        self.assertEqual(len(cands), 6)
        self.assertIn("provisional:bennett-stirtz", owners)                # resolved to the provisional identity, not merged
        self.assertNotIn("478.p.10573", owners)
        prov = ss._load(os.path.join(ss.DATA_DIR, "provisional_players.json"))
        self.assertFalse(any(p.get("yahooPlayerKey") for p in prov["players"]))  # linking stays a reviewed command

    def test_bn_and_il_are_lineup_slots_not_ownership_classes(self):
        si = ss.load_season(ls.load_inputs())
        snap = yr.reconcile(si, reference())["snapshot"]
        slots = ss.snapshot_slots(snap)
        self.assertEqual(slots[MILLER], "IL")
        self.assertEqual(ss.snapshot_owner(snap)[MILLER], BSY)              # IL players are owned like any other
        self.assertEqual(slots[JOKIC], "BN")


class TestValidation(unittest.TestCase):
    cfg = yr.load_config()

    def test_reference_capture_is_valid(self):
        obs = reference()
        check = yr.validate_observation(obs, self.cfg)
        self.assertEqual(check, {"blocking": [], "warnings": []})
        keys = [p["playerId"] for t in obs["teams"] for p in t["players"]]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(sorted(t["teamId"] for t in obs["teams"]), self.cfg["teamIds"])
        self.assertNotIn(10, self.cfg["teamIds"])

    def test_duplicate_ownership_bad_ids_slots_and_empty_rosters_block(self):
        obs = reference()
        obs["teams"][1]["players"].append(dict(obs["teams"][0]["players"][0]))
        obs["teams"][2]["players"][0]["playerId"] = "abc"
        obs["teams"][3]["players"][0]["slot"] = "XX"
        obs["teams"][4]["players"] = []
        codes = {b["code"] for b in yr.validate_observation(obs, self.cfg)["blocking"]}
        self.assertEqual(codes, {"DUPLICATE_OWNERSHIP", "BAD_PLAYER_ID", "UNKNOWN_SLOT", "EMPTY_ROSTER"})

    def test_invalid_and_missing_teams_block(self):
        obs = reference()
        obs["teams"][0]["teamId"] = 10
        codes = [b["code"] for b in yr.validate_observation(obs, self.cfg)["blocking"]]
        self.assertIn("INVALID_TEAM_ID", codes)
        self.assertIn("INCOMPLETE_CAPTURE", codes)
        with redirect_stdout(io.StringIO()) as out:
            rc = yr.main(["fetch", "--team", "10"], fetcher=FakeFetcher(), out_dir=tempfile.mkdtemp())
        self.assertEqual(rc, 2)
        self.assertIn("not in league 85092", out.getvalue())

    def test_roster_size_is_not_fixed(self):
        obs = reference()
        obs["teams"][0]["players"] = obs["teams"][0]["players"][:3]
        obs["teams"][1]["players"] += [{"playerId": "99999", "playerKey": "478.p.99999", "name": "Extra", "slot": "BN"}]
        self.assertEqual(yr.validate_observation(obs, self.cfg)["blocking"], [])

    def test_partial_fetch_failure_is_reported_and_not_saved(self):
        out_dir = tempfile.mkdtemp()
        try:
            fake = FakeFetcher(pages={5: LOGIN_PAGE}, status={9: 503})
            with redirect_stdout(io.StringIO()) as out:
                rc = yr.main(["fetch"], fetcher=fake, out_dir=out_dir)
            text = out.getvalue()
            self.assertEqual(rc, 1)
            self.assertEqual(len(fake.urls), 16)                            # every team is still attempted
            self.assertIn("FETCH_AUTH_REQUIRED", text)
            self.assertIn("FETCH_HTTP_503", text)
            self.assertIn("INCOMPLETE_CAPTURE", text)
            self.assertEqual(os.listdir(out_dir), [])                       # only successful acquisitions are saved
            self.assertTrue(all(u.startswith("https://basketball.fantasysports.yahoo.com/nba/85092/") for u in fake.urls))
        finally:
            shutil.rmtree(out_dir)

    def test_single_team_fetch_is_partial(self):
        out_dir = tempfile.mkdtemp()
        try:
            with redirect_stdout(io.StringIO()) as out:
                rc = yr.main(["fetch", "--team", "8"], fetcher=FakeFetcher(pages={8: page(8)}), out_dir=out_dir)
            self.assertEqual(rc, 0)
            saved = [ss._load(os.path.join(out_dir, f)) for f in os.listdir(out_dir)]
            self.assertEqual([(o["scope"], [t["teamId"] for t in o["teams"]]) for o in saved], [("PARTIAL", [8])])
            self.assertIn("not importable", out.getvalue())
            self.assertIsNone(yr.previous_observation(out_dir))             # a partial capture is never a baseline
        finally:
            shutil.rmtree(out_dir)


class TestReconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.si = ss.load_season(ls.load_inputs())
        cls.rec = yr.reconcile(cls.si, reference())

    def test_recorded_trades_are_reflected_and_not_reported_as_differences(self):
        d = self.rec["diff"]
        self.assertEqual([(t["txnId"], t["reflected"]) for t in d["transactions"]],
                         [("TXN-2026-001", True), ("PROP-2026-001", True), ("PROP-2026-002", True)])
        self.assertEqual(d["changedTeam"], [])                               # Jokić etc. already moved in the ledger
        moved = {x["player"] for k in ("added", "dropped") for x in d[k]}
        self.assertFalse(moved & {"Nikola Jokić", "Joan Beringer", "Cedric Coward", "Stephon Castle"})

    def test_differences_are_observations_not_transactions(self):
        d = self.rec["diff"]
        self.assertIn(("Zaccharie Risacher", "Bsy"), {(x["player"], x["team"]) for x in d["dropped"]})
        self.assertIn(("Jordan Miller", "Bsy"), {(x["player"], x["team"]) for x in d["added"]})
        self.assertTrue(all(x["note"] == "on Yahoo, not on our roster" for x in d["added"]))
        self.assertTrue(all("not on Yahoo" in x["note"] or "provisional" in x["note"] for x in d["dropped"]))
        unknown = [b for b in self.rec["report"]["blocking"] if b["code"] == "UNMATCHED_PLAYER"]
        self.assertEqual([b["detail"] for b in unknown], ["unknown player 'Jayden Quaintance' (478.p.10594)"])

    def test_team_change_matching_an_open_proposal_is_labelled_not_applied(self):
        with TempData() as td:
            doc = ss._load(os.path.join(td.dir, "season_transactions.json"))
            doc["transactions"].append({"txnId": "PROP-TEST", "type": "TRADE", "status": "PROPOSED", "label": "TEST",
                                        "participants": [BSY, SUP], "recordedAt": "2026-10-19",
                                        "assets": [{"type": "player", "playerKey": JOKIC, "from": BSY, "to": SUP}]})
            ss._write(os.path.join(td.dir, "season_transactions.json"), doc)
            obs = reference()
            b8 = next(t for t in obs["teams"] if t["teamId"] == 8)
            j = next(p for p in b8["players"] if p["playerId"] == "5352")
            b8["players"].remove(j)
            next(t for t in obs["teams"] if t["teamId"] == 16)["players"].append(j)
            rec = yr.reconcile(td.si(), obs, td.dir)
            x = rec["diff"]["changedTeam"]
            self.assertEqual([(y["player"], y["from"], y["to"]) for y in x], [("Nikola Jokić", "Bsy", "sup fam")])
            self.assertEqual(x[0]["note"], "matches PROP-TEST (PROPOSED), which is not recorded as completed")
            self.assertEqual(ss.season_state(td.si())["playerOwner"][JOKIC], BSY)

    def test_observation_vs_previous_observation(self):
        old = reference()
        new = copy.deepcopy(old)
        t1, t2 = new["teams"][0], new["teams"][1]
        moved = t1["players"].pop(0)
        t2["players"].append(moved)
        new["teams"][2]["players"][0]["slot"] = "IL"
        new["teams"][3]["players"].append({"playerId": "424242", "name": "New Guy", "slot": "BN"})
        gone = new["teams"][4]["players"].pop()
        d = yr.observation_diff(old, new)
        self.assertEqual([x["player"] for x in d["changedTeam"]], [moved["name"]])
        self.assertEqual([x["to"] for x in d["slotChanged"]], ["IL"])
        self.assertEqual([x["playerId"] for x in d["added"]], ["424242"])
        self.assertEqual([x["playerId"] for x in d["removed"]], [gone["playerId"]])
        self.assertEqual(yr.observation_diff(old, old), {"added": [], "removed": [], "changedTeam": [], "slotChanged": []})

    def test_previous_observation_ignores_partial_and_failed_captures(self):
        out_dir = tempfile.mkdtemp()
        try:
            ref = reference()
            yr.save_observation(ref, out_dir)
            later = dict(copy.deepcopy(ref), capturedAt="2026-10-20T00:00:00Z", scope="PARTIAL", digest="b" * 64)
            yr.save_observation(later, out_dir)
            failed = dict(copy.deepcopy(ref), capturedAt="2026-10-21T00:00:00Z", errors=[{"teamId": 5}], digest="c" * 64)
            yr.save_observation(failed, out_dir)
            self.assertEqual(yr.previous_observation(out_dir)[1]["capturedAt"], ref["capturedAt"])
            self.assertIsNone(yr.previous_observation(out_dir, before=ref["capturedAt"]))
        finally:
            shutil.rmtree(out_dir)

    def test_payroll_preview_uses_top_nine_frozen_salaries(self):
        pay = {p["team"]: p for p in self.rec["payroll"]}
        self.assertEqual(pay["Bsy"]["capNow"], ls.team_cap(self.si, ss.season_state(self.si), BSY))
        keys = [k for k, f in ss.snapshot_owner(self.rec["snapshot"]).items() if f == BSY]
        self.assertEqual(pay["Bsy"]["capIfImported"], sum(sorted((ls.player_cap(self.si, k) for k in keys), reverse=True)[:9]))
        self.assertEqual(pay["Bsy"]["il"], 1)
        self.assertEqual([x["player"] for x in self.rec["salaryEvidence"]], ["RJ Barrett"])  # reported, frozen salary kept


class TestGovernance(unittest.TestCase):
    """A fetch, a manual import, a validate or a diff never changes official data."""

    def test_unreviewed_commands_do_not_touch_official_data(self):
        before = tree_digest(ss.DATA_DIR)
        out_dir = tempfile.mkdtemp()
        try:
            ref = reference()
            cap = os.path.join(out_dir, "capture.json")
            with open(cap, "w", encoding="utf-8") as f:
                json.dump({"capturedAt": ref["capturedAt"], "leagueId": "85092",
                           "teams": [{"teamId": t["teamId"], "teamName": t["teamName"], "players": t["players"]} for t in ref["teams"]]}, f)
            with redirect_stdout(io.StringIO()):
                yr.main(["fetch"], fetcher=FakeFetcher(), out_dir=out_dir)
                yr.main(["import-json", cap], out_dir=out_dir)
                yr.main(["validate", REFERENCE], out_dir=out_dir)
                yr.main(["diff", REFERENCE], out_dir=out_dir)
        finally:
            shutil.rmtree(out_dir)
        self.assertEqual(tree_digest(ss.DATA_DIR), before)                  # rosters, ledger, salary freeze, keepers, history

    def test_observation_feeds_the_existing_reviewed_import_unchanged(self):
        with TempData() as td:
            si = td.si()
            obs = reference()
            for t in obs["teams"]:                                          # test data: drop the one unpriced player
                t["players"] = [p for p in t["players"] if p["playerId"] != "10594"]
            path = os.path.join(td.root, "obs.json")
            ss._write(path, obs)
            rows = ir.parse(path)                                           # the importer reads an observation as-is
            snap, rep = ir.build_snapshot(si, rows, obs["capturedAt"], obs["source"], td.dir)
            self.assertEqual(rep["blocking"], [])                           # teams resolve by yahooTeamKey
            d = ir.diff(si, snap)
            salaries = ss._load(os.path.join(td.dir, "salary_freeze.json"))
            with self.assertRaises(ir.ImportBlocked):
                ir.commit(si, snap, rep, d, td.dir, reviewed=False)
            self.assertEqual(ss.season_state(td.si())["playerOwner"].get(MILLER), None)
            ir.commit(si, snap, rep, d, td.dir, reviewed=True)
            si2 = td.si()
            cur = ss.season_state(si2)
            self.assertEqual(cur["playerOwner"][MILLER], BSY)
            self.assertEqual(ss._load(os.path.join(td.dir, "salary_freeze.json")), salaries)
            self.assertEqual(ss.checkpoint_findings(si2)[0]["shortfall"], 8)  # history and checkpoints untouched

    def test_no_credentials_or_browser_state_in_the_repository(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.assertFalse(yr.PROFILE_DIR.startswith(root))
        self.assertTrue(yr.OBS_DIR.startswith(os.path.join(root, "local_data")))
        with open(os.path.join(root, ".gitignore"), encoding="utf-8") as f:
            self.assertIn("/local_data/", f.read())
        cfg = json.dumps(ss._load(yr.CONFIG_PATH)).lower()
        for secret in ("cookie", "password", "token\"", "secret\""):
            self.assertNotIn(secret, cfg)
        for wf in os.listdir(os.path.join(root, ".github", "workflows")):
            with open(os.path.join(root, ".github", "workflows", wf), encoding="utf-8") as f:
                self.assertNotIn("yahoo_rosters", f.read(), wf)            # no scheduled or CI fetch


class TestInjuredList(unittest.TestCase):
    """Owned = every rostered player; counted payroll = the nine highest frozen salaries, IL or not; IL = a lineup slot."""

    def commit_slots(self, td, slots, when="2026-10-19T12:00:00Z"):
        si = td.si()
        rows = export_rows(si)
        for r in rows:
            if r[1] in slots:
                r[4] = slots[r[1]]
        snap, rep = ir.build_snapshot(si, ir.parse(td.csv(rows, f"r{when[:13]}.csv")), when, "test", td.dir)
        ir.commit(si, snap, rep, ir.diff(si, snap), td.dir, reviewed=True)
        return td.si()

    def test_expensive_il_player_stays_in_the_counted_nine(self):
        with TempData() as td:
            base = ls.team_cap(td.si(), ss.season_state(td.si()), BSY)
            si = self.commit_slots(td, {JOKIC: "IL"})
            cur = ss.season_state(si)
            self.assertEqual(ls.team_cap(si, cur, BSY), base)
            row = next(r for r in ls.team_roster(si, cur, BSY) if r["k"] == JOKIC)
            self.assertFalse(row["x"])                                       # $61 counts although on IL

    def test_cheap_il_player_outside_the_nine_is_owned_but_not_counted(self):
        with TempData() as td:
            si = td.si()
            roster = ls.team_roster(si, ss.season_state(si), BSY)
            cheap = roster[-1]["k"]
            self.assertTrue(roster[-1]["x"])
            base = ls.team_cap(si, ss.season_state(si), BSY)
            si = self.commit_slots(td, {cheap: "IL"})
            cur = ss.season_state(si)
            self.assertEqual(cur["playerOwner"][cheap], BSY)
            self.assertEqual(ls.team_cap(si, cur, BSY), base)
            self.assertTrue(next(r for r in ls.team_roster(si, cur, BSY) if r["k"] == cheap)["x"])

    def test_bn_il_moves_change_neither_ownership_nor_payroll(self):
        with TempData() as td:
            si1 = self.commit_slots(td, {JOKIC: "BN"}, "2026-10-19T12:00:00Z")
            cur1 = ss.season_state(si1)
            caps1 = {f: ls.team_cap(si1, cur1, f) for f in si1["franchises"]}
            for a, b, when in (("BN", "IL", "2026-10-20T12:00:00Z"), ("IL", "BN", "2026-10-21T12:00:00Z")):
                rows = export_rows(td.si())
                for r in rows:
                    if r[1] == JOKIC:
                        r[4] = b
                    if r[1] == "478.p.5765" and b == "BN":
                        r[4] = "PF"                    # unrelated lineup change: identical content is never re-imported
                si = td.si()
                snap, rep = ir.build_snapshot(si, ir.parse(td.csv(rows, f"m{when[:10]}.csv")), when, "test", td.dir)
                d = ir.diff(si, snap)
                self.assertEqual((d["added"], d["dropped"], d["changedTeam"]), ([], [], []))
                self.assertEqual([(x["player"], x["from"], x["to"]) for x in d["ilMoves"]], [("Nikola Jokić", a, b)])
                self.assertTrue(all(x["player"] == "Jayson Tatum" for x in d["lineupOnly"]))
                ir.commit(si, snap, rep, d, td.dir, reviewed=True)
                si = td.si()
                cur = ss.season_state(si)
                self.assertEqual(cur["playerOwner"], cur1["playerOwner"])
                self.assertEqual({f: ls.team_cap(si, cur, f) for f in si["franchises"]}, caps1)
            txns = ss._load(os.path.join(td.dir, "season_transactions.json"))["transactions"]
            self.assertEqual([t["txnId"] for t in txns], ["TXN-2026-001", "PROP-2026-001", "PROP-2026-002"])  # nothing invented

    def test_il_players_appear_in_snapshots_comparisons_and_rosters(self):
        with TempData() as td:
            si = self.commit_slots(td, {JOKIC: "IL"})
            self.assertIn({"playerKey": JOKIC, "name": "Nikola Jokić", "slot": "IL"}, si["rosterSnapshot"]["teams"][BSY])
            view = ss.season_view(si)["teams"][BSY]
            row = next(r for r in view["roster"] if r["k"] == JOKIC)
            self.assertEqual((row["s"], view["il"]), ("IL", 1))              # what the team card renders as an IL tag
            rec = yr.reconcile(si, reference(), td.dir)
            self.assertIn(("Nikola Jokić", "IL", "BN"), {(x["player"], x["from"], x["to"]) for x in rec["diff"]["ilMoves"]})
        with open(os.path.join(os.path.dirname(__file__), "..", "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn('if(r.s==="IL"||r.s==="IL+")row.querySelector(".pname").appendChild(h("span",{class:"il-tag",text:r.s}));', html)

    def test_removing_an_il_player_by_verified_transaction_recomputes_the_nine(self):
        with TempData() as td:
            si = self.commit_slots(td, {JOKIC: "IL"})
            doc = ss._load(os.path.join(td.dir, "season_transactions.json"))
            doc["transactions"].append({"txnId": "TXN-TEST-IL", "type": "TRADE", "status": "COMPLETED", "label": "TEST",
                                        "participants": [BSY, QUAN], "effectiveAt": "2026-10-20T00:00:00Z",
                                        "assets": [{"type": "player", "playerKey": JOKIC, "from": BSY, "to": QUAN}]})
            ss._write(os.path.join(td.dir, "season_transactions.json"), doc)
            si = td.si()
            cur = ss.season_state(si)
            left = [k for k, f in cur["playerOwner"].items() if f == BSY]
            self.assertNotIn(JOKIC, left)
            self.assertEqual(ls.team_cap(si, cur, BSY), sum(sorted((ls.player_cap(si, k) for k in left), reverse=True)[:9]))
            self.assertEqual(ls.team_cap(si, cur, BSY), 176 - 61)            # all $0 below: the 10th salary adds nothing
            quan = [k for k, f in cur["playerOwner"].items() if f == QUAN]
            self.assertEqual(ls.team_cap(si, cur, QUAN), sum(sorted((ls.player_cap(si, k) for k in quan), reverse=True)[:9]))


if __name__ == "__main__":
    unittest.main()
