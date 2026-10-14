"""Test fixture: the REAL trade definitions with every transaction reset to PROPOSED.

Production data now has all trades OFFICIAL (replayed over the keeper freeze). Scenario-engine tests still need
the original selectable-trade behaviour (chains, dependencies, toggling), so they run over this copy.
"""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import league_state as ls  # noqa: E402


def proposed_inputs(inputs=None):
    i = dict(inputs or ls.load_inputs())
    i["trades"] = copy.deepcopy(i["trades"])
    for t in i["trades"]["trades"]:
        t["status"] = "PROPOSED"
    i["tradeIndex"] = {t["tradeId"]: t for t in i["trades"]["trades"]}
    # draft selections are recorded against the post-trade ledger; this copy models the pre-trade world, so no draft yet
    i["draft"] = {**i["draft"], "events": [], "holds": []}
    return i


def predraft_index_html(path=None):
    """index.html with the FA/DRAFT 60 rebuilt as it stood BEFORE any draft selection (nobody excluded).

    The published board now excludes drafted players; regression tests about keeper/cut/ranking logic assert on the
    pre-draft board, which is the same pipeline minus the drafted-exclusion."""
    import build_fa_draft_pool as pool
    path = path or os.path.join(os.path.dirname(__file__), "..", "index.html")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    yahoo = os.path.join(os.path.dirname(__file__), "..", "data", "yahoo", "players_normalized.json")
    real = pool.drafted_names
    pool.drafted_names = lambda *a, **k: set()
    try:
        return pool.build(html, yahoo)[0]
    finally:
        pool.drafted_names = real
