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

    def drive(self, body_js, qs="", wait=2000, rookies=None, extra_css=""):
        with open(INDEX, encoding="utf-8") as f:
            page = f.read()
        script = ("<script>(function(){var R={};setTimeout(function(){try{" + body_js + "}catch(e){R.error=String(e&&e.stack||e);}"
                  "setTimeout(function(){var p=document.createElement('pre');p.id='o';p.textContent=JSON.stringify(R);document.body.appendChild(p);},%d);},500);})();</script>" % wait)
        if rookies is not None:
            page = re.sub(r'"rookies":\[[^\]]*\]', '"rookies":' + json.dumps(rookies), page, count=1)
        page = page.replace("https://raw.githubusercontent.com/phamtienlong19/nba-talk-vn-dynasty/live-data/live.json", "http://127.0.0.1:9/live.json")   # never the real feed: the fetch fails fast
        if extra_css:
            page = page.replace("</head>", "<style>" + extra_css + "</style></head>", 1)
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

    def test_rookies_get_the_purple_name_and_an_r_tag(self):
        pid = next(p["p"] for m in self.feed["matchups"] for t in m["teams"] for p in t["roster"] if p.get("n") and p.get("p"))
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);document.querySelectorAll('#live-root .lv-det').forEach(function(d){d.open=true;});
          R.rk=document.querySelectorAll('#live-root .lv-r tr.rk').length;R.tags=document.querySelectorAll('#live-root .lv-rk').length;
          R.color=getComputedStyle(document.querySelector('#live-root .lv-r tr.rk td.nm b')).color;""", rookies=[pid])
        self.assertGreaterEqual(r["rk"], 1)
        self.assertEqual(r["rk"], r["tags"])
        self.assertEqual(r["color"], "rgb(93, 39, 150)")

    def test_the_payload_lists_2026_rookies_by_yahoo_id(self):
        import live_page as lp
        ids = lp.payload()["rookies"]
        self.assertTrue(ids and all(i.isdigit() for i in ids))

    def test_rosters_close_from_the_sticky_bar_and_collapse_all(self):
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);var ds=function(){return document.querySelectorAll('#live-root .lv-det[open]').length;};
          document.getElementById('lv-all').click();R.afterExpand=ds();R.label=document.getElementById('lv-all').textContent;
          document.querySelector('#live-root .lv-det[open] .lv-x').click();R.afterClose=ds();
          document.getElementById('lv-all').click();R.afterAll=ds();
          document.querySelector('#live-root .lv-m .lv-mh').click();R.afterHeader=ds();""")
        self.assertEqual(r["afterExpand"], 8)
        self.assertEqual(r["label"], "Collapse all")
        self.assertEqual(r["afterClose"], 7)
        self.assertEqual(r["afterAll"], 0)
        self.assertEqual(r["afterHeader"], 1)

    def test_my_team_is_pinned_first_and_highlighted(self):
        mine = self.feed["matchups"][-1]["teams"][1]["team"]
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);window.NBA_ME=function(){return %s;};document.dispatchEvent(new Event('nba:me'));
          var ms=document.querySelectorAll('#live-root .lv-m');R.first=ms[0].classList.contains('me');R.ribbons=document.querySelectorAll('#live-root .lv-ribbon').length;
          R.rows=Array.prototype.map.call(document.querySelectorAll('#live-root .lv-stand tbody tr.me'),function(t){return t.getAttribute('data-team');});""" % json.dumps(mine))
        self.assertTrue(r["first"])
        self.assertEqual(r["ribbons"], 1)
        self.assertEqual(r["rows"], [mine])

    def test_on_a_phone_the_roster_scrolls_sideways_inside_its_card(self):
        css = open(os.path.join(HERE, "..", "scripts", "live.css"), encoding="utf-8").read()
        phone = css[css.index("@media(max-width:680px){"):].replace("@media(max-width:680px){", "", 1).rsplit("}", 1)[0]
        narrow = "#live{width:390px!important;max-width:390px!important;margin:0!important;padding:0 12px!important;box-sizing:border-box}.lv-grid{grid-template-columns:minmax(0,1fr)!important}" + phone
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);document.querySelector('.navlink[data-tab=live]').click();
          setTimeout(function(){var d=document.querySelector('#live-root .lv-m .lv-det');d.setAttribute('open','');
            var w=d.querySelector('.lv-wrap'),card=d.closest('.lv-m');
            R.client=w.clientWidth;R.scroll=w.scrollWidth;R.card=card.clientWidth;R.panel=d.querySelector('.lv-rc').clientWidth;},600);""", wait=2500, extra_css=narrow)
        self.assertGreater(r["scroll"], r["client"])               # there is more to the right than fits ...
        self.assertLessEqual(r["panel"], r["card"])                # ... and the panel stays inside its card, so it scrolls instead of being clipped

    def test_lineup_checks_are_listed_for_everyone_with_neutral_wording(self):
        t1, t2 = self.feed["table"][0]["team"], self.feed["table"][1]["team"]
        lc = {"week": 3, "rule": {"days": 2, "players": 3, "stars": 2}, "missing": [], "byDate": {"2026-11-02": {}, "2026-11-03": {}},
              "teams": [{"team": t1, "yahooId": 1, "missetDays": 2, "players": 2, "stars": 1, "meetsCount": True,
                         "days": [{"date": "2026-11-02", "issues": [{"k": "out_starter", "p": "Out Guy", "id": "1", "s": "PG", "r": "Bench Guy"}]},
                                  {"date": "2026-11-03", "issues": [{"k": "star_benched", "p": "Star", "id": "2", "s": "BN", "r": None, "rank": 9}]}]},
                        {"team": t2, "yahooId": 2, "missetDays": 0, "players": 0, "stars": 0, "meetsCount": False, "days": []}]}
        r = self.drive(self.feed_js(lineupChecks=lc) + """
          NBA_LIVE.set(FEED);document.querySelector('.navlink[data-tab=live]').click();
          setTimeout(function(){var b=document.querySelector('#live-root .lv-lc');R.has=!!b;R.title=b?b.querySelector('.lv-ct').textContent:'';
            R.teams=b?b.querySelectorAll('details.lv-lc-t').length:0;R.flag=b?(b.querySelector('.flag')||{}).textContent:'';
            R.items=b?b.querySelectorAll('li').length:0;R.text=b?b.textContent:'';},600);""", wait=2500)
        self.assertTrue(r["has"])
        self.assertEqual((r["title"], r["teams"], r["items"]), ("LINEUP CHECKS", 1, 2))
        self.assertEqual(r["flag"], "at the rule's count")
        self.assertIn("Out player held a starting slot", r["text"])
        self.assertNotIn("tank", r["text"].lower())                                # evidence, never a verdict
        self.assertIn("1 team: nothing found", r["text"])

    def test_week_totals_and_one_day_are_told_apart_and_players_show_made_over_attempted(self):
        feed = json.loads(json.dumps(self.feed))
        feed["dayDate"] = "2026-11-02"
        for m in feed["matchups"]:
            m["day"] = {"date": "2026-11-02", "stats": [{"fg": [1, 2], "ft": [1, 1], "tpm": 1, "pts": 9, "reb": 1, "ast": 1, "st": 1, "blk": 0, "to": 1},
                                                          {"fg": [2, 4], "ft": [0, 0], "tpm": 0, "pts": 7, "reb": 2, "ast": 0, "st": 0, "blk": 1, "to": 3}],
                        "cats": {"fgPct": "t", "ftPct": "a", "tpm": "a", "pts": "a", "reb": "b", "ast": "a", "st": "a", "blk": "b", "to": "a"}, "score": [6, 2, 1]}
            for t in m["teams"]:
                for r in t["roster"]:
                    if r.get("n"):
                        r.update({"wfg": [7, 15], "wft": [3, 4], "dfg": [5, 9], "dft": [2, 2], "dm": "30:01", "d": [0.556, 1.0, 1, 12, 4, 3, 1, 0, 2], "ds": r["s"]})
        r = self.drive("var FEED=%s;" % json.dumps(feed).replace("</", "<\\/") + """
          NBA_LIVE.set(FEED);document.querySelector('.navlink[data-tab=live]').click();
          setTimeout(function(){var q=function(s){return document.querySelector(s);};
            q('#live-root .lv-det').setAttribute('open','');
            R.cap1=q('#live-root .lv-m .lv-cap b').textContent;R.score1=q('#live-root .lv-m .lv-w').textContent;
            R.ratio1=q('#live-root .lv-r tbody tr:not(.gh) td.num small').textContent;R.cols1=q('#live-root .lv-r thead tr').children.length;
            q('#live-root .lv-seg button:nth-child(2)').click();
            setTimeout(function(){q('#live-root .lv-det').setAttribute('open','');
              R.cap2=q('#live-root .lv-m .lv-cap b').textContent;R.score2=q('#live-root .lv-m .lv-w').textContent;
              R.cols2=q('#live-root .lv-r thead tr').children.length;R.min=q('#live-root .lv-r tbody tr:not(.gh) td.num').textContent;
              R.ratio2=q('#live-root .lv-r tbody tr:not(.gh) td.num:nth-child(4) small').textContent;
              R.on=q('#live-root .lv-seg button.on').textContent;},300);},600);""", wait=3500)
        self.assertEqual(r["cap1"], "WEEK TOTALS")
        self.assertEqual(r["ratio1"], "7/15")
        self.assertEqual(r["cap2"], "DAY · 2 Nov")
        self.assertEqual(r["score2"], "6")                                         # the day's own category score, not the week's
        self.assertEqual(r["cols2"], r["cols1"] + 1)                               # the day view adds minutes
        self.assertEqual(r["min"], "30:01")
        self.assertEqual(r["ratio2"], "5/9")
        self.assertTrue(r["on"].startswith("Day"))

    def test_roto_stats_and_all_play_views_follow_the_week(self):
        mine = self.feed["matchups"][0]["teams"][0]["team"]
        r = self.drive(self.feed_js() + """
          window.NBA_ME=function(){return %s;};NBA_LIVE.set(FEED);document.querySelector('.navlink[data-tab=live]').click();
          setTimeout(function(){var q=function(s){return document.querySelector(s)},qa=function(s){return document.querySelectorAll(s)};
            R.tabs=Array.prototype.map.call(qa('#live-root .lv-views button'),function(b){return b.textContent;});
            q('#live-root .lv-views button:nth-child(2)').click();
            R.roto=qa('#live-root .lv-ro tbody tr').length;R.ranks=Array.prototype.map.call(qa('#live-root .lv-ro td.rk'),function(x){return x.textContent;});
            R.totals=Array.prototype.map.call(qa('#live-root .lv-ro td.tot'),function(x){return Number(x.textContent);});R.mineRow=qa('#live-root .lv-ro tr.me').length;R.note=q('#live-root .lv-note').textContent;
            q('#live-root .lv-views button:nth-child(3)').click();R.stats=qa('#live-root .lv-ro tbody tr').length;R.cols=qa('#live-root .lv-ro thead th').length;
            q('#live-root .lv-views button:nth-child(4)').click();R.cells=qa('#live-root .lv-ap td.cell:not(.self)').length;R.act=qa('#live-root .lv-ap td.cell.act').length;
            R.detailAuto=qa('#live-root .lv-dg .r').length;
            var c=qa('#live-root .lv-ap td.cell:not(.self)')[5];c.click();R.sel=qa('#live-root .lv-ap td.cell.sel').length;R.detail=qa('#live-root .lv-dg .r').length;
            q('#live-root .lv-views button:nth-child(1)').click();R.back=qa('#live-root .lv-m').length;},600);""" % json.dumps(mine), wait=3000)
        self.assertEqual(r["tabs"], ["Matchups", "Roto", "Raw stats", "All-play"])
        self.assertEqual(r["roto"], 16)
        self.assertEqual(sum(r["totals"]), 9 * 136)                                  # every category hands out 1+2+...+16
        self.assertEqual(r["totals"], sorted(r["totals"], reverse=True))
        self.assertEqual(r["ranks"][0], "1")
        self.assertEqual(r["mineRow"], 1)
        self.assertIn("Descriptive only", r["note"])
        self.assertEqual((r["stats"], r["cols"]), (16, 11))
        self.assertEqual((r["cells"], r["act"]), (240, 16))                          # 16 x 15 cells, one real matchup per row
        self.assertEqual((r["detailAuto"], r["sel"], r["detail"]), (9, 1, 9))        # my team's real matchup is opened; a click selects another
        self.assertEqual(r["back"], 8)

    def test_the_roto_views_are_hidden_without_a_live_week(self):
        r = self.drive("""
          document.querySelector('.navlink[data-tab=live]').click();
          setTimeout(function(){R.strip=document.querySelectorAll('#live-root .lv-views').length;},600);""", wait=2500)
        self.assertEqual(r["strip"], 0)

    def test_on_a_phone_the_roto_tables_scroll_inside_their_card(self):
        css = open(os.path.join(HERE, "..", "scripts", "live.css"), encoding="utf-8").read()
        phone = css[css.index("/* ---- phones ---- */") if "/* ---- phones ---- */" in css else css.index("@media(max-width:680px){"):]
        narrow = "#live{width:390px!important;max-width:390px!important;margin:0!important;padding:0 12px!important;box-sizing:border-box}.lv-grid{grid-template-columns:minmax(0,1fr)!important}" + phone
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);document.querySelector('.navlink[data-tab=live]').click();
          setTimeout(function(){var q=function(s){return document.querySelector(s)};var o={};
            [2,4].forEach(function(n){q('#live-root .lv-views button:nth-child('+n+')').click();var w=q('#live-root .lv-sw'),c=w.closest('.lv-pane');o[n]=[w.clientWidth,w.scrollWidth,c.clientWidth];});
            R.o=o;},600);""", wait=3000, extra_css=narrow)
        for n in ("2", "4"):
            client, scroll, card = r["o"][n]
            self.assertGreater(scroll, client)                                      # more to the right than fits ...
            self.assertLessEqual(client, card)                                      # ... and the scroller stays inside the card


if __name__ == "__main__":
    unittest.main()
