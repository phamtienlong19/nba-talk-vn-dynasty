"""The served page for the tests: index.html with its generated data blocks embedded (scripts/build_site.py), built once per process,
or once per run when scripts/run_tests.py already built it (NBA_TEST_SITE).

The repository does not commit those blocks (they are rebuilt from data/ at deploy time), so a test that needs the data, the what-if block or the
live block must read INDEX from here, not the raw file. The raw index.html is for tests of static markup that do not care."""
import atexit
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
_dir = os.environ.get("NBA_TEST_SITE")
if not _dir or not os.path.isfile(os.path.join(_dir, "index.html")):
    _dir = tempfile.mkdtemp(prefix="nba-site-")
    atexit.register(shutil.rmtree, _dir, True)
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_site.py"), "--out", _dir], check=True, capture_output=True)
INDEX = os.path.join(_dir, "index.html")
