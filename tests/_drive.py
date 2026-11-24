"""One way to run JavaScript inside index.html in headless Chrome and read a result back (shared by every page-driving test).

Timing uses performance.now() so a test may freeze Date. The page runs `body_js` (it fills R) `start` ms after load. The result is written as soon as the test sets `R.__done = 1`, or `wait` ms after the
body ran, whichever comes first. A test that waits for real async work (an image drawing, fonts, a promise) must set R.__done in its callback and
pass a generous `wait`: a fixed wait races a slow CI runner, which is where the flaky `KeyError` / `[] is not true` failures came from.
A test that only uses timers can ignore all of this (virtual time makes them exact). `waitFor(cond, then, ms)` polls for a condition."""
import os as _os, sys as _sys; _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import _site  # noqa: E402  (the built page: index.html + the generated data blocks)
import html as html_lib
import json
import os
import re
import shutil
import tempfile

INDEX = _site.INDEX


def drive_page(body_js, qs="", wait=2500, start=500, size="1000,1400", budget=60000, head="", page=None, mutate=None, out_id="o", timeout=150, pre_done=""):
    import test_scenario_rendering as tsr            # lazy: that module imports this one
    if page is None:
        with open(INDEX, encoding="utf-8") as f:
            page = f.read()
    if head:
        page = page.replace("<head>", "<head>" + head, 1)
    if mutate:
        page = mutate(page)
    script = ("<script>(function(){var R={},t0=performance.now();window.waitFor=function(c,cb,ms){var t=performance.now();(function p(){if(c()||performance.now()-t>ms)cb();else setTimeout(p,100);})();};"
              "setTimeout(function(){var t1=performance.now();try{" + body_js + "\n}catch(e){R.error=String(e&&e.stack||e);}"
              "(function w(){if(R.__done||performance.now()-t1>=__WAIT__){try{" + pre_done + "}catch(e){R.error=String(e);}var p=document.createElement('pre');p.id='" + out_id + "';delete R.__done;"
              "p.textContent=JSON.stringify(R);document.body.appendChild(p);}else setTimeout(w,100);})();},__START__);})();</script>").replace("__WAIT__", str(wait)).replace("__START__", str(start))
    page = page[:page.rindex("</body>")] + script + page[page.rindex("</body>"):]
    d = tempfile.mkdtemp()
    try:
        path = os.path.join(d, "index.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        out = tsr._chrome_run(["--window-size=" + size, "--virtual-time-budget=%d" % budget, "--dump-dom", "file://" + path + qs], timeout).stdout
    finally:
        shutil.rmtree(d)
    m = re.search(r'<pre id="%s">(.*?)</pre>' % out_id, out, re.S)
    if not m:
        raise AssertionError("page produced no result: " + out[-400:])
    r = json.loads(html_lib.unescape(m.group(1)))
    if "error" in r:
        raise AssertionError(r["error"])
    return r
