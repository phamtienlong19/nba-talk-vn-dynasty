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
import re
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
from test_season_ops import TempData, draft_night, export_rows  # noqa: E402

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "yahoo")
REFERENCE = os.path.join(FIX, "observation_2026-10-19.json")
BSY, THINH, SUP, QUAN, TT_ = "franchise-01", "franchise-11", "franchise-12", "franchise-13", "franchise-16"
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
        si = draft_night(ss.load_season(ls.load_inputs()))
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
        si = draft_night(ss.load_season(ls.load_inputs()))
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
            self.assertEqual(len({u for u in fake.urls}), 16)               # every team is still attempted
            self.assertEqual(sum(1 for u in fake.urls if u.endswith("/9")), 2)  # the 503 was retried once
            self.assertIn("FETCH_AUTH_REQUIRED", text)
            self.assertIn("FETCH_HTTP_503", text)
            self.assertIn("INCOMPLETE_CAPTURE", text)
            self.assertEqual(os.listdir(out_dir), [])                       # only successful acquisitions are saved
            self.assertTrue(all(u.startswith("https://basketball.fantasysports.yahoo.com/nba/85092/") for u in fake.urls))
        finally:
            shutil.rmtree(out_dir)

    def test_transient_errors_are_retried_once_auth_errors_never(self):
        class Flaky(FakeFetcher):
            def __init__(self):
                super().__init__(pages={5: LOGIN_PAGE})
                self.failed = set()

            def get(self, url):
                tid = int(url.rstrip("/").split("/")[-1])
                if tid in (4, 9) and (tid not in self.failed or tid == 9):
                    self.failed.add(tid)
                    self.urls.append(url)
                    raise yr.FetchError("NETWORK", "The read operation timed out")
                return super().get(url)
        f = Flaky()
        teams, errors = yr.fetch_teams(yr.load_config(), yr.load_config()["teamIds"], f, delay=0, sleep=lambda s: None)
        self.assertIn(4, [t["teamId"] for t in teams])                      # one timeout, then success
        self.assertEqual({(e["teamId"], e["code"], e["attempts"]) for e in errors},
                         {(9, "NETWORK", 2), (5, "AUTH_REQUIRED", 1)})        # sign-in page: no retry
        self.assertEqual(sum(1 for u in f.urls if u.endswith("/5")), 1)

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
        cls.si = draft_night(ss.load_season(ls.load_inputs()))   # the state the 2026-10-19 capture was compared with
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
        self.assertEqual(self.rec["report"]["blocking"], [])                 # importable under the 2026-10-19 rule
        self.assertEqual([p["name"] for p in self.rec["report"]["unlisted"]], ["Jayden Quaintance"])

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


class TestUnlistedPlayers(unittest.TestCase):
    """League rule (owner, 2026-10-19): a rostered player whose salary is not in the frozen table is a 0."""
    QUAINTANCE = "478.p.10594"

    def test_rule_is_recorded_in_policy_not_hidden_in_code(self):
        rule = ss._load(os.path.join(os.path.dirname(ss.DATA_DIR), "..", "config", "cap_policy.json"))["unlistedPlayerSalary"]
        self.assertEqual(rule["value"], 0)
        self.assertIn("2026-10-19", rule["source"])
        with TempData() as td:
            si = td.si()
            si["policy"] = {k: v for k, v in si["policy"].items() if k != "unlistedPlayerSalary"}
            self.assertIsNone(ir.resolve_player(si, {}, {"playerKey": self.QUAINTANCE, "name": "Jayden Quaintance"})[0])

    def test_preview_prices_the_unlisted_player_at_zero(self):
        si = draft_night(ss.load_season(ls.load_inputs()))
        rec = yr.reconcile(si, reference())
        u = rec["report"]["unlisted"]
        self.assertEqual(u, [{"playerKey": self.QUAINTANCE, "name": "Jayden Quaintance", "nbaTeam": "SAS",
                              "displayPosition": "PF", "cap": 0.0}])
        self.assertIn("UNLISTED_PLAYER_ZERO_SALARY", [w["code"] for w in rec["report"]["warnings"]])
        self.assertIn(("Jayden Quaintance", "sup fam"), {(x["player"], x["team"]) for x in rec["diff"]["added"]})
        sup = next(p for p in rec["payroll"] if p["team"] == "sup fam")
        self.assertEqual((sup["count"], sup["capIfImported"]), (15, sup["capNow"]))
        self.assertNotIn(self.QUAINTANCE, si.get("unlistedPlayers", {}))      # nothing recorded by a preview

    def test_live_state_carries_the_recorded_unlisted_player(self):
        si = ss.load_season(ls.load_inputs())
        self.assertEqual(si["unlistedPlayers"][self.QUAINTANCE]["cap"], 0)
        self.assertEqual(ir.resolve_player(si, {}, {"playerId": "10594", "name": "Jayden Quaintance"})[:2], (self.QUAINTANCE, "KEY"))
        rec = yr.reconcile(si, reference())                                 # an older capture of the same league: nothing new unlisted
        self.assertEqual(rec["report"]["unlisted"], [])                      # he is recorded already, so no second record

    def test_commit_records_identity_once_and_never_touches_the_salary_freeze(self):
        with TempData() as td:
            salaries = ss._load(os.path.join(td.dir, "salary_freeze.json"))
            obs = reference()
            path = os.path.join(td.root, "obs.json")
            ss._write(path, obs)
            si = td.si()
            snap, rep = ir.build_snapshot(si, ir.parse(path), obs["capturedAt"], obs["source"], td.dir)
            ir.commit(si, snap, rep, ir.diff(si, snap), td.dir, reviewed=True)
            si2 = td.si()
            cur = ss.season_state(si2)
            self.assertEqual((cur["playerOwner"][self.QUAINTANCE], cur["slots"][self.QUAINTANCE]), (SUP, "IL"))
            self.assertEqual((ls.player_cap(si2, self.QUAINTANCE), ls.player_name(si2, self.QUAINTANCE)), (0.0, "Jayden Quaintance"))
            row = next(r for r in ss.season_view(si2)["teams"][SUP]["roster"] if r["k"] == self.QUAINTANCE)
            self.assertEqual((row["pos"], row["nba"], row["s"], row["c"]), ("PF", "SAS", "IL", 0.0))
            self.assertEqual(ss._load(os.path.join(td.dir, "salary_freeze.json")), salaries)
            # a later import that still lists him does not add a second record
            obs2 = dict(obs, capturedAt="2026-10-20T00:00:00Z")
            obs2["teams"][0]["players"][0] = dict(obs2["teams"][0]["players"][0], slot="IL")
            ss._write(path, obs2)
            snap2, rep2 = ir.build_snapshot(si2, ir.parse(path), obs2["capturedAt"], "t", td.dir)
            self.assertEqual(rep2["unlisted"], [])
            ir.commit(si2, snap2, rep2, ir.diff(si2, snap2), td.dir, reviewed=True)
            recs = ss._load(os.path.join(td.dir, "unlisted_players.json"))["players"]
            self.assertEqual([p["playerKey"] for p in recs], [self.QUAINTANCE])
            self.assertEqual(recs[0]["firstSeen"], snap["snapshotId"])


class TestTeamNames(unittest.TestCase):
    """The site shows each team's current Yahoo name (rosters/team_map.json); locked history keeps the old names."""

    def test_current_names_come_from_the_team_map(self):
        i = ls.load_inputs()
        tm = ss._load(os.path.join(ss.ROSTER_DIR, "team_map.json"))
        self.assertEqual(tm["teams"]["franchise-01"]["yahooTeamName"], "Hai | Bulls Dynasty")
        self.assertEqual(ls.team_name(i, "franchise-01"), "Hai | Bulls Dynasty")  # the full Yahoo name
        self.assertEqual(ls.team_name(i, "franchise-12"), "sup fam | Crashed for Caleb")
        self.assertEqual(ls.team_name(i, "franchise-16"), "T T | Kratos Dynasty")  # spacing around "|" normalised
        self.assertEqual(ls.team_name(i, "franchise-07"), "Maxfixe")
        freeze = {t["franchiseId"]: t["teamName"] for t in i["freeze"]["teams"]}
        self.assertEqual(freeze["franchise-01"], "GTA San Antonio")              # the locked freeze is not rewritten
        self.assertEqual(i["franchises"]["franchise-01"]["displayName"], "Hai | GTA San Antonio")

    def test_page_labels_follow_the_current_names(self):
        import build_league_state as bls
        with open(os.path.join(os.path.dirname(__file__), "..", "index.html"), encoding="utf-8") as f:
            html = f.read()
        i = ls.load_inputs()
        self.assertEqual(bls.sync_team_names(html, i), html)                     # already in sync (idempotent)
        names = [re.sub(r"<[^>]+>", "", n) for n in re.findall(r'<div class="team-name">(.*?)</div>', html)]
        self.assertIn("Hai | Bulls Dynasty", names)
        self.assertIn("CrazyCat | Damageeeee", names)
        self.assertIn("Long con dynasty", names)
        self.assertIn("<b>sup fam</b><small>sup fam | Crashed for Caleb</small>", html)
        self.assertIn(">CrazyCat | Damageeeee</span>", html)
        self.assertIn(">Hai | Bulls Dynasty</span>", html)                       # chips show the full name
        for old in ("GTA San Antonio", "Bruised for Boozer", "Poop for Coop", "CrazyCat Damageee<"):
            self.assertNotIn(old, html)
        data = json.loads(re.search(r'id="league-data">(.*?)</script>', html, re.S).group(1).replace("<\\/", "</"))
        self.assertEqual({t["short"]: t["name"] for t in data["teams"]}["Bsy"], "Hai | Bulls Dynasty")
        # renaming back restores the old labels: the rewrite is driven by the map, not hard-coded
        i2 = dict(i, teamNames=dict(i["teamNames"], **{"franchise-01": "GTA San Antonio"}))
        back = bls.sync_team_names(html, i2)
        self.assertIn(">GTA San Antonio</span>", back)
        self.assertIn("<b>Bsy</b><small>GTA San Antonio</small>", back)


class TestRosterChecks(unittest.TestCase):
    """Anti-tank roster limits (docs/LEAGUE_RULES_MODEL.md) reported as evidence: injured stacking, single-position
    hoarding, position coverage and whether a full lineup can be fielded. Levels only -- never a tanking verdict."""

    def setUp(self):
        # Rule logic runs on the frozen draft-night baseline with injuries IMPOSED by each test, so the expectations do not
        # depend on whichever players managers have added, dropped or hurt on Yahoo this week.
        self.si = draft_night(ss.load_season(ls.load_inputs()))
        self.cur = ss.season_state(self.si)
        self.rules = ss._load(ss.RULES_PATH)

    def state_with(self, fid, slots=None, status=None, add=()):
        st = dict(self.cur, slots=dict(self.cur["slots"]), status=dict(self.cur.get("status", {})),
                  playerOwner=dict(self.cur["playerOwner"]))
        st["slots"].update(slots or {})
        st["status"].update(status or {})
        for k in add:
            st["playerOwner"][k] = fid
        return st

    def test_rules_are_recorded_with_their_source(self):
        self.assertEqual((self.rules["longTermInjured"]["max"], self.rules["minPerPosition"]), (5, 2))
        self.assertEqual((self.rules["singlePosition"]["max"], self.rules["singlePosition"]["maxWithComboTags"]), (5, 7))
        self.assertEqual(list(self.rules["lineupSlots"]), ["PG", "SG", "G", "SF", "PF", "F", "C", "FC", "Util"])
        self.assertIn("never decides tanking intent", self.rules["note"])

    def test_injured_stacking_counts_il_and_out_players(self):
        f = BSY
        keys = sorted(ls.team_players(self.si, self.cur, f), key=lambda k: -ls.player_cap(self.si, k))
        c = ss.roster_checks(self.si, self.cur, f)["injured"]
        self.assertEqual((c["count"], c["level"]), (0, "ok"))                     # baseline: nobody hurt
        four_il = {k: "IL" for k in keys[1:5]}
        out = {keys[0]: "O", keys[5]: "INJ"}                                         # Out but kept off IL still counts
        st = self.state_with(f, four_il, out)
        c = ss.roster_checks(self.si, st, f)["injured"]
        self.assertEqual((c["count"], c["il"], c["out"], c["level"]), (6, 4, 2, "over"))
        counted = sum(r["c"] for r in ls.team_roster(self.si, st, f) if r["k"] in keys[:6] and not r["x"])
        self.assertEqual(c["countedCap"], counted)                                  # their salaries still count if inside the nine
        five = ss.roster_checks(self.si, self.state_with(f, {k: "IL" for k in keys[:5]}), f)["injured"]
        self.assertEqual((five["count"], five["level"]), (5, "watch"))               # at the limit
        q = ss.roster_checks(self.si, self.state_with(f, status={keys[0]: "Q"}), f)["injured"]
        self.assertEqual(q["count"], 0)                                              # questionable is not injured-list stacking

    def test_single_position_hoarding_levels(self):
        for f in self.si["franchises"]:                                              # the level follows the count, for every team
            c = ss.roster_checks(self.si, self.cur, f)["singlePosition"]
            want = "over" if c["count"] > 7 else "watch" if c["count"] > 5 else "ok"  # >5 inside the combo exception: review; >7: over
            self.assertEqual(c["level"], want, self.si["shorts"][f])
        tight = dict(self.rules, singlePosition={"max": 0, "maxWithComboTags": 0})
        self.assertEqual(ss.roster_checks(self.si, self.cur, BSY, tight)["singlePosition"]["level"], "over")
        loose = dict(self.rules, singlePosition={"max": 0, "maxWithComboTags": 99})
        self.assertEqual(ss.roster_checks(self.si, self.cur, BSY, loose)["singlePosition"]["level"], "watch")

    def test_injured_players_do_not_count_toward_positional_limits(self):
        self.assertTrue(self.rules["positionalLimitsCountHealthyOnly"])
        single = [k for k in ls.team_players(self.si, self.cur, SUP) if len(ss._positions(self.si, k, self.rules["positions"])) == 1]
        self.assertGreaterEqual(len(single), 3)
        before = ss.roster_checks(self.si, self.cur, SUP)["singlePosition"]["count"]
        self.assertEqual(before, len(single))                                    # nobody injured: every single-position player counts
        for n in (1, 2, 3):                                                      # each one put on IL stops counting
            st = self.state_with(SUP, {k: "IL" for k in single[:n]})
            self.assertEqual(ss.roster_checks(self.si, st, SUP)["singlePosition"]["count"], before - n)

    def test_two_position_combos_need_three_healthy_players(self):
        self.assertEqual((self.rules["combos"], self.rules["minPerCombo"]), ({"G": ["PG", "SG"], "F": ["SF", "PF"]}, 3))
        c = ss.roster_checks(self.si, self.cur, BSY)["coverage"]
        self.assertEqual(c["shortCombo"], [])
        guards = [k for k in ls.team_players(self.si, self.cur, BSY) if ss._positions(self.si, k, self.rules["positions"]) & {"PG", "SG"}
                  and self.cur["slots"].get(k) not in ("IL", "IL+") and self.cur["status"].get(k) not in ("O", "INJ", "OFS")]
        keep = guards[:2]                                                          # leave only two healthy guards
        c = ss.roster_checks(self.si, self.state_with(BSY, {k: "IL" for k in guards if k not in keep}), BSY)["coverage"]
        self.assertEqual((c["byCombo"]["G"], c["shortCombo"], c["level"]), (2, ["G"], "over"))

    def test_healthy_cap_excludes_out_players_even_off_il_and_ties_prefer_healthy(self):
        base = ss.post_draft_state(self.si)
        f = max(self.si["franchises"], key=lambda x: max(ls.player_cap(self.si, k) for k in ls.team_players(self.si, self.cur, x)))
        keys = sorted(ls.team_players(self.si, self.cur, f), key=lambda k: -ls.player_cap(self.si, k))
        star = keys[0]
        plain = ss.team_view(self.si, self.cur, f, base)
        self.assertEqual((plain["injuredCap"], plain["healthyCap"]), (0, plain["cap"]))
        out = ss.team_view(self.si, self.state_with(f, status={star: "O"}), f, base)            # Out, still in a lineup slot
        self.assertEqual(out["cap"], plain["cap"])                                                 # payroll is unchanged
        self.assertEqual(out["injuredCap"], ls.player_cap(self.si, star))
        self.assertEqual(out["healthyCap"], plain["cap"] - ls.player_cap(self.si, star))         # but "healthy" drops him
        q = ss.team_view(self.si, self.state_with(f, status={star: "Q"}), f, base)
        self.assertEqual(q["healthyCap"], plain["cap"])                                           # questionable is not injured
        # ties at the ninth salary: the counted player is the healthy one, never an injured player picked by name order
        for g in self.si["franchises"]:
            ks = sorted(ls.team_players(self.si, self.cur, g), key=lambda k: -ls.player_cap(self.si, k))
            if len(ks) > 10 and ls.player_cap(self.si, ks[8]) == ls.player_cap(self.si, ks[9]):
                tied = [k for k in ks if ls.player_cap(self.si, k) == ls.player_cap(self.si, ks[8])]
                first = min(tied, key=lambda k: ls.player_name(self.si, k))                       # name order would pick him
                v = ss.team_view(self.si, self.state_with(g, {first: "IL"}), g, base)
                counted = {r["k"] for r in v["roster"] if not r["x"]}
                self.assertNotIn(first, counted, g)                                              # injured, tied: not the counted one
                self.assertEqual(v["cap"], ss.team_view(self.si, self.cur, g, base)["cap"], g)  # payroll identical
                break
        else:
            self.fail("no team has a tie at the ninth salary in the frozen baseline")

    def test_ofs_and_inj_count_as_long_term_injured(self):
        keys = ls.team_players(self.si, self.cur, TT_)
        c = ss.roster_checks(self.si, self.state_with(TT_, status={keys[0]: "OFS", keys[1]: "INJ", keys[2]: "D"}), TT_)["injured"]
        self.assertEqual((c["out"], c["count"]), (2, 2))                          # doubtful is not

    def test_coverage_and_full_lineup(self):
        def pgs_of(f):
            return [k for k in ls.team_players(self.si, self.cur, f) if "PG" in ss._positions(self.si, k, self.rules["positions"])]
        f = max(self.si["franchises"], key=lambda x: len(pgs_of(x)))                # a team with plenty of PG-eligible players
        pgs = pgs_of(f)
        self.assertGreaterEqual(len(pgs), 3)
        base = ss.roster_checks(self.si, self.cur, f)
        self.assertNotIn("PG", base["coverage"]["short"])
        keep = pgs[0]                                                              # leave exactly one healthy PG-eligible player
        short = ss.roster_checks(self.si, self.state_with(f, {k: "IL" for k in pgs if k != keep}), f)
        self.assertEqual((short["coverage"]["short"].count("PG"), short["coverage"]["byPosition"]["PG"], short["coverage"]["level"]), (1, 1, "over"))
        # put every healthy center on IL: the lineup can no longer be filled
        keys = ls.team_players(self.si, self.cur, BSY)
        centers = [k for k in keys if "C" in ss._positions(self.si, k, self.rules["positions"])]
        c = ss.roster_checks(self.si, self.state_with(BSY, {k: "IL" for k in centers}), BSY)
        self.assertIn("C", c["coverage"]["short"])
        self.assertIn("C", c["lineup"]["empty"])
        self.assertEqual(c["lineup"]["level"], "over")

    def test_status_is_observed_evidence_not_ownership(self):
        with TempData() as td:
            obs = reference()
            path = os.path.join(td.root, "obs.json")
            ss._write(path, obs)
            si = td.si()
            snap, rep = ir.build_snapshot(si, ir.parse(path), obs["capturedAt"], obs["source"], td.dir)
            rows = {r["playerKey"]: r for rows in snap["teams"].values() for r in rows}
            self.assertEqual((rows[MILLER]["slot"], rows[MILLER]["status"]), ("IL", "O"))
            self.assertEqual(rows["478.p.5464"]["status"], "O")                    # Porziņģis: Out, kept on the bench
            self.assertNotIn("status", rows[JOKIC])
            ir.commit(si, snap, rep, ir.diff(si, snap), td.dir, reviewed=True)
            si2 = td.si()
            cur = ss.season_state(si2)
            self.assertEqual(cur["status"]["478.p.5464"], "O")
            thinh = ss.roster_checks(si2, cur, THINH)["injured"]
            self.assertEqual((thinh["il"], thinh["out"]), (1, 1))                  # Butler on IL + Porziņģis out
            self.assertEqual(ss.snapshot_owner(snap)["478.p.5464"], THINH)          # status never moves ownership

    def test_cards_show_the_checks_quietly(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn('class:"tp-l "', html)                                         # each limit is a sentence in the team's detail panel
        self.assertIn('"Roster limits"', html)
        self.assertNotIn("rosterChecks", html)                                      # (the old tiny chips are gone)
        data = json.loads(re.search(r'id="league-data">(.*?)</script>', html, re.S).group(1).replace("<\\/", "</"))
        si = ss.load_season(ls.load_inputs())                                       # the embedded checks are the engine's, for any roster
        state = ss.season_state(si)
        for fid, team in data["official"]["teams"].items():
            self.assertEqual(team["checks"], json.loads(json.dumps(ss.roster_checks(si, state, fid))), fid)
        for word in ("tank", "Tank", "violator"):                                   # evidence, not a label on a team
            self.assertNotIn(word, json.dumps(data["official"]["teams"]))


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
                text = f.read()
            if wf == "update-yahoo-rosters.yml":                          # the one workflow the owner authorised (2026-10-20): manual only
                head = text.split("jobs:")[0]
                self.assertIn("workflow_dispatch:", head)
                for trigger in ("schedule:", "push:", "pull_request:", "pull_request_target:"):
                    self.assertNotIn("\n  " + trigger, head, trigger)
            else:
                self.assertNotIn("yahoo_rosters", text, wf)               # no scheduled or CI fetch anywhere else


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
            self.assertEqual([t["txnId"] for t in txns], ["TXN-2026-001", "PROP-2026-001", "PROP-2026-002", "PROP-2026-003"])  # nothing invented

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
        self.assertIn('sc=il?h("span",{class:"st-chip il"', html)   # status (or IL) chip left of the name
        self.assertIn('h("div",{class:"il-head"}', html)
        self.assertIn(".player-row.il-row .pname{white-space:normal;overflow:visible", html.replace(",.player-row.il-row", "\n.player-row.il-row"))  # long names wrap

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


# (The Yahoo standings importer has its own tests: tests/test_update_yahoo_standings.py.)


if __name__ == "__main__":
    unittest.main()
