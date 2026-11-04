"""Run a script inside the real page at a true phone width. Headless Chrome will not make a window narrower than 500px, so the page is
loaded into a 390px-wide iframe (srcdoc keeps it same-origin) and the script runs in that frame, where the phone media queries apply."""
import html as html_lib
import json
import os
import re
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_scenario_rendering as tsr  # noqa: E402

INDEX = os.path.join(HERE, "..", "index.html")


def phone_run(body_js, width=390, height=844, pre_js="", wait_ms=2500, budget=12000):
    with open(INDEX, encoding="utf-8") as f:
        page = f.read()
    if pre_js:
        page = page.replace("<head>", "<head><script>" + pre_js + "</script>", 1)
    inner = json.dumps(page).replace("</", "<\\/")
    body = json.dumps("(function(){var R={};try{" + body_js + "}catch(e){R.error=String(e&&e.stack||e);}return R;})()")
    wrapper = ("<!doctype html><html><body style='margin:0'><iframe id='f' style='width:%dpx;height:%dpx;border:0' srcdoc=''></iframe><pre id='o'></pre><script>"
               "var f=document.getElementById('f');f.srcdoc=%s;f.onload=function(){setTimeout(function(){var out;try{out=f.contentWindow.eval(%s);Promise.resolve(out).then(function(r){document.getElementById('o').textContent=JSON.stringify(r);});}"
               "catch(e){document.getElementById('o').textContent=JSON.stringify({error:String(e)});}},%d);};</script></body></html>") % (width, height, inner, body, wait_ms)
    d = tempfile.mkdtemp()
    try:
        path = os.path.join(d, "w.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(wrapper)
        out = tsr._chrome_run(["--window-size=%d,%d" % (width + 20, height + 20), "--virtual-time-budget=%d" % budget, "--dump-dom", "file://" + path], 150).stdout
    finally:
        shutil.rmtree(d)
    m = re.search(r'<pre id="o">(.*?)</pre>', out, re.S)
    if not m:
        raise AssertionError("no result: " + out[-300:])
    return json.loads(html_lib.unescape(m.group(1)))
