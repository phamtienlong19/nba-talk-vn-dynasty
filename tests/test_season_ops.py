"""Regular-season operations: layer separation (history / current season / Trade Lab), the in-season ledger, cap
checkpoints, the roster import workflow and provisional Yahoo identities. Write paths run on a temp copy of the data."""
import copy
import csv
import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import build_league_state as bls  # noqa: E402
import import_rosters as ir  # noqa: E402
import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402

BSY, CC, HCMC, DT, THINH, SUP = "franchise-01", "franchise-02", "franchise-05", "franchise-10", "franchise-11", "franchise-12"
CASTLE, MITCHELL, COWARD, BERINGER = "478.p.10290", "478.p.10304", "478.p.10465", "478.p.10460"
WEMBY, TYSON, JOKIC, OSO = "478.p.10094", "478.p.10279", "478.p.5352", "478.p.10313"
MOREZ, ZION = "478.p.10572", "478.p.6163"


def _read_html():
    with open(bls.INDEX_HTML, encoding="utf-8") as f:
        return f.read()


DRAFT_NIGHT = "RS-2026-10-14-DRAFT-NIGHT"


def draft_night(si):
    """The season layer as it stood before the first Yahoo import: the draft-night snapshot + completed trades. Trade and
    import mechanics are tested from this fixed baseline so later verified imports do not change the expectations."""
    si = dict(si)
    si["rosterSnapshot"] = ss._load(os.path.join(ss.ROSTER_DIR, "snapshots", DRAFT_NIGHT + ".json"))
    si["unlistedPlayers"] = {}
    return si


class TempData:
    """A private copy of data/2026-27 so commits, rollbacks and links never touch the repo. By default the copy is
    reset to the draft-night roster snapshot (no later imports, no unlisted players) -- a fixed baseline for tests."""

    def __init__(self, pin=True):
        self.pin = pin

    def __enter__(self):
        self.root = tempfile.mkdtemp()
        self.dir = os.path.join(self.root, "2026-27")
        shutil.copytree(ls.DATA_DIR, self.dir)
        if self.pin:
            idx_path = os.path.join(self.dir, "rosters", "index.json")
            idx = ss._load(idx_path)
            idx["current"] = f"snapshots/{DRAFT_NIGHT}.json"
            idx["history"] = [h for h in idx["history"] if h.get("snapshotId") == DRAFT_NIGHT]
            ss._write(idx_path, idx)
            for f in os.listdir(os.path.join(self.dir, "rosters", "snapshots")):
                if f != DRAFT_NIGHT + ".json":
                    os.remove(os.path.join(self.dir, "rosters", "snapshots", f))
            if os.path.exists(os.path.join(self.dir, "unlisted_players.json")):
                os.remove(os.path.join(self.dir, "unlisted_players.json"))
        return self

    def __exit__(self, *a):
        shutil.rmtree(self.root)

    def si(self):
        return ss.load_season(ls.load_inputs(data_dir=self.dir), data_dir=self.dir)

    def csv(self, rows, name="r.csv"):
        path = os.path.join(self.root, name)
        with open(path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["team", "player_key", "player_id", "player_name", "slot"])
            w.writerows(rows)
        return path


def export_rows(si):
    cur = ss.season_state(si)
    return [[si["shorts"][f], k, "", ls.player_name(si, k), cur["slots"].get(k) or ""] for k, f in cur["playerOwner"].items()]


class TestLayers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.i = ls.load_inputs()
        cls.si = draft_night(ss.load_season(cls.i))
        cls.hist = ls.resolve(cls.i, (), "OFFICIAL")
        cls.cur = ss.season_state(cls.si)

    def test_history_is_untouched_by_the_season_layer(self):
        snap = ss._load(ss.POST_DRAFT_PATH)
        self.assertEqual(snap, ss.make_post_draft_snapshot(self.i, "2026-10-14"))  # reproducible, immutable checkpoint
        self.assertEqual(snap["playerOwner"], dict(sorted(self.hist["playerOwner"].items())))
        self.assertEqual(self.hist["playerOwner"][MOREZ], CC)                      # draft night: Morez with CrazyCat
        self.assertEqual((snap["draftSelections"], snap["rookies"]), (48, 19))
        d = ls.draft_summary(self.i, self.hist)
        self.assertEqual((len(d["completed"]), d["rookies"], d["status"]), (48, 19, "COMPLETE"))
        pre = ss._load(os.path.join(ls.DATA_DIR, "snapshots", "PRE_DRAFT_LOCK.json"))
        self.assertEqual(pre["inputDigests"]["draftEvents"], ls._digest([]))       # pre-draft checkpoint unchanged

    def test_original_crazycat_hcmc_pre_draft_trade_is_preserved(self):
        f = self.i["tradeIndex"]["TRADE-F"]
        self.assertEqual(f["status"], "OFFICIAL")
        self.assertIn("TRADE-F", self.hist["activeTradeIds"])
        self.assertEqual(self.hist["pickOwner"]["2026-R2-07"], CC)
        sel = {c["label"]: c for c in ls.draft_summary(self.i, self.hist)["completed"]}["2.07"]
        self.assertEqual((sel["name"], sel["franchiseId"]), ("Morez Johnson Jr.", CC))  # the draft result is not rewritten

    def test_completed_in_season_trade_is_applied_exactly_once(self):
        t = self.si["tradeIndex"]["TXN-2026-001"]
        self.assertEqual((t["status"], t["phase"]), ("COMPLETED", "IN_SEASON"))
        self.assertEqual({(a["playerKey"], a["from"], a["to"]) for a in t["assets"]}, {(MOREZ, CC, HCMC), (ZION, HCMC, CC)})
        self.assertEqual((self.cur["playerOwner"][MOREZ], self.cur["playerOwner"][ZION]), (HCMC, CC))
        self.assertEqual(self.cur["activeTradeIds"].count("TXN-2026-001"), 1)
        # all-player sums move by exactly Zion's $12 (Morez is $0) ...
        self.assertEqual(sum(ls.player_cap(self.si, k) for k in ls.team_players(self.si, self.cur, CC)),
                         ls.team_cap(self.i, self.hist, CC) + 12)
        # ... and counted payroll (top 9 salaries) is CrazyCat 145, HCMC 133
        self.assertEqual((ls.team_cap(self.si, self.cur, CC), ls.team_cap(self.si, self.cur, HCMC)), (145, 133))
        self.assertNotIn("TXN-2026-001", self.i["tradeIndex"])                      # never part of the pre-draft ledger

    def test_completed_trade_with_wrong_owner_is_refused(self):
        si = copy.deepcopy(self.si)
        si["tradeIndex"]["TXN-2026-001"]["assets"][0]["from"] = HCMC  # Morez was CrazyCat's, not HCMC's
        si["seasonTxns"] = [si["tradeIndex"][t["txnId"]] for t in si["seasonTxns"]]
        with self.assertRaises(ls.StateError):
            ss.season_state(si)

    def test_proposals_are_isolated_from_the_current_state(self):
        before = ss._load(ss.TXN_PATH)
        views = ss.enumerate_views(self.si)
        self.assertEqual(ss._load(ss.TXN_PATH), before)  # enumerating writes nothing
        self.assertEqual(sorted(views), [""])  # both Bsy trades are completed: nothing is left to simulate
        cur = ss.season_state(self.si)
        for k, f in ((WEMBY, THINH), (TYSON, THINH), (JOKIC, BSY), (OSO, BSY)):
            self.assertEqual(cur["playerOwner"][k], f)                       # both completed trades are in the baseline
        data = json.loads(bls.re.search(r'id="league-data">(.*?)</script>', _read_html(), bls.re.S).group(1).replace("<\\/", "</"))
        live = ss.enumerate_views(ss.load_season(ls.load_inputs()))          # the page renders the live state
        self.assertEqual(data["official"]["teams"], live[""]["teams"])
        self.assertEqual(data["official"]["tradeIds"], ["TXN-2026-001", "PROP-2026-001", "PROP-2026-002"])
        for done in ("TXN-2026-001", "PROP-2026-001", "PROP-2026-002"):
            with self.assertRaises(ls.StateError):
                ss.season_state(self.si, [done])                               # completed is not a scenario

    def test_no_pending_proposals_remain_and_scenarios_start_from_the_updated_baseline(self):
        self.assertEqual(ss.selectable(self.si), [])
        base = ss.season_view(self.si, [])
        self.assertEqual({f: base["teams"][f]["cap"] for f in (BSY, THINH, SUP)}, {BSY: 176, THINH: 176, SUP: 144})
        self.assertEqual(sum(t["count"] for t in base["teams"].values()), 192)     # players move, none appear or vanish
        self.assertEqual(set(base["trades"]), {"TXN-2026-001", "PROP-2026-001", "PROP-2026-002"})

    def test_bsy_thinh_direction_is_the_ownership_consistent_one(self):
        t = self.si["tradeIndex"]["PROP-2026-002"]
        self.assertEqual(t["status"], "COMPLETED")
        self.assertEqual(t["directionCheck"]["status"], "RESOLVED_ASSUMED_STAGED_DIRECTION")
        hist = ls.resolve(self.i, (), "OFFICIAL")
        for a in t["assets"]:
            self.assertEqual(hist["playerOwner"][a["playerKey"]], a["from"])

    def test_in_season_rule_allows_moves_toward_the_band(self):
        self.assertEqual(ls.in_season_cap_checks(self.si, DT, 124, 128)[0]["code"], "CAP_STILL_OUTSIDE_BAND")
        self.assertEqual(ls.in_season_cap_checks(self.si, DT, 124, 120)[0]["detail"]["ladder"], "OVER_5")
        self.assertEqual(ls.in_season_cap_checks(self.si, DT, 131, 126)[0]["detail"]["ladder"], "EXACTLY_5")
        self.assertEqual(ls.in_season_cap_checks(self.si, DT, 124, 135), [])
        self.assertTrue(ss.trade_toward_band(self.si, self.cur, DT, +3)["ok"])
        self.assertFalse(ss.trade_toward_band(self.si, self.cur, DT, -2)["ok"])


class TestTopNineCounting(unittest.TestCase):
    """League owner, 2026-10-16: only the top 9 salaries on a roster count toward the cap, IL or not."""

    @classmethod
    def setUpClass(cls):
        cls.i = ls.load_inputs()
        cls.si = draft_night(ss.load_season(cls.i))
        cls.cur = ss.season_state(cls.si)

    def test_policy_and_counted_payroll(self):
        pc = self.i["policy"]["payrollCounting"]
        self.assertEqual((pc["rule"], pc["n"], pc["includesIL"]), ("TOP_N_SALARIES", 9, True))
        self.assertEqual(self.si["capCountTop"], 9)
        for f in self.si["franchises"]:
            caps = sorted((ls.player_cap(self.si, k) for k in ls.team_players(self.si, self.cur, f)), reverse=True)
            self.assertEqual(ls.team_cap(self.si, self.cur, f), sum(caps[:9]))
            rep = ls.team_report(self.si, self.cur, f, self.cur)
            self.assertEqual([r["x"] for r in rep["roster"]], [i >= 9 for i in range(len(rep["roster"]))])
            self.assertEqual(rep["cap"], sum(r["c"] for r in rep["roster"] if not r["x"]))
        self.assertEqual({self.si["shorts"][f]: ls.team_cap(self.si, self.cur, f) for f in (CC, "franchise-04", DT)},
                         {"CrazyCat": 145, "LC": 161, "DonTrick": 123})

    def test_il_players_still_count(self):
        cur = copy.deepcopy(self.cur)
        top = max(ls.team_players(self.si, cur, BSY), key=lambda k: ls.player_cap(self.si, k))
        cur["slots"][top] = "IL"
        self.assertEqual(ls.team_cap(self.si, cur, BSY), ls.team_cap(self.si, self.cur, BSY))

    def test_history_keeps_all_player_totals(self):
        hist = ls.resolve(self.i, (), "OFFICIAL")
        self.assertIsNone(self.i.get("capCountTop"))
        self.assertEqual(ls.team_cap(self.i, hist, DT), 124)          # draft-night record as computed at the time
        self.assertEqual(ls.draft_summary(self.i, hist)["completed"][-1]["capAfter"], 174)

    def test_trade_check_uses_counted_payroll(self):
        r = [x for x in self.cur_state()["tradeResults"] if x["tradeId"] == "PROP-2026-002"][0]
        self.assertEqual((r["teams"][BSY]["capBefore"], r["teams"][BSY]["capAfter"]), (175, 176))  # starts after the sup fam deal
        self.assertEqual((r["teams"][THINH]["capBefore"], r["teams"][THINH]["capAfter"]), (177, 176))

    def cur_state(self):
        return ss.season_state(self.si)


class TestBsyTradesCompleted(unittest.TestCase):
    """PROP-2026-001 (Bsy <-> sup fam) and PROP-2026-002 (Bsy <-> Thinh) were promoted to COMPLETED in place."""

    @classmethod
    def setUpClass(cls):
        cls.i = ls.load_inputs()
        cls.si = draft_night(ss.load_season(cls.i))
        cls.hist = ls.resolve(cls.i, (), "OFFICIAL")
        cls.cur = ss.season_state(cls.si)

    def test_records_are_promoted_in_place_with_an_audit_trail(self):
        ids = [t["txnId"] for t in self.si["seasonTxns"]]
        self.assertEqual(ids, ["TXN-2026-001", "PROP-2026-001", "PROP-2026-002"])      # no duplicate records
        for tid in ("PROP-2026-001", "PROP-2026-002"):
            t = self.si["tradeIndex"][tid]
            self.assertEqual((t["status"], t["phase"]), ("COMPLETED", "IN_SEASON"))
            self.assertEqual([h["status"] for h in t["statusHistory"]], ["PROPOSED", "COMPLETED"])
            self.assertEqual(t["effectiveAt"], "2026-10-18T00:00:00Z")                  # dated to the report, as for TXN-2026-001
            self.assertEqual((t["approvedOn"], t["approvedOnSource"]), ("2026-10-17", "owner-reported"))
            self.assertIn("not supplied", t["source"])                                   # no invented Yahoo time or id
            self.assertNotIn("yahooTransactionId", t)

    def test_confirmed_directions_and_final_ownership(self):
        sup = self.si["tradeIndex"]["PROP-2026-001"]
        self.assertEqual({(a["name"], a["from"], a["to"]) for a in sup["assets"]},
                         {("Stephon Castle", BSY, SUP), ("Ajay Mitchell", BSY, SUP), ("Cedric Coward", SUP, BSY), ("Joan Beringer", SUP, BSY)})
        thinh = self.si["tradeIndex"]["PROP-2026-002"]
        self.assertEqual({(a["name"], a["from"], a["to"]) for a in thinh["assets"]},
                         {("Victor Wembanyama", BSY, THINH), ("Jaylon Tyson", BSY, THINH), ("Nikola Jokić", THINH, BSY), ("Oso Ighodaro", THINH, BSY)})
        final = {CASTLE: SUP, MITCHELL: SUP, COWARD: BSY, BERINGER: BSY, WEMBY: THINH, TYSON: THINH, JOKIC: BSY, OSO: BSY}
        start = {CASTLE: BSY, MITCHELL: BSY, COWARD: SUP, BERINGER: SUP, WEMBY: BSY, TYSON: BSY, JOKIC: THINH, OSO: THINH}
        for k in final:
            self.assertEqual(self.cur["playerOwner"][k], final[k])
            self.assertEqual(self.hist["playerOwner"][k], start[k])                     # draft-night history untouched
        for tid in ("PROP-2026-001", "PROP-2026-002"):
            r = [x for x in self.cur["tradeResults"] if x["tradeId"] == tid][0]
            self.assertTrue(r["applied"] and not r["errors"] and r["warnings"] == [])

    def test_bsy_thinh_uses_the_only_ownership_consistent_direction(self):
        t = self.si["tradeIndex"]["PROP-2026-002"]
        self.assertEqual(t["directionCheck"]["status"], "RESOLVED_ASSUMED_STAGED_DIRECTION")
        for a in t["assets"]:   # every sender really owned the asset in the baseline BEFORE this trade
            self.assertEqual(self.hist["playerOwner"][a["playerKey"]], a["from"])
        self.assertIn("NOT specified", t["source"])                                         # the assumption is recorded, not hidden

    def test_payroll_uses_top_nine_and_frozen_salaries(self):
        self.assertEqual({f: self.cur_cap(f) for f in (BSY, SUP, THINH, CC, HCMC)}, {BSY: 176, SUP: 144, THINH: 176, CC: 145, HCMC: 133})
        for f in (BSY, SUP, THINH):
            caps = sorted((ls.player_cap(self.si, k) for k in ls.team_players(self.si, self.cur, f)), reverse=True)
            self.assertEqual(self.cur_cap(f), sum(caps[:9]))
        self.assertEqual((ls.player_cap(self.si, CASTLE), ls.player_cap(self.si, WEMBY), ls.player_cap(self.si, JOKIC)), (13.0, 60.0, 61.0))
        self.assertEqual({f: len(ls.team_players(self.si, self.cur, f)) for f in (BSY, SUP, THINH)}, {BSY: 12, SUP: 12, THINH: 12})
        self.assertEqual([ls.cap_status(self.si, self.cur_cap(f)) for f in (BSY, SUP, THINH)], ["NEAR_CEILING", "IN_RANGE", "NEAR_CEILING"])

    def cur_cap(self, f):
        return ls.team_cap(self.si, self.cur, f)

    def test_combined_final_state_and_no_double_processing(self):
        owners = self.cur["playerOwner"]
        self.assertEqual(len(owners), 192)                                                 # nobody appears or disappears
        self.assertEqual(self.cur["activeTradeIds"], ["TXN-2026-001", "PROP-2026-001", "PROP-2026-002"])  # each exactly once
        again = ss.season_state(draft_night(ss.load_season(ls.load_inputs())))              # a rebuild gives the same state
        self.assertEqual(again["playerOwner"], owners)
        self.assertEqual((owners[MOREZ], owners[ZION]), (HCMC, CC))                         # the earlier completed trade still stands
        self.assertEqual(ss.selectable(self.si), [])                                        # nothing pending
        self.assertEqual(sorted(ss.enumerate_views(self.si)), [""])

    def test_applying_the_same_trade_twice_fails_loudly(self):
        si = copy.deepcopy(self.si)
        dup = copy.deepcopy(si["tradeIndex"]["PROP-2026-001"])
        dup.update({"txnId": "DUP", "tradeId": "DUP", "order": 2000})
        si["tradeIndex"]["DUP"] = dup
        si["seasonTxns"] = si["seasonTxns"] + [dup]
        with self.assertRaises(ls.StateError):
            ss.season_state(si)                                                             # senders no longer own the assets

    def test_historical_layers_are_preserved(self):
        snap = ss._load(ss.POST_DRAFT_PATH)
        self.assertEqual(snap, ss.make_post_draft_snapshot(self.i, "2026-10-14"))
        self.assertEqual((snap["draftSelections"], snap["rookies"]), (48, 19))
        self.assertEqual(self.hist["activeTradeIds"], ["TRADE-A", "TRADE-B", "TRADE-C", "TRADE-D", "TRADE-E", "TRADE-F", "TRADE-D-AMEND"])
        self.assertEqual(self.hist["playerOwner"][MOREZ], CC)                               # draft-night owner of Morez
        self.assertEqual(ls.team_cap(self.i, self.hist, DT), 124)
        f = ss.checkpoint_findings(self.si)
        self.assertEqual([(x["short"], x["shortfall"]) for x in f], [("DonTrick", 8)])      # DonTrick finding intact
        idx = ss._load(ss.ROSTER_INDEX)
        self.assertEqual((idx["history"][0]["snapshotId"], idx["history"][0]["action"]), (DRAFT_NIGHT, "INIT"))
        dn = ss._load(os.path.join(ss.ROSTER_DIR, "snapshots", DRAFT_NIGHT + ".json"))
        self.assertEqual(dn["digest"], idx["history"][0]["digest"])                         # never rewritten by later imports

    def test_public_page_shows_completed_history_not_pending_and_no_internal_notes(self):
        data = json.loads(bls.re.search(r'id="league-data">(.*?)</script>', _read_html(), bls.re.S).group(1).replace("<\\/", "</"))
        by = {t["id"]: t for t in data["trades"]}
        self.assertEqual((by["PROP-2026-001"]["status"], by["PROP-2026-002"]["status"]), ("COMPLETED", "COMPLETED"))
        self.assertEqual(sorted(data["scenarios"]), [""])
        blob = json.dumps(data)
        for internal in ("statusHistory", "directionCheck", "not supplied", "relayed", "DISCREPANCY", "NOT specified", "RESOLVED_ASSUMED"):
            self.assertNotIn(internal, blob)


class TestVerifiedYahooImport(unittest.TestCase):
    """The live state after the 2026-10-19 Yahoo import: the snapshot already contains the three completed trades."""

    @classmethod
    def setUpClass(cls):
        cls.si = ss.load_season(ls.load_inputs())
        cls.cur = ss.season_state(cls.si)

    def test_snapshot_is_the_reviewed_yahoo_import(self):
        snap = self.si["rosterSnapshot"]
        self.assertEqual(snap["kind"], "VERIFIED_IMPORT")
        self.assertIn("Yahoo Fantasy league 85092", snap["source"])
        self.assertEqual(ss.pending_completed(self.si), [])
        self.assertEqual([t["txnId"] for t in ss.reflected_completed(self.si)][:3], ["TXN-2026-001", "PROP-2026-001", "PROP-2026-002"])

    def test_reflected_trades_are_history_not_reapplied(self):
        self.assertEqual(self.cur["playerOwner"], ss.snapshot_owner(self.si["rosterSnapshot"]))   # ownership = the snapshot
        self.assertEqual(self.cur["activeTradeIds"][:3], ["TXN-2026-001", "PROP-2026-001", "PROP-2026-002"])  # each once, in ledger order
        self.assertEqual(len(self.cur["activeTradeIds"]), len(set(self.cur["activeTradeIds"])))
        res = {r["tradeId"]: r for r in self.cur["tradeResults"]}
        self.assertTrue(all(r["reflected"] and r["applied"] for r in res.values()))
        self.assertEqual((res["PROP-2026-001"]["teams"][BSY]["capBefore"], res["PROP-2026-001"]["teams"][BSY]["capAfter"]), (178, 175))
        self.assertEqual((res["PROP-2026-002"]["teams"][BSY]["capBefore"], res["PROP-2026-002"]["teams"][BSY]["capAfter"]), (175, 176))
        self.assertEqual(self.cur["history"]["player:" + JOKIC][0], {"tradeId": "PROP-2026-002", "from": THINH, "to": BSY})

    def test_counts_payroll_and_moves(self):
        # Rosters change with every Yahoo update; everything is derived from the CURRENT snapshot.
        snap_owner = ss.snapshot_owner(self.si["rosterSnapshot"])
        self.assertEqual(self.cur["playerOwner"], snap_owner)
        view = ss.season_view(self.si)["teams"]
        self.assertEqual(sum(v["count"] for v in view.values()), len(snap_owner))     # nobody appears or vanishes
        for f in self.si["franchises"]:
            caps = sorted((ls.player_cap(self.si, k) for k in ls.team_players(self.si, self.cur, f)), reverse=True)
            self.assertEqual(ls.team_cap(self.si, self.cur, f), sum(caps[:9]), f)        # top 9 of everyone, IL included
        for f, v in view.items():
            il = [r for r in v["roster"] if r["s"] in ss.SLOTS_IL]
            self.assertEqual(v["il"], len(il), f)
            self.assertEqual(v["ilCap"], sum(r["c"] for r in il if not r["x"]), f)         # only IL salaries inside the counted nine
            self.assertEqual(v["healthyCap"], v["cap"] - v["ilCap"], f)
            self.assertFalse({a["k"] for a in v["added"]} & set(v["inKeys"]), f)            # a pickup is not a trade acquisition
            self.assertFalse({a["k"] for a in v["dropped"]} & set(v["outKeys"]) - {a["k"] for a in v["dropped"]}, f)
        for t in self.si["seasonTxns"]:                                                      # completed trades: shown as trade acquisitions
            if t["status"] == "COMPLETED":
                for a in t["assets"]:
                    if a["type"] == "player" and self.cur["playerOwner"].get(a["playerKey"]) == a["to"]:
                        self.assertIn(a["playerKey"], view[a["to"]]["inKeys"], (t["txnId"], a["name"]))


class TestFrozenSalaries(unittest.TestCase):
    def test_payroll_ignores_a_refreshed_yahoo_registry(self):
        i = ls.load_inputs()
        si = ss.load_season(i)
        cur = ss.season_state(si)
        before = {f: ls.team_cap(si, cur, f) for f in si["franchises"]}
        si2 = dict(si)
        si2["registry"] = {k: {**p, "projectedAuctionValue": p["projectedAuctionValue"] + 7} for k, p in si["registry"].items()}
        self.assertEqual({f: ls.team_cap(si2, cur, f) for f in si["franchises"]}, before)

    def test_freeze_digest_and_coverage(self):
        doc = ss._load(ss.SALARY_PATH)
        self.assertEqual(doc["digest"], ls._digest(doc["salaries"]))
        i = ls.load_inputs()
        cur = ss.season_state(ss.load_season(i))
        # every owned player has a frozen salary, or is an unlisted player at the league-rule 0 (owner, 2026-10-19)
        self.assertFalse([k for k in cur["playerOwner"] if k not in doc["salaries"] and k not in i["unlistedPlayers"]])
        self.assertFalse(set(i["unlistedPlayers"]) & set(doc["salaries"]))
        self.assertTrue(all(p["cap"] == 0 for p in i["unlistedPlayers"].values()))
        for k in i["extraPlayers"]:
            self.assertEqual(doc["salaries"][k], 0.0)


class TestCapCheckpoints(unittest.TestCase):
    def test_dontrick_post_draft_finding_is_derived_not_hardcoded(self):
        si = ss.load_season(ls.load_inputs())
        f = ss.checkpoint_findings(si)
        self.assertEqual([x["short"] for x in f], ["DonTrick"])
        x = f[0]
        snap = ss._load(ss.POST_DRAFT_PATH)
        dt_keys = [k for k, f in snap["playerOwner"].items() if f == DT]
        top9 = sum(sorted((ls.player_cap(si, k) for k in dt_keys), reverse=True)[:9])
        self.assertEqual(x["shortfall"], snap["capBand"]["floor"] - top9)       # from the checkpoint's ownership
        self.assertEqual((x["capAtCheckpoint"], x["floor"], x["shortfall"], x["checkpointDate"]), (123, 131, 8, "2026-10-14"))
        self.assertEqual(snap["teamCaps"][DT], 124)  # the checkpoint file itself (all players) is never rewritten
        want = "IMPROVING" if x["currentCap"] > x["capAtCheckpoint"] else ("WORSENING" if x["currentCap"] < x["capAtCheckpoint"] else "UNCHANGED")
        self.assertEqual((x["status"], x["penalty"], x["direction"]), ("FINDING_RECORDED", None, want))   # follows today's payroll
        self.assertFalse(x["deadlineCheckpoint"]["recorded"])

    def test_finding_survives_improvement_and_repeat_goes_to_review(self):
        with TempData() as td:
            doc = ss._load(os.path.join(td.dir, "season_transactions.json"))
            si = td.si()  # a hypothetical completed deal: DonTrick sends a $0 player for a $10 one
            cur = ss.season_state(si)
            dt_players = [k for k, o in cur["playerOwner"].items() if o == DT]
            other, partner = next((k, o) for k, o in sorted(cur["playerOwner"].items()) if o != DT and ls.player_cap(si, k) == 10)
            give = next(k for k in dt_players if ls.player_cap(si, k) == 0)
            doc["transactions"].append({"txnId": "TXN-TEST", "type": "TRADE", "status": "COMPLETED", "label": "TEST",
                                        "participants": [DT, partner], "effectiveAt": "2026-10-20T00:00:00Z",
                                        "assets": [{"type": "player", "playerKey": give, "from": DT, "to": partner},
                                                   {"type": "player", "playerKey": other, "from": partner, "to": DT}]})
            ss._write(os.path.join(td.dir, "season_transactions.json"), doc)
            x = ss.checkpoint_findings(td.si())[0]
            self.assertEqual((x["short"], x["shortfall"], x["currentCap"], x["direction"]), ("DonTrick", 8, 130, "IMPROVING"))
            self.assertEqual(x["currentGap"], 1)                    # closer to the floor; the finding stays on record
            # a later post-deadline checkpoint with DonTrick under the floor again -> commissioner review
            snap = ss.make_checkpoint_snapshot(td.si(), "POST_TRADE_DEADLINE", "2027-02-20")  # DonTrick at 130
            ss._write(os.path.join(td.dir, "snapshots", "POST_TRADE_DEADLINE.json"), snap)
            cp = ss._load(os.path.join(td.dir, "cap_checkpoints.json"))
            cp["checkpoints"][1].update({"date": "2027-02-20", "snapshot": "snapshots/POST_TRADE_DEADLINE.json", "status": "RECORDED"})
            ss._write(os.path.join(td.dir, "cap_checkpoints.json"), cp)
            x = ss.checkpoint_findings(td.si())[0]
            self.assertEqual((x["status"], x["deadlineCheckpoint"]["cap"], x["improvedSinceCheckpoint"], x["penalty"]),
                             ("REPEAT_UNDER_FLOOR_REVIEW", 130, True, None))  # improvement noted; nothing applied


class TestCheckpointRecording(unittest.TestCase):
    def test_deadline_checkpoint_snapshot_feeds_the_findings(self):
        with TempData() as td:
            si = td.si()
            snap = ss.make_checkpoint_snapshot(si, "POST_TRADE_DEADLINE", "2027-02-20")
            self.assertEqual(snap["teamCaps"][DT], 123)
            self.assertEqual(snap["countingRule"], {"rule": "TOP_N_SALARIES", "n": 9})
            self.assertEqual(snap["checkpoint"]["completedTransactions"], ["TXN-2026-001", "PROP-2026-001", "PROP-2026-002"])
            ss._write(os.path.join(td.dir, "snapshots", "POST_TRADE_DEADLINE.json"), snap)
            cp = ss._load(os.path.join(td.dir, "cap_checkpoints.json"))
            cp["checkpoints"][1].update({"date": "2027-02-20", "snapshot": "snapshots/POST_TRADE_DEADLINE.json", "status": "RECORDED"})
            ss._write(os.path.join(td.dir, "cap_checkpoints.json"), cp)
            x = ss.checkpoint_findings(td.si())[0]
            self.assertEqual((x["status"], x["improvedSinceCheckpoint"], x["penalty"]), ("REPEAT_UNDER_FLOOR_REVIEW", False, None))


class TestRosterImport(unittest.TestCase):
    def test_round_trip_is_a_no_op_and_reflects_the_completed_trade(self):
        with TempData() as td:
            si = td.si()
            snap, rep = ir.build_snapshot(si, ir.parse(td.csv(export_rows(si))), "2026-10-19T12:00:00Z", "test", td.dir)
            self.assertEqual(rep["blocking"], [])
            d = ir.diff(si, snap)
            self.assertEqual((d["added"], d["dropped"], d["changedTeam"], d["unchanged"]), ([], [], [], 192))
            self.assertEqual([(t["txnId"], t["reflected"]) for t in d["transactions"]], [("TXN-2026-001", True), ("PROP-2026-001", True), ("PROP-2026-002", True)])
            ir.commit(si, snap, rep, d, td.dir, reviewed=True)
            si2 = td.si()
            self.assertEqual(ss.pending_completed(si2), [])           # now reflected in the snapshot: not re-applied
            self.assertEqual([t["txnId"] for t in ss.reflected_completed(si2)], ["TXN-2026-001", "PROP-2026-001", "PROP-2026-002"])
            cur = ss.season_state(si2)
            self.assertEqual((cur["playerOwner"][MOREZ], cur["playerOwner"][ZION]), (HCMC, CC))
            self.assertEqual(ls.team_cap(si2, cur, CC), 145)            # exactly once, before and after the import
            self.assertEqual((ls.team_cap(si2, cur, BSY), ls.team_cap(si2, cur, SUP), ls.team_cap(si2, cur, THINH)), (176, 144, 176))

    def test_diff_categories_and_commit_rollback(self):
        with TempData() as td:
            si = td.si()
            rows = export_rows(si)
            fa = next(k for k in si["registry"] if k not in ss.season_state(si)["playerOwner"])
            rows = [r for r in rows if r[1] != "478.p.5187"]                                # Dennis Schröder dropped by Bsy
            rows.append(["Thịnh", fa, "", si["registry"][fa]["name"], "BN"])                # FA added
            for r in rows:
                if r[1] == WEMBY:
                    r[4] = "IL"                                                             # IL move
                if r[1] == CASTLE:
                    r[4] = "BN"
            first, rep = ir.build_snapshot(si, ir.parse(td.csv(rows)), "2026-10-18T00:00:00Z", "first", td.dir)
            ir.commit(si, first, rep, ir.diff(si, first), td.dir, reviewed=True)
            si = td.si()
            rows2 = [list(r) for r in rows]
            for r in rows2:
                if r[1] == CASTLE:
                    r[4] = "SG"                                                             # lineup-only
                if r[1] == WEMBY:
                    r[4] = "C"                                                              # back from IL
                if r[1] == TYSON:
                    r[0] = "sup fam"                                                        # team change
            snap, rep = ir.build_snapshot(si, ir.parse(td.csv(rows2, "r2.csv")), "2026-10-19T00:00:00Z", "second", td.dir)
            d = ir.diff(si, snap)
            self.assertEqual([x["player"] for x in d["lineupOnly"]], ["Stephon Castle"])
            self.assertEqual([(x["player"], x["from"], x["to"]) for x in d["ilMoves"]], [("Victor Wembanyama", "IL", "C")])
            self.assertEqual([(x["player"], x["from"], x["to"]) for x in d["changedTeam"]], [("Jaylon Tyson", "Thịnh", "sup fam")])
            # first import's add/drop came through as ownership changes
            d0 = ir.diff(ss.load_season(ls.load_inputs(data_dir=td.dir), data_dir=td.dir), first)
            self.assertEqual(d0["added"] + d0["dropped"], [])                                # already current
            ir.commit(si, snap, rep, d, td.dir, reviewed=True)
            with self.assertRaises(ir.ImportBlocked):                                        # same content again
                ir.commit(td.si(), snap, rep, d, td.dir, reviewed=True)
            back = ir.rollback(td.dir)
            self.assertIn(first["snapshotId"], back)
            self.assertEqual(ss.season_state(td.si())["playerOwner"][TYSON], THINH)
            self.assertTrue(os.path.exists(os.path.join(td.dir, "rosters", "snapshots", snap["snapshotId"] + ".json")))  # retained

    def test_first_import_reports_adds_and_drops(self):
        with TempData() as td:
            si = td.si()
            rows = [r for r in export_rows(si) if r[1] != "478.p.10313"]
            fa = next(k for k in si["registry"] if k not in ss.season_state(si)["playerOwner"])
            rows.append(["Thịnh", fa, "", si["registry"][fa]["name"], "BN"])
            snap, rep = ir.build_snapshot(si, ir.parse(td.csv(rows)), "2026-10-18T00:00:00Z", "t", td.dir)
            d = ir.diff(si, snap)
            self.assertEqual([x["key"] for x in d["dropped"]], ["478.p.10313"])
            self.assertEqual([x["key"] for x in d["added"]], [fa])

    def test_blocking_problems(self):
        with TempData() as td:
            si = td.si()
            base = export_rows(si)
            cases = {
                "UNMATCHED_PLAYER": base + [["Bsy", "", "", "Nobody Real", "BN"]],   # no Yahoo id, unknown name
                "UNMATCHED_TEAM": base + [["Not A Team", WEMBY, "", "Victor Wembanyama", ""]],
                "DUPLICATE_OWNERSHIP": base + [["TT", WEMBY, "", "Victor Wembanyama", ""]],
                "TEAM_MISSING": [r for r in base if r[0] != "TT"],
                "UNKNOWN_SLOT": [r if r[1] != WEMBY else r[:4] + ["BENCHWARMER"] for r in base],
            }
            for code, rows in cases.items():
                snap, rep = ir.build_snapshot(si, ir.parse(td.csv(rows)), "2026-10-18T00:00:00Z", "t", td.dir)
                self.assertIn(code, [b["code"] for b in rep["blocking"]], code)
                with self.assertRaises(ir.ImportBlocked):
                    ir.commit(si, snap, rep, {"transactions": []}, td.dir, reviewed=True)
            snap, rep = ir.build_snapshot(si, ir.parse(td.csv(base)), "2026-10-14T00:00:00Z", "old", td.dir)
            with self.assertRaises(ir.ImportBlocked):                                        # not newer than current
                ir.commit(si, snap, rep, ir.diff(si, snap), td.dir, reviewed=True)
            snap, rep = ir.build_snapshot(si, ir.parse(td.csv(base)), "2026-10-18T00:00:00Z", "t", td.dir)
            with self.assertRaises(ir.ImportBlocked):                                        # review is explicit
                ir.commit(si, snap, rep, ir.diff(si, snap), td.dir, reviewed=False)
            # a snapshot dated after a completed trade that does not show it cannot be committed
            stale = [[r[0] if r[1] not in (MOREZ, ZION) else ("CrazyCat" if r[1] == MOREZ else "HCMC")] + r[1:] for r in base]
            snap, rep = ir.build_snapshot(si, ir.parse(td.csv(stale)), "2026-10-18T00:00:00Z", "t", td.dir)
            d = ir.diff(si, snap)
            self.assertEqual(d["transactions"][0]["reflected"], False)
            with self.assertRaises(ir.ImportBlocked):
                ir.commit(si, snap, rep, d, td.dir, reviewed=True)

    def test_player_resolution_by_key_id_alias_and_name(self):
        with TempData() as td:
            si = td.si()
            al = {}
            self.assertEqual(ir.resolve_player(si, al, {"playerKey": WEMBY, "name": "x"})[:2], (WEMBY, "KEY"))
            self.assertEqual(ir.resolve_player(si, al, {"playerId": "10094", "name": "x"})[:2], (WEMBY, "KEY"))
            self.assertEqual(ir.resolve_player(si, {"Wemby": WEMBY}, {"name": "Wemby"})[:2], (WEMBY, "ALIAS"))
            self.assertEqual(ir.resolve_player(si, al, {"name": "Victor Wembanyama"})[:2], (WEMBY, "NAME"))
            # a Yahoo id outside the frozen table is an unlisted player at the league-rule salary 0 (2026-10-19)
            self.assertEqual(ir.resolve_player(si, al, {"playerKey": "478.p.999999", "name": "Nobody"})[:2], ("478.p.999999", "UNLISTED"))
            self.assertIsNone(ir.resolve_player(si, al, {"name": "Nobody"})[0])     # no id, unknown name: still blocks


class TestProvisionalPlayers(unittest.TestCase):
    def test_audit_count_is_six(self):
        i = ls.load_inputs()
        self.assertEqual(sorted(p["name"] for p in i["extraPlayers"].values()),
                         ["Bennett Stirtz", "Cameron Carr", "Dailyn Swain", "Hannes Steinbach", "Nate Ament", "Sergio de Larrea"])
        drafted = {e["playerKey"]: e for e in i["draft"]["events"]}
        for k in i["extraPlayers"]:
            self.assertTrue(drafted[k]["rookie"])                                            # all six were rookie picks
            self.assertNotIn(k, i["registry"])

    def test_linking_a_yahoo_id_keeps_the_drafted_identity(self):
        with TempData() as td:
            si = td.si()
            rows = [r if r[1] != "provisional:dailyn-swain" else [r[0], "478.p.77777", "", "Dailyn Swain", ""] for r in export_rows(si)]
            snap, rep = ir.build_snapshot(si, ir.parse(td.csv(rows)), "2026-10-18T00:00:00Z", "t", td.dir)
            self.assertIn("PROVISIONAL_LINK_CANDIDATE", [w["code"] for w in rep["warnings"]])
            self.assertIn({"playerKey": "provisional:dailyn-swain", "name": "Dailyn Swain", "slot": None}, snap["teams"][DT])
            ir.link_provisional(td.dir, "provisional:dailyn-swain", "478.p.77777", si["registry"])
            si = td.si()
            self.assertEqual(ir.resolve_player(si, {}, {"playerKey": "478.p.77777", "name": "D. Swain"})[:2],
                             ("provisional:dailyn-swain", "PROVISIONAL_LINK"))
            hist = ls.resolve(si, (), "OFFICIAL")
            d = ls.draft_summary(si, hist)
            self.assertEqual((len(d["completed"]), d["rookies"]), (48, 19))                  # no new player, count unchanged
            self.assertEqual(ls.player_cap(si, "provisional:dailyn-swain"), 0.0)              # frozen draft salary kept
            with self.assertRaises(ir.ImportBlocked):                                        # a key with its own identity
                ir.link_provisional(td.dir, "provisional:nate-ament", WEMBY, si["registry"])
            with self.assertRaises(ir.ImportBlocked):                                        # already linked elsewhere
                ir.link_provisional(td.dir, "provisional:nate-ament", "478.p.77777", si["registry"])


if __name__ == "__main__":
    unittest.main()
