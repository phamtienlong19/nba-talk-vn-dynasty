"""The player card (one standalone element), its history, its share image and text, and its link."""
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _phone  # noqa: E402
import test_export as tex  # noqa: E402
import test_live_feed as tlf  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402

PRE = "localStorage.setItem('nbaTalkVN.myTeam','franchise-05');window.fetch=function(){return Promise.reject(new Error('offline'))}"       # offline: no feed, no averages file
# a 2026 rookie who was drafted by one team and then traded in-season (CrazyCat -> HCMC, 2026-10-16)
TRADED = "478.p.10572"


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestPlayerCard(unittest.TestCase):
    def test_the_card_has_header_tiles_status_and_a_history_newest_first(self):
        r = _phone.phone_run("""var c=NBA_PLAYER.card('%s');document.body.appendChild(c);
          R.name=c.querySelector('.plc-n').textContent;R.rk=!!c.querySelector('.rk-mark');R.sal=[].map.call(c.querySelectorAll('.plc-sal i, .plc-sal b'),function(x){return x.textContent});R.tiles=c.querySelectorAll('.plc-t').length;
          var kids=[].slice.call(c.children);R.order=kids.map(function(x){return x.className.split(' ')[0]});R.keep=(c.querySelector('.plc-keep')||{}).textContent||'';
          R.pills=[].map.call(c.querySelectorAll('.plc-p'),function(x){return x.textContent});R.hist=[].map.call(c.querySelectorAll('.plc-tl li'),function(x){return x.textContent});
          R.mine=!!c.querySelector('.plc-own small');R.advice=/should|recommend|fair|value/i.test(c.textContent.replace('Salary','').replace('SALARY',''));""" % TRADED, pre_js=PRE, width=1100, wait_ms=2500)
        self.assertIn("Morez", r["name"])
        self.assertTrue(r["rk"])
        self.assertEqual(r["sal"][1], "SALARY NOW")                                         # the salary leads, as one strip
        self.assertEqual(r["tiles"], 0)                                                     # no next-year / keeper tiles
        self.assertEqual(r["order"][1], "plc-sal")                                          # straight after the header
        self.assertEqual(r["order"][-2], "plc-keep")                                        # the keeper line is the last thing before the footer
        self.assertRegex(r["keep"], r"^Keeper #\d+ · next year ")
        self.assertEqual(len(r["hist"]), 2)
        self.assertIn("Traded from", r["hist"][0])                                          # newest first
        self.assertIn("Drafted by", r["hist"][1])                                           # the draft is the oldest fact
        self.assertTrue(r["mine"])
        self.assertFalse(r["advice"])

    def test_the_game_log_is_one_plain_line_per_game_newest_first_with_no_totals(self):
        import json as _j
        rows = [["2026-11-%02d" % d, "PG", "vs TOR", "30:00", 5, 7, 1, 2, 2, 13, 7, 1, 1, 1, 3, 4] for d in range(1, 13)]
        rows[4][1] = "BN"
        doc = _j.dumps({"capturedAt": "2026-11-13T09:40:00Z", "days": ["2026-11-12"], "p": {"10572": rows}})
        r = _phone.phone_run("""NBA_PLAYER.logSet(%s);var c=NBA_PLAYER.card('%s');document.body.appendChild(c);var sec=c.querySelector('.plc-log');
          R.shown=!sec.hidden;R.lines=[].map.call(sec.querySelectorAll('.plc-gl li'),function(x){return x.textContent});R.title=sec.querySelector('.plc-k').textContent;
          R.off=sec.querySelectorAll('li.off').length;R.boxes=c.querySelectorAll('.plc-w').length;R.more=(sec.querySelector('.plc-more')||{}).textContent||'';
          sec.querySelector('.plc-more').click();R.all=sec.querySelectorAll('.plc-gl li').length;R.text=NBA_PLAYER.text('%s');R.total=/total/i.test(c.textContent);
          R.sw=document.documentElement.scrollWidth;R.cw=document.documentElement.clientWidth;""" % (doc, TRADED, TRADED), pre_js=PRE, wait_ms=2500)
        self.assertIsNone(r.get("error"), r)
        self.assertTrue(r["shown"])
        self.assertEqual(len(r["lines"]), 10)                                               # the last 10 games first
        self.assertTrue(r["lines"][0].upper().startswith("NOV 12"), r["lines"][0])                  # newest first
        self.assertIn("13-7-1-1-1", r["lines"][0])                                          # P-R-A-S-B
        self.assertIn("5/7 FG", r["lines"][0])
        self.assertIn("2 3PM", r["lines"][0])
        self.assertIn("1/2 FT", r["lines"][0])
        self.assertIn("3 TO", r["lines"][0])
        self.assertIn("P-R-A-S-B", r["title"])
        self.assertEqual(r["off"], 1)                                                       # a bench game is dimmed and says BN
        self.assertEqual(r["boxes"], 0)                                                     # no stat boxes
        self.assertFalse(r["total"])                                                        # no totals anywhere
        self.assertIn("Show all 12", r["more"])
        self.assertEqual(r["all"], 12)
        self.assertIn("NOV 12: 13-7-1-1-1 · 5/7 FG · 2 3PM · 1/2 FT · 3 TO · 30 min", r["text"])     # the share text carries the same lines
        self.assertEqual(sum(1 for x in r["text"].split("\n") if x.startswith("  NOV")), 5)
        self.assertNotIn("Next year", r["text"])                                            # the keeper rank is not in the share text
        self.assertLessEqual(r["sw"], r["cw"])

    def test_a_game_line_fits_a_phone_without_widening_the_page(self):
        import json as _j
        rows = [["2026-11-%02d" % d, "PG", "@ DAL", "34", 12, 20, 10, 12, 4, 33, 12, 11, 2, 3, 5, 4] for d in range(12, 2, -1)]
        doc = _j.dumps({"capturedAt": "2026-11-13T09:40:00Z", "days": [], "p": {"10572": rows}})
        r = _phone.phone_run("""NBA_PLAYER.logSet(%s);NBA_PLAYER.open('%s');var sec=document.querySelector('#pl-sheet .plc-log'),card=document.querySelector('#pl-sheet .plc');
          var cr=card.getBoundingClientRect();R.over=0;[].forEach.call(sec.querySelectorAll('.plc-gl li > *'),function(x){if(x.getBoundingClientRect().right>cr.right+1)R.over++;});
          R.lines=sec.querySelectorAll('.plc-gl li').length;R.h=sec.querySelector('.plc-gl li').getBoundingClientRect().height;R.sw=document.documentElement.scrollWidth;R.cw=document.documentElement.clientWidth;""" % (doc, TRADED),
                             pre_js=PRE, wait_ms=2500)
        self.assertIsNone(r.get("error"), r)
        self.assertEqual(r["over"], 0)
        self.assertLessEqual(r["sw"], r["cw"])

    def test_without_the_log_file_the_card_says_so_and_a_player_with_no_games_has_no_section(self):
        r = _phone.phone_run("""NBA_PLAYER.logSet(null);var c=NBA_PLAYER.card('%s');document.body.appendChild(c);var s=c.querySelector('.plc-log');R.failed=!s.hidden;R.msg=s.textContent;
          NBA_PLAYER.logSet({capturedAt:'x',days:[],p:{}});var d=NBA_PLAYER.card('%s');R.empty=d.querySelector('.plc-log').hidden;""" % (TRADED, TRADED), pre_js=PRE, wait_ms=2500)
        self.assertTrue(r["failed"])
        self.assertIn("none loaded", r["msg"])
        self.assertTrue(r["empty"])

    def test_the_export_is_the_card_itself_not_the_dialog_around_it(self):
        r = _phone.phone_run("""return new Promise(function(done){var spec={node:NBA_PLAYER.card('%s'),wrap:[],width:430,foot:'x'};NBA_EXPORT.snap(spec).then(function(cv){
            var c=cv.getContext('2d'),S=cv.width/430,px=function(x,y){var d=c.getImageData(Math.round(x),Math.round(y),1,1).data;return [d[0],d[1],d[2]];};
            R.size=[cv.width,cv.height];R.w=cv.width/S;R.h=cv.height/S;R.corner=px(3,3);R.mid=px(cv.width/2,cv.height*0.45);
            var dark=0;[3,cv.width-4].forEach(function(x){for(var y=cv.height*0.1;y<cv.height*0.9;y+=cv.height/40){var p=px(x,y);if(p[0]<80&&p[1]<80&&p[2]<110)dark++;}});R.dark=dark;done(R);});});""" % TRADED, pre_js=PRE, width=1100, wait_ms=6000)
        self.assertAlmostEqual(r["w"], 430, delta=2)                                       # phone width, 2.5x
        self.assertGreater(r["h"], 380)
        self.assertLess(r["h"], 1200)
        self.assertGreater(min(r["corner"]), 230)                                          # a light page background, not a dark overlay backdrop
        self.assertEqual(r["dark"], 0)

    def test_the_share_text_lists_every_fact_in_plain_lines(self):
        r = _phone.phone_run("""R.t=NBA_PLAYER.text('%s');""" % TRADED, pre_js=PRE, width=1100, wait_ms=2000)
        lines = r["t"].split("\n")
        self.assertIn("Morez Johnson Jr.", lines[0])
        self.assertTrue(any(x.startswith("Salary now:") for x in lines))
        self.assertTrue(any("Traded from CrazyCat to HCMC" in x for x in lines))
        self.assertTrue(any("Drafted by CrazyCat" in x for x in lines))
        self.assertIn("?player=10572", lines[-1])                                          # the link is the last line

    def test_the_link_opens_the_card(self):
        r = _phone.phone_run("""R.open=!!document.getElementById('pl-sheet');R.name=(document.querySelector('#pl-sheet .plc-n')||{}).textContent||'';""",
                             pre_js=PRE + ";location.hash='#player/10572'", width=1100, wait_ms=2500)
        self.assertIn("Morez", r["name"])

    def test_the_export_button_opens_a_preview_of_the_card(self):
        r = _phone.phone_run("""NBA_PLAYER.open('%s');var b=[].filter.call(document.querySelectorAll('#pl-sheet .pls-b'),function(x){return x.textContent==='Export'})[0];b.click();
          return new Promise(function(done){var t=Date.now();(function p(){var ov=document.getElementById('chk-imgov');if(ov||Date.now()-t>40000){R.ov=!!ov;R.title=ov?(ov.querySelector('.imgov-ttl')||{}).textContent:'';
            R.btns=ov?[].map.call(ov.querySelectorAll('.imgov-b'),function(x){return x.textContent}):[];R.sheetGone=!document.getElementById('pl-sheet');done(R);}else setTimeout(p,100);})();});""" % TRADED,
                             pre_js=PRE, width=1100, wait_ms=500, budget=90000)
        self.assertTrue(r["ov"])
        self.assertIn("Morez", r["title"])
        self.assertIn("Copy link", r["btns"])
        self.assertIn("Copy text", r["btns"])
        self.assertTrue(r["sheetGone"])


if __name__ == "__main__":
    unittest.main()
