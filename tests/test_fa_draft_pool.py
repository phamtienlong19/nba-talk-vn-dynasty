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

    def test_rui_hachimura_present(self):
        # CAP $0, Yahoo OR 121, available (not kept by any team): must
        # appear -- guards against dynasty prospects crowding him out.
        self.assertIn("Rui Hachimura", self.names)

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


def _yahoo_row(name, o_rank, cap=0.0, pos="SF"):
    return {"name": name, "nbaTeam": "ZZZ", "eligiblePositions": [pos],
            "oRank": o_rank, "capDollars": cap}


def _yahoo_map(*rows):
    return {pool.normalize_name(r["name"]): r for r in rows}


EMPTY_BOARD = '<section class="team-card"><span class="identity-tag">ZZ</span><div class="players"></div></section>'


class TestYahooDominatesWithinCapTier(unittest.TestCase):
    """Product rule: CAP desc is absolute; inside a CAP tier current Yahoo
    O-Rank is the dominant relevance signal, dynasty consensus is only a
    small secondary refinement, and the curated overlay exists to cover
    Yahoo gaps -- not to override Yahoo."""

    def _cand(self, name, o_rank=pool.MISSING_OR, dynasty_rank=None, proxy_or=None, cap=0.0):
        return pool.Candidate(
            name=name, pos="SF", nba="XXX", cap=cap, o_rank=o_rank, proxy_or=proxy_or,
            dynasty_rank=dynasty_rank, yahoo_rank_max=300, dynasty_rank_max=400,
        )

    def test_yahoo_listed_rookie_uses_actual_yahoo_or(self):
        yahoo = _yahoo_map(_yahoo_row("Cameron Boozer", 51, cap=20, pos="PF"))
        cands = pool.build_candidates(EMPTY_BOARD, yahoo, {pool.normalize_name("Cameron Boozer"): {"rank": 1}}, 400)
        boozer = cands[pool.normalize_name("Cameron Boozer")]
        self.assertEqual(boozer.o_rank, 51)
        self.assertIsNone(boozer.proxy_or, "a Yahoo-ranked rookie must never get a synthetic proxy")
        self.assertEqual(boozer.effective_or(), 51)
        self.assertTrue(boozer.rookie)

    def test_current_yahoo_or_dominates_within_the_same_cap_tier(self):
        vet = self._cand("Vet", o_rank=121)  # Rui Hachimura shape: no dynasty buzz
        prospect = self._cand("Prospect", o_rank=250, dynasty_rank=1)
        ranked = pool.sort_and_truncate({"a": prospect, "b": vet})
        self.assertEqual([c.name for c in ranked], ["Vet", "Prospect"])

    def test_dynasty_bonus_is_bounded_even_for_the_best_dynasty_rank(self):
        deep_prospect = self._cand("Deep", o_rank=250, dynasty_rank=1)
        solid = self._cand("Solid", o_rank=200)
        self.assertGreater(deep_prospect.relevance_score(), solid.relevance_score())

    def test_dynasty_rank_acts_as_secondary_relevance(self):
        plain = self._cand("Plain", o_rank=100)
        buzzy = self._cand("Buzzy", o_rank=100, dynasty_rank=5)
        ranked = pool.sort_and_truncate({"a": plain, "b": buzzy})
        self.assertEqual([c.name for c in ranked], ["Buzzy", "Plain"])

    def test_poor_dynasty_rank_never_penalizes_a_good_yahoo_player(self):
        a = self._cand("NoDynasty", o_rank=121)
        b = self._cand("BadDynasty", o_rank=121, dynasty_rank=399)
        self.assertEqual(a.relevance_score(), b.relevance_score())

    def test_yahoo_missing_curated_prospect_still_enters_the_universe(self):
        yahoo = _yahoo_map(_yahoo_row("Some Vet", 130))
        cands = pool.build_candidates(EMPTY_BOARD, yahoo, {}, 400)
        flemings = cands[pool.normalize_name("Kingston Flemings")]
        self.assertTrue(flemings.rookie)
        self.assertEqual(flemings.o_rank, pool.MISSING_OR)
        self.assertEqual(flemings.proxy_or, pool.PROXY_OR_BASE + pool.PROXY_OR_STEP * 5)

    def test_proxy_is_monotonic_in_dynasty_rank(self):
        self.assertLess(pool._conservative_proxy_or(5), pool._conservative_proxy_or(36))

    def test_speculative_yahoo_missing_rookie_cannot_leapfrog_a_block_of_credible_yahoo_players(self):
        block = [self._cand(f"Vet{i}", o_rank=121 + i) for i in range(30)]  # OR 121-150, all $0
        best_case = self._cand("Prospect", proxy_or=pool._conservative_proxy_or(1))
        speculative = self._cand("Speculative", proxy_or=pool._conservative_proxy_or(36))
        pool_in = {c.name: c for c in block + [best_case, speculative]}
        order = [c.name for c in sorted(pool_in.values(), key=lambda c: c.sort_key())]
        self.assertEqual(order[-2:], ["Prospect", "Speculative"])

    def test_reviewed_names_without_dynasty_rank_get_no_fabricated_advantage(self):
        yahoo = _yahoo_map(_yahoo_row("Some Vet", 130))
        cands = pool.build_candidates(EMPTY_BOARD, yahoo, {}, 400)
        for name in ("Cameron Carr", "Labaron Philon Jr."):
            cand = cands[pool.normalize_name(name)]
            self.assertEqual(cand.effective_or(), pool.MISSING_OR)
            self.assertFalse(cand.guaranteed)

    def test_curated_prospects_are_never_force_included(self):
        yahoo = _yahoo_map(_yahoo_row("Some Vet", 130))
        cands = pool.build_candidates(EMPTY_BOARD, yahoo, {}, 400)
        forced = [c.name for c in cands.values() if c.guaranteed]
        self.assertEqual(forced, [])  # Paul Reed isn't in this synthetic Yahoo set

    def test_rui_hachimura_cap0_or121_makes_the_pool_when_available(self):
        # Exact over-dynasty failure being corrected: a current Yahoo-ranked
        # $0 rotation player must beat a field of deep dynasty prospects.
        rows = [_yahoo_row("Rui Hachimura", 121)]
        rows += [_yahoo_row(f"Deep Prospect {i}", 230 + i) for i in range(70)]
        dynasty = {pool.normalize_name(f"Deep Prospect {i}"): {"rank": 1 + i} for i in range(70)}
        cands = pool.build_candidates(EMPTY_BOARD, _yahoo_map(*rows), dynasty, 400)
        ranked = pool.sort_and_truncate(cands)
        self.assertEqual(ranked[0].name, "Rui Hachimura")


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
