"""Tests for T2.7 tree-leaf-index similarity (leaf_similarity.py + predict_leaf_indices)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.leaf_similarity import (
    find_similar_by_leaves,
    pairwise_similarity_by_id,
    similarity_by_leaves,
)


# ---------------------------------------------------------------------------
# similarity_by_leaves — core math
# ---------------------------------------------------------------------------

class TestSimilarityByLeaves:
    def test_identical_rows(self):
        seed = np.array([1, 2, 3, 4], dtype=np.int32)
        cands = np.array([[1, 2, 3, 4]], dtype=np.int32)
        result = similarity_by_leaves(seed, cands)
        assert result.shape == (1,)
        np.testing.assert_allclose(result, [1.0])

    def test_no_match(self):
        seed = np.array([1, 2, 3, 4], dtype=np.int32)
        cands = np.array([[5, 6, 7, 8]], dtype=np.int32)
        result = similarity_by_leaves(seed, cands)
        np.testing.assert_allclose(result, [0.0])

    def test_partial_match(self):
        seed = np.array([1, 2, 3, 4], dtype=np.int32)
        cands = np.array([[1, 2, 0, 0]], dtype=np.int32)
        result = similarity_by_leaves(seed, cands)
        np.testing.assert_allclose(result, [0.5])

    def test_multiple_candidates(self):
        seed = np.array([1, 2, 3, 4], dtype=np.int32)
        cands = np.array([
            [1, 2, 3, 4],   # 100%
            [1, 2, 0, 0],   # 50%
            [0, 0, 0, 0],   # 0%
        ], dtype=np.int32)
        result = similarity_by_leaves(seed, cands)
        assert result.shape == (3,)
        np.testing.assert_allclose(result, [1.0, 0.5, 0.0])

    def test_returns_values_in_0_1(self):
        rng = np.random.default_rng(42)
        seed = rng.integers(0, 100, size=50).astype(np.int32)
        cands = rng.integers(0, 100, size=(20, 50)).astype(np.int32)
        result = similarity_by_leaves(seed, cands)
        assert np.all(result >= 0.0)
        assert np.all(result <= 1.0)

    def test_empty_candidates(self):
        seed = np.array([1, 2, 3], dtype=np.int32)
        cands = np.empty((0, 3), dtype=np.int32)
        result = similarity_by_leaves(seed, cands)
        assert result.shape == (0,)

    def test_shape_preserved(self):
        seed = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        cands = np.arange(50, dtype=np.int32).reshape(10, 5)
        result = similarity_by_leaves(seed, cands)
        assert result.shape == (10,)


# ---------------------------------------------------------------------------
# find_similar_by_leaves — integration with cache
# ---------------------------------------------------------------------------

def _make_fake_cache(n: int = 5, n_trees: int = 4) -> dict:
    rng = np.random.default_rng(7)
    ids = np.array([f"tt{i:07d}" for i in range(n)], dtype=object)
    leaves = rng.integers(0, 10, size=(n, n_trees)).astype(np.int32)
    # Make tt0000000 identical to tt0000001 for predictable test
    leaves[1] = leaves[0].copy()
    return {"ids": ids, "leaves": leaves}


class TestFindSimilarByLeaves:
    def test_returns_none_when_no_cache(self):
        with patch("app.services.leaf_similarity._get_cache", return_value=None):
            result = find_similar_by_leaves("tt0000000")
        assert result is None

    def test_returns_none_when_seed_not_in_cache(self):
        cache = _make_fake_cache()
        with patch("app.services.leaf_similarity._get_cache", return_value=cache):
            result = find_similar_by_leaves("tt9999999")
        assert result is None

    def test_returns_list_of_tuples(self):
        cache = _make_fake_cache()
        with patch("app.services.leaf_similarity._get_cache", return_value=cache):
            result = find_similar_by_leaves("tt0000000", top_n=3)
        assert result is not None
        assert all(isinstance(imdb_id, str) and isinstance(sim, float) for imdb_id, sim in result)

    def test_self_excluded(self):
        cache = _make_fake_cache()
        with patch("app.services.leaf_similarity._get_cache", return_value=cache):
            result = find_similar_by_leaves("tt0000000", top_n=10)
        ids = [imdb_id for imdb_id, _ in result]
        assert "tt0000000" not in ids

    def test_identical_row_ranked_first(self):
        """tt0000001 is a clone of tt0000000, so should be top hit."""
        cache = _make_fake_cache()
        with patch("app.services.leaf_similarity._get_cache", return_value=cache):
            result = find_similar_by_leaves("tt0000000", top_n=10)
        assert result is not None
        top_id, top_sim = result[0]
        assert top_id == "tt0000001"
        assert top_sim == pytest.approx(1.0)

    def test_scores_descending(self):
        cache = _make_fake_cache(n=10, n_trees=20)
        with patch("app.services.leaf_similarity._get_cache", return_value=cache):
            result = find_similar_by_leaves("tt0000000", top_n=9)
        sims = [s for _, s in result]
        assert sims == sorted(sims, reverse=True)

    def test_top_n_respected(self):
        cache = _make_fake_cache(n=10)
        with patch("app.services.leaf_similarity._get_cache", return_value=cache):
            result = find_similar_by_leaves("tt0000000", top_n=3)
        assert len(result) <= 3

    def test_all_non_negative_scores(self):
        cache = _make_fake_cache(n=8, n_trees=10)
        with patch("app.services.leaf_similarity._get_cache", return_value=cache):
            result = find_similar_by_leaves("tt0000000", top_n=7)
        assert all(s >= 0.0 for _, s in result)


# ---------------------------------------------------------------------------
# pairwise_similarity_by_id
# ---------------------------------------------------------------------------

class TestPairwiseSimilarityById:
    def test_no_cache_returns_zero(self):
        with patch("app.services.leaf_similarity._get_cache", return_value=None):
            sim = pairwise_similarity_by_id("tt0000000", "tt0000001")
        assert sim == 0.0

    def test_unknown_id_returns_zero(self):
        cache = _make_fake_cache()
        with patch("app.services.leaf_similarity._get_cache", return_value=cache):
            sim = pairwise_similarity_by_id("tt9999998", "tt9999999")
        assert sim == 0.0

    def test_identical_rows_return_1(self):
        cache = _make_fake_cache()
        with patch("app.services.leaf_similarity._get_cache", return_value=cache):
            sim = pairwise_similarity_by_id("tt0000000", "tt0000001")
        assert sim == pytest.approx(1.0)

    def test_value_in_0_1(self):
        cache = _make_fake_cache(n=5, n_trees=8)
        with patch("app.services.leaf_similarity._get_cache", return_value=cache):
            sim = pairwise_similarity_by_id("tt0000000", "tt0000002")
        assert 0.0 <= sim <= 1.0


# ---------------------------------------------------------------------------
# predict_leaf_indices — model.py integration
# ---------------------------------------------------------------------------

class TestPredictLeafIndices:
    def test_empty_features_returns_empty_array(self):
        from app.services.model import predict_leaf_indices

        mock_model = MagicMock()
        result = predict_leaf_indices(mock_model, ["f1", "f2"], [])
        assert result.shape == (0, 0)
        mock_model.predict.assert_not_called()

    def test_shape_matches_n_candidates_x_n_trees(self):
        from app.services.features import ALL_GENRES
        from app.models.schemas import FeatureVector
        from app.services.model import predict_leaf_indices

        def _make_fv():
            return FeatureVector(
                title="T",
                title_type="movie",
                imdb_rating=7.0,
                runtime_mins=100.0,
                year=2020,
                num_votes=10_000,
                genre_flags={f"genre_{g.lower().replace('-', '_')}": 0 for g in ALL_GENRES},
                decade=2020,
                rating_vote_ratio=0.5,
                is_anime=False,
                director_taste_score=0.0,
                has_known_director=False,
                actor_taste_score=0.0,
                has_known_actor=False,
            )

        n_candidates = 3
        n_trees = 5
        features = [_make_fv() for _ in range(n_candidates)]

        mock_model = MagicMock()
        mock_model.predict.return_value = np.zeros((n_candidates, n_trees), dtype=np.int32)

        result = predict_leaf_indices(mock_model, ["imdb_rating", "year"], features)
        assert result.shape == (n_candidates, n_trees)
        assert result.dtype == np.int32

    def test_pred_leaf_kwarg_passed_to_model(self):
        from app.models.schemas import FeatureVector
        from app.services.features import ALL_GENRES
        from app.services.model import predict_leaf_indices

        fv = FeatureVector(
            title="T",
            title_type="movie",
            imdb_rating=7.0,
            runtime_mins=100.0,
            year=2020,
            num_votes=10_000,
            genre_flags={f"genre_{g.lower().replace('-', '_')}": 0 for g in ALL_GENRES},
            decade=2020,
            rating_vote_ratio=0.5,
            is_anime=False,
            director_taste_score=0.0,
            has_known_director=False,
            actor_taste_score=0.0,
            has_known_actor=False,
        )
        mock_model = MagicMock()
        mock_model.predict.return_value = np.array([[1, 2]], dtype=np.int32)

        predict_leaf_indices(mock_model, ["imdb_rating"], [fv])
        _, kwargs = mock_model.predict.call_args
        assert kwargs.get("pred_leaf") is True
