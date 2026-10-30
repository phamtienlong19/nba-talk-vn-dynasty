"""Quality-of-life features of index.html, driven in headless Chrome: cooldown lock tags, what-changed strip, Trade Machine filters,
the not-checked note and the deadline calendar. Every expectation is derived from the embedded data, none pins today's rosters."""
import html as html_lib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_scenario_rendering as tsr  # noqa: E402

INDEX = os.path.join(os.path.dirname(__file__), "..", "index.html")
HTML = open(INDEX, encoding="utf-8").read()


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestQol(unittest.TestCase):
    def drive(self, body_js, head_js="", hash_="#trade-lab", wait=700):
        script = ("<script>(function(){var R={};setTimeout(function(){try{" + body_js + "}catch(e){R.error=String(e&&e.stack||e);}"
                  "setTimeout(function(){var p=document.createElement('pre');p.id='o';p.textContent=JSON.stringify(R);document.body.appendChild(p);},%d);},400);})();</script>" % wait)
        html = HTML.replace("<head>", "<head><script>" + head_js + "</script>", 1) if head_js else HTML
        html = html[:html.rindex("</body>")] + script + html[html.rindex("</body>"):]
        d = tempfile.mkdtemp()
        try:
            path = os.path.join(d, "index.html")
            with open(path, "w", encoding="utf-8") as f:
                f.write(html)
            out = tsr._chrome_run(["--window-size=900,1400", "--virtual-time-budget=8000", "--dump-dom", "file://" + path + hash_], 120).stdout
        finally:
            shutil.rmtree(d)
        m = re.search(r'<pre id="o">(.*?)</pre>', out, re.S)
        self.assertIsNotNone(m, out[-300:])
        r = json.loads(html_lib.unescape(m.group(1)))
        self.assertNotIn("error", r, r.get("error"))
        return r

    def test_cooldown_lock_tags_match_the_acquisition_data(self):
        r = self.drive("""
          var D=NBA_NAV.D,n=0;
          D.teams.forEach(function(t){D.scenarios[''].teams[t.id].roster.forEach(function(x){var at=D.trade.acq[x.k+'|'+t.id];
            if(at){var days=D.trade.rules.cooldown[D.trade.top.indexOf(x.k)>=0?'daysTopRanked':'days'];if(new Date().toISOString()<new Date(Date.parse(at)+days*864e5).toISOString())n++;}});});
          R.expected=n;R.tags=document.querySelectorAll('.lock-tag').length;""", hash_="#teams")
        self.assertEqual(r["tags"], r["expected"])

    def test_the_strip_lists_what_changed_since_the_stored_visit_and_got_it_clears_it(self):
        head = ("try{localStorage.setItem('nbaSeenRosters',JSON.stringify({sid:'old',at:'2026-10-01T00:00:00Z',"
                "own:{'478.p.1':'franchise-01'},nm:{'478.p.1':'Ghost Player'}}));}catch(e){}")
        r = self.drive("""
          var b=document.getElementById('whatsnew');R.shown=!!b;R.text=b?b.textContent:'';
          if(b){b.querySelector('button').click();R.after=!!document.getElementById('whatsnew');R.sid=JSON.parse(localStorage.getItem('nbaSeenRosters')).sid;}
          R.cur=NBA_NAV.D.season.snapshot.snapshotId;""", head_js=head, hash_="#teams")
        self.assertTrue(r["shown"])
        self.assertIn("Since your last visit", r["text"])
        self.assertIn("1 dropped", r["text"])
        self.assertIn("Ghost Player", r["text"])
        self.assertFalse(r["after"])
        self.assertEqual(r["sid"], r["cur"])                                                      # remembered: it will not nag again

    def test_first_visit_stays_quiet(self):
        r = self.drive("R.shown=!!document.getElementById('whatsnew');", hash_="#teams")
        self.assertFalse(r["shown"])

    def test_filters_narrow_the_pickable_rows_and_the_verdict_says_what_is_not_checked(self):
        r = self.drive("""
          var rows=function(){return document.querySelectorAll('#chk .chk-col .players .player-row').length;};
          R.all=rows();var q=document.getElementById('chk-q');q.value='zzzzqq';q.dispatchEvent(new Event('input'));R.none=rows();
          q=document.getElementById('chk-q');q.value='';q.dispatchEvent(new Event('input'));
          var s=document.getElementById('chk-pos');s.value='C';s.dispatchEvent(new Event('change'));R.centres=rows();
          s=document.getElementById('chk-pos');s.value='';s.dispatchEvent(new Event('change'));R.back=rows();
          document.querySelector('#chk .chk-col .players .player-row').click();
          var ne=document.querySelector('#chk .chk-ne');R.ne=ne?ne.textContent:'';""")
        self.assertGreater(r["all"], 10)
        self.assertEqual(r["none"], 0)
        self.assertTrue(0 < r["centres"] < r["all"])
        self.assertEqual(r["back"], r["all"])
        self.assertIn("Trade Tank eligibility", r["ne"])
        self.assertIn("LEGAL means the automated rules pass, not that the trade is approved", r["ne"])

    def test_the_calendar_file_has_both_deadlines(self):
        r = self.drive("""
          var cap=null;URL.createObjectURL=function(b){cap=b;return 'blob:x';};
          R.chips=document.querySelectorAll('#chk .chk-cal .cal-d').length;
          document.getElementById('chk-ics').click();
          cap.text().then(function(t){R.ics=t;});""", wait=900)
        self.assertEqual(r["chips"], 2)
        rules = json.loads(re.search(r'id="league-data">(.*?)</script>', HTML, re.S).group(1).replace("<\\/", "</"))["trade"]["rules"]["yahoo"]
        self.assertIn("DTSTART;VALUE=DATE:" + rules["tradeEndDate"].replace("-", ""), r["ics"])
        self.assertEqual(r["ics"].count("BEGIN:VEVENT"), 2)
        self.assertTrue(r["ics"].startswith("BEGIN:VCALENDAR"))
