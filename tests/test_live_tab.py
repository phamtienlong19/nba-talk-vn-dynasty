"""The LIVE tab in headless Chrome: every team's current lineup and what stands out in it, the week's lineup checks, staleness and exports."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import _site  # noqa: E402  (the built page: index.html + the generated data blocks)
import datetime
import json
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
import test_live_feed as tlf  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402
from _drive import drive_page  # noqa: E402
from _phone import phone_run  # noqa: E402

INDEX = _site.INDEX


def contrast(fg, bg):
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def side(feed, yahoo_id=8):
    return next(t for m in feed["matchups"] for t in m["teams"] if t["yahooId"] == yahoo_id)


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestLiveTab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feed = tlf.feed()
        cls.feed["asOf"] = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%SZ")

    def drive(self, body_js, qs="", wait=2000, rookies=None):
        def mutate(page):
            if rookies is not None:
                page = re.sub(r'"rookies":\[[^\]]*\]', '"rookies":' + json.dumps(rookies), page, count=1)
            return page.replace("https://raw.githubusercontent.com/phamtienlong19/nba-talk-vn-dynasty/live-data/live.json", "http://127.0.0.1:9/live.json")   # never the real feed
        return drive_page(body_js, qs=qs, wait=wait, start=500, size="1500,1400", budget=12000, mutate=mutate)

    def feed_js(self, feed=None, **over):
        f = dict(feed or self.feed, **over)
        return "var FEED=%s;" % json.dumps(f).replace("</", "<\\/")

    def copy(self):
        return json.loads(json.dumps(self.feed))

    def test_without_a_feed_it_says_so_and_shows_no_made_up_lineups(self):
        r = self.drive("""
          document.querySelector('.navlink[data-tab=live]').click();
          setTimeout(function(){R.shown=!document.getElementById('live').classList.contains('tab-off');R.pill=document.querySelector('#live-root .lv-pill').textContent;
            R.note=(document.querySelector('#live-root .lv-note')||{}).textContent||'';R.cards=document.querySelectorAll('#live-root .lv-team').length;R.src=NBA_LIVE.source();},600);""", wait=2500)
        self.assertEqual((r["shown"], r["pill"], r["cards"], r["src"]), (True, "NOT LOADED", 0, "none"))
        self.assertIn("TEAMS tab", r["note"])

    def test_every_team_has_a_lineup_card_and_nothing_about_scores_or_standings(self):
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);var root=document.getElementById('live-root');
          [].forEach.call(root.querySelectorAll('.lv-team'),function(d){d.open=true;});
          R.cards=root.querySelectorAll('.lv-team').length;R.groups=[].map.call(root.querySelector('.lv-team[data-team="%s"]').querySelectorAll('tr.gh b'),function(b){return b.textContent;});
          R.text=root.textContent;R.old=root.querySelectorAll('.lv-stand,.lv-m,.lv-views,.lv-rev,.lv-ro,.lv-sc').length;
          R.asof=document.getElementById('lv-asof').textContent;R.order=document.querySelectorAll('.stand-pill .so').length?[].map.call(document.querySelectorAll('.stand-pill .so'),function(b){return b.textContent;}):[];""" % side(self.feed)["team"])
        self.assertEqual((r["cards"], r["old"]), (16, 0))
        self.assertEqual(r["groups"], ["STARTERS", "BENCH", "INJURED LIST"])
        for gone in ("STANDINGS", "MATCHUPS", "REVERSE", "All-play", "Roto", "Playoffs", "tied"):
            self.assertNotIn(gone, r["text"])
        self.assertIn("min ago", r["asof"])
        self.assertFalse([b for b in r["order"] if "LIVE" in b])                    # the TEAMS tab no longer offers a live standings order

    def test_what_stands_out_in_a_current_lineup_is_flagged_and_counted(self):
        f = self.copy()
        t = side(f)
        starters = [p for p in t["roster"] if p.get("n") and p["s"] in ("PG", "SG", "G", "SF", "PF", "F", "C", "FC", "Util")]
        for p in t["roster"]:
            p["st"] = ""
        starters[0].update(st="O", g="7:30 pm vs BOS", gs="upcoming")
        starters[1].update(st="O", g=None, gs=None)                                    # out without a game today: nothing to flag
        starters[2].update(n=None, p=None)
        il = next(p for p in t["roster"] if p["s"] == "IL")
        il["st"] = "Q"
        r = self.drive(self.feed_js(f) + """
          NBA_LIVE.set(FEED);var c=document.querySelector('#live-root .lv-team[data-team="%s"]');c.open=true;
          R.count=c.querySelector('summary .lv-n').textContent;R.flags=[].map.call(c.querySelectorAll('.lv-f'),function(e){return e.textContent;}).sort();
          R.first=document.querySelector('#live-root .lv-team').getAttribute('data-team');""" % t["team"])
        self.assertEqual(r["flags"], ["EMPTY", "IL !", "OUT IN LINEUP"])
        self.assertEqual(r["count"], "3 to check")
        self.assertEqual(r["first"], t["team"])                                        # teams with something to check come first

    def test_my_team_is_first_and_open_and_expand_all_works(self):
        mine = self.feed["matchups"][-1]["teams"][1]["team"]
        r = self.drive(self.feed_js() + """
          window.NBA_ME=function(){return %s;};NBA_LIVE.set(FEED);
          var open=function(){return document.querySelectorAll('#live-root .lv-team[open]').length;};
          var first=document.querySelector('#live-root .lv-team');R.first=first.getAttribute('data-team');R.me=first.classList.contains('me');R.open=open();
          document.getElementById('lv-all').click();R.all=open();R.label=document.getElementById('lv-all').textContent;document.getElementById('lv-all').click();R.none=open();""" % json.dumps(mine))
        self.assertEqual((r["first"], r["me"], r["open"], r["all"], r["label"], r["none"]), (mine, True, 1, 16, "Collapse all", 0))

    def test_roster_changes_show_and_players_who_left_are_not_in_the_lineup(self):
        f = self.copy()
        t = side(f)
        t["roster"].append(dict(t["roster"][0], s="--", n="Gone Guy", p="1234"))
        f["moves"] = [{"date": "2026-11-03", "team": t["team"], "yahooId": 8, "add": ["New Guy"], "drop": ["Gone Guy"], "addIds": ["999"], "dropIds": ["1234"]}]
        r = self.drive(self.feed_js(f) + """
          NBA_LIVE.set(FEED);var c=document.querySelector('#live-root .lv-team[data-team="%s"]');c.open=true;
          R.inTable=/Gone Guy/.test(c.querySelector('.lv-r').textContent);R.mv=c.querySelector('.lv-mv').textContent;R.chips=c.querySelectorAll('.lv-mv .mv').length;""" % t["team"])
        self.assertEqual((r["inTable"], r["chips"]), (False, 2))
        self.assertIn("ROSTER CHANGES THIS WEEK", r["mv"])

    def test_an_old_feed_is_flagged_stale(self):
        old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        r = self.drive(self.feed_js(asOf=old) + """
          NBA_LIVE.set(FEED);R.stale=document.querySelector('#live-root .lv-pill').classList.contains('stale');
          R.note=(document.querySelector('#live-root .lv-note')||{}).textContent||'';""")
        self.assertTrue(r["stale"])
        self.assertIn("out of date", r["note"])

    def test_a_feed_that_does_not_cover_16_teams_is_refused_and_an_older_shape_still_reads(self):
        old = self.copy()
        old.update(table=[], projectedReverse=[])                                       # the previous feed carried standings: still readable
        short = self.copy()
        short["matchups"] = short["matchups"][:7]
        r = self.drive(self.feed_js(old) + "var SHORT=%s;" % json.dumps(short).replace("</", "<\\/") + """
          try{NBA_LIVE.set(SHORT);R.bad='accepted';}catch(e){R.bad=e.message;}NBA_LIVE.set(FEED);R.cards=document.querySelectorAll('#live-root .lv-team').length;""")
        self.assertEqual((r["bad"], r["cards"]), ("unreadable feed", 16))

    def test_lineup_checks_are_listed_with_neutral_wording(self):
        t1, t2 = side(self.feed, 1)["team"], side(self.feed, 2)["team"]
        lc = {"week": 3, "rule": {"days": 2, "players": 3, "stars": 2}, "missing": [], "byDate": {"2026-11-02": {}, "2026-11-03": {}},
              "teams": [{"team": t1, "yahooId": 1, "missetDays": 2, "players": 2, "stars": 1, "meetsCount": True,
                         "days": [{"date": "2026-11-02", "issues": [{"k": "out_starter", "p": "Out Guy", "id": "1", "s": "PG", "r": "Bench Guy"}]},
                                  {"date": "2026-11-03", "issues": [{"k": "star_benched", "p": "Star", "id": "2", "s": "BN", "r": None, "rank": 9}]}]},
                        {"team": t2, "yahooId": 2, "missetDays": 0, "players": 0, "stars": 0, "meetsCount": False, "days": []}]}
        r = self.drive(self.feed_js(lineupChecks=lc) + """
          NBA_LIVE.set(FEED);var b=document.querySelector('#live-root .lv-lc');R.title=b.querySelector('.lv-ct').firstChild.textContent;
          R.teams=b.querySelectorAll('details.lv-lc-t').length;R.flag=b.querySelector('.flag').textContent;R.items=b.querySelectorAll('li').length;R.text=b.textContent;""")
        self.assertEqual((r["title"], r["teams"], r["items"], r["flag"]), ("LINEUP CHECKS", 1, 2, "at the rule's count"))
        self.assertNotIn("tank", r["text"].lower())

    def test_reviewed_lineup_checks_show_faults_only(self):
        item = lambda o, n: {"o": o, "case": 3, "n": n, "p": n, "what": "started while out", "fact": "PG", "dates": ["2026-11-25"], "at": "2026-11-25T20:00:00Z"}  # noqa: E731
        review = {"week": 6, "rule": {"days": 2, "players": 3, "stars": 2}, "cleared": 3, "since": "2026-11-25", "teams": {
            "franchise-01": {"items": [item("fault", "Real Fault"), item("watch", "Only Watch")], "days": 1, "players": 1, "stars": 0, "meets": False},
            "franchise-02": {"items": [item("watch", "Other Watch")], "days": 0, "players": 0, "stars": 0, "meets": False}}}
        r = self.drive(self.feed_js(lineupReview=review) + """
          NBA_LIVE.set(FEED);var b=document.querySelector('#live-root .lv-lc');R.teams=b.querySelectorAll('.lv-lc-t').length;b.querySelector('details').open=true;R.text=b.textContent;
          R.head=document.querySelector('#live-root .lv-team[data-team="franchise-01"] summary').textContent;""")
        self.assertEqual(r["teams"], 1)
        self.assertIn("Real Fault: started while out (PG)", r["text"])
        self.assertNotIn("Watch", r["text"])
        self.assertIn("1 team: no faults.", r["text"])
        self.assertIn("1 fault day", r["head"])

    def test_rookies_get_the_purple_name_and_an_r_tag(self):
        pid = next(p["p"] for m in self.feed["matchups"] for t in m["teams"] for p in t["roster"] if p.get("n") and p.get("p") and p["s"] not in ("--", "BN", "IL"))
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);document.getElementById('lv-all').click();
          R.rk=document.querySelectorAll('#live-root .lv-r tr.rk').length;R.tags=document.querySelectorAll('#live-root .lv-rk').length;
          R.color=getComputedStyle(document.querySelector('#live-root .lv-r tr.rk td.nm b')).color;""", rookies=[pid])
        self.assertGreaterEqual(r["rk"], 1)
        self.assertEqual(r["rk"], r["tags"])
        self.assertEqual(r["color"], "rgb(93, 39, 150)")

    def test_the_payload_is_teams_rookies_and_the_feed_address_only(self):
        import live_page as lp
        p = lp.payload()
        self.assertEqual(sorted(p), ["liveUrl", "rookies", "teams"])
        self.assertTrue(p["rookies"] and all(i.isdigit() for i in p["rookies"]))

    def test_cards_can_be_exported_and_names_open_the_player(self):
        r = self.drive(self.feed_js() + """
          NBA_LIVE.set(FEED);document.getElementById('lv-all').click();var root=document.getElementById('live-root');
          R.btns=root.querySelectorAll('.lv-team .share-btn').length;R.pl=root.querySelectorAll('.lv-r td.nm.pl[role=button]').length;
          var cat=NBA_EXPORT.catalog().filter(function(i){return /^live-/.test(i.id);});R.ids=cat.map(function(i){return i.id;});
          var pages=cat[0].pages();R.pages=pages.length;R.text=NBA_EXPORT.text(pages[0].doc);""")
        self.assertEqual((r["btns"], r["ids"], r["pages"]), (16, ["live-lineups"], 4))
        self.assertGreater(r["pl"], 0)
        self.assertNotRegex(r["text"], "undefined|NaN")

    def test_my_team_keeps_games_left_and_the_lineup_checks(self):
        mine = side(self.feed)["team"]
        r = self.drive(self.feed_js() + """
          localStorage.setItem('nbaTalkVN.myTeam',%s);NBA_LIVE.set(FEED);location.hash='#me';window.dispatchEvent(new PopStateEvent('popstate'));
          var c=[].filter.call(document.querySelectorAll('#me-root .me-c'),function(x){return /This week/.test(x.querySelector('.me-ch').textContent);})[0];R.text=c.textContent;""" % json.dumps(mine))
        self.assertIn("Games left (starters)", r["text"])
        self.assertIn("Lineup checks", r["text"])
        for gone in ("If the week ended now", "Next opponents"):
            self.assertNotIn(gone, r["text"])

    def test_on_a_phone_the_lineups_fit_the_screen(self):
        feed = json.dumps(self.feed).replace("</", "<\\/")
        r = phone_run("""var FEED=%s;document.querySelector('.navlink[data-tab=live]').click();NBA_LIVE.set(FEED);document.getElementById('lv-all').click();
          R.over=document.documentElement.scrollWidth-document.documentElement.clientWidth;
          var r0=document.querySelector('#live-root .lv-team .lv-r tr:not(.gh)');R.slot=r0.children[0].offsetWidth;R.name=r0.children[1].offsetWidth;
          R.wide=[].filter.call(document.querySelectorAll('#live-root .lv-r'),function(t){return t.scrollWidth>t.closest('.lv-team').clientWidth;}).length;R.n=document.querySelectorAll('#live-root .lv-r').length;""" % feed)
        self.assertNotIn("error", r)
        self.assertEqual((r["over"], r["wide"], r["n"]), (0, 0, 16))
        self.assertLess(r["slot"], 60)                                                 # the name column gets the room, not the slot
        self.assertGreater(r["name"], 180)

    def test_small_text_stays_readable(self):
        css = open(os.path.join(HERE, "..", "scripts", "live.css"), encoding="utf-8").read()
        sizes = [float(x) for x in re.findall(r"font:\d+ ([0-9.]+)px", css)]
        self.assertGreaterEqual(min(sizes), 9.5)
        self.assertLessEqual(sum(1 for x in sizes if x < 10.5), 3)
        faint = re.search(r"--lv-faint:(#[0-9a-fA-F]{6})", css).group(1)
        self.assertGreaterEqual(contrast(faint, "#ffffff"), 4.5)


if __name__ == "__main__":
    unittest.main()
