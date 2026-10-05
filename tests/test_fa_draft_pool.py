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

    def test_established_current_value_players_survive(self):
        for name in ("Rui Hachimura", "Paul Reed", "Tari Eason", "Tobias Harris"):
            self.assertIn(name, self.names, f"{name} must not be crowded out by dynasty prospects")

    def test_page_three_keeps_pinned_names_and_drops_replaced_veterans(self):
        tail = self.names[40:]
        for kept in ("Grayson Allen", "Julian Champagnie", "Scotty Pippen Jr.", "Jake LaRavia", "Jared McCain", "Bilal Coulibaly"):
            self.assertIn(kept, tail)
        for gone in ("De&#x27;Andre Hunter", "Bobby Portis Jr.", "Robert Williams III", "Anfernee Simons",
                     "Nikola Vučević", "Brook Lopez", "Naji Marshall", "Jordan Poole", "Dennis Schröder"):
            self.assertNotIn(gone, self.names)

    def test_young_dynasty_players_beyond_yahoo_reach_the_board(self):
        # Hannes Steinbach / Dailyn Swain: no Yahoo O-Rank, strong consensus rank.
        for name in ("Hannes Steinbach", "Dailyn Swain"):
            self.assertIn(name, self.names)

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


class TestHybridWithinCapTier(unittest.TestCase):
    """Product rule: CAP desc is absolute; inside a CAP tier a 65% Yahoo /
    35% dynasty-consensus hybrid of normalized percentile scores decides
    order; the candidate universe is built from cuts + Yahoo + the project
    dynasty consensus + approved prospects BEFORE ranking."""

    def _cand(self, name, o_rank=pool.MISSING_OR, dynasty_rank=None, cap=0.0):
        return pool.Candidate(
            name=name, pos="SF", nba="XXX", cap=cap, o_rank=o_rank,
            dynasty_rank=dynasty_rank, yahoo_rank_max=300, dynasty_rank_max=500,
        )

    # --- weights / scores -------------------------------------------------
    def test_weights_are_65_35_and_yahoo_is_the_larger_component(self):
        self.assertAlmostEqual(pool.YAHOO_WEIGHT, 0.65)
        self.assertAlmostEqual(pool.DYNASTY_WEIGHT, 0.35)
        self.assertGreater(pool.YAHOO_WEIGHT, pool.DYNASTY_WEIGHT)

    def test_blend_uses_normalized_percentiles_of_each_list(self):
        c = self._cand("X", o_rank=60, dynasty_rank=100)  # 0.2 yahoo pct, 0.2 dynasty pct
        self.assertAlmostEqual(c.relevance_score(), 0.65 * (60 / 300) + 0.35 * (100 / 500))

    def test_yahoo_remains_dominant_where_both_signals_exist(self):
        # Same total rank distance, opposite sources: the better YAHOO rank wins.
        yahoo_strong = self._cand("YahooStrong", o_rank=50, dynasty_rank=250)
        dynasty_strong = self._cand("DynastyStrong", o_rank=250, dynasty_rank=50 * 500 // 300)
        self.assertLess(yahoo_strong.relevance_score(), dynasty_strong.relevance_score())

    def test_dynasty_signal_materially_moves_a_young_player_ahead_of_a_veteran(self):
        vet = self._cand("Vet", o_rank=165, dynasty_rank=450)  # replaceable veteran
        young = self._cand("Young", o_rank=210, dynasty_rank=40)  # elite dynasty asset, weak current OR
        ranked = pool.sort_and_truncate({"a": vet, "b": young})
        self.assertEqual([c.name for c in ranked], ["Young", "Vet"])

    def test_dynasty_does_not_automatically_push_speculative_rookies_over_established_players(self):
        useful = self._cand("Useful", o_rank=121, dynasty_rank=218 * 500 // 541)
        speculative = self._cand("Speculative", o_rank=240, dynasty_rank=200)
        ranked = pool.sort_and_truncate({"a": speculative, "b": useful})
        self.assertEqual([c.name for c in ranked], ["Useful", "Speculative"])

    # --- Yahoo-missing ----------------------------------------------------
    def test_missing_yahoo_carries_the_documented_penalty(self):
        c = self._cand("NoYahoo", dynasty_rank=50)
        self.assertEqual(c.yahoo_score(), pool.MISSING_YAHOO_SCORE)
        self.assertAlmostEqual(c.relevance_score(), 0.65 * pool.MISSING_YAHOO_SCORE + 0.35 * (50 / 500))

    def test_dynasty_only_player_does_not_outrank_a_credible_yahoo_rotation_player(self):
        rotation = self._cand("Rotation", o_rank=140, dynasty_rank=250)
        elite_but_unranked = self._cand("EliteNoYahoo", dynasty_rank=60)
        self.assertLess(rotation.relevance_score(), elite_but_unranked.relevance_score())

    def test_elite_dynasty_only_player_beats_deep_yahoo_only_names_and_can_make_the_cut(self):
        elite = self._cand("EliteNoYahoo", dynasty_rank=10)
        deep = [self._cand(f"Deep{i}", o_rank=230 + i) for i in range(59)]
        ranked = pool.sort_and_truncate({c.name: c for c in deep + [elite]})
        self.assertIn("EliteNoYahoo", [c.name for c in ranked])

    def test_absent_from_dynasty_board_is_worst_case_on_that_axis(self):
        self.assertEqual(self._cand("X", o_rank=100).dynasty_score(), 1.0)

    def test_cap_is_absolute_primary_even_for_elite_dynasty(self):
        paid = self._cand("Paid", o_rank=290, cap=1)
        elite = self._cand("Elite", o_rank=5, dynasty_rank=1, cap=0)
        ranked = pool.sort_and_truncate({"a": elite, "b": paid})
        self.assertEqual([c.name for c in ranked], ["Paid", "Elite"])

    # --- candidate universe ----------------------------------------------
    def test_yahoo_listed_rookie_uses_actual_yahoo_or(self):
        yahoo = _yahoo_map(_yahoo_row("Cameron Boozer", 51, cap=20, pos="PF"))
        cands = pool.build_candidates(EMPTY_BOARD, yahoo, {pool.normalize_name("Cameron Boozer"): {"rank": 1}}, 400)
        boozer = cands[pool.normalize_name("Cameron Boozer")]
        self.assertEqual(boozer.o_rank, 51)
        self.assertTrue(boozer.rookie)

    def test_dynasty_consensus_players_outside_yahoo_enter_the_universe(self):
        dyn = {pool.normalize_name("Young Breakout"): {"rank": 120, "pos": "SG", "team": "SA", "name": "Young Breakout"},
               pool.normalize_name("Deep Nobody"): {"rank": 400, "pos": "SG", "team": "SA", "name": "Deep Nobody"}}
        cands = pool.build_candidates(EMPTY_BOARD, _yahoo_map(_yahoo_row("Some Vet", 130)), dyn, 541)
        self.assertIn(pool.normalize_name("Young Breakout"), cands)
        self.assertNotIn(pool.normalize_name("Deep Nobody"), cands)  # beyond DYNASTY_CANDIDATE_CUTOFF
        yb = cands[pool.normalize_name("Young Breakout")]
        self.assertEqual((yb.pos, yb.nba, yb.cap, yb.o_rank), ("SG", "SAS", 0.0, pool.MISSING_OR))

    def test_kept_players_never_enter_the_universe_from_any_source(self):
        board = ('<section class="team-card"><span class="identity-tag">ZZ</span><div class="players">'
                 '<div class="player-row"><div class="pos">SG</div><div class="pname">Kept Young</div>'
                 '<div class="nba">AAA</div><div class="cap">3</div></div></div></section>')
        dyn = {pool.normalize_name("Kept Young"): {"rank": 20, "pos": "SG", "team": "AAA", "name": "Kept Young"}}
        cands = pool.build_candidates(board, _yahoo_map(_yahoo_row("Kept Young", 50, cap=3)), dyn, 541)
        self.assertNotIn(pool.normalize_name("Kept Young"), cands)

    def test_cuts_enter_the_universe_with_the_cutting_team_as_source(self):
        board = ('<section class="team-card"><span class="identity-tag">TT</span><div class="players"></div>'
                 '<footer class="cuts"><div class="cuts-label">CUTS</div><div class="cuts-list">'
                 '<span class="cut-chip">Cut Guy <strong>2</strong></span></div></footer></section>')
        cands = pool.build_candidates(board, _yahoo_map(_yahoo_row("Cut Guy", 113, cap=2)), {}, 541)
        cut = cands[pool.normalize_name("Cut Guy")]
        self.assertEqual((cut.src, cut.src_team, cut.cap), ("cut", "TT", 2.0))

    def test_rookie_flag_comes_from_the_project_rookie_source(self):
        dyn = {pool.normalize_name("Source Rookie"): {"rank": 90, "pos": "PF", "team": "CHI", "name": "Source Rookie"}}
        cands = pool.build_candidates(EMPTY_BOARD, _yahoo_map(_yahoo_row("Some Vet", 130)), dyn, 541,
                                      rookie_names={pool.normalize_name("Source Rookie")})
        self.assertTrue(cands[pool.normalize_name("Source Rookie")].rookie)

    def test_curated_prospects_enter_but_are_never_force_included(self):
        cands = pool.build_candidates(EMPTY_BOARD, _yahoo_map(_yahoo_row("Some Vet", 130)), {}, 541)
        self.assertIn(pool.normalize_name("Kingston Flemings"), cands)
        self.assertEqual([c.name for c in cands.values() if c.guaranteed], [])

    def test_rui_hachimura_cap0_or121_makes_the_pool_when_available(self):
        rows = [_yahoo_row("Rui Hachimura", 121)]
        rows += [_yahoo_row(f"Deep Prospect {i}", 230 + i) for i in range(70)]
        dynasty = {pool.normalize_name(f"Deep Prospect {i}"): {"rank": 60 + i} for i in range(70)}
        dynasty[pool.normalize_name("Rui Hachimura")] = {"rank": 218}
        cands = pool.build_candidates(EMPTY_BOARD, _yahoo_map(*rows), dynasty, 541)
        ranked = pool.sort_and_truncate(cands)
        self.assertIn("Rui Hachimura", [c.name for c in ranked])

    def test_paul_reed_is_guaranteed(self):
        rows = [_yahoo_row("Paul Reed", 165)] + [_yahoo_row(f"Better {i}", 100 + i) for i in range(80)]
        cands = pool.build_candidates(EMPTY_BOARD, _yahoo_map(*rows), {}, 541)
        self.assertIn("Paul Reed", [c.name for c in pool.sort_and_truncate(cands)])


class TestPageThreeYoungTail(unittest.TestCase):
    """Rows 1-40 are the plain ranking; rows 41-60 hold owner-pinned depth
    names, then the best rookies / sophomores / 3rd-years by hybrid score."""

    def _c(self, name, o_rank, dyn=None, young=False, pinned=False, cap=0.0):
        return pool.Candidate(name=name, pos="SF", nba="XXX", cap=cap, o_rank=o_rank, dynasty_rank=dyn,
                              yahoo_rank_max=300, dynasty_rank_max=500, young=young, pinned=pinned)

    def _universe(self):
        c = {}
        for i in range(40):  # strong core, mixed vets
            x = self._c(f"Core{i}", 100 + i, 150 + i)
            c[x.name] = x
        for i in range(15):  # replaceable vets right behind the core
            x = self._c(f"Vet{i}", 141 + i, 190 + i)
            c[x.name] = x
        x = self._c("PinnedVet", 190, 300, pinned=True); c[x.name] = x
        for i in range(25):  # weaker young players
            x = self._c(f"Young{i}", 230 + i, 100 + 5 * i, young=True); c[x.name] = x
        return c

    def test_core_is_untouched_and_total_is_sixty(self):
        c = self._universe()
        plain = sorted(c.values(), key=lambda x: x.sort_key())[:pool.CORE_SIZE]
        ranked = pool.sort_and_truncate(c)
        self.assertEqual(len(ranked), 60)
        self.assertEqual([x.name for x in ranked[:pool.CORE_SIZE]], [x.name for x in plain])

    def test_tail_is_pinned_then_young_and_replaceable_vets_are_dropped(self):
        ranked = pool.sort_and_truncate(self._universe())
        tail = [x.name for x in ranked[pool.CORE_SIZE:]]
        self.assertIn("PinnedVet", tail)
        self.assertFalse([n for n in tail if n.startswith("Vet")])
        self.assertEqual(len([n for n in tail if n.startswith("Young")]), 19)

    def test_best_young_by_hybrid_score_get_the_slots_no_quota(self):
        ranked = pool.sort_and_truncate(self._universe())
        young = [x.name for x in ranked if x.name.startswith("Young")]
        self.assertEqual(young, [f"Young{i}" for i in range(19)])  # best 19 by score, not an arbitrary 19

    def test_not_enough_young_candidates_falls_back_to_plain_order(self):
        c = {f"P{i}": self._c(f"P{i}", 100 + i) for i in range(70)}
        ranked = pool.sort_and_truncate(c)
        self.assertEqual([x.name for x in ranked], [f"P{i}" for i in range(60)])

    def test_cap_still_monotonic_with_the_tail(self):
        c = self._universe()
        c["PaidYoung"] = self._c("PaidYoung", 280, 450, young=True, cap=1)
        caps = [x.cap for x in pool.sort_and_truncate(c)]
        self.assertEqual(caps, sorted(caps, reverse=True))

    def test_pinned_names_are_the_owner_approved_six(self):
        self.assertEqual(pool.TAIL_PINNED_NAMES, {"Grayson Allen", "Julian Champagnie", "Scotty Pippen Jr.",
                                                  "Jake LaRavia", "Jared McCain", "Bilal Coulibaly"})

    def test_draft_class_table_marks_sophomores_and_third_years_but_not_older_players(self):
        years = pool.load_draft_years()
        self.assertEqual(years[pool.normalize_name("Tre Johnson")], 2025)
        self.assertEqual(years[pool.normalize_name("Isaiah Collier")], 2024)
        for old in ("Dereck Lively II", "Bilal Coulibaly", "Grayson Allen", "Tobias Harris"):
            self.assertNotIn(pool.normalize_name(old), years)

    def test_build_candidates_flags_young_and_pinned(self):
        yahoo = _yahoo_map(_yahoo_row("Tre Johnson", 220), _yahoo_row("Grayson Allen", 187), _yahoo_row("Old Vet", 170))
        cands = pool.build_candidates(EMPTY_BOARD, yahoo, {}, 541, draft_years={pool.normalize_name("Tre Johnson"): 2025})
        self.assertTrue(cands[pool.normalize_name("Tre Johnson")].young)
        self.assertFalse(cands[pool.normalize_name("Old Vet")].young)
        self.assertTrue(cands[pool.normalize_name("Grayson Allen")].pinned)


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
