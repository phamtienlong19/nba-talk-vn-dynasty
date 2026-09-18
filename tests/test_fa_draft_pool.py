import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_fa_draft_pool as pool  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")

CURATED_ROOKIE_NAMES = [
    "Cameron Boozer", "Caleb Wilson", "AJ Dybantsa", "Darryn Peterson",
    "Darius Acuff Jr.", "Keaton Wagler", "Mikel Brown Jr.", "Kingston Flemings",
    "Yaxel Lendeborg", "Morez Johnson Jr.", "Allen Graves", "Meleek Thomas",
    "Ebuka Okorie", "Brayden Burries", "Aday Mara", "Hannes Steinbach",
]


def _read_index_html():
    with open(INDEX_HTML, encoding="utf-8") as f:
        return f.read()


def _pool_block(index_html):
    start, end = pool._find_pool_grid_span(index_html)
    return index_html[start:end]


def _pool_rows(index_html):
    block = _pool_block(index_html)
    rows = re.findall(r'<div class="pool-row.*?</div></div>', block, re.S)
    parsed = []
    for row in rows:
        rank = int(re.search(r'<div class="pool-rank">(\d+)</div>', row).group(1))
        cap = float(re.search(r'<div class="pool-cap">([\d.]+)</div>', row).group(1))
        name = re.search(r'<div class="pool-player">(.*?)</div>', row, re.S).group(1)
        parsed.append({"rank": rank, "cap": cap, "name": name})
    return parsed


class TestIndexHtmlPoolRegressions(unittest.TestCase):
    """Regression checks against the committed index.html FA/DRAFT 60 board."""

    @classmethod
    def setUpClass(cls):
        cls.html = _read_index_html()
        cls.rows = _pool_rows(cls.html)
        cls.names = [r["name"] for r in cls.rows]

    def test_exactly_sixty_players_sequential(self):
        self.assertEqual(len(self.rows), 60)
        self.assertEqual([r["rank"] for r in self.rows], list(range(1, 61)))

    def test_cap_is_strictly_non_increasing(self):
        caps = [r["cap"] for r in self.rows]
        for a, b in zip(caps, caps[1:]):
            self.assertGreaterEqual(a, b, "CAP column must never increase top to bottom")

    def test_no_duplicate_players(self):
        normed = [pool.normalize_name(n) for n in self.names]
        self.assertEqual(len(normed), len(set(normed)), "duplicate player/alias found in pool")

    def test_paul_reed_present(self):
        self.assertIn("Paul Reed", self.names)

    def test_curated_rookies_not_silently_omitted(self):
        missing = [n for n in CURATED_ROOKIE_NAMES if pool.normalize_name(n) not in
                   {pool.normalize_name(x) for x in self.names}]
        self.assertEqual(missing, [], f"curated rookies missing from FA/DRAFT 60: {missing}")

    def test_defending_champion_crown_present_in_pool_source_tag(self):
        block = _pool_block(self.html)
        self.assertIn(f'src-cut">{pool.CROWN}{pool.DEFENDING_CHAMPION_SHORT_NAME}<', block)


class TestCrownMarker(unittest.TestCase):
    """The defending champion crown must survive rendering everywhere the
    team's identity is shown, without touching any ranking/cap/keeper logic."""

    @classmethod
    def setUpClass(cls):
        cls.html = _read_index_html()

    def test_crown_on_draft_order_pick_chips(self):
        chips = re.findall(r'<span class="pick-chip"[^>]*>([^<]*Silver Seekers[^<]*)</span>', self.html)
        self.assertTrue(chips, "no Silver Seekers pick-chip found in draft order")
        for chip in chips:
            self.assertTrue(chip.startswith(pool.CROWN), f"missing crown on draft order chip: {chip!r}")

    def test_crown_on_keeper_board_team_card(self):
        self.assertIn(f'<div class="team-name">{pool.CROWN}The Silver Seekers</div>', self.html)

    def test_crown_on_cap_page_team_row(self):
        self.assertIn(f'<b>{pool.CROWN}{pool.DEFENDING_CHAMPION_SHORT_NAME}</b>', self.html)

    def test_crown_does_not_appear_on_other_teams(self):
        crown_count = self.html.count(pool.CROWN)
        # draft order (3 picks) + keeper card + cap row + FA/DRAFT pool src tag = 6
        self.assertEqual(crown_count, 6, "crown count drifted -- check no other team picked it up")


class TestUiPolishRegressions(unittest.TestCase):
    """Light regression coverage for the UI polish items in this PR."""

    @classmethod
    def setUpClass(cls):
        cls.html = _read_index_html()

    def test_cuts_ordered_by_cap_descending_per_team(self):
        for card in re.findall(r'<section class="team-card".*?</section>', self.html, re.S):
            cuts_block = re.search(r'<div class="cuts-list">(.*?)</div></footer>', card, re.S)
            if not cuts_block:
                continue
            chips = re.findall(r'<span class="cut-chip">(.*?)</span>', cuts_block.group(1), re.S)
            caps = []
            for chip in chips:
                m = re.search(r"<strong>(\d+)</strong>", chip)
                caps.append(int(m.group(1)) if m else 0)
            for a, b in zip(caps, caps[1:]):
                self.assertGreaterEqual(a, b, f"cuts not CAP-ordered: {chips}")

    def test_draft_order_has_three_round_panels_of_sixteen(self):
        for label in ("ROUND 1", "ROUND 2", "ROUND 3"):
            count = len(re.findall(rf'<div class="pick-slot">{label[-1]}\.\d\d</div>', self.html))
            self.assertEqual(count, 16, f"{label} does not have 16 picks")

    def test_no_duplicate_or_missing_draft_picks(self):
        slots = re.findall(r'<div class="pick-slot">(\d\.\d\d)</div>', self.html)
        self.assertEqual(len(slots), 48)
        self.assertEqual(len(slots), len(set(slots)), "duplicate draft pick slot found")


class TestSortAndTruncateUnit(unittest.TestCase):
    """Unit-level coverage of the ranking pipeline against synthetic data,
    independent of live Yahoo/index.html state."""

    def _cand(self, name, cap, o_rank=pool.MISSING_OR, pick=pool.MISSING_PICK):
        return pool.Candidate(name=name, pos="PF", nba="XXX", cap=cap, o_rank=o_rank, pick=pick)

    def test_cap_is_primary_key(self):
        candidates = {
            "a": self._cand("A", cap=5, o_rank=200),
            "b": self._cand("B", cap=10, o_rank=1),
        }
        ranked = pool.sort_and_truncate(candidates)
        self.assertEqual([c.name for c in ranked], ["B", "A"])

    def test_dynasty_or_manual_relevance_never_beats_cap_tier(self):
        # "B" has a much better manual-relevance pick number, but $0 vs $1
        # must still keep A ahead of B.
        candidates = {
            "a": self._cand("A", cap=1),
            "b": self._cand("B", cap=0, pick=1),
        }
        ranked = pool.sort_and_truncate(candidates)
        self.assertEqual([c.name for c in ranked], ["A", "B"])

    def test_or_is_tiebreak_within_cap_tier(self):
        candidates = {
            "a": self._cand("A", cap=0, o_rank=50),
            "b": self._cand("B", cap=0, o_rank=10),
        }
        ranked = pool.sort_and_truncate(candidates)
        self.assertEqual([c.name for c in ranked], ["B", "A"])

    def test_truncation_happens_after_full_sort(self):
        candidates = {}
        for i in range(70):
            candidates[str(i)] = self._cand(f"P{i}", cap=70 - i)
        ranked = pool.sort_and_truncate(candidates)
        self.assertEqual(len(ranked), 60)
        self.assertEqual(ranked[0].name, "P0")
        self.assertEqual(ranked[-1].name, "P59")

    def test_guaranteed_name_forced_in_without_breaking_cap_order(self):
        candidates = {}
        for i in range(65):
            name = f"P{i}"
            candidates[pool.normalize_name(name)] = self._cand(name, cap=100 - i)
        candidates[pool.normalize_name("Paul Reed")] = self._cand("Paul Reed", cap=0)
        ranked = pool.sort_and_truncate(candidates)
        names = [c.name for c in ranked]
        self.assertIn("Paul Reed", names)
        caps = [c.cap for c in ranked]
        for a, b in zip(caps, caps[1:]):
            self.assertGreaterEqual(a, b)

    def test_no_duplicate_aliases_across_sources(self):
        html = _read_index_html()
        yahoo = pool.load_yahoo_players()
        candidates = pool.build_candidates(html, yahoo)
        names = [c.name for c in candidates.values()]
        normed = [pool.normalize_name(n) for n in names]
        self.assertEqual(len(normed), len(set(normed)))


if __name__ == "__main__":
    unittest.main()
