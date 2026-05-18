"""Tests for T2.6 MMR diversity re-ranking (mmr.py + _apply_mmr in recommend.py)."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.mmr import mmr_rerank


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sim_by_director(a, b) -> float:
    """1.0 if directors share any name, 0.0 otherwise."""
    a_dirs = set(a.get("directors", []))
    b_dirs = set(b.get("directors", []))
    return 1.0 if a_dirs & b_dirs else 0.0


def _items(count: int, directors: list[str | None] | None = None) -> list[dict]:
    """Produce simple dicts with a 'directors' key so _sim_by_director works."""
    result = []
    for i in range(count):
        d = directors[i] if directors else f"Dir{i}"
        result.append({"id": i, "directors": [d] if d else []})
    return result


# ---------------------------------------------------------------------------
# mmr_rerank — core algorithm
# ---------------------------------------------------------------------------

class TestMmrRerank:
    def test_empty_input(self):
        assert mmr_rerank([], [], _sim_by_director) == []

    def test_single_item(self):
        items = _items(1)
        assert mmr_rerank(items, [1.0], _sim_by_director) == [0]

    def test_returns_all_indices(self):
        n = 6
        items = _items(n)
        scores = list(range(n, 0, -1))
        order = mmr_rerank(items, scores, _sim_by_director)
        assert sorted(order) == list(range(n))

    def test_lambda_1_preserves_original_order(self):
        """lambda_=1.0 is pure relevance — identical to original order."""
        n = 5
        items = _items(n)
        scores = [5.0, 4.0, 3.0, 2.0, 1.0]
        order = mmr_rerank(items, scores, _sim_by_director, lambda_=1.0)
        assert order == list(range(n))

    def test_diversity_breaks_same_director_cluster(self):
        """Top-N from same director should be split when lambda < 1."""
        # 6 items: first 4 share director "Nolan", last 2 are unique.
        directors = ["Nolan", "Nolan", "Nolan", "Nolan", "Villeneuve", "Tarkovsky"]
        items = [{"id": i, "directors": [directors[i]]} for i in range(6)]
        scores = [6.0, 5.0, 4.0, 3.0, 2.0, 1.0]

        # With lambda=1.0, top-3 are indices 0,1,2 (all Nolan).
        order_pure = mmr_rerank(items, scores, _sim_by_director, lambda_=1.0)
        nolan_in_top3_pure = sum(1 for i in order_pure[:3] if directors[i] == "Nolan")

        # With lambda=0.5, MMR should push non-Nolan titles into the top-3.
        order_mmr = mmr_rerank(items, scores, _sim_by_director, lambda_=0.5)
        nolan_in_top3_mmr = sum(1 for i in order_mmr[:3] if directors[i] == "Nolan")

        assert nolan_in_top3_pure == 3
        assert nolan_in_top3_mmr < 3, "MMR should reduce same-director pileup in top-3"

    def test_pool_size_caps_mmr_window(self):
        """Items beyond pool_size are appended in original order after the MMR window."""
        n = 6
        items = _items(n, directors=["A", "A", "A", "B", "B", "B"])
        scores = [6.0, 5.0, 4.0, 3.0, 2.0, 1.0]
        order = mmr_rerank(items, scores, _sim_by_director, lambda_=0.5, pool_size=3)
        # Items 3, 4, 5 must appear at the end in their original relative order.
        tail = order[3:]
        assert tail == [3, 4, 5]

    def test_equal_scores_does_not_crash(self):
        """Flat scores (all same value) should not cause division-by-zero."""
        items = _items(4)
        order = mmr_rerank(items, [1.0, 1.0, 1.0, 1.0], _sim_by_director)
        assert sorted(order) == [0, 1, 2, 3]

    def test_zero_similarity_preserves_relevance_order(self):
        """When all pairs are dissimilar, MMR reduces to relevance-only."""
        items = _items(4, directors=["A", "B", "C", "D"])
        scores = [4.0, 3.0, 2.0, 1.0]
        order = mmr_rerank(items, scores, _sim_by_director, lambda_=0.5)
        # Since sim is always 0, the MMR term λ*rel - (1-λ)*0 = λ*rel → relevance order.
        assert order[0] == 0

    def test_perfect_similarity_promotes_diverse_item(self):
        """When all items are clones, the second pick should still differ from first."""
        items = _items(3, directors=["Same", "Same", "Other"])
        scores = [3.0, 2.0, 1.0]
        order = mmr_rerank(items, scores, _sim_by_director, lambda_=0.5)
        # After picking index 0 (highest score), next pick should be index 2 (diverse)
        # rather than index 1 (same director clone).
        assert order[1] == 2

    def test_accepts_callable_similarity(self):
        """Ensure any callable works, not just dicts — tests the generic type."""
        # Use string items with a simple equality-based sim.
        items = ["apple", "apple", "banana"]
        scores = [3.0, 2.0, 1.0]
        sim = lambda a, b: 1.0 if a == b else 0.0  # noqa: E731
        order = mmr_rerank(items, scores, sim, lambda_=0.5)
        assert sorted(order) == [0, 1, 2]
        # "banana" should be bumped ahead of the second "apple"
        assert order[1] == 2


# ---------------------------------------------------------------------------
# _apply_mmr integration with recommend.py
# ---------------------------------------------------------------------------

class TestApplyMmr:
    """Tests for the _apply_mmr wrapper in recommend.py."""

    def _make_scored(self, n: int, directors: list[str | None] | None = None):
        from app.models.schemas import CandidateTitle, FeatureVector
        from app.services.features import ALL_GENRES

        scored = []
        for i in range(n):
            d = directors[i] if directors else f"Dir{i}"
            cand = CandidateTitle(
                imdb_id=f"tt{i:07d}",
                title=f"Movie {i}",
                original_title=f"Movie {i}",
                title_type="movie",
                imdb_rating=8.0 - i * 0.1,
                year=2020,
                genres=["Drama"],
                num_votes=100_000,
                runtime_mins=120,
                language="English",
                country_code="US",
                directors=[d] if d else [],
                actors=[],
            )
            fv = FeatureVector(
                title=cand.title,
                title_type="movie",
                imdb_rating=cand.imdb_rating,
                runtime_mins=120.0,
                year=2020,
                num_votes=100_000,
                genre_flags={f"genre_{g.lower().replace('-', '_')}": 0 for g in ALL_GENRES},
                decade=2020,
                rating_vote_ratio=0.5,
                is_anime=False,
                director_taste_score=0.0,
                has_known_director=False,
                actor_taste_score=0.0,
                has_known_actor=False,
            )
            scored.append((cand, fv, float(n - i)))
        return scored

    def test_disabled_returns_unchanged(self):
        from app.services.recommend import _apply_mmr
        from app.core.config import MMRConfig

        scored = self._make_scored(5)
        mock_cfg = MMRConfig(enabled=False, lambda_=0.7, pool_size=200)
        with patch("app.services.recommend.get_settings") as mock_settings:
            mock_settings.return_value.mmr = mock_cfg
            result = _apply_mmr(scored)
        assert result is scored

    def test_enabled_returns_same_length(self):
        from app.services.recommend import _apply_mmr
        from app.core.config import MMRConfig

        scored = self._make_scored(8)
        mock_cfg = MMRConfig(enabled=True, lambda_=0.7, pool_size=200)
        with patch("app.services.recommend.get_settings") as mock_settings:
            mock_settings.return_value.mmr = mock_cfg
            result = _apply_mmr(scored)
        assert len(result) == len(scored)

    def test_fewer_than_3_items_unchanged(self):
        from app.services.recommend import _apply_mmr
        from app.core.config import MMRConfig

        scored = self._make_scored(2)
        mock_cfg = MMRConfig(enabled=True, lambda_=0.5, pool_size=200)
        with patch("app.services.recommend.get_settings") as mock_settings:
            mock_settings.return_value.mmr = mock_cfg
            result = _apply_mmr(scored)
        assert result is scored

    def test_acceptance_fewer_same_director_runs_in_top_n(self):
        """Acceptance: mmr.enabled=true produces fewer same-director runs than disabled."""
        from app.services.recommend import _apply_mmr
        from app.core.config import MMRConfig

        # 10 items: first 6 share director "Nolan", last 4 are diverse
        directors = ["Nolan"] * 6 + ["Villeneuve", "Kubrick", "Tarkovsky", "Lynch"]
        scored = self._make_scored(10, directors=directors)

        def _nolan_runs(result):
            """Count consecutive Nolan pairs in top-6."""
            runs = 0
            for i in range(min(5, len(result) - 1)):
                d_i = result[i][0].directors[0] if result[i][0].directors else ""
                d_j = result[i + 1][0].directors[0] if result[i + 1][0].directors else ""
                if d_i == d_j == "Nolan":
                    runs += 1
            return runs

        disabled_cfg = MMRConfig(enabled=False, lambda_=0.7, pool_size=200)
        enabled_cfg = MMRConfig(enabled=True, lambda_=0.5, pool_size=200)

        with patch("app.services.recommend.get_settings") as ms:
            ms.return_value.mmr = disabled_cfg
            no_mmr = _apply_mmr(scored)

        with patch("app.services.recommend.get_settings") as ms:
            ms.return_value.mmr = enabled_cfg
            with_mmr = _apply_mmr(scored)

        runs_without = _nolan_runs(no_mmr)
        runs_with = _nolan_runs(with_mmr)
        assert runs_with < runs_without, (
            f"MMR should reduce same-director runs: got {runs_with} (MMR) vs {runs_without} (no MMR)"
        )
