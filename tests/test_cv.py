"""Tests for T2.9 k-fold cross-validation (model.py).

Covers:
- _expanding_window_folds: fold structure, monotonic train growth, edge cases
- _cross_validate: temporal + random strategies, key names, extra-row merging,
  failed-fold resilience
- cross_validate (public): full feature pipeline, decay toggle, strategy wiring,
  LOO fallback (<100 ratings), result shape
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from app.services.model import _cross_validate, _expanding_window_folds, cross_validate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rated_title(
    imdb_id: str = "tt0000001",
    user_rating: int = 7,
    date_rated: str = "2020-01-01",
):
    from app.models.schemas import RatedTitle

    return RatedTitle(
        imdb_id=imdb_id,
        title="Test Movie",
        original_title="Test Movie",
        title_type="movie",
        user_rating=user_rating,
        date_rated=date_rated,
        imdb_rating=7.0,
        runtime_mins=100,
        year=2020,
        genres=["Drama"],
        num_votes=50_000,
        release_date="2020-01-01",
        directors=["Director A"],
        url=f"https://www.imdb.com/title/{imdb_id}/",
    )


def _make_titles(n: int, base_year: int = 2010):
    """Return n RatedTitle objects with sequential date_rated and distinct imdb_ids."""
    return [
        _make_rated_title(
            imdb_id=f"tt{i:07d}",
            user_rating=max(1, min(10, 5 + (i % 5))),
            date_rated=f"{base_year + i // 12}-{(i % 12) + 1:02d}-01",
        )
        for i in range(n)
    ]


def _make_df(n: int, n_features: int = 4) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        rng.uniform(0, 10, size=(n, n_features)),
        columns=[f"f{i}" for i in range(n_features)],
    )


def _make_mock_model(constant: float = 5.0):
    m = MagicMock()
    m.predict.side_effect = lambda X: np.full(len(X), constant)
    return m


def _default_params() -> dict:
    return {
        "n_estimators": 50,
        "learning_rate": 0.1,
        "max_depth": 3,
        "num_leaves": 15,
        "min_child_samples": 2,
        "reg_alpha": 0.0,
        "reg_lambda": 0.0,
        "feature_fraction": 1.0,
        "bagging_fraction": 1.0,
        "bagging_freq": 0,
        "random_state": 42,
    }


def _mock_settings(decay_enabled: bool = False, objective: str = "regression"):
    from app.core.config import ModelConfig, ModelDecayConfig

    cfg = ModelConfig(
        objective=objective,
        ndcg_at_k=5,
        decay=ModelDecayConfig(enabled=decay_enabled),
    )
    mock = MagicMock()
    mock.model = cfg
    return mock


# ---------------------------------------------------------------------------
# _expanding_window_folds
# ---------------------------------------------------------------------------


class TestExpandingWindowFolds:
    def test_standard_case_returns_n_folds(self):
        folds = _expanding_window_folds(20, 4)
        assert len(folds) == 4

    def test_train_sets_monotonically_grow(self):
        folds = _expanding_window_folds(20, 4)
        train_lens = [len(tr) for tr, _ in folds]
        assert train_lens == sorted(train_lens)
        assert all(b > a for a, b in zip(train_lens, train_lens[1:]))

    def test_test_follows_train_no_overlap(self):
        folds = _expanding_window_folds(15, 3)
        for tr, te in folds:
            assert not set(tr) & set(te)
            if tr and te:
                assert max(tr) < min(te)

    def test_train_is_always_a_prefix(self):
        """Train indices are always [0, end_train) — no gaps."""
        folds = _expanding_window_folds(18, 3)
        for tr, _ in folds:
            assert tr == list(range(len(tr)))

    def test_single_item_returns_no_folds(self):
        assert _expanding_window_folds(1, 5) == []

    def test_zero_n_returns_empty(self):
        assert _expanding_window_folds(0, 5) == []

    def test_two_items_returns_at_least_one_fold(self):
        folds = _expanding_window_folds(2, 5)
        assert len(folds) >= 1

    def test_small_n_fewer_folds_than_requested(self):
        folds = _expanding_window_folds(4, 20)
        assert 0 < len(folds) <= 4

    def test_fold_test_sets_are_contiguous(self):
        folds = _expanding_window_folds(20, 4)
        for _, te in folds:
            assert te == list(range(te[0], te[-1] + 1))

    def test_last_test_does_not_exceed_n(self):
        n = 20
        folds = _expanding_window_folds(n, 4)
        _, last_te = folds[-1]
        assert last_te[-1] <= n - 1

    def test_small_n_produces_single_item_test_folds(self):
        """With n=6 and n_folds=5, fold_size=1 → each fold tests exactly 1 item."""
        folds = _expanding_window_folds(6, 5)
        test_sizes = [len(te) for _, te in folds]
        assert all(s == 1 for s in test_sizes)

    def test_large_n_folds_matches_n_folds(self):
        folds = _expanding_window_folds(100, 10)
        assert len(folds) == 10


# ---------------------------------------------------------------------------
# _cross_validate (internal)
# ---------------------------------------------------------------------------


class TestCrossValidateInternal:
    """Tests _cross_validate directly using pre-built DataFrames."""

    def _call(
        self,
        n: int = 20,
        n_folds: int = 3,
        strategy: str = "temporal",
        raise_on_fold: int | None = None,
        k: int = 5,
    ):
        X = _make_df(n)
        y = np.arange(n, dtype=float) + 1
        w = np.ones(n)
        titles = _make_titles(n)
        call_count = [0]

        def _fake_fit(Xtr, ytr, wtr, *, objective, params):
            call_count[0] += 1
            if raise_on_fold is not None and call_count[0] == raise_on_fold:
                raise RuntimeError("Simulated fold failure")
            return _make_mock_model()

        with patch("app.services.model._fit_estimator", side_effect=_fake_fit):
            result = _cross_validate(
                X_all=X,
                y_all=y,
                w_all=w,
                X_extra=pd.DataFrame(columns=X.columns),
                y_extra=np.array([], dtype=float),
                w_extra=np.array([], dtype=float),
                titles=titles,
                objective="regression",
                params=_default_params(),
                n_folds=n_folds,
                strategy=strategy,
                k=k,
            )
        return result, call_count[0]

    def test_temporal_returns_correct_keys(self):
        result, _ = self._call(strategy="temporal")
        assert "cv_ndcg_at_5_mean" in result
        assert "cv_ndcg_at_5_std" in result
        assert "cv_folds_completed" in result

    def test_random_returns_correct_keys(self):
        result, _ = self._call(strategy="random")
        assert "cv_ndcg_at_5_mean" in result
        assert "cv_ndcg_at_5_std" in result
        assert "cv_folds_completed" in result

    def test_key_names_include_k(self):
        result, _ = self._call(k=10)
        assert "cv_ndcg_at_10_mean" in result

    def test_folds_completed_matches_requested(self):
        result, _ = self._call(n=20, n_folds=3)
        assert result["cv_folds_completed"] == 3.0

    def test_mean_is_float(self):
        result, _ = self._call()
        assert isinstance(result["cv_ndcg_at_5_mean"], float)

    def test_std_is_non_negative(self):
        result, _ = self._call(n=20, n_folds=3)
        assert result["cv_ndcg_at_5_std"] >= 0.0

    def test_failed_fold_is_skipped_gracefully(self):
        """A single fold failure should reduce folds_completed, not raise."""
        result, _ = self._call(n=20, n_folds=3, raise_on_fold=1)
        assert result["cv_folds_completed"] == 2.0

    def test_all_folds_fail_returns_empty(self):
        X = _make_df(20)
        y = np.ones(20)
        w = np.ones(20)
        titles = _make_titles(20)
        with patch("app.services.model._fit_estimator", side_effect=RuntimeError("boom")):
            result = _cross_validate(
                X_all=X,
                y_all=y,
                w_all=w,
                X_extra=pd.DataFrame(columns=X.columns),
                y_extra=np.array([], dtype=float),
                w_extra=np.array([], dtype=float),
                titles=titles,
                objective="regression",
                params=_default_params(),
                n_folds=3,
                strategy="temporal",
                k=5,
            )
        assert result == {}

    def test_extra_rows_included_in_train(self):
        """Every training fold must receive the extra rows appended."""
        n = 10
        n_extra = 3
        X = _make_df(n)
        X_extra = _make_df(n_extra)
        y = np.ones(n)
        w = np.ones(n)
        titles = _make_titles(n)
        train_sizes: list[int] = []

        def _fake_fit(Xtr, ytr, wtr, *, objective, params):
            train_sizes.append(len(Xtr))
            return _make_mock_model()

        with patch("app.services.model._fit_estimator", side_effect=_fake_fit):
            _cross_validate(
                X_all=X,
                y_all=y,
                w_all=w,
                X_extra=X_extra,
                y_extra=np.ones(n_extra) * 2.0,
                w_extra=np.ones(n_extra) * 0.3,
                titles=titles,
                objective="regression",
                params=_default_params(),
                n_folds=2,
                strategy="temporal",
                k=5,
            )
        assert all(s >= n_extra for s in train_sizes), (
            f"Each fold train size {train_sizes} must include {n_extra} extra rows"
        )

    def test_temporal_and_random_both_produce_results(self):
        for strategy in ("temporal", "random"):
            result, _ = self._call(strategy=strategy, n=20, n_folds=3)
            assert result.get("cv_folds_completed", 0) > 0, (
                f"strategy={strategy} produced no completed folds"
            )

    def test_empty_folds_list_returns_empty_dict(self):
        """When n=1 no folds can be formed → empty result."""
        X = _make_df(1)
        y = np.array([7.0])
        w = np.array([1.0])
        titles = _make_titles(1)
        result = _cross_validate(
            X_all=X,
            y_all=y,
            w_all=w,
            X_extra=pd.DataFrame(columns=X.columns),
            y_extra=np.array([], dtype=float),
            w_extra=np.array([], dtype=float),
            titles=titles,
            objective="regression",
            params=_default_params(),
            n_folds=5,
            strategy="temporal",
            k=5,
        )
        assert result == {}


# ---------------------------------------------------------------------------
# cross_validate (public entrypoint)
# ---------------------------------------------------------------------------


class TestCrossValidatePublic:
    """Tests for the public cross_validate that drives the full feature pipeline."""

    def test_returns_dict_with_mean_key(self):
        titles = _make_titles(20)
        with (
            patch("app.services.model.get_settings", return_value=_mock_settings()),
            patch("app.services.model._fit_estimator", return_value=_make_mock_model()),
        ):
            result = cross_validate(titles, n_folds=3)
        assert any("mean" in k for k in result)

    def test_temporal_strategy_accepted(self):
        titles = _make_titles(20)
        with (
            patch("app.services.model.get_settings", return_value=_mock_settings()),
            patch("app.services.model._fit_estimator", return_value=_make_mock_model()),
        ):
            result = cross_validate(titles, strategy="temporal", n_folds=3)
        assert result.get("cv_folds_completed", 0) > 0

    def test_random_strategy_accepted(self):
        titles = _make_titles(20)
        with (
            patch("app.services.model.get_settings", return_value=_mock_settings()),
            patch("app.services.model._fit_estimator", return_value=_make_mock_model()),
        ):
            result = cross_validate(titles, strategy="random", n_folds=3)
        assert result.get("cv_folds_completed", 0) > 0

    def test_decay_enabled_does_not_crash(self):
        titles = _make_titles(20)
        with (
            patch(
                "app.services.model.get_settings",
                return_value=_mock_settings(decay_enabled=True),
            ),
            patch("app.services.model._fit_estimator", return_value=_make_mock_model()),
        ):
            result = cross_validate(titles, n_folds=3)
        assert isinstance(result, dict)

    def test_mean_ndcg_is_non_negative(self):
        titles = _make_titles(20)
        with (
            patch("app.services.model.get_settings", return_value=_mock_settings()),
            patch("app.services.model._fit_estimator", return_value=_make_mock_model()),
        ):
            result = cross_validate(titles, n_folds=3)
        mean_key = next((k for k in result if "mean" in k), None)
        if mean_key:
            assert result[mean_key] >= 0.0

    def test_folds_completed_not_exceeds_n_folds(self):
        titles = _make_titles(120)  # > 100 so no LOO override
        with (
            patch("app.services.model.get_settings", return_value=_mock_settings()),
            patch("app.services.model._fit_estimator", return_value=_make_mock_model()),
        ):
            result = cross_validate(titles, n_folds=4)
        assert result.get("cv_folds_completed", 0) <= 4

    # --- LOO fallback (<100 ratings) ----------------------------------------

    def test_loo_fallback_triggers_below_100_ratings(self):
        """With 10 titles (< 100), effective_n_folds should be 9 (n-1), not 5."""
        titles = _make_titles(10)
        effective_used = []

        original_cv = _cross_validate

        def _capture_cv(**kwargs):
            effective_used.append(kwargs["n_folds"])
            return original_cv(**kwargs)

        with (
            patch("app.services.model.get_settings", return_value=_mock_settings()),
            patch("app.services.model._fit_estimator", return_value=_make_mock_model()),
            patch("app.services.model._cross_validate", side_effect=_capture_cv),
        ):
            cross_validate(titles, n_folds=5)

        assert effective_used, "No _cross_validate call captured"
        assert effective_used[0] == 9, (
            f"LOO fallback should use n-1=9 folds for 10 titles, got {effective_used[0]}"
        )

    def test_loo_fallback_not_triggered_above_100_ratings(self):
        """With 120 titles (≥ 100), requested n_folds=4 must be passed through unchanged."""
        titles = _make_titles(120)
        effective_used = []

        original_cv = _cross_validate

        def _capture_cv(**kwargs):
            effective_used.append(kwargs["n_folds"])
            return original_cv(**kwargs)

        with (
            patch("app.services.model.get_settings", return_value=_mock_settings()),
            patch("app.services.model._fit_estimator", return_value=_make_mock_model()),
            patch("app.services.model._cross_validate", side_effect=_capture_cv),
        ):
            cross_validate(titles, n_folds=4)

        assert effective_used[0] == 4, (
            f"Should pass n_folds=4 unchanged for 120 titles, got {effective_used[0]}"
        )

    def test_loo_fallback_with_two_titles(self):
        """Edge: 2 titles → effective_n_folds=1 (only 1 fold possible)."""
        titles = _make_titles(2)
        effective_used = []

        original_cv = _cross_validate

        def _capture_cv(**kwargs):
            effective_used.append(kwargs["n_folds"])
            return original_cv(**kwargs)

        with (
            patch("app.services.model.get_settings", return_value=_mock_settings()),
            patch("app.services.model._fit_estimator", return_value=_make_mock_model()),
            patch("app.services.model._cross_validate", side_effect=_capture_cv),
        ):
            cross_validate(titles, n_folds=5)

        assert effective_used[0] == 1

    def test_very_few_ratings_does_not_crash(self):
        """5 titles with LOO should produce results without exception."""
        titles = _make_titles(5)
        with (
            patch("app.services.model.get_settings", return_value=_mock_settings()),
            patch("app.services.model._fit_estimator", return_value=_make_mock_model()),
        ):
            result = cross_validate(titles, n_folds=5)
        assert isinstance(result, dict)
