import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_fa_draft_pool as pool  # noqa: E402
import build_league_state as bls  # noqa: E402
import league_state as ls  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _proposed import proposed_inputs  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
BSY, DUNG, LC, MELO, SUP, BZ = ("franchise-01", "franchise-06", "franchise-04", "franchise-03", "franchise-12", "franchise-15")


def _html():
    with open(os.path.join(REPO_ROOT, "index.html"), encoding="utf-8") as f:
        return f.read()


class TestRepoState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.o = ls.load_inputs()          # production: trades are OFFICIAL
        cls.i = proposed_inputs(cls.o)    # same definitions, selectable -> exercises the scenario engine

    def _scn(self, *ids):
        return ls.resolve(self.i, list(ids), "SCENARIO")

    # ----- registry / identity
    def test_registry_is_expanded_beyond_the_fa60(self):
        self.assertGreater(len(self.i["registry"]), 300)
        self.assertGreaterEqual(len(self.i["registry"]), 600)

    def test_registry_identity_is_the_stable_yahoo_player_key(self):
        reg = self.i["registry"]
        self.assertEqual(len(reg), len({p["playerId"] for p in reg.values()}))
        for key, p in reg.items():
            self.assertEqual(key, p["playerKey"])
            self.assertEqual(p["playerKey"], f"478.p.{p['playerId']}")
        self.assertEqual(reg["478.p.5352"]["name"], "Nikola Jokić")

    def test_trade_assets_reference_players_by_yahoo_key_and_name_matches(self):
        for t in self.i["trades"]["trades"]:
            for a in t["assets"]:
                if a["type"] == "player":
                    self.assertEqual(self.i["registry"][a["playerKey"]]["name"], a["name"])

    # ----- baseline
    def test_keeper_freeze_is_the_official_locked_baseline(self):
        f = self.i["freeze"]
        self.assertEqual(f["status"], "locked")
        self.assertTrue(f["lockedAt"])
        self.assertTrue(ls.verify_lock(f))
        self.assertNotIn("projected", f["statusNote"].lower())

    def test_baseline_matches_the_keeper_board_totals(self):
        html = _html()
        teams, _ = bls.parse_board(html)
        state = ls.initial_state(self.i)
        for fid, t in zip(sorted(self.i["franchises"]), teams):
            self.assertEqual(ls.team_cap(self.i, state, fid), sum(c for _, c in t["kept"]), t["short"])
            self.assertEqual(len(ls.team_players(self.i, state, fid)), len(t["kept"]))

    def test_picks_are_stable_ids_with_48_original_owners(self):
        picks = self.i["picks"]["picks"]
        self.assertEqual(len(picks), 48)
        self.assertEqual(picks[0]["pickId"], "2026-R1-01")
        self.assertEqual(self.i["pickIndex"]["2026-R1-03"]["originalOwner"], BSY)
        self.assertEqual(self.i["pickIndex"]["2026-R1-15"]["originalOwner"], BZ)

    def test_trade_ledger_is_official_and_processed_once_in_dependency_order(self):
        self.assertEqual({t["status"] for t in self.o["trades"]["trades"] if not t.get("amends")}, {"OFFICIAL"})
        official = ls.resolve(self.o, [], "OFFICIAL")
        self.assertEqual(official["activeTradeIds"], ["TRADE-A", "TRADE-B", "TRADE-C", "TRADE-D", "TRADE-E", "TRADE-F"])
        self.assertTrue(all(r["applied"] and not r["errors"] for r in official["tradeResults"]))
        self.assertEqual(len(official["tradeResults"]), 6)  # each transaction executed exactly once
        self.assertEqual(official["pickOwner"]["2026-R1-03"], SUP)  # Bsy -> Bz (A) -> sup fam (C)
        # repeated resolution is a pure replay: identical, never cumulative
        again = ls.resolve(self.o, [], "OFFICIAL")
        self.assertEqual((official["playerOwner"], official["pickOwner"]), (again["playerOwner"], again["pickOwner"]))
        # a processed trade cannot be re-applied as a scenario on top of the new baseline
        with self.assertRaises(ls.StateError):
            ls.resolve(self.o, ["TRADE-A"], "SCENARIO")

    # ----- Trades A / B / C
    def test_trade_a_ownership(self):
        s = self._scn("TRADE-A")
        self.assertEqual(s["pickOwner"]["2026-R1-03"], BZ)
        self.assertEqual(s["pickOwner"]["2026-R1-15"], BSY)
        self.assertEqual(s["playerOwner"]["478.p.5197"], BZ)   # Gobert
        self.assertEqual(s["playerOwner"]["478.p.5638"], BSY)  # Murray

    def test_trade_b_ownership(self):
        s = self._scn("TRADE-B")
        self.assertEqual(s["pickOwner"]["2026-R3-06"], BZ)
        self.assertEqual(s["pickOwner"]["2026-R3-03"], DUNG)  # Melo's original R3, held by Bz
        self.assertEqual(s["pickOwner"]["2026-R2-15"], MELO)  # untouched by Trade B
        self.assertEqual(s["playerOwner"]["478.p.6550"], BZ)    # F. Wagner
        self.assertEqual(s["playerOwner"]["478.p.6703"], DUNG)  # Duren

    def test_trade_c_chains_and_ownership(self):
        s = self._scn("TRADE-A", "TRADE-B", "TRADE-C")
        self.assertTrue(all(r["applied"] for r in s["tradeResults"]))
        self.assertEqual(s["pickOwner"]["2026-R1-03"], SUP)
        self.assertEqual(s["pickOwner"]["2026-R3-06"], SUP)
        self.assertEqual(s["pickOwner"]["2026-R3-12"], BZ)
        self.assertEqual([(h["from"], h["to"]) for h in s["history"]["pick:2026-R1-03"]], [(BSY, BZ), (BZ, SUP)])
        self.assertEqual([(h["from"], h["to"]) for h in s["history"]["pick:2026-R3-06"]], [(DUNG, BZ), (BZ, SUP)])

    def test_pick_table_current_and_original_columns(self):
        rows = {r["label"]: r for r in ls.pick_table(self.i, self._scn("TRADE-A", "TRADE-B", "TRADE-C"))}
        expect = {"1.03": (SUP, BSY), "1.15": (BSY, BZ), "3.03": (DUNG, MELO), "3.06": (SUP, DUNG), "3.12": (BZ, SUP)}
        for label, (cur, orig) in expect.items():
            self.assertEqual((rows[label]["current"], rows[label]["original"]), (cur, orig), label)

    def test_trade_c_without_upstream_is_a_broken_dependency(self):
        for sel in (["TRADE-C"], ["TRADE-A", "TRADE-C"], ["TRADE-B", "TRADE-C"]):
            s = self._scn(*sel)
            c = [r for r in s["tradeResults"] if r["tradeId"] == "TRADE-C"][0]
            self.assertFalse(c["applied"], sel)
            self.assertEqual([e["code"] for e in c["errors"]], ["BROKEN_DEPENDENCY"], sel)
            self.assertEqual(s["pickOwner"]["2026-R1-03"], BZ if "TRADE-A" in sel else BSY)

    # ----- BZ folded + chained cap
    def test_bz_folded_summary(self):
        s = self._scn("TRADE-A", "TRADE-B", "TRADE-C")
        fold = ls.fold_team(self.i, s, BZ)
        self.assertEqual(sorted(a["n"] for a in fold["in"]), sorted(["Rudy Gobert", "Franz Wagner", "Jalen Williams", "Reed Sheppard", "3.12"]))
        self.assertEqual(sorted(a["n"] for a in fold["out"]), sorted(["Jamal Murray", "Jalen Duren", "Julius Randle", "1.15", "3.03"]))
        self.assertEqual({p["asset"]["n"]: p["chain"] for p in fold["pass"]},
                         {"1.03": ["Bsy", "Bz", "sup fam"], "3.06": ["Dũng", "Bz", "sup fam"]})
        self.assertEqual(len(fold["tradeIds"]), 3)

    def test_bz_chained_cap_uses_the_previous_resulting_state(self):
        s = self._scn("TRADE-A", "TRADE-B", "TRADE-C")
        a, b, c = (r["teams"][BZ] for r in s["tradeResults"])
        base = ls.team_cap(self.i, ls.initial_state(self.i), BZ)
        self.assertEqual(a["capBefore"], base)
        self.assertEqual(b["capBefore"], a["capAfter"])
        self.assertEqual(c["capBefore"], b["capAfter"])
        self.assertEqual(a["playerCapDelta"], 11 - 40)
        self.assertEqual(b["playerCapDelta"], 21 - 27)
        self.assertEqual(c["playerCapDelta"], (26 + 1) - 14)
        self.assertEqual(c["capAfter"], base + (11 - 40) + (21 - 27) + ((26 + 1) - 14))
        self.assertEqual(c["roomToCeiling"], 178 - c["capAfter"])

    def test_cap_numbers_are_derived_not_stored(self):
        raw = json.dumps(self.i["trades"])
        for field in ("capAfter", "capBefore", "playerCapDelta", "roomToCeiling"):
            self.assertNotIn(field, raw)

    # ----- Trade D
    def test_trade_d_is_scenario_only_and_flags_asset_count(self):
        s = self._scn("TRADE-D")
        d = s["tradeResults"][0]
        self.assertTrue(d["applied"])  # still visualisable
        w = [x for x in d["warnings"] if x["code"] == "ASSET_COUNT_UNBALANCED"]
        self.assertEqual(w, [])  # 2-for-2 once the Gordon amendment is in (3.03 is not part of the trade)
        self.assertEqual(self.o["tradeIndex"]["TRADE-D"]["status"], "OFFICIAL")

    def test_trade_d_gordon_amendment_and_3_03_not_in_trade(self):
        base = ls.initial_state(self.i)
        legs = {(a["type"], a.get("playerKey") or a["pickId"], a["from"], a["to"]) for a in self.i["tradeIndex"]["TRADE-D"]["assets"]}
        self.assertEqual(len(legs), 4)  # Buzelis, 1.05, Sengun + Gordon; 3.03 is NOT part of the trade
        self.assertIn(("player", "478.p.5295", "franchise-04", "franchise-03"), legs)
        self.assertFalse([l for l in legs if l[1] == "2026-R3-03"])
        lc, melo = "franchise-04", "franchise-03"
        once = ls.resolve(self.i, ["TRADE-D"], "SCENARIO")
        again = ls.resolve(self.i, ["TRADE-D", "TRADE-D"], "SCENARIO")
        self.assertEqual(ls.team_players(self.i, once, melo).count("478.p.5295"), 1)
        self.assertNotIn("478.p.5295", ls.team_players(self.i, once, lc))
        self.assertNotIn("2026-R3-03", ls.team_picks(once, lc))
        self.assertNotIn("2026-R3-03", ls.team_picks(once, melo))
        self.assertEqual(once["pickOwner"]["2026-R3-03"], BZ)  # Bz holds it since the last-season swap
        self.assertEqual(ls.team_cap(self.i, once, lc), ls.team_cap(self.i, again, lc))
        g = ls.player_cap(self.i, "478.p.5295")
        self.assertEqual(g, 1.0)
        self.assertEqual(ls.team_cap(self.i, once, lc), ls.team_cap(self.i, base, lc) + 16 - 32 - g)
        self.assertEqual(ls.team_cap(self.i, once, melo), ls.team_cap(self.i, base, melo) - 16 + 32 + g)
        official = ls.resolve(self.i, [], "OFFICIAL")
        self.assertEqual(official["playerOwner"], base["playerOwner"])
        self.assertEqual(official["pickOwner"]["2026-R3-03"], BZ)

    # ----- historical (last-season) swaps, baked into the baseline
    def test_historical_swaps_in_the_baseline(self):
        o = ls.initial_state(self.i)  # keeper freeze + completed last-season swaps, before any 2026 trade
        MAX, HC = "franchise-07", "franchise-05"
        owner = o["pickOwner"]
        self.assertEqual((owner["2026-R2-15"], owner["2026-R3-03"]), (MELO, BZ))
        self.assertEqual((owner["2026-R2-07"], owner["2026-R3-05"]), (HC, MAX))
        def rounds(f):
            return sorted(int(k.split("-R")[1][0]) for k, v in owner.items() if v == f)
        self.assertEqual(rounds(MELO), [1, 2, 2])
        self.assertEqual(rounds(BZ), [1, 3, 3])
        self.assertEqual(rounds(HC), [1, 2, 2])
        self.assertEqual(rounds(MAX), [1, 3, 3])
        self.assertNotIn("2026-R2-15", ls.team_picks(o, BZ))
        # original owner is preserved, history is tagged historical
        self.assertEqual(self.i["pickIndex"]["2026-R2-15"]["originalOwner"], BZ)
        self.assertEqual(self.i["pickIndex"]["2026-R3-03"]["originalOwner"], MELO)
        row = {r["pickId"]: r for r in ls.pick_table(self.i, o)}["2026-R3-03"]
        self.assertEqual((row["original"], row["current"]), (MELO, BZ))
        self.assertTrue(row["history"][0]["historical"])

    def test_draft_order_ledger_shows_official_owner_and_via(self):
        panel = _html()
        panel = panel[panel.index('id="draft-order"'):panel.index('id="rosters-a"')]
        official = ls.resolve(self.o, [], "OFFICIAL")
        shorts = {t["franchiseId"]: t["short"] for t in self.o["freeze"]["teams"]}
        rows = re.findall(r'<div class="pick-slot">(\d+)\.(\d+)</div>\s*<div class="pick-team">(.*?)</div>\s*<div class="pick-note">(.*?)</div>', panel, re.S)
        self.assertEqual(len(rows), 48)
        teams, _ = bls.parse_board(_html())
        moved = 0
        for rnd, slot, chip, note in rows:
            pid = f"2026-R{rnd}-{int(slot):02d}"
            text = re.sub(r"<.*?>", "", chip).replace("\U0001F451", "").strip()
            owner = official["pickOwner"][pid]
            self.assertEqual(bls._team_for_chip(text, teams), list(shorts).index(owner), pid)
            via = re.search(r"VIA ([^<]+)<", note)
            orig = self.o["pickIndex"][pid]["originalOwner"]
            if owner != orig:
                moved += 1
                self.assertEqual(via.group(1).strip(), shorts[orig].upper(), pid)
            else:
                self.assertIsNone(via, pid)
        self.assertEqual(moved, sum(1 for p, o in official["pickOwner"].items() if o != self.o["pickIndex"][p]["originalOwner"]))
        self.assertEqual(moved, 11)
        self.assertEqual(bls.sync_ledger(_html(), self.o), _html())  # page ledger is in sync (idempotent)

    def test_official_reconciliation_audit(self):
        a = ls.audit_official(self.o)
        self.assertTrue(all(a["checks"].values()), a["checks"])
        t = {v["short"]: (v["cap"], v["count"]) for v in a["teams"].values()}
        # post-trade caps + the 19 drafted players (counts include draftees)
        self.assertEqual(t, {"Bsy": (178, 11), "CrazyCat": (131, 10), "Melo": (157, 11), "LC": (161, 10), "HCMC": (145, 11),
                             "Dũng": (132, 10), "Maxfixe": (149, 10), "DHA": (154, 10), "Đạt": (174, 10), "DonTrick": (123, 10),
                             "Thịnh": (177, 10), "sup fam": (141, 10), "Quân": (163, 10), "TuLy": (148, 10), "Bz": (156, 10), "TT": (174, 10)})
        # violations are surfaced, not corrected
        codes = sorted({v["code"] for v in a["violations"]})
        self.assertIn("ROSTER_COUNT_ABOVE_9", codes)
        self.assertIn("PRE_DRAFT_TRADE_LIMIT", codes)
        self.assertEqual(sorted(v["detail"]["team"] for v in a["violations"] if v["code"] == "FINAL_ROSTER_ABOVE_9"), ["Bz", "CrazyCat", "Melo"])
        self.assertEqual([v["code"] for v in a["violations"] if v["code"].startswith("CAP_OVER")], [])

    def test_ownership_integrity_audit_all_sixteen_teams(self):
        for sel in ([], ["TRADE-A"], ["TRADE-B"], ["TRADE-A", "TRADE-B", "TRADE-C"], ["TRADE-D"],
                    ["TRADE-A", "TRADE-B", "TRADE-C", "TRADE-D"]):
            s = ls.resolve(self.i, sel, "SCENARIO" if sel else "OFFICIAL")
            all_ids = sorted(p["pickId"] for p in self.i["picks"]["picks"])
            self.assertEqual(len(all_ids), 48)
            self.assertEqual(sorted(s["pickOwner"]), all_ids)
            listed = [pid for f in self.i["franchises"] for pid in ls.team_picks(s, f)]
            self.assertEqual(sorted(listed), all_ids, sel)  # each pick exactly once across the 16 inventories
            self.assertEqual(sum(len(ls.team_picks(s, f)) for f in self.i["franchises"]), 48)

    def test_trade_b_corrected_and_chain_still_executes(self):
        b = self.i["tradeIndex"]["TRADE-B"]
        legs = {(a.get("playerKey") or a["pickId"], a["from"], a["to"]) for a in b["assets"]}
        self.assertEqual(legs, {("478.p.6550", DUNG, BZ), ("2026-R3-06", DUNG, BZ), ("478.p.6703", BZ, DUNG), ("2026-R3-03", BZ, DUNG)})
        self.assertEqual(self.o["tradeIndex"]["TRADE-B"]["status"], "OFFICIAL")
        base = ls.initial_state(self.i)
        self.assertIn("2026-R3-03", ls.team_picks(base, BZ))
        s = self._scn("TRADE-B")
        self.assertIn("2026-R3-03", ls.team_picks(s, DUNG))
        self.assertIn("2026-R3-06", ls.team_picks(s, BZ))
        full = self._scn("TRADE-A", "TRADE-B", "TRADE-C")
        self.assertTrue(all(r["applied"] and not r["errors"] for r in full["tradeResults"]))
        self.assertEqual([t for t in self.i["tradeIndex"]["TRADE-C"]["dependsOn"]], ["TRADE-A", "TRADE-B"])

    def test_invalid_transfers_are_rejected(self):
        # Bz no longer owns 2.15 (Melo does): the OLD Trade B leg must be refused, never silently applied
        import copy
        inp = copy.deepcopy(self.i)
        for a in inp["tradeIndex"]["TRADE-B"]["assets"]:
            if a.get("pickId") == "2026-R3-03":
                a["pickId"] = "2026-R2-15"
        s = ls.resolve(inp, ["TRADE-B"], "SCENARIO")
        r = s["tradeResults"][0]
        self.assertFalse(r["applied"])
        self.assertEqual(r["errors"][0]["code"], "NOT_OWNED")
        self.assertEqual(r["errors"][0]["detail"]["actualOwner"], MELO)
        self.assertEqual(s["pickOwner"]["2026-R2-15"], MELO)
        # a bad historical record is a structural error
        bad = copy.deepcopy(self.i)
        bad["picks"]["historicalTransfers"][0]["assets"][0]["from"] = BSY
        with self.assertRaises(ls.StateError):
            ls.validate_inputs(bad)

    def test_historical_moves_are_not_shown_as_scenario_moves(self):
        v = ls.scenario_view(self.i, [])
        self.assertEqual(v["picks"], [])
        v = ls.scenario_view(self.i, ["TRADE-B"])
        self.assertEqual(sorted(p["label"] for p in v["picks"]), ["3.03", "3.06"])

    def test_pre_draft_window_trade_limit_is_surfaced_for_bz(self):
        s = self._scn("TRADE-A", "TRADE-B", "TRADE-C")
        self.assertEqual([w["detail"]["team"] for w in s["windowWarnings"]], ["Bz"])


class TestDraftRoom(unittest.TestCase):
    """First 19 confirmed selections + the staged CrazyCat-HCMC amendment + the 2.07 hold."""

    @classmethod
    def setUpClass(cls):
        cls.i = ls.load_inputs()
        cls.o = ls.resolve(cls.i, (), "OFFICIAL")
        cls.d = ls.draft_summary(cls.i, cls.o)
        cls.html = _html()
        m = re.search(r'<script type="application/json" id="league-data">(.*?)</script>', cls.html, re.S)
        cls.data = json.loads(m.group(1).replace("<\\/", "</"))

    def test_exactly_19_unique_selections_in_draft_order(self):
        ev = self.i["draft"]["events"]
        self.assertEqual(len(ev), 19)
        self.assertEqual(len({e["playerKey"] for e in ev}), 19)
        self.assertEqual(len({e["pickId"] for e in ev}), 19)
        order = [p["pickId"] for p in sorted(self.i["picks"]["picks"], key=lambda p: (p["round"], p["slot"]))]
        self.assertEqual([e["pickId"] for e in ev], order[:19])
        self.assertEqual([c["label"] for c in self.d["completed"]][:3], ["1.01", "1.02", "1.03"])

    def test_state_summary(self):
        d = self.d
        self.assertEqual((len(d["completed"]), d["remaining"], d["total"], d["rookies"]), (19, 29, 48, 9))
        self.assertEqual((d["cursor"]["label"], d["cursor"]["owner"]), ("2.04", "franchise-04"))  # LC owns 2.04
        self.assertEqual((d["latest"]["label"], d["latest"]["name"]), ("2.03", "Neemias Queta"))
        self.assertEqual(d["status"], "IN_PROGRESS")

    def test_selecting_franchise_is_the_post_trade_pick_owner(self):
        got = {c["label"]: self.i["shorts"][c["franchiseId"]] for c in self.d["completed"]}
        self.assertEqual(got["1.03"], "sup fam")                      # Caleb Wilson
        self.assertEqual((got["1.01"], got["1.05"], got["1.04"], got["1.06"], got["2.02"], got["2.03"]),
                         ("Maxfixe", "LC", "HCMC", "HCMC", "HCMC", "Melo"))
        for c in self.d["completed"]:
            self.assertEqual(self.o["playerOwner"][c["playerKey"]], c["franchiseId"])
            self.assertEqual(self.o["pickOwner"][c["pickId"]], c["franchiseId"])

    def test_names_ids_salaries_and_rookie_flags(self):
        by = {c["label"]: c for c in self.d["completed"]}
        self.assertEqual((by["1.03"]["name"], by["1.03"]["playerKey"], by["1.03"]["cap"]), ("Caleb Wilson", "478.p.10595", 10.0))
        self.assertEqual((by["1.01"]["cap"], by["1.06"]["name"], by["1.06"]["cap"]), (20.0, "Day'Ron Sharpe", 6.0))
        self.assertEqual(sorted(c["label"] for c in self.d["completed"] if c["rookie"]),
                         ["1.01", "1.02", "1.03", "1.04", "1.05", "1.07", "1.13", "1.14", "2.02"])
        rookies = pool.load_rookie_names()
        for c in self.d["completed"]:
            self.assertEqual(c["rookie"], pool.normalize_name(c["name"]) in rookies, c["name"])  # agrees with the rookie source

    def test_drafted_players_leave_the_pool_and_join_rosters(self):
        avail = {r[1] for r in self.data["available"]["rows"]}
        board = set(re.findall(r'<div class="pool-player">(.*?)</div>', self.html))
        for c in self.d["completed"]:
            self.assertNotIn(c["name"], avail)
            self.assertNotIn(c["name"], board)
            self.assertIn(c["playerKey"], ls.team_players(self.i, self.o, c["franchiseId"]))
        self.assertEqual(len(board), 60)  # the 60 is refilled from the next-best remaining players

    def test_caps_include_the_draftees(self):
        base = ls.resolve(dict(self.i, draft={**self.i["draft"], "events": []}), (), "OFFICIAL")
        for fid in self.i["franchises"]:
            add = sum(c["cap"] for c in self.d["completed"] if c["franchiseId"] == fid)
            self.assertEqual(ls.team_cap(self.i, self.o, fid), ls.team_cap(self.i, base, fid) + add, fid)
        self.assertEqual(ls.team_cap(self.i, self.o, "franchise-07"), 129 + 20)  # Maxfixe + Boozer

    def test_import_is_idempotent_and_rejects_contradictions(self):
        import copy
        import import_draft_results as imp
        results = ls._load(imp.RESULTS_PATH)
        ev = self.i["draft"]["events"]
        self.assertEqual(imp.build_events(self.i, results, ev), ev)           # re-import: no change, no double selection
        self.assertEqual(imp.build_events(self.i, results, []), ev)           # from scratch: identical events
        bad = copy.deepcopy(results)
        bad["results"][0]["player"] = "AJ Dybantsa"
        with self.assertRaises(imp.ImportError_):
            imp.build_events(self.i, bad, ev)                                  # contradicts the recorded 1.01
        dup = copy.deepcopy(results)
        dup["results"].append({"pickId": "2026-R2-04", "player": "Cameron Boozer", "rookie": True})
        with self.assertRaises(imp.ImportError_):
            imp.build_events(self.i, dup, ev)                                  # a player cannot be picked twice
        skip = copy.deepcopy(results)
        skip["results"][3], skip["results"][4] = skip["results"][4], skip["results"][3]
        with self.assertRaises(imp.ImportError_):
            imp.build_events(self.i, skip, [])                                 # order must be preserved
        with self.assertRaises(imp.ImportError_):
            imp.resolve_name(self.i["registry"], "Nobody Real")

    def test_pick_2_07_is_on_hold_and_cannot_be_recorded(self):
        self.assertEqual([h["label"] for h in self.d["holds"]], ["2.07"])
        self.assertEqual(self.d["holds"][0]["waitingOn"], "TRADE-F-AMEND")
        self.assertEqual(self.o["pickOwner"]["2026-R2-07"], "franchise-02")   # ledger NOT silently reassigned
        import copy
        bad = copy.deepcopy(self.i)
        bad["draft"]["events"].append({"eventId": "x", "type": "DRAFT_PICK", "pickId": "2026-R2-07", "franchiseId": "franchise-02",
                                       "playerKey": "478.p.6733-none", "rookie": False})
        with self.assertRaises(ls.StateError):
            ls.resolve(bad, (), "OFFICIAL")
        self.assertIn("OWNERSHIP HOLD", self.html)

    def test_amendment_is_staged_not_applied(self):
        a = self.i["tradeIndex"]["TRADE-F-AMEND"]
        self.assertEqual((a["status"], a["amends"], a["dependsOn"], a["pendingConfirmation"]), ("PROPOSED", "TRADE-F", ["TRADE-F"], True))
        legs = {(x.get("playerKey") or x["pickId"], x["from"], x["to"]) for x in a["assets"]}
        self.assertEqual(legs, {("2026-R2-07", "franchise-02", "franchise-05"), ("478.p.10444", "franchise-05", "franchise-02")})
        self.assertEqual(self.i["registry"]["478.p.10444"]["name"], "Derik Queen")
        self.assertEqual(self.o["playerOwner"]["478.p.10444"], "franchise-05")  # HCMC still owns Queen officially
        self.assertEqual([r["tradeId"] for r in self.o["tradeResults"]].count("TRADE-F"), 1)
        # nothing else depends on 2.07 or Queen
        others = [t["tradeId"] for t in self.i["trades"]["trades"] if t["tradeId"] not in ("TRADE-F", "TRADE-F-AMEND")
                  and any((x.get("pickId") == "2026-R2-07" or x.get("playerKey") == "478.p.10444") for x in t["assets"])]
        self.assertEqual(others, [])

    def test_amendment_preview_is_a_correction_not_a_replay(self):
        s = ls.resolve(self.i, ["TRADE-F-AMEND"], "SCENARIO")
        self.assertTrue(all(r["applied"] and not r["errors"] for r in s["tradeResults"]))
        self.assertEqual([r["tradeId"] for r in s["tradeResults"]].count("TRADE-F"), 1)   # TRADE-F not replayed
        self.assertEqual((s["pickOwner"]["2026-R2-07"], s["playerOwner"]["478.p.10444"]), ("franchise-05", "franchise-02"))
        for fid, delta in (("franchise-02", +5), ("franchise-05", -5)):
            self.assertEqual(ls.team_cap(self.i, s, fid), ls.team_cap(self.i, self.o, fid) + delta)
        # earlier results stand: 1.04 and 2.02 still belong to HCMC's selections
        self.assertEqual({c["label"]: c["franchiseId"] for c in self.d["completed"]}["1.04"], "franchise-05")
        self.assertEqual(s["windowWarnings"], ls.resolve(self.i, (), "OFFICIAL")["windowWarnings"])  # a correction is not a new trade
        pt = ls.pick_table(self.i, s)
        self.assertEqual(len([r for r in pt if r["pickId"] == "2026-R2-07"]), 1)

    def test_confirming_the_amendment_lifts_the_hold_and_keeps_audit_clean(self):
        import copy
        c = copy.deepcopy(self.i)
        c["tradeIndex"]["TRADE-F-AMEND"]["status"] = "OFFICIAL"
        s = ls.resolve(c, (), "OFFICIAL")
        self.assertEqual(ls.active_holds(c), [])
        self.assertEqual(s["pickOwner"]["2026-R2-07"], "franchise-05")
        self.assertEqual(s["playerOwner"]["478.p.10444"], "franchise-02")
        self.assertEqual(len(s["completedPicks"]), 19)          # no selection undone
        self.assertEqual(ls.audit_official(c)["checks"]["everyOfficialTradeApplied"], True)

    def test_page_ledger_and_picks_agree(self):
        panel = self.html[self.html.index('id="draft-order"'):self.html.index('id="rosters-a"')]
        self.assertIn("ON THE CLOCK", panel)
        self.assertRegex(re.sub(r"<[^>]+>", " ", panel), r"ON THE CLOCK\s+2\.04")
        self.assertIn("Neemias Queta", panel)
        self.assertEqual(panel.count("pick-sel"), 19)
        self.assertEqual(panel.count('pick-r"'), 9)  # nine rookie badges (the LATEST pick, Queta, is not a rookie)
        self.assertEqual(bls.sync_ledger(self.html, self.i), self.html)
        self.assertEqual(self.data["draft"], ls.draft_summary(self.i, self.o))


class TestEmbeddedPageData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = _html()
        cls.js = re.search(r'<script id="league-app">(.*?)</script>', cls.html, re.S).group(1)
        m = re.search(r'<script type="application/json" id="league-data">(.*?)</script>', cls.html, re.S)
        cls.data = json.loads(m.group(1).replace("<\\/", "</"))
        cls.i = ls.load_inputs()

    def test_embedded_data_is_exactly_what_the_engine_derives(self):
        fresh = bls.build_page_data(self.i, self.html)
        self.assertEqual(self.data, fresh)

    def test_page_data_derives_from_tracked_canonical_yahoo_not_local_data(self):
        self.assertEqual(os.path.relpath(bls.CANONICAL_YAHOO_PATH, REPO_ROOT), os.path.join("data", "yahoo", "players_normalized.json"))
        self.assertNotIn("local_data", bls.CANONICAL_YAHOO_PATH)
        opened = []
        real_open = open

        def spy(path, *a, **k):
            opened.append(str(path))
            return real_open(path, *a, **k)

        import builtins
        old_default = pool.YAHOO_NORMALIZED
        pool.YAHOO_NORMALIZED = os.path.join(REPO_ROOT, "local_data", "yahoo", "DOES_NOT_EXIST.json")  # any implicit use would fail
        builtins.open = spy
        try:
            data = bls.build_page_data(self.i, self.html)
        finally:
            builtins.open = real_open
            pool.YAHOO_NORMALIZED = old_default
        self.assertEqual(data, self.data)
        self.assertFalse([p for p in opened if "local_data" in p], opened)

    def test_yahoo_source_is_injectable_for_tests(self):
        import inspect
        self.assertEqual(inspect.signature(bls.build_page_data).parameters["yahoo_path"].default, bls.CANONICAL_YAHOO_PATH)

    def test_all_scenario_combinations_are_present(self):
        self.assertEqual(len(self.data["scenarios"]), 2 ** len(ls.selectable_trades(self.i)))
        self.assertEqual(list(self.data["scenarios"]), ["", "TRADE-F-AMEND"])  # only the staged amendment is selectable

    def test_official_view_has_no_movement_and_scenario_view_has_it(self):
        view = self.data["scenarios"][""]
        self.assertEqual(sorted(view["teams"]), sorted(self.i["franchises"]))  # trade teams + every drafting team
        self.assertEqual(view["teams"][BZ]["fold"]["tradeIds"], ["TRADE-A", "TRADE-B", "TRADE-C", "TRADE-E"])

    def test_legal_universe_is_larger_than_the_recommendation_board(self):
        rows = self.data["available"]["rows"]
        self.assertGreater(len(rows), 60)
        on_board = [r for r in rows if r[6] is not None]
        self.assertEqual(len(on_board), 60)
        outside = [r for r in rows if r[6] is None and r[5] and r[5] > 300]
        self.assertTrue(outside, "a Yahoo-ranked player outside the recommendation board must be selectable")

    def test_kept_players_are_not_available(self):
        keys = {r[0] for r in self.data["available"]["rows"]}
        kept = {k["playerKey"] for t in self.i["freeze"]["teams"] for k in t["keepers"]}
        self.assertFalse(keys & kept)

    def test_dynasty_rank_is_not_exposed_in_the_operational_data(self):
        self.assertEqual(self.data["available"]["cols"], ["key", "name", "nba", "pos", "cap", "yahooOr", "board", "src"])
        keys = set(re.findall(r'"([A-Za-z_]+)":', json.dumps(self.data)))
        self.assertFalse([k for k in keys if "dynasty" in k.lower() or "consensus" in k.lower()])

    def test_board_rank_in_the_universe_matches_the_fa60(self):
        pool_names = re.findall(r'<div class="pool-rank">(\d+)</div><div class="pool-pos">[^<]*</div><div class="pool-player">(.*?)</div>', self.html)
        import html as h
        by_rank = {int(r): h.unescape(n) for r, n in pool_names}
        for row in self.data["available"]["rows"]:
            if row[6] is not None:
                self.assertEqual(by_rank[row[6]], row[1])

    def test_page_exposes_the_new_surfaces_and_existing_ones_remain(self):
        for anchor in ('id="trade-lab"', 'id="picks"', 'id="draft-pool"', 'id="cap"', 'id="rosters-a"', 'id="draft-order"'):
            self.assertIn(anchor, self.html)
        for label in (">TRADE LAB<", ">PICKS<", ">OFFICIAL<", ">SCENARIO<", 'id="scn-banner"', "SCENARIO VIEW — NOT OFFICIAL"):
            self.assertIn(label, self.html + self.js)
        self.assertIn('id="avail"', self.html)
        self.assertIn("exports/yahoo_top300_proj_dollar_rank.xlsx", self.html)

    def test_embed_is_idempotent(self):
        once = bls.embed(self.html, self.data)
        self.assertEqual(once, self.html)
        self.assertEqual(bls.embed(once, self.data), once)


if __name__ == "__main__":
    unittest.main()
