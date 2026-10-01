import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import build_fa_draft_pool as pool  # noqa: E402

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
INDEX_HTML = os.path.join(REPO_ROOT, "index.html")

# Small deterministic Yahoo fixture -- unit tests must not depend on the
# developer-local, gitignored local_data/yahoo/players_normalized.json
# (absent in a clean CI checkout). Contains only synthetic players, so
# these tests stay valid even after real Yahoo rankings change.
FIXTURE_YAHOO = os.path.join(os.path.dirname(__file__), "fixtures", "yahoo_players_small.json")

# Curated names Yahoo has ZERO data for -- these are the ones that must
# never be silently omitted, per build_fa_draft_pool.Candidate.guaranteed.
GUARANTEED_CURATED_ROOKIE_NAMES = [
    "Kingston Flemings", "Allen Graves", "Meleek Thomas", "Ebuka Okorie", "Aday Mara",
]

# Curated names Yahoo DOES rank (even weakly). These compete on real merit
# and are deliberately NOT force-included -- forcing every named rookie
# regardless of real value was the bug that piled rookies up at the
# bottom of the pool, displacing genuinely better non-rookie candidates.
MERIT_ONLY_CURATED_ROOKIE_NAMES = [
    "Cameron Boozer", "Caleb Wilson", "AJ Dybantsa", "Darryn Peterson",
    "Darius Acuff Jr.", "Keaton Wagler", "Mikel Brown Jr.",
    "Yaxel Lendeborg", "Morez Johnson Jr.", "Brayden Burries", "Hannes Steinbach",
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

    def test_guaranteed_curated_rookies_not_silently_omitted(self):
        present = {pool.normalize_name(x) for x in self.names}
        missing = [n for n in GUARANTEED_CURATED_ROOKIE_NAMES if pool.normalize_name(n) not in present]
        self.assertEqual(missing, [], f"guaranteed curated rookies missing from FA/DRAFT 60: {missing}")

    def test_yahoo_ranked_rookie_src_badge_is_r_not_fa(self):
        # A rookie found via the live Yahoo fetch is still a rookie --
        # the SRC badge must say "R", not "FA", regardless of which
        # source supplied their metadata. Anchored directly off each
        # player's own name (fields are strictly ordered within a row),
        # so this can't accidentally match a neighboring row.
        block = _pool_block(self.html)
        present = {pool.normalize_name(x) for x in self.names}
        for name in MERIT_ONLY_CURATED_ROOKIE_NAMES:
            if pool.normalize_name(name) not in present:
                continue  # didn't clear the pool naturally this cycle, nothing to check
            m = re.search(
                rf'<div class="pool-player">{re.escape(name)}</div>'
                rf'<div class="pool-nba">[^<]*</div><div class="pool-cap">[^<]*</div>'
                rf'<div class="pool-src">(.*?)</div></div>',
                block, re.S,
            )
            self.assertIsNotNone(m, f"{name} row not found in expected field order")
            self.assertIn('src-r">R<', m.group(1), f"{name} should carry the R badge, not FA/cut")

    def test_defending_champion_crown_present_in_pool_source_tag_if_a_cut_made_it(self):
        # Whether any of the champion's own cut players naturally clears
        # the top 60 varies with the ranking methodology/cycle (e.g. the
        # dynasty-blend tiebreak can legitimately displace all of them) --
        # this only checks the crown renders correctly WHEN one does,
        # not that one always must.
        block = _pool_block(self.html)
        if f'src-cut">{pool.DEFENDING_CHAMPION_SHORT_NAME}<' not in block.replace(pool.CROWN, ""):
            return
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
        # draft order (3 picks) + keeper card + cap row = 5, always present.
        # + 1 more FA/DRAFT pool src tag, ONLY if one of the champion's own
        # cut players naturally clears the top 60 this cycle (varies with
        # ranking methodology -- see test_defending_champion_crown_present_
        # in_pool_source_tag_if_a_cut_made_it).
        block = _pool_block(self.html)
        champion_cut_in_pool = f'src-cut">{pool.DEFENDING_CHAMPION_SHORT_NAME}<' in block.replace(pool.CROWN, "")
        expected = 6 if champion_cut_in_pool else 5
        self.assertEqual(crown_count, expected, "crown count drifted -- check no other team picked it up")


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

    def _cand(self, name, cap, o_rank=pool.MISSING_OR):
        return pool.Candidate(name=name, pos="PF", nba="XXX", cap=cap, o_rank=o_rank)

    def test_cap_is_primary_key(self):
        candidates = {
            "a": self._cand("A", cap=5, o_rank=200),
            "b": self._cand("B", cap=10, o_rank=1),
        }
        ranked = pool.sort_and_truncate(candidates)
        self.assertEqual([c.name for c in ranked], ["B", "A"])

    def test_dynasty_or_manual_relevance_never_beats_cap_tier(self):
        # "B" has a far better O-Rank (dynasty-calibrated or real), but
        # $0 vs $1 must still keep A ahead of B.
        candidates = {
            "a": self._cand("A", cap=1),
            "b": self._cand("B", cap=0, o_rank=1),
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
        guaranteed = self._cand("Guaranteed Guy", cap=0)
        guaranteed.guaranteed = True
        candidates[pool.normalize_name("Guaranteed Guy")] = guaranteed
        ranked = pool.sort_and_truncate(candidates)
        names = [c.name for c in ranked]
        self.assertIn("Guaranteed Guy", names)
        caps = [c.cap for c in ranked]
        for a, b in zip(caps, caps[1:]):
            self.assertGreaterEqual(a, b)

    def test_non_guaranteed_candidate_not_forced_in(self):
        candidates = {}
        for i in range(65):
            name = f"P{i}"
            candidates[pool.normalize_name(name)] = self._cand(name, cap=100 - i)
        candidates[pool.normalize_name("Not Guaranteed")] = self._cand("Not Guaranteed", cap=0)
        ranked = pool.sort_and_truncate(candidates)
        self.assertNotIn("Not Guaranteed", [c.name for c in ranked])

    def test_no_duplicate_aliases_across_sources(self):
        html = _read_index_html()
        yahoo = pool.load_yahoo_players(FIXTURE_YAHOO)
        candidates = pool.build_candidates(html, yahoo)
        names = [c.name for c in candidates.values()]
        normed = [pool.normalize_name(n) for n in names]
        self.assertEqual(len(normed), len(set(normed)))

    def test_cut_chip_with_nested_health_badge_is_parsed_fully(self):
        # A bare non-greedy `(.*?)</span>` stops at the health-badge
        # span's own close instead of the chip's, truncating the name and
        # silently losing the cap/position lookup for any cut player who
        # also carries a health badge (see CUT_CHIP_RE).
        html = (
            '<section class="team-card">'
            '<span class="identity-tag">ZZ</span>'
            '<div class="players"></div>'
            '<footer><div class="cuts-list">'
            '<span class="cut-chip">Hurt Guy'
            '<span class="health-badge inj" title="ACL">INJ</span></span>'
            '<span class="cut-chip">Paid Guy <strong>7</strong></span>'
            '</div></footer></section>'
        )
        kept, cuts = pool.parse_team_cards(html)
        names = {c["name"]: c for c in cuts}
        self.assertIn("Hurt Guy", names)
        self.assertNotIn("span", names["Hurt Guy"]["name"].lower())
        self.assertEqual(names["Paid Guy"]["cap"], 7.0)


class TestDynastyOrProxy(unittest.TestCase):
    """A Yahoo-missing curated rookie's tiebreak position must reflect its
    real dynasty rank, not just get dumped after every Yahoo-ranked player
    regardless of relative quality -- this is what makes it possible for a
    well-regarded rookie to outrank a mediocre real-OR veteran within a
    CAP tier."""

    def test_proxy_is_monotonic_in_dynasty_rank(self):
        yahoo = pool.load_yahoo_players(FIXTURE_YAHOO)
        scale = pool._fit_dynasty_or_scale(yahoo)
        better = pool._dynasty_or_proxy(5, scale)
        worse = pool._dynasty_or_proxy(36, scale)
        self.assertLess(better, worse)

    def test_top_rookie_proxy_beats_some_real_or_yahoo_players(self):
        # Kingston Flemings (real post-draft dynasty rank 5, not in the
        # Yahoo fetch) must be able to outrank at least one $0 Yahoo
        # player with a real but mediocre O-Rank -- confirms the fix
        # doesn't just re-sort the 5 Yahoo-missing rookies among
        # themselves at the bottom of the pool.
        html = _read_index_html()
        yahoo = pool.load_yahoo_players(FIXTURE_YAHOO)
        candidates = pool.build_candidates(html, yahoo)
        flemings = candidates[pool.normalize_name("Kingston Flemings")]
        self.assertEqual(flemings.cap, 0.0)
        beaten = [
            c for c in candidates.values()
            if c.cap == 0.0 and c.o_rank != pool.MISSING_OR and c.o_rank > flemings.o_rank
        ]
        self.assertTrue(beaten, "top curated rookie should outrank at least one real-OR $0 player")

    def test_reviewed_names_without_dynasty_rank_get_no_fabricated_advantage(self):
        # Cameron Carr / Labaron Philon Jr. have dynastyRank=None (reviewed,
        # not guaranteed) -- if Yahoo doesn't rank them either, they must
        # fall back to MISSING_OR, never a fabricated proxy value.
        html = _read_index_html()
        yahoo = pool.load_yahoo_players(FIXTURE_YAHOO)
        candidates = pool.build_candidates(html, yahoo)
        for name in ("Cameron Carr", "Labaron Philon Jr."):
            cand = candidates.get(pool.normalize_name(name))
            if cand is not None and cand.o_rank != pool.MISSING_OR:
                continue  # Yahoo ranked them directly, nothing to check
            self.assertEqual(cand.o_rank, pool.MISSING_OR)


class TestBlendScore(unittest.TestCase):
    """Owner-flagged bug: a candidate with real dynasty buzz but ZERO live
    Yahoo data (e.g. Cameron Carr, Labaron Philon Jr. -- reviewed,
    deliberately not force-guaranteed) was floating artificially high
    because missing the Yahoo axis entirely meant it was skipped rather
    than counted against them, the mirror image of the dynasty-consensus
    absence-penalty bug. Both axes must now be symmetric: missing either
    signal is a worst-case percentile (1.0) on that axis, not a free
    pass averaged away."""

    def _cand(self, cap=0.0, o_rank=pool.MISSING_OR, dynasty_rank=None,
              yahoo_rank_max=300, dynasty_rank_max=500):
        return pool.Candidate(
            name="X", pos="PF", nba="XXX", cap=cap, o_rank=o_rank, dynasty_rank=dynasty_rank,
            yahoo_rank_max=yahoo_rank_max, dynasty_rank_max=dynasty_rank_max,
        )

    def test_both_signals_present_is_a_straight_average(self):
        c = self._cand(o_rank=30, dynasty_rank=50, yahoo_rank_max=300, dynasty_rank_max=500)
        self.assertAlmostEqual(c.blend_score(), 0.5 * (30 / 300) + 0.5 * (50 / 500))

    def test_missing_dynasty_signal_is_penalized_not_skipped(self):
        c = self._cand(o_rank=30, dynasty_rank=None, yahoo_rank_max=300)
        self.assertAlmostEqual(c.blend_score(), 0.5 * (30 / 300) + 0.5 * 1.0)

    def test_missing_yahoo_signal_is_penalized_not_skipped(self):
        # This is the Cameron Carr / Labaron Philon Jr. shape: real
        # dynasty rank, zero Yahoo data. Must NOT collapse to the
        # dynasty component alone.
        c = self._cand(o_rank=pool.MISSING_OR, dynasty_rank=50, dynasty_rank_max=500)
        self.assertAlmostEqual(c.blend_score(), 0.5 * 1.0 + 0.5 * (50 / 500))

    def test_a_yahoo_missing_candidate_with_mediocre_dynasty_rank_no_longer_floats_to_the_top(self):
        # A mediocre-dynasty, Yahoo-missing candidate must sort BEHIND a
        # real-Yahoo-ranked candidate with a comparably mediocre O-Rank,
        # not ahead of it just for having half a signal.
        yahoo_missing = self._cand(o_rank=pool.MISSING_OR, dynasty_rank=250, dynasty_rank_max=500)  # 0.5 dynasty pct
        yahoo_ranked = self._cand(o_rank=140, yahoo_rank_max=300)  # ~0.47 yahoo pct, no dynasty data
        self.assertLess(yahoo_ranked.blend_score(), yahoo_missing.blend_score())

    def test_missing_both_signals_is_worst_case(self):
        c = self._cand()
        self.assertAlmostEqual(c.blend_score(), 1.0)


class TestLoadYahooPlayersInjectable(unittest.TestCase):
    """load_yahoo_players must default to the real production path (so
    build()'s no-arg call is unaffected) but accept an explicit path/fixture
    for tests -- no network, no dependency on gitignored local_data/."""

    def test_default_path_is_the_production_yahoo_file(self):
        import inspect
        default = inspect.signature(pool.load_yahoo_players).parameters["path"].default
        self.assertEqual(default, pool.YAHOO_NORMALIZED)

    def test_explicit_path_loads_the_supplied_fixture(self):
        by_norm = pool.load_yahoo_players(FIXTURE_YAHOO)
        self.assertIn(pool.normalize_name("Fixture Bench Guy"), by_norm)
        self.assertIn(pool.normalize_name("Fixture Vet Guy"), by_norm)
        self.assertEqual(len(by_norm), 2)

    def test_build_defaults_to_the_production_yahoo_file(self):
        import inspect
        default = inspect.signature(pool.build).parameters["yahoo_players_path"].default
        self.assertEqual(default, pool.YAHOO_NORMALIZED)

    def test_build_accepts_an_explicit_yahoo_players_path(self):
        html = _read_index_html()
        new_html, ranked = pool.build(html, FIXTURE_YAHOO)
        self.assertEqual(len(ranked), 60)


if __name__ == "__main__":
    unittest.main()
