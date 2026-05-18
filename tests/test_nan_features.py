"""Tests for T2.10 NaN-sentinel for missing TMDB/OMDb features (no zero-fill).

Covers:
- compute_critic_features (omdb.py): NaN when missing, correct scores when present,
  gap propagation, partial data
- compute_keyword_features (tmdb.py): NaN for no-match / empty input, binary flags
- FeatureVector defaults: NaN for critic/keyword score fields
- features_to_dataframe: NaN preserved end-to-end (no fillna)
- model.py: zero_as_missing=False in LGB params so NaN is treated as missing
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# compute_critic_features (omdb.py)
# ---------------------------------------------------------------------------


class TestComputeCriticFeatures:
    def _call(self, imdb_id="tt0000001", imdb_rating=7.0, omdb_scores=None):
        from app.services.omdb import compute_critic_features

        return compute_critic_features(
            imdb_id=imdb_id,
            imdb_rating=imdb_rating,
            omdb_scores=omdb_scores or {},
        )

    def test_missing_entry_returns_nan_for_all_fields(self):
        result = self._call(omdb_scores={})
        assert math.isnan(result["rt_score"])
        assert math.isnan(result["metacritic_score"])
        assert math.isnan(result["imdb_rt_gap"])
        assert math.isnan(result["imdb_metacritic_gap"])

    def test_none_rt_returns_nan(self):
        result = self._call(omdb_scores={"tt0000001": {"rt": None, "metacritic": None}})
        assert math.isnan(result["rt_score"])
        assert math.isnan(result["metacritic_score"])

    def test_valid_rt_score_scaled_to_10(self):
        # RT 80% → 8.0 (already normalised in _parse_rt_score)
        result = self._call(omdb_scores={"tt0000001": {"rt": 8.0, "metacritic": None}})
        assert result["rt_score"] == pytest.approx(8.0)

    def test_valid_metacritic_score_returned(self):
        result = self._call(omdb_scores={"tt0000001": {"rt": None, "metacritic": 7.5}})
        assert result["metacritic_score"] == pytest.approx(7.5)
        assert math.isnan(result["rt_score"])

    def test_gap_is_nan_when_score_missing(self):
        result = self._call(imdb_rating=8.0, omdb_scores={"tt0000001": {"rt": None, "metacritic": None}})
        assert math.isnan(result["imdb_rt_gap"])
        assert math.isnan(result["imdb_metacritic_gap"])

    def test_gap_correct_when_both_present(self):
        result = self._call(
            imdb_rating=8.0,
            omdb_scores={"tt0000001": {"rt": 6.0, "metacritic": 7.0}},
        )
        assert result["imdb_rt_gap"] == pytest.approx(8.0 - 6.0)
        assert result["imdb_metacritic_gap"] == pytest.approx(8.0 - 7.0)

    def test_partial_data_nan_gap_only_for_missing(self):
        result = self._call(
            imdb_rating=8.0,
            omdb_scores={"tt0000001": {"rt": 7.0, "metacritic": None}},
        )
        assert result["imdb_rt_gap"] == pytest.approx(8.0 - 7.0)
        assert math.isnan(result["imdb_metacritic_gap"])

    def test_zero_rt_preserved_as_zero_not_nan(self):
        """A score of 0.0 is a real critic verdict, not missing."""
        result = self._call(omdb_scores={"tt0000001": {"rt": 0.0, "metacritic": None}})
        assert result["rt_score"] == pytest.approx(0.0)
        assert not math.isnan(result["rt_score"])


# ---------------------------------------------------------------------------
# compute_keyword_features (tmdb.py)
# ---------------------------------------------------------------------------


class TestComputeKeywordFeatures:
    def _call(self, candidate_keywords, keyword_affinity):
        from app.services.tmdb import compute_keyword_features

        return compute_keyword_features(candidate_keywords, keyword_affinity)

    def test_empty_candidate_keywords_returns_nan_affinity(self):
        result = self._call([], {"thriller": 8.0})
        assert math.isnan(result["keyword_affinity_score"])

    def test_empty_affinity_map_returns_nan(self):
        result = self._call(["thriller", "heist"], {})
        assert math.isnan(result["keyword_affinity_score"])

    def test_no_overlap_returns_nan_affinity(self):
        result = self._call(["thriller"], {"heist": 8.0})
        assert math.isnan(result["keyword_affinity_score"])
        assert result["has_known_keywords"] is False
        assert result["keyword_overlap_count"] == 0

    def test_matching_keywords_returns_mean(self):
        result = self._call(["thriller", "heist"], {"thriller": 8.0, "heist": 6.0})
        assert result["keyword_affinity_score"] == pytest.approx(7.0)
        assert result["has_known_keywords"] is True
        assert result["keyword_overlap_count"] == 2

    def test_single_match_returns_that_score(self):
        result = self._call(["thriller", "drama"], {"thriller": 9.0})
        assert result["keyword_affinity_score"] == pytest.approx(9.0)
        assert result["keyword_overlap_count"] == 1

    def test_has_known_keywords_is_bool_not_nan(self):
        result = self._call([], {})
        assert isinstance(result["has_known_keywords"], bool)
        assert result["has_known_keywords"] is False

    def test_overlap_count_is_integer_not_nan(self):
        result = self._call([], {})
        assert result["keyword_overlap_count"] == 0
        assert isinstance(result["keyword_overlap_count"], int)


# ---------------------------------------------------------------------------
# FeatureVector NaN defaults
# ---------------------------------------------------------------------------


class TestFeatureVectorNanDefaults:
    def _make_fv(self, **overrides):
        from app.models.schemas import FeatureVector
        from app.services.features import ALL_GENRES

        defaults = dict(
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
        defaults.update(overrides)
        return FeatureVector(**defaults)

    def test_rt_score_defaults_to_nan(self):
        fv = self._make_fv()
        assert math.isnan(fv.rt_score)

    def test_metacritic_score_defaults_to_nan(self):
        fv = self._make_fv()
        assert math.isnan(fv.metacritic_score)

    def test_imdb_rt_gap_defaults_to_nan(self):
        fv = self._make_fv()
        assert math.isnan(fv.imdb_rt_gap)

    def test_imdb_metacritic_gap_defaults_to_nan(self):
        fv = self._make_fv()
        assert math.isnan(fv.imdb_metacritic_gap)

    def test_keyword_affinity_score_defaults_to_nan(self):
        fv = self._make_fv()
        assert math.isnan(fv.keyword_affinity_score)

    def test_has_known_keywords_defaults_to_false(self):
        """has_known_keywords is a binary flag — must not be NaN."""
        fv = self._make_fv()
        assert fv.has_known_keywords is False

    def test_keyword_overlap_count_defaults_to_zero(self):
        """keyword_overlap_count is a meaningful integer, not missing."""
        fv = self._make_fv()
        assert fv.keyword_overlap_count == 0


# ---------------------------------------------------------------------------
# features_to_dataframe: NaN preserved, no silent zero-fill
# ---------------------------------------------------------------------------


class TestFeaturesNanPreservation:
    def _make_fv_with_nan_critics(self):
        from app.models.schemas import FeatureVector
        from app.services.features import ALL_GENRES

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
            rt_score=float("nan"),
            metacritic_score=float("nan"),
            imdb_rt_gap=float("nan"),
            imdb_metacritic_gap=float("nan"),
            keyword_affinity_score=float("nan"),
        )

    def test_nan_fields_remain_nan_in_dataframe(self):
        from app.services.features import features_to_dataframe

        fv = self._make_fv_with_nan_critics()
        df = features_to_dataframe([fv])
        for col in ("rt_score", "metacritic_score", "imdb_rt_gap", "imdb_metacritic_gap",
                    "keyword_affinity_score"):
            assert col in df.columns, f"Missing column: {col}"
            assert math.isnan(df[col].iloc[0]), f"{col} should be NaN, got {df[col].iloc[0]}"

    def test_known_scores_preserved_not_zeroed(self):
        from app.models.schemas import FeatureVector
        from app.services.features import ALL_GENRES, features_to_dataframe

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
            rt_score=8.5,
            metacritic_score=7.2,
        )
        df = features_to_dataframe([fv])
        assert df["rt_score"].iloc[0] == pytest.approx(8.5)
        assert df["metacritic_score"].iloc[0] == pytest.approx(7.2)

    def test_mixed_nan_and_real_rows_preserved(self):
        from app.models.schemas import FeatureVector
        from app.services.features import ALL_GENRES, features_to_dataframe

        def _fv(rt):
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
                rt_score=rt,
            )

        df = features_to_dataframe([_fv(float("nan")), _fv(9.0)])
        assert math.isnan(df["rt_score"].iloc[0])
        assert df["rt_score"].iloc[1] == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# Model config: zero_as_missing=False (LGB NaN handling)
# ---------------------------------------------------------------------------


class TestLgbZeroAsMissingConfig:
    def test_fit_estimator_sets_zero_as_missing_false(self):
        """_fit_estimator must pass zero_as_missing=False to the LGB estimator."""
        import inspect
        from app.services.model import _fit_estimator
        import lightgbm as lgb

        fitted_models = []

        original_ranker = lgb.LGBMRanker

        class CapturingRanker(lgb.LGBMRanker):
            def __init__(self, **kwargs):
                fitted_models.append(kwargs)
                super().__init__(**kwargs)

        import unittest.mock as mock

        params = {
            "n_estimators": 10,
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
        # Simply inspect the source to confirm zero_as_missing=False is in the call.
        source = inspect.getsource(_fit_estimator)
        assert "zero_as_missing=False" in source, (
            "_fit_estimator must set zero_as_missing=False so LGB treats NaN as missing"
        )

    def test_nan_feature_survives_lgb_prediction(self):
        """A model trained on clean data can still score rows with NaN features."""
        import lightgbm as lgb
        import pandas as pd
        import numpy as np

        n = 30
        rng = np.random.default_rng(0)
        X_train = pd.DataFrame(rng.uniform(0, 10, size=(n, 3)), columns=["a", "b", "c"])
        y_train = rng.integers(1, 10, size=n).astype(float)

        model = lgb.LGBMRegressor(
            n_estimators=20,
            learning_rate=0.1,
            zero_as_missing=False,
            verbose=-1,
        )
        model.fit(X_train, y_train)

        X_nan = pd.DataFrame(
            {"a": [7.0, float("nan")], "b": [5.0, 5.0], "c": [float("nan"), 8.0]}
        )
        preds = model.predict(X_nan)
        assert len(preds) == 2
        assert all(np.isfinite(preds)), "Predictions on NaN-feature rows must be finite"
