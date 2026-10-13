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
    return i
