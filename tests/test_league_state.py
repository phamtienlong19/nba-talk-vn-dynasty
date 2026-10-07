import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import league_state as ls  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
A, B, C = "franchise-01", "franchise-02", "franchise-03"


def synth(trades=None, events=None, status="projected"):
    """Tiny league: three teams, six players, nine picks -- independent of live data."""
    reg = {f"k{i}": {"playerKey": f"k{i}", "name": f"P{i}", "projectedAuctionValue": float(c), "oRank": i}
           for i, c in enumerate([30, 20, 10, 5, 1, 0], start=1)}
    reg["free"] = {"playerKey": "free", "name": "Free Agent", "projectedAuctionValue": 0.0, "oRank": 400}
    teams = [{"franchiseId": A, "short": "A", "keepers": [{"playerKey": "k1"}, {"playerKey": "k4"}]},
             {"franchiseId": B, "short": "B", "keepers": [{"playerKey": "k2"}, {"playerKey": "k5"}]},
             {"franchiseId": C, "short": "C", "keepers": [{"playerKey": "k3"}, {"playerKey": "k6"}]}]
    picks = [{"pickId": f"2026-R{r}-{s:02d}", "round": r, "slot": s, "originalOwner": o}
             for r in (1, 2, 3) for s, o in ((1, A), (2, B), (3, C))]
    inputs = {
        "franchises": {f: {"franchiseId": f} for f in (A, B, C)},
        "freeze": {"season": "2026-27", "status": status, "teams": teams},
        "picks": {"picks": picks},
        "trades": {"trades": trades if trades is not None else []},
        "draft": {"events": events or []},
        "registry": reg,
        "policy": {"officialFloor": 10, "officialCeiling": 40},
        "extraPlayers": {},
    }
    inputs["shorts"] = {t["franchiseId"]: t["short"] for t in teams}
    inputs["pickIndex"] = {p["pickId"]: p for p in picks}
    inputs["tradeIndex"] = {t["tradeId"]: t for t in inputs["trades"]["trades"]}
    return inputs


def pl(key, frm, to):
    return {"type": "player", "playerKey": key, "from": frm, "to": to}


def pk(pid, frm, to):
    return {"type": "pick", "pickId": pid, "from": frm, "to": to}


def trade(tid, order, parts, assets, status="PROPOSED", deps=()):
    return {"tradeId": tid, "label": tid, "order": order, "status": status, "participants": list(parts),
            "assets": assets, "dependsOn": list(deps)}


def reindex(inputs):
    inputs["tradeIndex"] = {t["tradeId"]: t for t in inputs["trades"]["trades"]}
    return inputs


class TestOwnershipAndPicks(unittest.TestCase):
    def setUp(self):
        t1 = trade("T1", 1, (A, B), [pl("k1", A, B), pk("2026-R1-01", A, B), pl("k2", B, A), pk("2026-R1-02", B, A)])
        t2 = trade("T2", 2, (B, C), [pk("2026-R1-01", B, C), pl("k3", C, B), pk("2026-R3-03", C, B), pl("k5", B, C)], deps=("T1",))
        self.inputs = reindex(synth([t1, t2]))

    def test_official_state_excludes_proposed_trades(self):
        s = ls.resolve(self.inputs, ["T1"], "OFFICIAL")
        self.assertEqual(s["pickOwner"]["2026-R1-01"], A)
        self.assertEqual(s["playerOwner"]["k1"], A)
        self.assertEqual(s["activeTradeIds"], [])

    def test_scenario_state_includes_selected_trades_only(self):
        s = ls.resolve(self.inputs, ["T1"], "SCENARIO")
        self.assertEqual(s["playerOwner"]["k1"], B)
        self.assertEqual(s["pickOwner"]["2026-R1-01"], B)
        self.assertEqual(s["playerOwner"]["k3"], C)  # T2 not selected -> untouched

    def test_inactive_trade_does_not_mutate_state(self):
        base = ls.initial_state(self.inputs)
        s = ls.resolve(self.inputs, [], "SCENARIO")
        self.assertEqual(s["playerOwner"], base["playerOwner"])
        self.assertEqual(s["pickOwner"], base["pickOwner"])

    def test_original_owner_is_preserved_and_current_is_derived(self):
        s = ls.resolve(self.inputs, ["T1", "T2"], "SCENARIO")
        row = {r["pickId"]: r for r in ls.pick_table(self.inputs, s)}["2026-R1-01"]
        self.assertEqual((row["original"], row["current"]), (A, C))
        self.assertEqual(self.inputs["pickIndex"]["2026-R1-01"]["originalOwner"], A)

    def test_pick_history_chain(self):
        s = ls.resolve(self.inputs, ["T1", "T2"], "SCENARIO")
        hist = s["history"]["pick:2026-R1-01"]
        self.assertEqual([(h["tradeId"], h["from"], h["to"]) for h in hist], [("T1", A, B), ("T2", B, C)])

    def test_no_duplicate_player_or_pick_ownership(self):
        s = ls.resolve(self.inputs, ["T1", "T2"], "SCENARIO")
        owners = list(s["playerOwner"].items())
        self.assertEqual(len(owners), len({k for k, _ in owners}))
        self.assertEqual(len(s["pickOwner"]), 9)
        every = [k for f in (A, B, C) for k in ls.team_players(self.inputs, s, f)]
        self.assertEqual(len(every), len(set(every)))

    def test_duplicate_player_in_freeze_is_rejected(self):
        bad = synth()
        bad["freeze"]["teams"][1]["keepers"].append({"playerKey": "k1"})
        with self.assertRaises(ls.StateError):
            ls.validate_inputs(bad)

    def test_duplicate_pick_ids_are_rejected(self):
        bad = synth()
        bad["picks"]["picks"].append(dict(bad["picks"]["picks"][0]))
        with self.assertRaises(ls.StateError):
            ls.validate_inputs(bad)

    def test_unknown_status_and_unselectable_trade(self):
        bad = synth([trade("X", 1, (A, B), [pl("k1", A, B), pl("k2", B, A)], status="MAYBE")])
        with self.assertRaises(ls.StateError):
            ls.validate_inputs(bad)
        void = reindex(synth([trade("V", 1, (A, B), [pl("k1", A, B), pl("k2", B, A)], status="VOID")]))
        with self.assertRaises(ls.StateError):
            ls.resolve(void, ["V"], "SCENARIO")

    def test_official_trade_mutates_official_state(self):
        t = trade("O", 1, (A, B), [pl("k1", A, B), pl("k2", B, A)], status="OFFICIAL")
        s = ls.resolve(reindex(synth([t])), [], "OFFICIAL")
        self.assertEqual(s["playerOwner"]["k1"], B)


class TestValidation(unittest.TestCase):
    def test_sender_must_own_the_player(self):
        t = trade("T", 1, (A, B), [pl("k2", A, B), pl("k1", B, A)])  # A does not own k2
        s = ls.resolve(reindex(synth([t])), ["T"], "SCENARIO")
        r = s["tradeResults"][0]
        self.assertFalse(r["applied"])
        self.assertIn("NOT_OWNED", [e["code"] for e in r["errors"]])
        self.assertEqual(s["playerOwner"]["k1"], A)  # nothing silently "fixed"

    def test_sender_must_own_the_pick(self):
        t = trade("T", 1, (A, B), [pk("2026-R1-02", A, B), pl("k2", B, A)])
        r = ls.resolve(reindex(synth([t])), ["T"], "SCENARIO")["tradeResults"][0]
        self.assertIn("NOT_OWNED", [e["code"] for e in r["errors"]])

    def test_unknown_assets_and_bad_participants(self):
        t = trade("T", 1, (A, B), [pl("nope", A, B), pk("2026-R9-99", B, A), pl("k4", A, C)])
        codes = {e["code"] for e in ls.resolve(reindex(synth([t])), ["T"], "SCENARIO")["tradeResults"][0]["errors"]}
        self.assertTrue({"UNKNOWN_PLAYER", "UNKNOWN_PICK", "BAD_PARTICIPANT"} <= codes)

    def test_same_asset_twice_in_one_trade(self):
        t = trade("T", 1, (A, B), [pl("k1", A, B), pl("k1", A, B), pl("k2", B, A)])
        codes = [e["code"] for e in ls.resolve(reindex(synth([t])), ["T"], "SCENARIO")["tradeResults"][0]["errors"]]
        self.assertIn("DUPLICATE_ASSET", codes)

    def test_same_asset_cannot_move_in_two_trades_simultaneously(self):
        t1 = trade("T1", 1, (A, B), [pl("k1", A, B), pl("k2", B, A)])
        t2 = trade("T2", 2, (A, C), [pl("k1", A, C), pl("k3", C, A)])  # k1 already left A
        s = ls.resolve(reindex(synth([t1, t2])), ["T1", "T2"], "SCENARIO")
        self.assertTrue(s["tradeResults"][0]["applied"])
        self.assertFalse(s["tradeResults"][1]["applied"])
        self.assertEqual(s["playerOwner"]["k1"], B)

    def test_a_pick_already_used_in_the_draft_cannot_be_traded(self):
        i = reindex(synth([trade("T", 1, (A, B), [pk("2026-R1-01", A, B), pl("k2", B, A)])]))
        state = ls.initial_state(i)
        state["completedPicks"]["2026-R1-01"] = {"franchiseId": A, "playerKey": "free"}
        errors, _ = ls.validate_trade(i, state, i["tradeIndex"]["T"], {"T"})
        self.assertIn("PICK_ALREADY_USED", [e["code"] for e in errors])

    def test_unbalanced_asset_count_is_a_warning_not_a_block(self):
        t = trade("T", 1, (A, B), [pl("k1", A, B), pk("2026-R1-01", A, B), pl("k2", B, A)])
        r = ls.resolve(reindex(synth([t])), ["T"], "SCENARIO")["tradeResults"][0]
        self.assertTrue(r["applied"])
        self.assertEqual([w["code"] for w in r["warnings"] if w["code"] == "ASSET_COUNT_UNBALANCED"], ["ASSET_COUNT_UNBALANCED"])
        self.assertEqual(r["warnings"][0]["detail"], {"A": 1, "B": 2})

    def test_cap_direction_and_ceiling_warnings(self):
        t = trade("T", 1, (A, B), [pl("k4", A, B), pl("k5", B, A)])
        ok = ls.resolve(reindex(synth([t])), ["T"], "SCENARIO")["tradeResults"][0]
        self.assertFalse([w for w in ok["warnings"] if w["code"].startswith("CAP_")])
        over = synth([trade("T", 1, (A, B), [pl("k4", A, B), pl("k2", B, A)])])  # A: 35 -> 50 > 40
        r = ls.resolve(reindex(over), ["T"], "SCENARIO")["tradeResults"][0]
        self.assertIn("CAP_OVER_CEILING", [w["code"] for w in r["warnings"]])


class TestDependencies(unittest.TestCase):
    def setUp(self):
        t1 = trade("T1", 1, (A, B), [pk("2026-R1-02", B, A), pl("k2", B, A), pl("k1", A, B), pk("2026-R1-01", A, B)])
        t2 = trade("T2", 2, (A, C), [pk("2026-R1-02", A, C), pl("k3", C, A)], deps=("T1",))
        self.inputs = reindex(synth([t1, t2]))

    def test_dependent_trade_without_upstream_is_a_broken_dependency(self):
        s = ls.resolve(self.inputs, ["T2"], "SCENARIO")
        r = s["tradeResults"][0]
        self.assertFalse(r["applied"])
        self.assertEqual([e["code"] for e in r["errors"]], ["BROKEN_DEPENDENCY"])
        self.assertEqual(r["errors"][0]["detail"]["reason"], ["inactive"])
        self.assertEqual(s["pickOwner"]["2026-R1-02"], B)  # no silent resolution

    def test_dependent_trade_with_upstream_resolves(self):
        s = ls.resolve(self.inputs, ["T1", "T2"], "SCENARIO")
        self.assertTrue(all(r["applied"] for r in s["tradeResults"]))
        self.assertEqual(s["pickOwner"]["2026-R1-02"], C)

    def test_failed_upstream_breaks_downstream(self):
        self.inputs["trades"]["trades"][0]["assets"][1] = pl("k4", B, A)  # B does not own k4 -> T1 invalid
        reindex(self.inputs)
        s = ls.resolve(self.inputs, ["T1", "T2"], "SCENARIO")
        self.assertFalse(s["tradeResults"][0]["applied"])
        r2 = s["tradeResults"][1]
        self.assertIn("BROKEN_DEPENDENCY", [e["code"] for e in r2["errors"]])
        self.assertEqual(r2["errors"][0]["detail"]["reason"], ["not applied (invalid)"])

    def test_dependency_ordering_error(self):
        self.inputs["trades"]["trades"][0]["dependsOn"] = ["T2"]
        reindex(self.inputs)
        s = ls.resolve(self.inputs, ["T1", "T2"], "SCENARIO")
        self.assertIn("DEPENDENCY_ORDER", [e["code"] for e in s["tradeResults"][0]["errors"]])


class TestCapDerivation(unittest.TestCase):
    def test_cap_before_delta_after_and_room(self):
        t = trade("T", 1, (A, B), [pl("k1", A, B), pl("k2", B, A)])  # A: 35 -> 25 ; B: 25 -> 35
        r = ls.resolve(reindex(synth([t])), ["T"], "SCENARIO")["tradeResults"][0]
        a = r["teams"][A]
        self.assertEqual((a["capBefore"], a["playerCapDelta"], a["capAfter"], a["roomToCeiling"]), (35, -10, 25, 15))
        b = r["teams"][B]
        self.assertEqual((b["capBefore"], b["playerCapDelta"], b["capAfter"], b["roomToCeiling"]), (21, 10, 31, 9))
        self.assertEqual(a["capBefore"] + a["playerCapDelta"], a["capAfter"])

    def test_chained_trades_use_the_previous_resulting_state(self):
        t1 = trade("T1", 1, (A, B), [pl("k1", A, B), pl("k2", B, A)])
        t2 = trade("T2", 2, (A, C), [pl("k2", A, C), pl("k3", C, A)], deps=("T1",))
        s = ls.resolve(reindex(synth([t1, t2])), ["T1", "T2"], "SCENARIO")
        r1, r2 = s["tradeResults"]
        self.assertEqual(r1["teams"][A]["capAfter"], 25)  # 35 - 30 + 20
        self.assertEqual(r2["teams"][A]["capBefore"], r1["teams"][A]["capAfter"])  # NOT the 35 baseline
        self.assertEqual(r2["teams"][A]["capAfter"], 15)  # 25 - 20 + 10

    def test_floor_status_and_no_stored_cap(self):
        i = synth()
        self.assertEqual(ls.floor_status(i, 9), "UNDER_FLOOR")
        self.assertEqual(ls.floor_status(i, 25), "IN_BAND")
        self.assertEqual(ls.floor_status(i, 41), "OVER_CEILING")
        for t in i["trades"]["trades"]:
            self.assertNotIn("capAfter", json.dumps(t))


class TestFolding(unittest.TestCase):
    def setUp(self):
        t1 = trade("T1", 1, (A, B), [pk("2026-R1-02", B, A), pl("k2", B, A), pl("k1", A, B), pk("2026-R1-01", A, B)])
        t2 = trade("T2", 2, (A, C), [pk("2026-R1-02", A, C), pl("k3", C, A), pk("2026-R3-03", C, A), pl("k4", A, C)], deps=("T1",))
        self.inputs = reindex(synth([t1, t2]))
        self.state = ls.resolve(self.inputs, ["T1", "T2"], "SCENARIO")

    def test_pass_through_is_preserved_not_erased(self):
        fold = ls.fold_team(self.inputs, self.state, A)
        self.assertEqual([p["asset"]["n"] for p in fold["pass"]], ["1.02"])
        self.assertEqual(fold["pass"][0]["chain"], ["B", "A", "C"])
        in_names = [a["n"] for a in fold["in"]]
        out_names = [a["n"] for a in fold["out"]]
        self.assertNotIn("1.02", in_names + out_names)

    def test_folded_in_out_and_cap_delta(self):
        fold = ls.fold_team(self.inputs, self.state, A)
        self.assertEqual(sorted(a["n"] for a in fold["in"]), sorted(["P2", "P3", "3.03"]))
        self.assertEqual(sorted(a["n"] for a in fold["out"]), sorted(["P1", "P4", "1.01"]))
        self.assertEqual(fold["playerCapDelta"], (20 + 10) - (30 + 5))
        self.assertEqual(fold["tradeIds"], ["T1", "T2"])
        self.assertEqual(ls.team_cap(self.inputs, self.state, A), 35 + fold["playerCapDelta"])


class TestDraftLedger(unittest.TestCase):
    def test_draft_pick_events_update_roster_cap_availability_and_cursor(self):
        ev = [{"eventId": "e1", "type": "DRAFT_PICK", "pickId": "2026-R1-01", "franchiseId": A, "playerKey": "free"}]
        i = synth(events=ev)
        s = ls.resolve(i, [], "OFFICIAL")
        self.assertEqual(s["playerOwner"]["free"], A)
        self.assertIn("2026-R1-01", s["completedPicks"])
        self.assertEqual(ls.draft_cursor(i, s), "2026-R1-02")
        self.assertIn("free", s["draftedPlayers"])
        self.assertEqual(len(ls.team_players(i, s, A)), 3)

    def test_draft_event_validation(self):
        bad_owner = [{"eventId": "e", "type": "DRAFT_PICK", "pickId": "2026-R1-01", "franchiseId": B, "playerKey": "free"}]
        with self.assertRaises(ls.StateError):
            ls.resolve(synth(events=bad_owner), [], "OFFICIAL")
        owned = [{"eventId": "e", "type": "DRAFT_PICK", "pickId": "2026-R1-01", "franchiseId": A, "playerKey": "k2"}]
        with self.assertRaises(ls.StateError):
            ls.resolve(synth(events=owned), [], "OFFICIAL")


class TestKeeperFreezeAndSnapshots(unittest.TestCase):
    def test_lock_creates_immutable_digest_and_refuses_relock(self):
        i = synth()
        locked = ls.lock_keepers(i["freeze"], "2026-10-09T00:00:00Z")
        self.assertEqual(locked["status"], "locked")
        self.assertTrue(ls.verify_lock(locked))
        self.assertEqual(i["freeze"]["status"], "projected")  # original untouched
        with self.assertRaises(ls.StateError):
            ls.lock_keepers(locked, "later")
        tampered = copy.deepcopy(locked)
        tampered["teams"][0]["keepers"].pop()
        self.assertFalse(ls.verify_lock(tampered))

    def test_snapshots_are_reproducible_from_inputs(self):
        i = synth([trade("O", 1, (A, B), [pl("k1", A, B), pl("k2", B, A)], status="OFFICIAL")])
        for kind in ls.SNAPSHOT_KINDS:
            s1, s2 = ls.make_snapshot(i, kind), ls.make_snapshot(copy.deepcopy(i), kind)
            self.assertEqual(s1, s2)
        self.assertEqual(ls.make_snapshot(i, "KEEPER_FREEZE")["playerOwner"]["k1"], A)  # pre-trade baseline
        self.assertEqual(ls.make_snapshot(i, "PRE_DRAFT_LOCK")["playerOwner"]["k1"], B)  # after official trade
        with self.assertRaises(ls.StateError):
            ls.make_snapshot(i, "NOPE")


class TestScenarioEnumeration(unittest.TestCase):
    def test_every_combination_is_enumerated_and_keyed(self):
        t = [trade(f"T{n}", n, (A, B), [pl("k1", A, B), pl("k2", B, A)]) for n in (1, 2)]
        views = ls.enumerate_scenarios(reindex(synth(t)))
        self.assertEqual(sorted(views), ["", "T1", "T1,T2", "T2"])
        self.assertEqual(views[""]["teams"], {})


if __name__ == "__main__":
    unittest.main()
