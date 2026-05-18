"""Sanity tests for the ranking metrics used by training + the eval harness."""

import math

import pytest

from app.services.eval_metrics import (
    average_precision_at_k,
    catalog_coverage,
    diversity,
    mrr,
    ndcg_at_k,
    ndcg_at_k_from_scores,
    novelty,
    recall_at_k,
    spearman_corr,
)


class TestNdcg:
    def test_perfect_ranking_is_one(self):
        # Already sorted descending → ideal == actual
        assert ndcg_at_k([10, 8, 5, 3, 1], k=5) == pytest.approx(1.0)

    def test_reverse_ranking_below_one(self):
        ascending = [1, 3, 5, 8, 10]
        score = ndcg_at_k(ascending, k=5)
        assert 0.0 < score < 1.0

    def test_empty_list_is_zero(self):
        assert ndcg_at_k([], k=10) == 0.0

    def test_all_zero_relevance_is_zero(self):
        assert ndcg_at_k([0, 0, 0], k=3) == 0.0

    def test_from_scores_aligns_with_pred_order(self):
        # Predicted order: idx 1, 0, 2. True relevance read in that order:
        # [5, 9, 1]. The descending sort of those gives ideal = [9,5,1].
        y_true = [9, 5, 1]
        y_pred = [0.2, 0.9, 0.1]
        assert 0.0 < ndcg_at_k_from_scores(y_true, y_pred, k=3) < 1.0


class TestAveragePrecision:
    def test_all_relevant_in_top_k(self):
        ap = average_precision_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3)
        assert ap == pytest.approx(1.0)

    def test_none_relevant(self):
        ap = average_precision_at_k(["a", "b", "c"], {"x"}, k=3)
        assert ap == 0.0

    def test_one_at_top(self):
        ap = average_precision_at_k(["a", "b", "c"], {"a"}, k=3)
        # min(1, 3) denom; first hit at position 1 → AP = 1/1 / 1 = 1.0
        assert ap == pytest.approx(1.0)

    def test_one_at_bottom(self):
        ap = average_precision_at_k(["x", "y", "a"], {"a"}, k=3)
        # hit at position 3 → P = 1/3
        assert ap == pytest.approx(1.0 / 3)


class TestRecallAtK:
    def test_perfect_recall(self):
        assert recall_at_k(["a", "b"], {"a", "b"}, k=2) == 1.0

    def test_partial_recall(self):
        assert recall_at_k(["a", "x"], {"a", "b"}, k=2) == 0.5

    def test_no_relevant(self):
        assert recall_at_k(["a", "b"], set(), k=2) == 0.0


class TestMRR:
    def test_first_position(self):
        assert mrr(["a", "b", "c"], {"a"}) == 1.0

    def test_third_position(self):
        assert mrr(["x", "y", "a"], {"a"}) == pytest.approx(1.0 / 3)

    def test_none_relevant(self):
        assert mrr(["x", "y"], {"a"}) == 0.0


class TestSpearman:
    def test_perfect_positive(self):
        assert spearman_corr([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)

    def test_perfect_negative(self):
        assert spearman_corr([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)

    def test_zero_variance(self):
        # All predictions equal → no variance → return 0.0
        assert spearman_corr([1, 2, 3], [5, 5, 5]) == 0.0


class TestCoverage:
    def test_full_coverage(self):
        assert catalog_coverage([["a", "b", "c"]], total_catalog_size=3) == 1.0

    def test_half_coverage(self):
        assert catalog_coverage([["a"]], total_catalog_size=2) == 0.5

    def test_empty_catalog(self):
        assert catalog_coverage([["a"]], total_catalog_size=0) == 0.0


class TestDiversity:
    def test_identical_items_diversity_zero(self):
        # Similarity always 1.0 → dissimilarity 0
        assert diversity(["a", "b", "c"], lambda x, y: 1.0) == 0.0

    def test_orthogonal_items_diversity_one(self):
        assert diversity(["a", "b", "c"], lambda x, y: 0.0) == 1.0

    def test_singleton_diversity_zero(self):
        assert diversity(["a"], lambda x, y: 0.0) == 0.0


class TestNovelty:
    def test_unpopular_high_novelty(self):
        nov = novelty(["a"], {"a": 1 / 16})
        # -log2(1/16) = 4
        assert nov == pytest.approx(4.0)

    def test_popular_low_novelty(self):
        nov = novelty(["a"], {"a": 1.0})
        # -log2(1) = 0
        assert nov == pytest.approx(0.0)

    def test_missing_item_skipped(self):
        # Empty popularity map → no items count → 0
        assert novelty(["a"], {}) == 0.0

    def test_zero_popularity_skipped(self):
        # popularity 0 would be -log2(0) = inf; we skip
        nov = novelty(["a", "b"], {"a": 0.0, "b": 0.5})
        assert math.isfinite(nov)
