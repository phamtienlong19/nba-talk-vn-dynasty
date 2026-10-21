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

LATER = "2030-01-01T00:00:00Z"   # far past every cooldown
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

    def verdict(self, moves, now=LATER, state=None):
        return tc.check_proposal(self.si, state or self.state, moves, now, self.rules)

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
        self.assertIn("must move a team toward the band", next(x for x in r["rules"] if x["level"] == "blocked" and x["rule"] == "cap")["reason"])

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
