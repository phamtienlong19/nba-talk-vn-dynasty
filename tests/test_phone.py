"""The site at a true phone width (390px, in an iframe): header, overflow on every tab, touch targets."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _phone  # noqa: E402
import test_scenario_rendering as tsr  # noqa: E402

PRE = "localStorage.setItem('nbaTalkVN.myTeam','franchise-04')"


@unittest.skipUnless(tsr._chrome(), "no Chrome")
class TestPhone(unittest.TestCase):
    def test_the_header_is_one_scrolling_row_of_sections_and_a_fifth_of_the_screen_at_most(self):
        r = _phone.phone_run("""var tb=document.querySelector('.topbar'),row=document.querySelector('.navrow');R.h=tb.offsetHeight-(parseInt(tb.style.getPropertyValue('--tb-fold'))||0);R.links=row.querySelectorAll('.navlink').length;
          var tops={};[].forEach.call(row.querySelectorAll('.navlink'),function(a){tops[Math.round(a.getBoundingClientRect().top)]=1;});R.rows=Object.keys(tops).length;
          R.scroll=row.scrollWidth>row.clientWidth;R.vh=innerHeight;""", pre_js=PRE)
        self.assertEqual(r["rows"], 1)                                                   # one row, not two
        self.assertGreaterEqual(r["links"], 6)
        self.assertLess(r["h"], r["vh"] * 0.16)                                          # the pinned part was 167px of 844 (20%) with the mode row; now one row of sections

    def test_the_header_leaves_while_reading_down_and_returns_scrolling_up(self):
        r = _phone.phone_run("""document.body.style.minHeight='4000px';var tb=document.querySelector('.topbar'),sc=function(y){window.scrollTo({top:y,behavior:'instant'});window.dispatchEvent(new Event('scroll'));};
          return new Promise(function(done){sc(300);setTimeout(function(){sc(700);setTimeout(function(){R.hiddenDown=tb.classList.contains('tb-hide');sc(500);setTimeout(function(){R.backUp=!tb.classList.contains('tb-hide');done(R);},300);},300);},300);});""", pre_js=PRE)
        self.assertTrue(r["hiddenDown"] and r["backUp"])

    def test_no_tab_scrolls_sideways_at_390px(self):
        r = _phone.phone_run("""R.bad={};['teams','cap','trade-lab','draft','live','me'].forEach(function(t){var a=document.querySelector('.navlink[data-tab="'+t+'"]');if(a)a.click();else{location.hash='#'+t;window.dispatchEvent(new HashChangeEvent('hashchange'));}
          var de=document.documentElement;if(de.scrollWidth>de.clientWidth)R.bad[t]=de.scrollWidth;});""", pre_js=PRE)
        self.assertEqual(r["bad"], {})

    def test_touch_targets_on_the_teams_tab_meet_the_phone_minimum_when_the_pointer_is_coarse(self):
        with open(os.path.join(HERE, "..", "index.html"), encoding="utf-8") as f:
            src = f.read()
        self.assertIn("@media(pointer:coarse){.tc-info{width:44px;height:44px", src)
        self.assertIn("input,select,textarea{font-size:16px!important}", src)             # no zoom-on-focus on iPhone


if __name__ == "__main__":
    unittest.main()
