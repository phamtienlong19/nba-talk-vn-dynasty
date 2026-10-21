"""Trade checker rules: pass / block / boundary for each rule, derived from the current data (nothing pinned to a roster)."""
import copy
import datetime
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import league_state as ls  # noqa: E402
import season_state as ss  # noqa: E402
import trade_checker as tc  # noqa: E402

LATER = "2026-12-31T00:00:00Z"   # past every cooldown, before the Feb 18, 2027 deadline
ROOT = os.path.join(os.path.dirname(__file__), "..")


def swaps(si, state):
    """Every 1-for-1 swap between two teams (first / last ranked player of each), as move lists."""
    fids = sorted(si["franchises"])
    rows = {f: ss.ranked_roster(si, state, f) for f in fids}
    for i, a in enumerate(fids):
        for b in fids[i + 1:]:
            for ra in (rows[a][0], rows[a][-1]):
                for rb in (rows[b][0], rows[b][-1]):
                    yield [{"key": ra["k"], "from": a, "to": b}, {"key": rb["k"], "from": b, "to": a}]


def plus(ts, **kw):
    d = datetime.datetime.fromisoformat(ts.replace("Z", "+00:00")) + datetime.timedelta(**kw)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


class TradeChecker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.si = ss.load_season(ls.load_inputs())
        cls.state = ss.season_state(cls.si)
        cls.rules = tc.load_rules()

    def verdict(self, moves, now=LATER, state=None, drops=(), ils=()):
        return tc.check_proposal(self.si, state or self.state, moves, now, self.rules, drops, ils)

    def levels(self, res, rule):
        return [r["level"] for r in res["rules"] if r["rule"] == rule]

    def test_invalid_proposals_are_blocked(self):
        a, b = sorted(self.si["franchises"])[:2]
        k = ss.ranked_roster(self.si, self.state, a)[0]["k"]
        self.assertEqual(self.verdict([])["status"], "BLOCKED")
        self.assertEqual(self.verdict([{"key": k, "from": b, "to": a}])["status"], "BLOCKED")   # not on that team
        self.assertEqual(self.verdict([{"key": k, "from": a, "to": a}])["status"], "BLOCKED")

    def test_cap_direction_blocks_and_shows_the_ladder_rung(self):
        blocked = [(m, self.verdict(m)) for m in swaps(self.si, self.state)]
        hit = [(m, r) for m, r in blocked if "blocked" in self.levels(r, "cap")]
        self.assertTrue(hit, "no swap leaves a team outside the band?")
        r = hit[0][1]
        self.assertEqual(r["status"], "BLOCKED")
        self.assertTrue(self.levels(r, "ladder"))
        self.assertIn("in the band or move it toward it", next(x for x in r["rules"] if x["level"] == "blocked" and x["rule"] == "cap")["reason"])

    def test_some_swaps_are_legal_and_legal_means_only_ok_or_info(self):
        legal = [self.verdict(m) for m in swaps(self.si, self.state)]
        legal = [r for r in legal if r["status"] == "LEGAL"]
        self.assertTrue(legal)
        for r in legal:
            self.assertTrue(all(x["level"] in ("ok", "info") for x in r["rules"]))
            self.assertIn("pending", [x["rule"] for x in r["rules"]])

    def test_cooldown_boundary_14_days_and_28_for_preseason_top_32(self):
        acq, top = tc.acquisitions(self.si), tc.top_ranked(self.si, self.rules)
        for want_top, days in ((False, 14), (True, 28)):
            pick = next(((k, f, at) for (k, f), at in acq.items() if (k in top) == want_top and self.state["playerOwner"].get(k) == f), None)
            if pick is None:
                continue   # data has no such acquired player right now
            k, f, at = pick
            g = next(x for x in sorted(self.si["franchises"]) if x != f)
            back = self._free_of_cooldown(g)
            moves = [{"key": k, "from": f, "to": g}, {"key": back, "from": g, "to": f}]
            self.assertIn("blocked", self.levels(self.verdict(moves, plus(at, days=days, seconds=-1)), "cooldown"), (want_top, days))
            self.assertEqual(self.levels(self.verdict(moves, plus(at, days=days)), "cooldown"), ["ok"], (want_top, days))

    def test_cooldown_reason_leads_with_the_days_left(self):
        acq = tc.acquisitions(self.si)
        (k, f), at = next((kf, at) for kf, at in acq.items() if self.state["playerOwner"].get(kf[0]) == kf[1])
        g = next(x for x in sorted(self.si["franchises"]) if x != f)
        mv = [{"key": k, "from": f, "to": g}, {"key": self._free_of_cooldown(g), "from": g, "to": f}]
        top = k in tc.top_ranked(self.si, self.rules)
        end = tc.cooldown_end(at, k, tc.top_ranked(self.si, self.rules), self.rules)
        now = plus(end, days=-3, seconds=-1)                                      # a hair over 3 days left rounds up to 4
        row = next(x for x in self.verdict(mv, now)["rules"] if x["rule"] == "cooldown" and x["level"] == "blocked")
        self.assertRegex(row["reason"], r"can't be traded for 4 more days \(until " + end[:10])
        row = next(x for x in self.verdict(mv, plus(end, days=-1))["rules"] if x["rule"] == "cooldown" and x["level"] == "blocked")
        self.assertIn("for 1 more day (until", row["reason"])
        self.assertEqual(top, k in tc.top_ranked(self.si, self.rules))

    def test_cooldown_only_binds_the_team_that_acquired_the_player(self):
        acq = tc.acquisitions(self.si)
        (k, f), at = next((kf, at) for kf, at in acq.items() if self.state["playerOwner"].get(kf[0]) == kf[1])
        g = next(x for x in sorted(self.si["franchises"]) if x != f)
        other = self._free_of_cooldown(g)
        # the same pair of players, but the held player is not the one leaving his acquirer: no cooldown row
        res = self.verdict([{"key": other, "from": g, "to": f}], plus(at, seconds=1))
        self.assertEqual(self.levels(res, "cooldown"), ["ok"])

    def _free_of_cooldown(self, fid):
        acq = tc.acquisitions(self.si)
        return next(r["k"] for r in ss.ranked_roster(self.si, self.state, fid) if (r["k"], fid) not in acq)

    def _injured_state(self, fid, n, extra_out=()):
        st = copy.copy(self.state)
        st["status"], st["slots"] = dict(self.state["status"]), dict(self.state["slots"])
        own = [r["k"] for r in ss.ranked_roster(self.si, self.state, fid)]
        for k in own:                                                   # start from a clean team, then mark exactly n players out
            st["status"].pop(k, None)
            st["slots"][k] = None
        for k in own[:n]:
            st["status"][k] = "OUT"
        for k in extra_out:
            st["status"][k] = "OUT"
        return st

    def _pair(self):
        a, b = sorted(self.si["franchises"])[:2]
        return a, b, ss.ranked_roster(self.si, self.state, b)[-1]["k"], ss.ranked_roster(self.si, self.state, a)[-1]["k"]

    def test_anti_tank_blocks_worsening_an_already_over_limit(self):
        a, b, kb, ka = self._pair()
        lim = ss._load(ss.RULES_PATH)["longTermInjured"]["max"]
        st = self._injured_state(a, lim + 1, extra_out=[kb])           # a is over; b's player is also out
        res = self.verdict([{"key": kb, "from": b, "to": a}, {"key": ss.ranked_roster(self.si, st, a)[-1]["k"], "from": a, "to": b}], state=st)
        # a gives up its last-ranked player (healthy, or injured) and takes an injured one: only judge when the count grew
        before, after = ss.roster_checks(self.si, st, a)["injured"]["count"], None
        hyp = tc._moved_state(st, [{"key": kb, "to": a}, {"key": res["moves"][1]["key"], "to": b}])
        after = ss.roster_checks(self.si, hyp, a)["injured"]["count"]
        if after > before:
            self.assertIn("blocked", [r["level"] for r in res["rules"] if r["rule"] == "antitank"])
        else:
            self.assertNotIn("blocked", [r["level"] for r in res["rules"] if r["rule"] == "antitank" and r.get("check") == "injured"])

    def test_anti_tank_newly_over_is_review_not_blocked(self):
        a, b, kb, _ = self._pair()
        lim = ss._load(ss.RULES_PATH)["longTermInjured"]["max"]
        st = self._injured_state(a, lim, extra_out=[kb])               # a sits exactly at the limit; b sends an injured player
        give = next(r["k"] for r in ss.ranked_roster(self.si, st, a) if r["k"] not in ss.injured_keys(st, [x["k"] for x in ss.ranked_roster(self.si, st, a)]))
        res = self.verdict([{"key": kb, "from": b, "to": a}, {"key": give, "from": a, "to": b}], state=st)
        rows = [r for r in res["rules"] if r["rule"] == "antitank" and r.get("check") == "injured"]
        self.assertEqual([r["level"] for r in rows], ["review"])
        self.assertNotEqual(res["status"], "LEGAL")

    def test_three_team_trades_are_checked_per_team(self):
        a, b, c = sorted(self.si["franchises"])[:3]
        ra, rb, rc = (ss.ranked_roster(self.si, self.state, f)[-1]["k"] for f in (a, b, c))
        res = self.verdict([{"key": ra, "from": a, "to": b}, {"key": rb, "from": b, "to": c}, {"key": rc, "from": c, "to": a}])
        self.assertEqual({r["team"] for r in res["rules"] if r["rule"] == "cap"}, {self.si["shorts"][f] for f in (a, b, c)})
        self.assertIn(res["status"], ("LEGAL", "BLOCKED", "COMMISSIONER REVIEW"))

    def test_explanations_state_the_numbers_and_never_use_dollar_signs(self):
        for m in list(swaps(self.si, self.state))[:40]:
            for r in self.verdict(m)["rules"]:
                self.assertNotIn("$", r["reason"])
        cap = next(r for m in swaps(self.si, self.state) for r in self.verdict(m)["rules"] if r["rule"] == "cap")
        self.assertRegex(cap["reason"], r"Payroll \d+(\.\d+)? → \d+(\.\d+)?")
        self.assertNotIn("$", json.dumps(self.rules))

    def _roster_pair(self):
        """(full team, other team) so that a 2-for-1 into the full team overflows the 15 spots."""
        sizes = {f: len(ls.team_players(self.si, self.state, f)) for f in self.si["franchises"]}
        spots = self.rules["roster"]["spots"]
        full = max(sizes, key=sizes.get)
        other = next(f for f in sorted(sizes) if f != full and sizes[f] >= 2)
        return full, other, spots, sizes

    def test_roster_over_the_limit_is_blocked_until_drops_bring_it_back(self):
        full, other, spots, sizes = self._roster_pair()
        acq = tc.acquisitions(self.si)
        give = [r["k"] for r in ss.ranked_roster(self.si, self.state, other) if (r["k"], other) not in acq][:2]
        extra = sizes[full] + 2 - spots
        if extra <= 0:
            self.skipTest("no team is close enough to the roster limit")
        moves = [{"key": k, "from": other, "to": full} for k in give]
        res = self.verdict(moves)
        self.assertIn("blocked", self.levels(res, "size"))
        own = [r for r in ss.ranked_roster(self.si, self.state, full) if self.si["registry"] and ls.player_cap(self.si, r["k"]) < self.rules["drops"]["reviewFrom"]]
        drops = [{"key": r["k"], "team": full} for r in own[-extra:]]
        if len(drops) == extra:
            res2 = self.verdict(moves, drops=drops)
            self.assertEqual([x["level"] for x in res2["rules"] if x["rule"] == "size" and x["team"] == self.si["shorts"][full]], ["ok"])
            self.assertEqual({x["level"] for x in res2["rules"] if x["rule"] == "drop"}, {"info"})

    def test_drop_rules_protect_20_plus_and_send_10_to_19_to_review(self):
        full, other, spots, sizes = self._roster_pair()
        rows = ss.ranked_roster(self.si, self.state, full)
        dr = self.rules["drops"]
        a, b = sorted(self.si["franchises"])[:2]
        for want, test in (("blocked", lambda c: c >= dr["neverAtOrAbove"]), ("review", lambda c: dr["reviewFrom"] <= c < dr["neverAtOrAbove"]), ("info", lambda c: c < dr["reviewFrom"])):
            hit = next(((f, r) for f in (a, b) for r in ss.ranked_roster(self.si, self.state, f) if test(r["c"])), None)
            if hit is None:
                continue
            f, r = hit
            g = b if f == a else a
            mv = [{"key": ss.ranked_roster(self.si, self.state, g)[-1]["k"], "from": g, "to": f}, {"key": ss.ranked_roster(self.si, self.state, f)[-1]["k"], "from": f, "to": g}]
            if r["k"] in {m["key"] for m in mv}:
                continue
            res = self.verdict(mv, drops=[{"key": r["k"], "team": f}])
            self.assertEqual([x["level"] for x in res["rules"] if x["rule"] == "drop"], [want], (want, r["n"], r["c"]))

    def _cheap_player(self, f, below):
        return next(r for r in ss.ranked_roster(self.si, self.state, f) if r["c"] < below and r["c"] >= 0)

    def test_top_50_preseason_players_cannot_be_dropped_even_when_cheap(self):
        """The rule is 'paid 20+ OR preseason top 50'. No live player is both cheap and top 50 today, so make one."""
        a, b = sorted(self.si["franchises"])[:2]
        cheap = self._cheap_player(a, self.rules["drops"]["reviewFrom"])
        si2 = dict(self.si)
        si2["registry"] = {k: dict(v) for k, v in self.si["registry"].items()}
        si2["registry"][cheap["k"]]["oRank"] = 7
        give = [r["k"] for r in ss.ranked_roster(self.si, self.state, b)][-1]
        take = [r["k"] for r in ss.ranked_roster(self.si, self.state, a) if r["k"] != cheap["k"]][-1]
        mv = [{"key": give, "from": b, "to": a}, {"key": take, "from": a, "to": b}]
        res = tc.check_proposal(si2, self.state, mv, LATER, self.rules, [{"key": cheap["k"], "team": a}])
        drop = [x for x in res["rules"] if x["rule"] == "drop"]
        self.assertEqual([x["level"] for x in drop], ["blocked"])
        self.assertIn("preseason O-Rank 7", drop[0]["reason"])
        # the same player at his real rank (outside the top 50) is a plain drop
        self.assertEqual([x["level"] for x in self.verdict(mv, drops=[{"key": cheap["k"], "team": a}])["rules"] if x["rule"] == "drop"], ["info"])

    def test_restricted_drops_name_the_criterion(self):
        for f in sorted(self.si["franchises"]):
            hit = next((r for r in ss.ranked_roster(self.si, self.state, f) if self.rules["drops"]["reviewFrom"] <= r["c"] < self.rules["drops"]["neverAtOrAbove"]
                        and r["k"] not in tc.preseason_ranks(self.si, self.rules["drops"]["neverTopRanked"])), None)
            if hit:
                g = next(x for x in sorted(self.si["franchises"]) if x != f)
                mv = [{"key": ss.ranked_roster(self.si, self.state, g)[-1]["k"], "from": g, "to": f}, {"key": ss.ranked_roster(self.si, self.state, f)[-1]["k"], "from": f, "to": g}]
                if hit["k"] in {m["key"] for m in mv}:
                    continue
                res = self.verdict(mv, drops=[{"key": hit["k"], "team": f}])
                row = next(x for x in res["rules"] if x["rule"] == "drop")
                self.assertEqual(row["level"], "review")
                self.assertIn("top 100", row["reason"])
                return
        self.skipTest("no 10-19 salary player outside the preseason top 50")

    def test_protected_players_are_named_with_their_reason(self):
        for f in sorted(self.si["franchises"]):
            big = next((r for r in ss.ranked_roster(self.si, self.state, f) if r["c"] >= self.rules["drops"]["neverAtOrAbove"]), None)
            if big:
                g = next(x for x in sorted(self.si["franchises"]) if x != f)
                mv = [{"key": ss.ranked_roster(self.si, self.state, g)[-1]["k"], "from": g, "to": f}, {"key": ss.ranked_roster(self.si, self.state, f)[-1]["k"], "from": f, "to": g}]
                if big["k"] in {m["key"] for m in mv}:
                    continue
                row = next(x for x in self.verdict(mv, drops=[{"key": big["k"], "team": f}])["rules"] if x["rule"] == "drop")
                self.assertEqual(row["level"], "blocked")
                self.assertIn(f"paid {big['c']:g}", row["reason"])
                return
        self.skipTest("no 20+ player on any roster")

    def test_invalid_drops_are_rejected(self):
        a, b = sorted(self.si["franchises"])[:2]
        ra, rb = ss.ranked_roster(self.si, self.state, a)[-1]["k"], ss.ranked_roster(self.si, self.state, b)[-1]["k"]
        mv = [{"key": ra, "from": a, "to": b}, {"key": rb, "from": b, "to": a}]
        self.assertEqual(self.verdict(mv, drops=[{"key": ra, "team": a}])["status"], "BLOCKED")     # dropping a player who is also traded
        self.assertEqual(self.verdict(mv, drops=[{"key": rb, "team": a}])["status"], "BLOCKED")     # dropping someone from the wrong team

    def test_drop_thresholds_mirror_the_keeper_assumptions(self):
        with open(os.path.join(ROOT, "config", "what_if_assumptions.json"), encoding="utf-8") as f:
            wi = json.load(f)
        self.assertEqual(self.rules["drops"]["neverAtOrAbove"], wi["neverDropAtOrAbove"])
        self.assertEqual(self.rules["drops"]["reviewFrom"], wi["reviewDropFrom"])
        self.assertEqual(len(tc.preseason_ranks(self.si, self.rules["drops"]["neverTopRanked"])), self.rules["drops"]["neverTopRanked"])

    # ---- picks: 1sts are locked in-season, next season's 2nd / 3rd only inside a Trade Tank trade, nothing further ahead
    def _pk(self, rnd, fid, year=2027):
        return {"key": f"{year}-R{rnd}-{fid}", "type": "pick"}

    def test_first_round_picks_are_blocked_and_later_rounds_go_to_review(self):
        a, b = sorted(self.si["franchises"])[:2]
        keys = {m["key"]: m for m in [self._pk(1, a), self._pk(2, a), self._pk(3, a)]}
        r1 = self.verdict([{**self._pk(1, a), "from": a, "to": b}])
        self.assertEqual([x["level"] for x in r1["rules"] if x["rule"] == "pick"], ["blocked"])
        self.assertIn("1st-round", [x for x in r1["rules"] if x["rule"] == "pick"][0]["reason"])
        for rnd in (2, 3):
            r = self.verdict([{**self._pk(rnd, a), "from": a, "to": b}])
            self.assertEqual([x["level"] for x in r["rules"] if x["rule"] == "pick"], ["review"])
            self.assertIn("Trade Tank", [x for x in r["rules"] if x["rule"] == "pick"][0]["reason"])
        self.assertEqual(len(keys), 3)

    def test_picks_must_be_owned_and_cannot_be_further_ahead(self):
        a, b = sorted(self.si["franchises"])[:2]
        self.assertEqual(self.verdict([{**self._pk(2, b), "from": a, "to": b}])["status"], "BLOCKED")       # not a's pick
        far = self.verdict([{**self._pk(2, a, 2028), "from": a, "to": b}])
        self.assertEqual(far["status"], "BLOCKED")
        self.assertIn("beyond next season", far["rules"][0]["reason"])

    def test_picks_do_not_change_payroll_or_roster_counts(self):
        a, b = sorted(self.si["franchises"])[:2]
        res = self.verdict([{**self._pk(3, a), "from": a, "to": b}, {**self._pk(3, b), "from": b, "to": a}])
        for x in res["rules"]:
            if x["rule"] == "cap":
                self.assertEqual(x["before"], x["after"])
        self.assertEqual([x["level"] for x in res["rules"] if x["rule"] == "pick"], ["review", "review"])   # the overall verdict depends on the rosters, the pick rows do not

    # ---- Yahoo slots: incoming players land outside IL; only injured players can go on IL
    def _slot_case(self):
        """A team with 12 players outside IL receives a player without sending one: 13 outside IL."""
        elig = set(self.rules["yahoo"]["ilEligibleStatuses"])
        cap = self.rules["yahoo"]["activeSlots"] + self.rules["yahoo"]["benchSlots"]
        for f in sorted(self.si["franchises"]):
            keys = ls.team_players(self.si, self.state, f)
            non_il = [k for k in keys if self.state["slots"].get(k) not in ss.SLOTS_IL]
            if len(non_il) == cap:
                g = next(x for x in sorted(self.si["franchises"]) if x != f)
                give = ss.ranked_roster(self.si, self.state, g)[-1]["k"]
                return f, g, give, [k for k in non_il if self.state["status"].get(k) in elig]
        self.skipTest("no team is exactly at the lineup + bench limit")

    def test_receiving_a_player_with_no_free_lineup_or_bench_spot_is_blocked(self):
        f, g, give, movable = self._slot_case()
        res = self.verdict([{"key": give, "from": g, "to": f}, {"key": ss.ranked_roster(self.si, self.state, f)[0]["k"], "from": f, "to": g}] if False else [{"key": give, "from": g, "to": f}])
        slots = [x for x in res["rules"] if x["rule"] == "slots" and x["team"] == self.si["shorts"][f]]
        self.assertEqual([x["level"] for x in slots], ["blocked"])
        self.assertIn("never straight on IL", slots[0]["reason"])

    def test_moving_an_injured_player_to_il_first_makes_room_but_a_healthy_one_cannot(self):
        f, g, give, movable = self._slot_case()
        il_now = [k for k in ls.team_players(self.si, self.state, f) if self.state["slots"].get(k) in ss.SLOTS_IL]
        healthy = next(k for k in ls.team_players(self.si, self.state, f) if k not in il_now and self.state["status"].get(k) not in self.rules["yahoo"]["ilEligibleStatuses"])
        bad = self.verdict([{"key": give, "from": g, "to": f}], ils=[{"key": healthy, "team": f}])
        self.assertIn("blocked", [x["level"] for x in bad["rules"] if x["rule"] == "il"])                  # healthy players can't be parked on IL
        if movable and len(il_now) < self.rules["yahoo"]["ilSlots"]:
            ok = self.verdict([{"key": give, "from": g, "to": f}], ils=[{"key": movable[0], "team": f}])
            self.assertEqual([x["level"] for x in ok["rules"] if x["rule"] == "slots" and x["team"] == self.si["shorts"][f]], ["ok"])

    def test_il_slots_are_capped(self):
        f, g, give, movable = self._slot_case()
        keys = [k for k in ls.team_players(self.si, self.state, f) if self.state["slots"].get(k) not in ss.SLOTS_IL]
        many = [{"key": k, "team": f} for k in keys[:self.rules["yahoo"]["ilSlots"] + 1]]
        res = self.verdict([{"key": give, "from": g, "to": f}], ils=many)
        self.assertTrue(any(x["rule"] == "slots" and "IL slots" in x["reason"] for x in res["rules"]))

    def test_deadline_and_trade_tank_cutoff(self):
        a, b = sorted(self.si["franchises"])[:2]
        ra, rb = ss.ranked_roster(self.si, self.state, a)[-1]["k"], ss.ranked_roster(self.si, self.state, b)[-1]["k"]
        swap = [{"key": ra, "from": a, "to": b}, {"key": rb, "from": b, "to": a}]
        self.assertEqual([x["level"] for x in self.verdict(swap, "2027-02-18T23:00:00Z")["rules"] if x["rule"] == "deadline"], ["ok"])
        late = self.verdict(swap, "2027-02-19T00:00:00Z")
        self.assertEqual(late["status"], "BLOCKED")
        self.assertEqual([x["level"] for x in late["rules"] if x["rule"] == "deadline"], ["blocked"])
        pick = [{**self._pk(2, a), "from": a, "to": b}]
        self.assertEqual([x["level"] for x in self.verdict(pick, "2027-02-04T12:00:00Z")["rules"] if x["rule"] == "pick"], ["review"])
        self.assertEqual([x["level"] for x in self.verdict(pick, "2027-02-05T00:00:00Z")["rules"] if x["rule"] == "pick"], ["blocked"])

    def test_checking_never_changes_state(self):
        before = json.dumps(self.state, sort_keys=True, default=str)
        for m in list(swaps(self.si, self.state))[:20]:
            self.verdict(m)
        self.assertEqual(before, json.dumps(self.state, sort_keys=True, default=str))

    def test_top_32_matches_the_preseason_snapshot(self):
        with open(os.path.join(ROOT, "data", "what_if", "snapshots", "2026-10-08", "players.json"), encoding="utf-8") as f:
            snap = json.load(f)
        rows = snap if isinstance(snap, list) else snap.get("players", snap)
        top = {p["playerKey"] for p in sorted(rows, key=lambda p: p["oRank"])[:32]}
        self.assertEqual(top, tc.top_ranked(self.si, self.rules))

    def test_verdict_vocabulary_has_no_judgement(self):
        for m in list(swaps(self.si, self.state))[:10]:
            r = self.verdict(m)
            self.assertIn(r["status"], ("LEGAL", "BLOCKED", "COMMISSIONER REVIEW"))
            text = " ".join(x["reason"].lower() for x in r["rules"])
            for word in ("fair", "good trade", "should", "recommend"):
                self.assertNotIn(word, text)


if __name__ == "__main__":
    unittest.main()
