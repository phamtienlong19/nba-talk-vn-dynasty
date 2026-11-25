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


def lock(team, name, flags, slot="IL", st=None, gs="final", date="2026-11-24"):
    return json.dumps({"kind": "lock", "date": date, "capturedAt": "2026-11-25T06:11:00Z", "team": team, "k": "478.p.1", "n": name,
                       "slot": slot, "st": st, "il": None, "game": "W, 1-0 vs BOS", "gs": gs, "flags": flags})


LOG = "\n".join([
    json.dumps({"kind": "first_tip", "date": "2026-11-24", "capturedAt": "2026-11-25T01:00:00Z", "teams": {}}),
    lock("franchise-01", "Zed Idle", ["healthy_on_il"]),
    lock("franchise-01", "Zed Starter", ["out_starter"], slot="PG", st="O", gs="live"),
    lock("franchise-01", "Zed Doubtful", ["healthy_on_il"], st="D"),       # written before D counted as IL-eligible
    lock("franchise-01", "Zed Quiet", []),
    "{not json",
])
OPEN = "location.hash='#commissioner';window.dispatchEvent(new PopStateEvent('popstate'));"
SET = "NBA_COMMISH.setLog({[NBA_COMMISH.dates(2)[1]]:%s});" % json.dumps(LOG)


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
          R.items={};d.teams.forEach(function(t){R.items[t.id]=t.items.map(function(i){return [i.kind,i.text,i.fact||'',i.at||''];});});
          R.violations=(D.violations||[]).map(function(v){return v.team;});
          R.il={};D.teams.forEach(function(t){D.scenarios[''].teams[t.id].roster.forEach(function(p){if((p.s==='IL'||p.s==='IL+')&&p.st==='Q')R.il[t.id]=(R.il[t.id]||0)+1;});});
          R.cap=D.teams.filter(function(t){return /OVER_CEILING|UNDER_FLOOR/.test(D.scenarios[''].teams[t.id].status);}).map(function(t){return t.id;});
          R.cards=root.querySelectorAll('.com-t').length;R.withItems=d.teams.filter(function(t){return t.items.length||t.notes.length;}).length;
          R.dates=NBA_COMMISH.dates(3,new Date('2026-11-25T06:00:00Z'));
          document.getElementById('tb-export').click();var b=document.querySelector('[data-ex="commissioner"]');R.export=!!b;
        """, qs="#teams", wait=1500)

    def kinds(self, team, kind):
        return [i for i in self.r["items"][team] if i[0] == kind]

    def test_the_tab_opens_and_replaces_the_other_pages(self):
        self.assertTrue(self.r["shown"])
        self.assertEqual(self.r["nav"], "REVIEW")
        self.assertEqual(self.r["cards"], self.r["withItems"])

    def test_lock_log_flags_are_listed_with_the_capture_time_and_when_it_was_read(self):
        got = self.kinds("franchise-01", "lock")
        self.assertEqual([g[1] for g in got], ["Zed Idle · On IL, not IL-eligible", "Zed Starter · Listed out, in a starting slot"])
        self.assertIn("no Yahoo status", got[0][2])
        self.assertRegex(got[0][3], r"^Captured .*13:11 ICT, read after the game had ended$")
        self.assertTrue(got[1][3].endswith("read while the game was on"))

    def test_a_doubtful_player_is_not_reported_for_sitting_on_il(self):
        self.assertNotIn("Zed Doubtful", self.r["text"])
        self.assertNotIn("Zed Quiet", self.r["text"])

    def test_recorded_violations_and_cap_breaches_come_from_the_data(self):
        for team in self.r["violations"]:
            self.assertTrue(self.kinds(team, "record"), team)
        for team in self.r["cap"]:
            self.assertTrue(self.kinds(team, "cap"), team)

    def test_every_item_carries_the_time_it_was_read(self):
        for items in self.r["items"].values():
            for kind, text, _fact, at in items:
                self.assertRegex(at, r"ICT|Recorded by the commissioner|Checkpoint", (kind, text))

    def test_it_states_facts_and_leaves_the_ruling_to_the_commissioner(self):
        text = self.r["text"]
        self.assertIn("the commissioner decides", text)
        self.assertNotIn("$", text)
        self.assertIsNone(re.search(r"\b(should|consider|recommend|suggest)", text, re.I))
        self.assertNotIn("HEALTHY", text)

    def test_log_days_are_us_pacific_newest_first(self):
        self.assertEqual(self.r["dates"], ["2026-11-24", "2026-11-23", "2026-11-22"])

    def test_it_can_be_exported(self):
        self.assertTrue(self.r["export"])

    def test_the_roster_feed_moves_the_il_facts_to_its_own_time(self):
        r = drive_page(OPEN + """
          var D=JSON.parse(document.getElementById('league-data').textContent),teams={};
          D.teams.forEach(function(t,n){teams[t.id]={asOf:'2026-11-26T03:00:00Z',players:D.scenarios[''].teams[t.id].roster.map(function(p,i){return {k:p.k,n:p.n,s:n===0&&i===0?'IL':p.s,st:n===0&&i===0?'Q':p.st};})};});
          NBA_ROSTERS.set({schema:'roster-feed/1',asOf:'2026-11-26T03:00:00Z',teams:teams});
          var d=NBA_COMMISH.data();R.il=d.teams[0].items.filter(function(i){return i.kind==='il';}).map(function(i){return [i.text,i.fact,i.at];});R.page=document.getElementById('com-root').textContent;
        """, qs="#teams", wait=1500)
        self.assertTrue(any("Yahoo status Q" in f and a.startswith("Yahoo rosters read") and "10:00 ICT" in a for _t, f, a in r["il"]), r["il"])
        self.assertIn("Yahoo rosters read", r["page"])

    def test_a_direct_link_opens_the_tab(self):
        r = drive_page("""R.shown=!document.getElementById('com-page').classList.contains('tab-off');R.text=document.getElementById('com-root').textContent.slice(0,200);""", qs="#commissioner", wait=800)
        self.assertTrue(r["shown"])
        self.assertIn("the commissioner decides", r["text"])

    def test_the_log_is_read_day_by_day_and_a_failed_day_is_said_so(self):
        r = drive_page(OPEN + """
          var days=NBA_COMMISH.dates(7),asked=[];
          window.fetch=function(u){var d=/(\\d{4}-\\d\\d-\\d\\d)\\.jsonl/.exec(u);if(!d)return Promise.reject();asked.push(d[1]);
            if(d[1]===days[1])return Promise.resolve({ok:true,status:200,text:function(){return Promise.resolve(%s);}});
            if(d[1]===days[2])return Promise.resolve({ok:false,status:500});
            return Promise.resolve({ok:false,status:404});};
          NBA_COMMISH.load();
          setTimeout(function(){var x=NBA_COMMISH.data();R.asked=asked.length;R.log=x.log;R.n=x.teams[0].items.filter(function(i){return i.kind==='lock';}).length;R.text=document.getElementById('com-root').textContent;R.__done=1;},600);
        """ % json.dumps(LOG), qs="#teams", wait=5000)
        self.assertEqual((r["asked"], r["log"]["files"], r["log"]["failed"], r["log"]["busy"], r["n"]), (7, 1, 1, 0, 2))
        self.assertIn("1 day could not be read", r["text"])

    def test_it_fits_a_phone(self):
        r = phone_run("""document.querySelector('.navlink[data-tab=commissioner]').click();NBA_COMMISH.setLog({[NBA_COMMISH.dates(2)[1]]:%s});
          [].forEach.call(document.querySelectorAll('#com-root details'),function(e){e.open=true;});R.over=document.documentElement.scrollWidth-document.documentElement.clientWidth;
          R.shown=document.querySelectorAll('.com-i').length;""" % json.dumps(LOG))
        self.assertNotIn("error", r)
        self.assertEqual(r["over"], 0)
        self.assertGreater(r["shown"], 0)

    def test_the_header_keeps_everything_on_screen_on_a_laptop(self):
        for width in (1100, 1280, 1440):
            r = drive_page("var t=document.querySelector('.topbar-inner');R.over=t.scrollWidth-t.clientWidth;", size="%d,900" % width, wait=600)
            self.assertEqual(r["over"], 0, width)


if __name__ == "__main__":
    unittest.main()
