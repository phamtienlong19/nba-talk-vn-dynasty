"""The LIVE tab in headless Chrome: the official fallback, a live feed handed in, staleness, the Teams-tab live order and the exports."""
import datetime
import html as html_lib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import test_live_feed as tlf  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402

INDEX = os.path.join(HERE, "..", "index.html")


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestLiveTab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = tlf.feed()
        cls.feed["asOf"] = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def drive(self, body_js, qs="", wait=2000):
        with open(INDEX, encoding="utf-8") as f:
            page = f.read()
        script = ("<script>(function(){var R={};setTimeout(function(){try{" + body_js + "}catch(e){R.error=String(e&&e.stack||e);}"
                  "setTimeout(function(){var p=document.createElement('pre');p.id='o';p.textContent=JSON.stringify(R);document.body.appendChild(p);},%d);},500);})();</script>" % wait)
        page = page.replace("https://raw.githubusercontent.com/phamtienlong19/nba-talk-vn-dynasty/live-data/live.json", "http://127.0.0.1:9/live.json")   # never the real feed: the fetch fails fast
        page = page[:page.rindex("</body>")] + script + page[page.rindex("</body>"):]
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "index.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(page)
            out = tsr._chrome_run(["--window-size=1500,1400", "--virtual-time-budget=12000", "--dump-dom", "file://" + path + qs], 150).stdout
        finally:
            shutil.rmtree(d)
        m = re.search(r'<pre id="o">(.*?)</pre>', out, re.S)
        self.assertIsNotNone(m, out[-300:])
        r = json.loads(html_lib.unescape(m.group(1)))
        self.assertNotIn("error", r, r.get("error"))
        return r

    def feed_js(self, **over):
        f = dict(self.feed, **over)
        return "var FEED=%s;" % json.dumps(f).replace("</", "<\\/")

    def test_without_a_live_feed_the_official_finished_weeks_are_shown_and_labelled(self):
        r = self.drive("""
          R.nav=!!document.querySelector('.navlink[data-tab=live]');document.querySelector('.navlink[data-tab=live]').click();
          setTimeout(function(){var s=document.getElementById('live');R.shown=!s.classList.contains('tab-off');R.hash=location.hash;
            R.rows=document.querySelectorAll('#live-root .lv-stand tbody tr').length;R.pill=document.querySelector('#live-root .lv-pill').textContent;
            R.note=(document.querySelector('#live-root .lv-note')||{}).textContent||'';R.cards=document.querySelectorAll('#live-root .lv-m').length;
            R.other=document.getElementById('cap').classList.contains('tab-off');},600);""", wait=2500)
        self.assertTrue(r["nav"] and r["shown"] and r["other"])
        self.assertEqual(r["hash"], "#live")
        self.assertEqual((r["rows"], r["cards"]), (16, 8))
        self.assertEqual(r["pill"], "OFFICIAL WEEKS ONLY")
        self.assertIn("official finished weeks", r["note"])

    def test_a_live_feed_renders_standings_with_movement_ties_and_the_playoff_line_and_eight_matchups(self):
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);document.querySelector('.navlink[data-tab=live]').click();
          setTimeout(function(){R.pill=document.querySelector('#live-root .lv-pill').textContent;R.live=document.querySelector('#live-root .lv-pill').classList.contains('on');
            R.rows=Array.prototype.map.call(document.querySelectorAll('#live-root .lv-stand tbody tr'),function(t){return {team:t.getAttribute('data-team'),rank:t.children[0].firstChild.textContent,mv:t.children[0].children.length?t.children[0].children[0].textContent:'',po:t.lastChild.textContent,cut:t.classList.contains('cut')};});
            R.cards=document.querySelectorAll('#live-root .lv-m').length;R.cats=document.querySelectorAll('#live-root .lv-m')[0].querySelectorAll('.lv-c').length;
            R.rev=document.querySelectorAll('#live-root .lv-rev li').length;R.asof=document.getElementById('lv-asof').textContent;},600);""", wait=2500)
        self.assertTrue(r["live"])
        self.assertEqual(r["pill"], "LIVE")
        self.assertEqual((len(r["rows"]), r["cards"], r["cats"], r["rev"]), (16, 8, 9, 16))
        table = {t["team"]: t for t in self.feed["table"]}
        for row in r["rows"]:
            t = table[row["team"]]
            self.assertEqual(row["rank"], ("T-" if t["tied"] else "") + str(t["rank"]))
            if t["moved"]:
                self.assertTrue(row["mv"].startswith("▲" if t["moved"] > 0 else "▼"), row)
        self.assertEqual(sum(1 for x in r["rows"] if x["cut"]), 1)                       # one line between the playoff teams and the rest
        self.assertIn("ICT", r["asof"])
        self.assertIn("min ago", r["asof"])

    def test_an_old_feed_is_flagged_stale(self):
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = self.drive(self.feed_js(asOf=old) + """
          NBA_LIVE.set(FEED);R.stale=document.querySelector('#live-root .lv-pill').classList.contains('stale');
          R.note=(document.querySelector('#live-root .lv-note')||{}).textContent||'';""")
        self.assertTrue(r["stale"])
        self.assertIn("out of date", r["note"])

    def test_the_teams_tab_can_follow_the_live_order(self):
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);window.NBA_LIVE.standings&&0;
          var btns=Array.prototype.slice.call(document.querySelectorAll('.stand-pill .so'));R.labels=btns.map(function(b){return b.textContent;});
          var live=btns.filter(function(b){return /LIVE/.test(b.textContent);})[0];live.click();
          var tags=Array.prototype.map.call(document.querySelectorAll('#rosters-a section.team-card .identity-tag,#rosters-b section.team-card .identity-tag'),function(e){return e.textContent.trim();});
          R.tags=tags;R.url=location.search;R.first=document.querySelector('#rosters-a .stand-tag')?document.querySelector('#rosters-a .stand-tag').textContent:'';""")
        self.assertIn("LIVE ↓", r["labels"])
        short = {}
        import league_state as ls
        for t in ls.load_inputs()["freeze"]["teams"]:
            short[t["franchiseId"]] = t["short"]
        self.assertEqual(r["tags"], [short[x["team"]] for x in self.feed["projectedReverse"]])   # worst first, as the Teams tab orders standings
        self.assertIn("order=live", r["url"])

    def test_live_standings_and_matchups_are_exports(self):
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);var cat=NBA_EXPORT.catalog();R.ids=cat.map(function(i){return i.id;});
          R.texts=['live-standings','live-matchups'].map(function(id){var it=cat.filter(function(i){return i.id===id;})[0];var p=it.pages()[0];return NBA_EXPORT.text(p.doc);});""")
        self.assertIn("live-standings", r["ids"])
        self.assertIn("live-matchups", r["ids"])
        self.assertIn("PROVISIONAL", r["texts"][0])
        self.assertTrue(all("undefined" not in t and "NaN" not in t for t in r["texts"]), r["texts"])

    def test_rosters_open_under_each_matchup_with_slots_and_game_text(self):
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);var d=document.querySelector('#live-root .lv-m[data-m="8"] .lv-det');d.setAttribute('open','');
          R.slots=Array.prototype.map.call(d.querySelectorAll('.lv-r tbody tr td.sl'),function(t){return t.textContent;});
          R.names=d.querySelectorAll('.lv-r td.nm b').length;""")
        self.assertTrue({"BN", "IL"} <= set(r["slots"]), r["slots"])
        self.assertGreater(r["names"], 10)

    def test_an_out_starter_with_nothing_recorded_shows_dashes_and_real_zeros_are_dimmed(self):
        r = self.drive(self.feed_js() + """
          var M=FEED.matchups.filter(function(x){return x.teams.some(function(t){return t.roster.length;});})[0],T=M.teams.filter(function(t){return t.roster.length;})[0],m=T.roster;var st=m.filter(function(x){return x.n&&x.s!=='BN'&&x.s!=='IL';});var s=st[0];s.st='O';s.l=[null,null,0,0,0,0,0,0,0];
          var q=st[1];q.st='';q.l=[0.4,1,0,5,1,1,0,0,2];
          NBA_LIVE.set(FEED);var d=document.querySelector('#live-root .lv-m[data-m="'+M.teams[0].yahooId+'"] .lv-det');d.setAttribute('open','');
          var rows=d.querySelectorAll('.lv-rc'+(M.teams[0]===T?'.ca':'.cb')+' .lv-r tbody tr');var pick=function(slot){return Array.prototype.filter.call(rows,function(t){var c=t.querySelector('td.sl');return c&&c.textContent===slot;})[0];};
          var txt=function(t){return Array.prototype.map.call(t.querySelectorAll('td.num'),function(x){return x.textContent;});};
          R.out=txt(pick(s.s));R.sg=txt(pick(q.s));R.zeros=pick(q.s).querySelectorAll('td.num.z').length;R.outZeros=pick(s.s).querySelectorAll('td.num.z').length;""")
        self.assertEqual(set(r["out"]), {"–"})
        self.assertEqual(r["sg"][2], "0")
        self.assertEqual((r["zeros"], r["outZeros"]), (3, 0))


if __name__ == "__main__":
    unittest.main()
