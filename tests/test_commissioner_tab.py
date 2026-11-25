"""The Commissioner tab (tab label REVIEW): every review item in one place, facts with the time they were read, never a ruling."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import _site  # noqa: E402  (the built page: index.html + the generated data blocks)
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import test_scenario_rendering as tsr  # noqa: E402
from _drive import drive_page  # noqa: E402
from _phone import phone_run  # noqa: E402


def item(o, what, name, case, at="2026-11-25T20:00:00Z", dates=("2026-11-25",), fact="PG, Zed Bench on bench", unconfirmed=False):
    return {"o": o, "case": case, "p": name, "n": name, "what": what, "fact": fact, "dates": list(dates), "at": at, "unconfirmed": unconfirmed}


def team(items, days=0, players=0, meets=False, opponent=None):
    return {"items": items, "days": days, "players": players, "stars": 0, "meets": meets, "opponent": opponent}


REVIEW = {"week": 6, "since": "2026-11-25", "cleared": 4, "rule": {"days": 2, "players": 3, "stars": 2}, "teams": {
    "franchise-01": team([item("fault", "started while out", "Zed Starter", 3, dates=("2026-11-24", "2026-11-25")),
                          item("il", "out, IL slot free", "Zed Idle", 12, fact="bench, out since 2026-11-20"),
                          item("watch", "on IL, Q", "Zed Maybe", 15, unconfirmed=False)], days=2, players=1, meets=True, opponent="franchise-02"),
    "franchise-02": team([item("fault", "top-50 benched", "Zed Star", 9)], days=1, players=1, opponent="franchise-01"),
    "franchise-03": team([item("watch", "started while out", "Zed Old", 19, unconfirmed=True)])}}
OPEN = "location.hash='#commissioner';window.dispatchEvent(new PopStateEvent('popstate'));"
SET = ("var real=window.NBA_LIVE;window.NBA_LIVE={source:function(){return 'live';},feed:function(){return {asOf:'2026-11-25T21:00:00Z',lineupReview:%s};},"
       "next:real&&real.next,exports:real&&real.exports};NBA_COMMISH.render();") % json.dumps(REVIEW)


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestCommissionerTab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = drive_page(OPEN + SET + """
          var D=JSON.parse(document.getElementById('league-data').textContent),d=NBA_COMMISH.data(),root=document.getElementById('com-root');
          R.shown=!document.getElementById('com-page').classList.contains('tab-off')&&document.getElementById('rosters-a').classList.contains('tab-off');
          R.nav=document.querySelector('.navlink.on').textContent;
          [].forEach.call(root.querySelectorAll('details'),function(e){e.open=true;});
          R.text=root.textContent;
          R.items={};d.teams.forEach(function(t){R.items[t.id]=t.items.map(function(i){return [i.kind,i.text,i.fact||'',i.at||'',i.sev];});});
          R.violations=(D.violations||[]).map(function(v){return v.team;});
          R.cap=D.teams.filter(function(t){return /OVER_CEILING|UNDER_FLOOR/.test(D.scenarios[''].teams[t.id].status);}).map(function(t){return t.id;});
          R.cards=root.querySelectorAll('.com-t').length;R.withItems=d.teams.filter(function(t){return t.items.length||t.notes.length;}).length;
          R.chips=[].map.call(root.querySelector('.com-t[data-team=franchise-01] summary').querySelectorAll('.com-c'),function(c){return c.textContent;});
          document.getElementById('tb-export').click();var b=document.querySelector('[data-ex="commissioner"]');R.export=!!b;
        """, qs="#teams", wait=1500)

    def kinds(self, team_id, kind):
        return [i for i in self.r["items"][team_id] if i[0] == kind]

    def test_the_tab_opens_and_replaces_the_other_pages(self):
        self.assertTrue(self.r["shown"])
        self.assertEqual(self.r["nav"], "REVIEW")
        self.assertEqual(self.r["cards"], self.r["withItems"])

    def test_review_outcomes_become_faults_il_rule_and_watch(self):
        fault = self.kinds("franchise-01", "fault")[0]
        self.assertEqual(fault[1:], ["Zed Starter: started while out", "NOV 24, NOV 25 · PG, Zed Bench on bench", "Read 26 Nov, 03:00", "bad"])
        self.assertEqual(self.kinds("franchise-01", "ilrule")[0][4], "warn")
        self.assertEqual(self.kinds("franchise-01", "watch")[0][4], "mute")
        self.assertTrue(self.kinds("franchise-03", "watch")[0][3].endswith("unconfirmed (no read 1 h before tip)"))
        self.assertTrue({"1 fault", "1 week", "1 IL rule", "1 watch"} <= set(self.r["chips"]), self.r["chips"])

    def test_the_week_line_carries_the_rule_count_and_the_opponent(self):
        week = self.kinds("franchise-01", "week")[0]
        self.assertEqual(week[1], "Week 6: 2 misset days, 1 player · meets rule count")
        self.assertIn("opponent also has faults", week[2])
        self.assertEqual(self.kinds("franchise-02", "week")[0][4], "warn")

    def test_the_rules_used_and_the_cleared_count_are_on_the_page(self):
        self.assertIn("4 cleared (nothing the manager could do)", self.r["text"])
        self.assertIn("Status as shown 1 hour before tip", self.r["text"])

    def test_recorded_violations_and_cap_breaches_come_from_the_data(self):
        for team_id in self.r["violations"]:
            self.assertTrue(self.kinds(team_id, "record"), team_id)
        for team_id in self.r["cap"]:
            self.assertTrue(self.kinds(team_id, "cap"), team_id)

    def test_every_item_carries_the_time_it_was_read(self):
        for items in self.r["items"].values():
            for kind, text, _fact, at, _sev in items:
                self.assertRegex(at, r"^(Snapshot|Live rosters|Read|Feed|Checkpoint) |Recorded by commissioner", (kind, text))

    def test_it_states_facts_and_leaves_the_ruling_to_the_commissioner(self):
        text = self.r["text"]
        self.assertIn("the commissioner decides", text)
        self.assertIn("Times are ICT", text)
        self.assertNotIn("$", text)
        self.assertIsNone(re.search(r"\b(should|consider|recommend|suggest)", text, re.I))
        self.assertNotIn("HEALTHY", text)

    def test_it_can_be_exported(self):
        self.assertTrue(self.r["export"])

    def test_without_a_review_it_says_so(self):
        r = drive_page(OPEN + "R.text=document.getElementById('com-root').textContent;", qs="#teams", wait=800)
        self.assertRegex(r["text"], "Lineups(feed not loaded|not in the feed yet)")

    def test_the_roster_feed_moves_the_il_facts_to_its_own_time(self):
        r = drive_page(OPEN + """
          var D=JSON.parse(document.getElementById('league-data').textContent),teams={};
          D.teams.forEach(function(t,n){teams[t.id]={asOf:'2026-11-26T03:00:00Z',players:D.scenarios[''].teams[t.id].roster.map(function(p,i){return {k:p.k,n:p.n,s:n===0&&i===0?'IL':p.s,st:n===0&&i===0?'Q':p.st};})};});
          NBA_ROSTERS.set({schema:'roster-feed/1',asOf:'2026-11-26T03:00:00Z',teams:teams});
          var d=NBA_COMMISH.data();R.il=d.teams[0].items.filter(function(i){return i.kind==='il';}).map(function(i){return [i.text,i.fact,i.at];});R.page=document.getElementById('com-root').textContent;
        """, qs="#teams", wait=1500)
        self.assertTrue(any("status Q" == f and a.startswith("Live rosters") and "10:00" in a for _t, f, a in r["il"]), r["il"])
        self.assertIn("Live rosters", r["page"])

    def test_a_direct_link_opens_the_tab(self):
        r = drive_page("""R.shown=!document.getElementById('com-page').classList.contains('tab-off');R.text=document.getElementById('com-root').textContent.slice(0,200);""", qs="#commissioner", wait=800)
        self.assertTrue(r["shown"])
        self.assertIn("the commissioner decides", r["text"])

    def test_it_fits_a_phone(self):
        r = phone_run("""document.querySelector('.navlink[data-tab=commissioner]').click();var real=window.NBA_LIVE;window.NBA_LIVE={source:function(){return "live";},feed:function(){return {asOf:"2026-11-25T21:00:00Z",lineupReview:%s};},next:real&&real.next,exports:real&&real.exports};NBA_COMMISH.render();
          [].forEach.call(document.querySelectorAll('#com-root details'),function(e){e.open=true;});R.over=document.documentElement.scrollWidth-document.documentElement.clientWidth;
          R.shown=document.querySelectorAll('.com-i').length;""" % json.dumps(REVIEW))
        self.assertNotIn("error", r)
        self.assertEqual(r["over"], 0)
        self.assertGreater(r["shown"], 0)

    def test_the_header_keeps_everything_on_screen_on_a_laptop(self):
        for width in (1100, 1280, 1440):
            r = drive_page("var t=document.querySelector('.topbar-inner');R.over=t.scrollWidth-t.clientWidth;", size="%d,900" % width, wait=600)
            self.assertEqual(r["over"], 0, width)


if __name__ == "__main__":
    unittest.main()
