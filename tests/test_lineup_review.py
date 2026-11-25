"""The lineup review: one test per row of the owner's case table (scripts/lineup_review.py), then the combinations."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import lineup_log as ll  # noqa: E402
import lineup_review as lv  # noqa: E402

RULES = lv.load_rules()
DAY = "2026-11-25"
TIP = "2026-11-25T20:00:00Z"                      # noon Pacific
EARLY = "2026-11-25T16:00:00Z"
POS = {"PG": ["PG"], "SG": ["SG"], "G": ["PG"], "SF": ["SF"], "PF": ["PF"], "F": ["SF"], "C": ["C"], "FC": ["C"], "Util": ["PG"]}


def P(pid, slot, st=None, game=True, pos=None, team="t1", **kw):
    """A player on a roster; `st` = the status all day, or `late` = a status that only appears after the one-hour mark."""
    return dict({"p": pid, "n": "N" + pid, "team": team, "slot": slot, "st": st, "g": "7:30 pm" if game else None,
                 "pos": pos or POS.get(slot) or ["PG"]}, **kw)


def full(*override):
    """A complete healthy lineup (nine starters with a game), with the given players added or replacing a slot's starter."""
    rows = {s: P("s" + s, s) for s in RULES["slots"]}
    extra = []
    for o in override:
        if o["slot"] in rows:
            rows[o["slot"]] = o
        else:
            extra.append(o)
    return [r for r in rows.values() if r["p"] is not None] + extra


def empty(slot):
    return {"p": None, "slot": slot}


def day(players, date=DAY, late=(), gap=False, final=False, start=EARLY, tip=TIP):
    """The log records of one day: day_start, the late changes (30 minutes before tip), and a lock for every player with a game."""
    tip, start = tip.replace(DAY, date), start.replace(DAY, date)
    recs = [{"kind": "day_start", "date": date, "capturedAt": start, "players": [dict(p) for p in players]}]
    now = {p["p"]: dict(p) for p in players}
    for pid, st in late:
        now[pid]["st"] = st
        recs.append(dict(now[pid], kind="state", date=date, capturedAt=tip.replace("T20:00", "T19:30")))
    if gap:
        recs.append({"kind": "gap", "date": date, "capturedAt": tip, "from": tip.replace("T20:00", "T18:00"), "to": tip.replace("T20:00", "T19:20")})
    for p in now.values():
        if p["g"]:
            recs.append({"kind": "lock", "date": date, "capturedAt": tip, "team": p["team"], "k": "478.p." + p["p"], "n": p["n"], "slot": p["slot"],
                         "st": p["st"], "pos": p["pos"], "gs": "final" if final else "live", **({"ie": p["ie"]} if "ie" in p else {})})
    return recs


def run(days, ranks=None, played=None, il=None):
    items, cleared = lv.Review(days, RULES, ranks or {}, il or {}, {}, played or {}).run()
    return items, [(c["case"], c["n"]) for c in cleared]


def got(items, team="t1"):
    return sorted((i["case"], i["o"], i["n"]) for i in items if i["team"] == team)


IL3 = [P("il%d" % n, "IL", "O") for n in range(3)]      # a full injured list


class TestStarters(unittest.TestCase):
    def test_1_healthy_uncertain_or_gameless_starters_are_nothing(self):
        items, _ = run({DAY: day(full(P("a", "PG", "Q"), P("b", "SG", "P"), P("c", "G", None, game=False), P("x", "BN")))})
        self.assertEqual(got(items), [])

    def test_2_listed_out_after_the_hour_is_cleared(self):
        items, cleared = run({DAY: day(full(P("a", "PG", "Q"), P("x", "BN", pos=["PG"])), late=[("a", "O")])})
        self.assertEqual(got(items), [])
        self.assertIn((2, "Na"), cleared)

    def test_3_out_with_bench_cover_is_a_fault(self):
        items, _ = run({DAY: day(full(P("a", "PG", "O"), P("x", "BN", pos=["PG"])))})
        self.assertEqual(got(items), [(3, "fault", "Na")])
        self.assertIn("Nx on bench", items[0]["fact"])

    def test_4_and_5_no_cover_with_an_open_il_slot_is_an_il_item_after_two_days(self):
        out = lambda date: day(full(P("a", "PG", "O")), date=date)  # noqa: E731
        items, _ = run({DAY: out(DAY)})
        self.assertEqual(got(items), [(5, "watch", "Na")])
        days = {d: out(d) for d in ("2026-11-22", "2026-11-23", "2026-11-24", DAY)}
        items, _ = run(days)
        self.assertEqual([(i["date"], i["case"], i["o"]) for i in items],
                         [("2026-11-22", 5, "watch"), ("2026-11-23", 5, "watch"), ("2026-11-24", 5, "watch"), (DAY, 4, "il")])

    def test_6_no_cover_and_no_il_room_is_cleared_and_na_cannot_go_to_il(self):
        for players in (full(P("a", "PG", "O"), *IL3), full(P("a", "PG", "NA"))):
            items, cleared = run({DAY: day(players)})
            self.assertEqual([x for x in got(items) if x[2] == "Na"], [])
            self.assertIn((6, "Na"), cleared)

    def test_7_and_8_an_empty_slot_is_a_fault_only_with_cover(self):
        items, _ = run({DAY: day(full(empty("C"), P("x", "BN", pos=["C"])))})
        self.assertEqual(got(items), [(7, "fault", "C slot")])
        items, cleared = run({DAY: day(full(empty("C"), P("x", "BN", pos=["PG"])))})
        self.assertEqual(got(items), [])
        self.assertIn((8, "C slot"), cleared)


class TestBench(unittest.TestCase):
    RANKS = {"star": 10, **{"s" + s: 20 for s in ("PG", "SG", "G", "SF", "PF", "F", "C", "FC", "Util")}}

    def test_9_a_star_who_could_start_over_a_non_star_is_a_fault(self):
        items, _ = run({DAY: day(full(P("star", "BN", pos=["PG"])))}, ranks={"star": 10})
        self.assertEqual(got(items), [(9, "fault", "Nstar")])

    def test_10_a_lineup_full_of_stars_clears_it(self):
        items, cleared = run({DAY: day(full(P("star", "BN", pos=["PG"])))}, ranks=self.RANKS)
        self.assertEqual(got(items), [])
        self.assertIn((10, "Nstar"), cleared)

    def test_11_an_uncertain_star_or_one_just_back_is_cleared(self):
        items, cleared = run({DAY: day(full(P("star", "BN", "Q", pos=["PG"])))}, ranks={"star": 10})
        self.assertEqual((got(items), cleared), ([], [(11, "Nstar")]))
        days = {"2026-11-24": day(full(P("star", "BN", "O", pos=["PG"]), *IL3), date="2026-11-24"), DAY: day(full(P("star", "BN", pos=["PG"]), *IL3))}
        items, cleared = run(days, ranks={"star": 10})
        self.assertEqual(got(items), [])
        self.assertIn((11, "Nstar"), cleared)

    def test_11_a_player_just_back_is_not_counted_as_cover_either(self):
        days = {"2026-11-24": day(full(P("x", "BN", "O", pos=["PG"]), *IL3), date="2026-11-24"),
                DAY: day(full(P("a", "PG", "O"), P("x", "BN", pos=["PG"]), *IL3))}
        self.assertEqual([i for i in run(days)[0] if i["case"] == 3], [])

    def test_12_and_13_an_out_bench_player_matters_only_with_il_room_and_after_two_days(self):
        out = lambda date, extra=(): day(full(P("a", "BN", "O", game=False), *extra), date=date)  # noqa: E731
        self.assertEqual(got(run({DAY: out(DAY)})[0]), [(13, "watch", "Na")])
        days = {d: out(d) for d in ("2026-11-22", "2026-11-23", "2026-11-24", DAY)}
        self.assertEqual([(i["case"], i["o"]) for i in run(days)[0] if i["date"] == DAY], [(12, "il")])
        self.assertEqual(got(run({DAY: out(DAY, IL3)})[0]), [])

    def test_one_open_il_slot_covers_one_player_the_longest_out(self):
        first = day(full(P("b", "BN", "O", game=False), IL3[0], IL3[1]), date="2026-11-22")
        both = lambda date: day(full(P("a", "BN", "O", game=False), P("b", "BN", "O", game=False), IL3[0], IL3[1]), date=date)  # noqa: E731
        days = {"2026-11-22": first, **{d: both(d) for d in ("2026-11-23", "2026-11-24", DAY)}}
        self.assertEqual([i["n"] for i in run(days)[0] if i["date"] == DAY], ["Nb"])


class TestInjuredList(unittest.TestCase):
    def il(self, *dates_and_status, **kw):
        days = {d: day(full(P("a", "IL", st, ie=ie, **kw)), date=d) for d, st, ie in dates_and_status}
        return [(i["date"], i["case"], i["o"]) for i in run(days, played=getattr(self, "played", None))[0] if i["n"] == "Na"]

    def test_14_out_or_doubtful_on_il_is_nothing(self):
        for st in ("O", "INJ", "OFS", "D"):
            self.assertEqual(self.il((DAY, st, 1)), [], st)
        self.assertEqual(self.il((DAY, None, 1)), [])               # no status but Yahoo still shows him IL-eligible

    def test_15_questionable_waits(self):
        self.assertEqual(self.il((DAY, "Q", 0)), [(DAY, 15, "watch")])
        self.assertEqual(self.il(("2026-11-24", "Q", 0), (DAY, "Q", 0)), [("2026-11-24", 15, "watch"), (DAY, 15, "watch")])

    def test_16_then_17_one_game_of_grace_after_clearance(self):
        self.assertEqual(self.il(("2026-11-23", "O", 1), ("2026-11-24", None, 0), (DAY, None, 0)),
                         [("2026-11-24", 16, "watch"), (DAY, 17, "fault")])

    def test_17_playing_while_questionable_starts_the_clock(self):
        self.played = {"a": {"2026-11-24"}}
        self.assertEqual(self.il(("2026-11-24", "Q", 0), (DAY, "Q", 0)), [("2026-11-24", 16, "watch"), (DAY, 17, "fault")])

    def test_going_back_out_resets_the_clock(self):
        self.assertEqual(self.il(("2026-11-23", None, 0), ("2026-11-24", "O", 1), (DAY, None, 0)),
                         [("2026-11-23", 16, "watch"), (DAY, 16, "watch")])

    def test_18_suspended_or_not_active_is_shown_not_faulted(self):
        for st in ("NA", "SUSP"):
            self.assertEqual(self.il((DAY, st, 0)), [(DAY, 18, "watch")], st)


class TestUnconfirmed(unittest.TestCase):
    def check(self, records):
        items, _ = run({DAY: records})
        self.assertEqual(got(items), [(19, "watch", "Na")])
        self.assertTrue(items[0]["unconfirmed"])

    def test_19_a_gap_across_the_hour_a_game_first_seen_over_or_a_late_first_read(self):
        players = full(P("a", "PG", "O"), P("x", "BN", pos=["PG"]))
        self.check(day(players, gap=True))
        self.check(day(players, final=True))
        self.check(day(players, start="2026-11-25T19:30:00Z"))

    def test_19_old_records_without_history(self):
        records = [r for r in day(full(P("a", "PG", "O"), P("x", "BN", pos=["PG"]))) if r["kind"] == "lock"]
        self.check(records)

    def test_a_player_added_after_the_hour_is_not_judged(self):
        base = full(P("x", "BN", pos=["PG"]))
        records = day(base)
        late = P("a", "PG", "O")
        records = [records[0]] + [dict(late, kind="state", date=DAY, capturedAt="2026-11-25T19:30:00Z")] + records[1:] + \
                  [{"kind": "lock", "date": DAY, "capturedAt": TIP, "team": "t1", "k": "478.p.a", "n": "Na", "slot": "PG", "st": "O", "pos": ["PG"], "gs": "live"}]
        records = [r for r in records if not (r.get("kind") == "lock" and r.get("n") == "NsPG")]
        self.assertEqual([i for i in run({DAY: records})[0] if i["n"] == "Na" and i["o"] == "fault"], [])


class TestCombinations(unittest.TestCase):
    def test_two_wasted_starts_and_one_bench_player_make_one_fault(self):
        items, _ = run({DAY: day(full(P("a", "PG", "O"), P("b", "G", "O"), P("x", "BN", pos=["PG"]), *IL3))})
        self.assertEqual(len([i for i in items if i["case"] == 3]), 1)

    def test_cover_may_rearrange_the_healthy_starters(self):
        # the centre slot is wasted; the bench player is a guard, but the FC starter can slide to C and the guard take... nothing he fits: no cover
        items, _ = run({DAY: day(full(P("a", "C", "O"), P("x", "BN", pos=["PG"]), *IL3))})
        self.assertEqual([i for i in items if i["case"] == 3], [])
        # here the bench player fits Util only after the Util starter slides to the wasted PG slot
        items, _ = run({DAY: day(full(P("a", "PG", "O"), P("u", "Util", pos=["PG", "C"]), P("x", "BN", pos=["C"]), *IL3))})
        self.assertEqual([(i["case"], i["n"]) for i in items if i["case"] == 3], [(3, "Na")])

    def test_week_counts_come_from_faults_only_and_merge_by_player(self):
        days = {d: day(full(P("a", "PG", "O"), P("x", "BN", pos=["PG"]), P("q", "IL", "Q", ie=0)), date=d) for d in ("2026-11-24", DAY)}
        feed = {"week": 6, "asOf": TIP, "matchups": [{"teams": [{"team": "t1"}, {"team": "t2"}]}], "lineupChecks": {"teams": [], "byDate": {}}}
        out = lv.build(feed, days, "2026-10-19", RULES, {}, {}, {}, {})
        t = out["teams"]["t1"]
        self.assertEqual((t["days"], t["players"], t["stars"], t["meets"], t["opponent"]), (2, 1, 0, True, "t2"))
        self.assertEqual([(i["o"], i["what"], len(i["dates"])) for i in t["items"]], [("fault", "started while out", 2), ("watch", "on IL, Q", 2)])

    def test_days_before_the_log_come_in_as_unconfirmed(self):
        feed = {"week": 6, "asOf": TIP, "matchups": [], "lineupChecks": {"teams": [{"yahooId": 1, "team": "t1"}], "byDate": {
            "2026-11-23": {"1": [{"k": "star_benched", "p": "Old Star", "id": "9"}]}, DAY: {"1": [{"k": "empty_slot", "s": "C"}]}}}}
        out = lv.build(feed, {DAY: []}, "2026-10-19", RULES, {}, {}, {}, {})
        self.assertEqual([(i["n"], i["o"], i["unconfirmed"]) for i in out["teams"]["t1"]["items"]], [("Old Star", "watch", True)])
        self.assertEqual(out["teams"]["t1"]["days"], 0)

    def test_it_runs_on_what_the_logger_writes(self):
        def read(minute, st, gs, hour=18):
            row = {"s": "PG", "n": "A", "p": "1", "pos": ["PG"], "st": st, "g": "x", "gs": gs}
            bench = {"s": "BN", "n": "B", "p": "2", "pos": ["PG"], "st": "", "g": "x", "gs": gs}
            return {"week": 6, "asOf": "2026-11-25T%02d:%02d:00Z" % (hour, minute), "matchups": [{"teams": [{"team": "t1", "roster": [row, bench]}]}]}
        with tempfile.TemporaryDirectory() as d:
            previous = None
            reads = [read(m, "O", "upcoming") for m in (0, 20, 40)] + [read(m, "O", "upcoming", 19) for m in (0, 20, 40)] + [read(0, "O", "live", 20)]
            for f in reads:
                ll.append(d, f, {}, {}, f["asOf"], previous)
                previous = f
            out = d + "/live.json"
            with open(out, "w") as fh:
                json.dump(reads[-1], fh)
            with open(d + "/reg.json", "w") as fh:
                json.dump({"players": []}, fh)
            self.assertEqual(lv.main(["--log-dir", d, "--feed", out, "--registry", d + "/reg.json", "--season-start", "2026-10-19"]), 0)
            with open(out) as fh:
                items = json.load(fh)["lineupReview"]["teams"]["t1"]["items"]
        self.assertEqual([(i["o"], i["case"], i["n"]) for i in items if i["case"] == 3], [("fault", 3, "A")])


if __name__ == "__main__":
    unittest.main()
