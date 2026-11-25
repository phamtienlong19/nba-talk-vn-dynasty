"""The roster feed: Yahoo's current rosters every few minutes, overlaid on the page, display only."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import _site  # noqa: E402,F401
import build_roster_feed as brf  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402
import yahoo_rosters as yr  # noqa: E402
from _drive import drive_page  # noqa: E402

ROOT = os.path.join(HERE, "..")
CFG = yr.load_config()
with open(os.path.join(ROOT, "data", "2026-27", "rosters", "team_map.json"), encoding="utf-8") as _f:
    TEAM_MAP = json.load(_f)
NOW = "2026-11-24T12:00:00Z"


def team_page(tid, n=8, slot="BN"):
    return {"teamId": tid, "teamName": f"Team {tid}", "players": [
        {"playerId": str(1000 * tid + i), "name": f"P{tid}-{i}", "slot": slot if i else "PG", "injury": "o" if i == 1 else "", "nbaTeam": "BOS"} for i in range(n)]}


class TestBuilder(unittest.TestCase):
    def build(self, pages, previous=None):
        orig = yr.fetch_teams
        yr.fetch_teams = lambda cfg, ids, fetcher, delay=None, **k: ([pages[t] for t in ids if t in pages], [{"teamId": t, "code": "HTTP_500", "detail": "x"} for t in ids if t not in pages])
        try:
            return brf.build(CFG, TEAM_MAP, None, NOW, previous)
        finally:
            yr.fetch_teams = orig

    def test_shape_keys_and_statuses(self):
        doc = self.build({t: team_page(t) for t in CFG["teamIds"]})
        self.assertEqual((doc["schema"], doc["asOf"], doc["complete"]), ("roster-feed/1", NOW, True))
        self.assertEqual(len(doc["teams"]), 16)
        team = doc["teams"]["franchise-01"]
        p = team["players"]
        self.assertTrue(all(x["k"].startswith("478.p.") for x in p))
        self.assertEqual([x.get("st") for x in p[:3]], [None, "O", None])        # injury text upper-cased, healthy has no key
        self.assertEqual(team["asOf"], NOW)

    def test_a_failed_team_keeps_its_previous_entry_with_its_own_older_time(self):
        first = self.build({t: team_page(t) for t in CFG["teamIds"]})
        old = dict(first, teams={k: dict(v, asOf="2026-11-24T11:00:00Z") for k, v in first["teams"].items()})
        pages = {t: team_page(t) for t in CFG["teamIds"] if t != CFG["teamIds"][0]}
        doc = self.build(pages, previous=old)
        self.assertFalse(doc["complete"])
        fid = yr.franchise_for(CFG, TEAM_MAP, CFG["teamIds"][0])
        self.assertEqual(doc["teams"][fid]["asOf"], "2026-11-24T11:00:00Z")
        self.assertEqual(len(doc["teams"]), 16)

    def test_a_page_with_too_few_rows_is_not_a_roster(self):
        pages = {t: team_page(t) for t in CFG["teamIds"]}
        pages[CFG["teamIds"][0]] = team_page(CFG["teamIds"][0], n=2)
        doc = self.build(pages)
        self.assertEqual(len(doc["teams"]), 15)
        self.assertEqual(doc["errors"][-1]["code"], "UNUSABLE")

    def test_nothing_readable_raises_and_never_writes_an_empty_feed(self):
        with self.assertRaises(yr.FetchError):
            self.build({})

    def test_digest_ignores_the_clock(self):
        a = self.build({t: team_page(t) for t in CFG["teamIds"]})
        orig = brf.yr.fetch_teams
        b = brf.build.__wrapped__ if hasattr(brf.build, "__wrapped__") else None
        self.assertIsNone(b)
        yr.fetch_teams = lambda cfg, ids, fetcher, delay=None, **k: ([team_page(t) for t in ids], [])
        try:
            c = brf.build(CFG, TEAM_MAP, None, "2026-11-24T13:00:00Z")
        finally:
            yr.fetch_teams = orig
        self.assertEqual(a["digest"], c["digest"])

    def test_the_feed_workflow_never_touches_main_or_data(self):
        wf = open(os.path.join(ROOT, ".github", "workflows", "update-roster-feed.yml"), encoding="utf-8").read()
        loop = open(os.path.join(ROOT, "scripts", "roster_feed_loop.sh"), encoding="utf-8").read()
        self.assertIn("gh workflow run update-roster-feed.yml", wf)                       # queues its own successor first
        self.assertNotIn("pull-requests", wf)
        self.assertNotIn("gh pr", wf + loop)
        self.assertIn("push -q --force", loop)
        self.assertIn("roster-data", loop)
        self.assertNotIn("origin main", wf + loop)
        self.assertNotIn("data/2026-27", wf + loop)


    def test_roster_prs_skip_the_browser_suite_but_everything_else_still_runs_it(self):
        v = open(os.path.join(ROOT, ".github", "workflows", "validate.yml"), encoding="utf-8").read()
        self.assertIn("if: ${{ !startsWith(github.head_ref, 'automation/yahoo-rosters-') }}\n        run: python3 scripts/run_tests.py -j 4 --chrome 2\n", v)
        self.assertIn("startsWith(github.head_ref, 'automation/yahoo-rosters-') }}\n        run: python3 scripts/run_tests.py -j 4 --chrome 2 tests/test_*roster*.py test_season_ops test_league_state_data\n", v)
        self.assertIn("./validate.sh", v)                                                 # the site validation still runs for every PR
        helper = open(os.path.join(ROOT, "scripts", "bot_pr.sh"), encoding="utf-8").read()
        self.assertIn("gh workflow run pages.yml --ref main", helper)                      # a bot merge asks for the deploy right away


FEED_JS = """
  var D=NBA_NAV.D,off=D.scenarios[''],feed={schema:'roster-feed/1',asOf:'%s',teams:{}};
  D.teams.forEach(function(t){feed.teams[t.id]={teamId:1,name:t.short,asOf:feed.asOf,players:off.teams[t.id].roster.map(function(r){var p={k:r.k,n:r.n,s:r.s};if(r.st)p.st=r.st;return p;})};});
"""


def drive(js, asof="NOW", qs=""):
    pre = FEED_JS % {"NOW": "'+new Date().toISOString().slice(0,19)+'Z", "OLD": "'+new Date(Date.now()-40*6e4).toISOString().slice(0,19)+'Z"}.get(asof, asof)
    return drive_page(pre + js, qs=qs, wait=3000, start=600, size="1000,1400", budget=20000)


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestPageOverlay(unittest.TestCase):
    def test_a_feed_equal_to_the_verified_rosters_changes_nothing_and_says_how_fresh_it_is(self):
        r = drive("""
          var before=JSON.stringify(off.teams);R.ok=NBA_ROSTERS.set(feed);R.same=before===JSON.stringify(off.teams);R.pend=NBA_ROSTERS.pending();
          R.label=document.querySelector('.roster-verified').textContent;R.box=!!document.querySelector('.rf-pend');""")
        self.assertTrue(r["ok"] and r["same"])
        self.assertEqual(r["pend"], {"add": [], "drop": [], "moved": []})
        self.assertFalse(r["box"])
        self.assertRegex(r["label"], r"ROSTERS \d\d:\d\d · NOW")

    def test_slot_and_status_follow_yahoo_but_cap_and_ownership_never_move(self):
        r = drive("""
          var t=D.teams[0].id,row=off.teams[t].roster[0],orig={s:row.s,st:row.st},cap0=off.teams[t].cap,n0=off.teams[t].roster.length,own0=off.teams[t].roster.map(function(x){return x.k;}).join();
          feed.teams[t].players[0].s='IL';feed.teams[t].players[0].st='O';NBA_ROSTERS.set(feed);
          R.slot=row.s;R.st=row.st;R.cap=off.teams[t].cap===cap0;R.n=off.teams[t].roster.length===n0;R.own=off.teams[t].roster.map(function(x){return x.k;}).join()===own0;
          R.checker=typeof NBA_NAV.compositeNow==='function';
          var s0=orig.s,st0=orig.st;feed.teams[t].players[0].s=s0;if(st0)feed.teams[t].players[0].st=st0;else delete feed.teams[t].players[0].st;feed.digest='x2';NBA_ROSTERS.set(feed);R.back=[row.s===s0,row.st===st0];""")
        self.assertEqual((r["slot"], r["st"]), ("IL", "O"))
        self.assertTrue(r["cap"] and r["n"] and r["own"])
        self.assertEqual(r["back"], [True, True])                                       # the overlay is reversible

    def test_adds_drops_and_trades_are_listed_as_unverified_not_applied(self):
        r = drive("""
          var a=D.teams[0].id,b=D.teams[1].id,pa=feed.teams[a].players,pb=feed.teams[b].players;
          var gone=pa.splice(0,1)[0];                                   /* A loses a player ... */
          pb.push({k:gone.k,n:gone.n,s:'BN'});                           /* ... who is now on B: a trade */
          var drop=pb.splice(0,1)[0];                                    /* B also drops someone */
          pa.push({k:'478.p.99999',n:'New Guy',s:'BN'});                 /* A adds a free agent */
          var own0=JSON.stringify(off.teams[a].roster.map(function(x){return x.k;}));
          NBA_ROSTERS.set(feed);var p=NBA_ROSTERS.pending();
          R.moved=p.moved.map(function(m){return [m.n,m.from,m.to];});R.add=p.add.map(function(x){return x.n;});R.drop=p.drop.map(function(x){return x.n;});
          R.a=a;R.b=b;R.gone=gone.n;R.drop_n=drop.n;R.owned=JSON.stringify(off.teams[a].roster.map(function(x){return x.k;}))===own0;
          R.box=document.querySelector('.rf-pend summary').textContent;R.label=document.querySelector('.roster-verified').textContent;""")
        self.assertEqual(r["moved"], [[r["gone"], r["a"], r["b"]]])
        self.assertEqual((r["add"], r["drop"]), (["New Guy"], [r["drop_n"]]))
        self.assertTrue(r["owned"])                                                     # official ownership is untouched
        self.assertIn("3 moves on Yahoo not yet in the verified rosters", r["box"])
        self.assertIn("3 UNVERIFIED", r["label"])

    def test_a_provisional_identity_is_the_same_player_as_his_yahoo_id(self):
        r = drive("""
          var t=D.teams[0].id,row=off.teams[t].roster[0],pl=feed.teams[t].players[0],orig={k:row.k,s:row.s};
          row.k='provisional:'+row.n.toLowerCase().replace(/[^a-z]/g,'-');pl.s='IL';pl.st='O';          /* the page knows him provisionally; Yahoo has his real id */
          NBA_ROSTERS.set(feed);R.pend=NBA_ROSTERS.pending();R.slot=row.s;R.st=row.st;""")
        self.assertEqual(r["pend"], {"add": [], "drop": [], "moved": []})
        self.assertEqual((r["slot"], r["st"]), ("IL", "O"))                               # and his slot / status still follow Yahoo

    def test_an_old_feed_says_how_old_and_a_non_feed_is_refused(self):
        r = drive("""
          R.bad=[NBA_ROSTERS.set({schema:'x',asOf:feed.asOf,teams:{}}),NBA_ROSTERS.set(null)];NBA_ROSTERS.set(feed);
          var e=document.querySelector('.roster-verified');R.label=e.textContent;R.age=e.getAttribute('data-age');""", asof="OLD")
        self.assertEqual(r["bad"], [False, False])
        self.assertIn("AGO", r["label"])
        self.assertTrue(r["age"])

    def test_a_page_opened_from_disk_never_fetches(self):
        r = drive("R.feed=NBA_ROSTERS.feed();")
        self.assertIsNone(r["feed"])


if __name__ == "__main__":
    unittest.main()
