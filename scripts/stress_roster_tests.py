#!/usr/bin/env python3
"""Run the full test suite against randomly perturbed rosters, in a TEMPORARY COPY of the repository.

    python3 scripts/stress_roster_tests.py [SEED ...]        # default seeds 1-5

Why: the `Update Yahoo Rosters` workflow runs the whole suite on the regenerated site before it opens a PR. A test that
hard-codes a detail of today's roster ("Bsy has 13 players", "Zion is on CrazyCat") makes the first real roster change
block that PR. Each seed applies a different set of drops, free-agent pickups, IL moves and status changes as a new verified
snapshot (the same way an import would), regenerates the site, and runs the tests. Any failure means a test pins live data.

Nothing in your working tree is touched: every seed runs in its own copy under the system temp directory.
Standard library only.
"""
from __future__ import annotations

import datetime
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def perturb(seed: int) -> str:
    """Apply one random roster change to THIS repository's data (run inside the temp copy)."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import import_rosters as ir
    import league_state as ls
    import season_state as ss
    random.seed(seed)
    i = ls.load_inputs()
    si = ss.load_season(i)
    snap = json.loads(json.dumps(si["rosterSnapshot"]))
    teams, fids = snap["teams"], list(snap["teams"])

    def rows():
        return [(f, r) for f in fids for r in teams[f]]
    paid = [(f, r) for f, r in rows() if ls.player_cap(si, r["playerKey"]) > 0]
    for f, r in random.sample(paid, 4) + random.sample(rows(), 4):            # drops (biased to paid players)
        if r in teams[f] and len(teams[f]) > 8:
            teams[f].remove(r)
    taken = {r["playerKey"] for _, r in rows()}
    for p in random.sample([p for p in i["registry"].values() if p["playerKey"] not in taken], 8):   # free-agent pickups
        teams[random.choice(fids)].append({"playerKey": p["playerKey"], "name": p["name"], "slot": "BN"})
    for _, r in random.sample(rows(), 5):                                       # five players Out and on IL
        r["slot"], r["status"] = "IL", "O"
    for _, r in random.sample(rows(), 4):                                       # status changes
        if random.random() < .5:
            r.pop("status", None)
        else:
            r["status"] = "Q"
    for _, r in random.sample(rows(), 3):                                       # lineup moves
        r["slot"] = random.choice(["PG", "SG", "C", "BN", "Util"])
    for f in fids:
        teams[f].sort(key=lambda r: r["playerKey"])
    when = (datetime.datetime.fromisoformat(snap["verifiedAt"].replace("Z", "+00:00")) + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    snap.update(verifiedAt=when, kind="VERIFIED_IMPORT", source=f"Yahoo Fantasy league 85092 team pages, stress seed {seed}")
    snap["digest"] = ls._digest(teams)
    snap["ownershipDigest"] = ls._digest({f: sorted(r["playerKey"] for r in rs) for f, rs in teams.items()})
    snap["snapshotId"] = f"RS-{when[:10]}-{snap['digest'][:8]}"
    ir.commit(si, snap, {"blocking": []}, {"transactions": []}, ss.DATA_DIR, reviewed=True)
    for cmd in (["build_league_state.py", "sync-ledger"], ["build_league_state.py", "embed"], ["what_if.py", "embed"]):
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", cmd[0])] + cmd[1:], check=True, cwd=ROOT, stdout=subprocess.DEVNULL)
    return snap["snapshotId"]


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args[:1] == ["--apply"]:                                                 # internal: perturb the repo we are running in
        print(perturb(int(args[1])))
        return 0
    seeds = [int(a) for a in args] or [1, 2, 3, 4, 5]
    bad = 0
    for seed in seeds:
        work = tempfile.mkdtemp(prefix="roster-stress-")
        try:
            copy = os.path.join(work, "repo")
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", "local_data", "local_sources", "__pycache__", "artifacts", ".issue-context"))
            subprocess.run([sys.executable, os.path.join(copy, "scripts", "stress_roster_tests.py"), "--apply", str(seed)],
                           check=True, cwd=copy, stdout=subprocess.DEVNULL)
            r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=copy, capture_output=True, text=True)
            tail = (r.stderr.strip().splitlines() or ["?"])[-1]
            fails = [l for l in r.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
            print(f"seed {seed}: {'OK' if r.returncode == 0 else 'FAILED'} ({tail})")
            for l in fails:
                print("   ", l)
            bad += r.returncode != 0
        finally:
            shutil.rmtree(work, ignore_errors=True)
    print("every test is independent of the current roster" if not bad else f"{bad} seed(s) failed: a test pins live roster data")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
