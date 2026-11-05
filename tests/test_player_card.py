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
          R.name=c.querySelector('.plc-n').textContent;R.rk=!!c.querySelector('.rk-mark');R.tiles=[].map.call(c.querySelectorAll('.plc-t > span'),function(x){return x.textContent});
          R.pills=[].map.call(c.querySelectorAll('.plc-p'),function(x){return x.textContent});R.hist=[].map.call(c.querySelectorAll('.plc-tl li'),function(x){return x.textContent});
          R.mine=!!c.querySelector('.plc-own small');R.advice=/should|recommend|fair|value/i.test(c.textContent.replace('Salary','').replace('SALARY',''));""" % TRADED, pre_js=PRE, width=1100, wait_ms=2500)
        self.assertIn("Morez", r["name"])
        self.assertTrue(r["rk"])
        self.assertEqual(r["tiles"], ["SALARY NOW", "NEXT YEAR", "KEEPER RANK"])
        self.assertEqual(len(r["hist"]), 2)
        self.assertIn("Traded from", r["hist"][0])                                          # newest first
        self.assertIn("Drafted by", r["hist"][1])                                           # the draft is the oldest fact
        self.assertTrue(r["mine"])
        self.assertFalse(r["advice"])

    def test_the_week_block_appears_only_with_the_live_feed(self):
        feed = json.dumps(tlf.feed()).replace("</", "<\\/")
        r = _phone.phone_run("""var a=NBA_PLAYER.card('%s');R.before=/WEEK/.test(a.textContent);NBA_LIVE.set(%s);var b=NBA_PLAYER.card('%s');R.after=/WEEK/.test(b.textContent);""" % (TRADED, feed, TRADED),
                             pre_js=PRE, width=1100, wait_ms=2500)
        self.assertFalse(r["before"])

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
