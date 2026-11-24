#!/usr/bin/env python3
"""Build the page that is served: index.html with its generated data blocks (league data, what-if, live, draft status) embedded.

    python3 scripts/build_site.py [--out site]

Copies index.html and the other served files into --out and runs the same embedders the data bots run, but against the COPY
(NBA_INDEX_HTML points them at it), so the repository's own index.html is never touched. Today the repo still commits the embedded blocks, so
the build must reproduce the committed page byte for byte (tests/test_build_site.py); that equivalence is what lets the blocks later be dropped
from git, which is what ends the index.html merge conflicts between data PRs (docs/BOT_PRS.md, plan A piece 3)."""
import argparse
import os
import shutil
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SERVED = ("index.html", "build.json", "CNAME", ".nojekyll")


def build(out):
    out = os.path.abspath(out)
    os.makedirs(out, exist_ok=True)
    for name in SERVED:
        src = os.path.join(ROOT, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(out, name))
    for d in ("exports",):   # linked from the page (the Yahoo top-300 xlsx / md); a branch deploy served the whole repo, an artifact deploy only this
        src = os.path.join(ROOT, d)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(out, d), dirs_exist_ok=True)
    env = dict(os.environ, NBA_INDEX_HTML=os.path.join(out, "index.html"))
    for script, arg in (("build_league_state.py", "sync-ledger"), ("build_league_state.py", "embed"), ("what_if.py", "embed"), ("live_page.py", "embed")):
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script), arg], check=True, env=env, stdout=subprocess.DEVNULL)
    return os.path.join(out, "index.html")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "site"))
    print(build(ap.parse_args().out))


if __name__ == "__main__":
    main()
