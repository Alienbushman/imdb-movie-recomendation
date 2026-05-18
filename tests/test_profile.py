"""Tests for T3.14 taste-profile service (profile.py) and GET /profile endpoint.

Covers:
- _person_stats: aggregation, min_count filter, top-n, sorting
- _genre_stats: multi-genre titles, sorted by mean_rating
- _decade_stats: year bucketing, chronological order, missing year skipped
- _language_stats: top-n, None language skipped
- _runtime_histogram: bucket placement, None runtime skipped
- _rating_distribution: all 1-10 keys present, zero-fill
- build_taste_profile: empty input, rated_count, genres, health footer
- API GET /profile: 200, correct schema
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rt(
    imdb_id="tt0000001",
    user_rating=7,
    genres=None,
    year=2020,
    runtime_mins=100,
    language="English",
    directors=None,
    writers=None,
):
    from app.models.schemas import RatedTitle

    return RatedTitle(
        imdb_id=imdb_id,
        title="Test",
        original_title="Test",
        title_type="movie",
        user_rating=user_rating,
        date_rated="2024-01-01",
        imdb_rating=7.0,
        runtime_mins=runtime_mins,
        year=year,
        genres=genres or ["Drama"],
        num_votes=10_000,
        release_date=f"{year}-01-01",
        directors=directors or ["Director A"],
        writers=writers or [],
        url=f"https://www.imdb.com/title/{imdb_id}/",
        language=language,
    )


# ---------------------------------------------------------------------------
# _person_stats
# ---------------------------------------------------------------------------


class TestPersonStats:
    def _call(self, pairs, top_n=20, min_count=2):
        from app.services.profile import _person_stats

        return _person_stats(pairs, top_n=top_n, min_count=min_count)

    def test_basic_aggregation(self):
        pairs = [("Nolan", 9), ("Nolan", 8)]
        stats = self._call(pairs, min_count=1)
        assert len(stats) == 1
        assert stats[0].name == "Nolan"
        assert stats[0].mean_rating == pytest.approx(8.5)
        assert stats[0].count == 2

    def test_min_count_filters_out_single_appearance(self):
        pairs = [("Nolan", 9), ("Kubrick", 8)]
        stats = self._call(pairs, min_count=2)
        assert stats == []

    def test_sorted_by_mean_rating_descending(self):
        pairs = [("A", 9), ("A", 9), ("B", 7), ("B", 7)]
        stats = self._call(pairs, min_count=1)
        assert stats[0].name == "A"
        assert stats[1].name == "B"

    def test_top_n_limits_results(self):
        pairs = [(f"Dir{i}", 8) for i in range(10) for _ in range(3)]
        stats = self._call(pairs, top_n=5, min_count=1)
        assert len(stats) <= 5

    def test_empty_input_returns_empty(self):
        assert self._call([]) == []

    def test_empty_name_skipped(self):
        pairs = [("", 7), ("", 7)]
        stats = self._call(pairs, min_count=1)
        assert stats == []

    def test_multiple_directors_aggregated_separately(self):
        pairs = [("A", 10), ("A", 10), ("B", 5), ("B", 5)]
        stats = self._call(pairs, min_count=1)
        names = [s.name for s in stats]
        assert "A" in names and "B" in names


# ---------------------------------------------------------------------------
# _genre_stats
# ---------------------------------------------------------------------------


class TestGenreStats:
    def _call(self, titles, top_n=23):
        from app.services.profile import _genre_stats

        return _genre_stats(titles, top_n=top_n)

    def test_aggregates_genres(self):
        titles = [_rt(genres=["Drama"], user_rating=8), _rt(genres=["Drama"], user_rating=6)]
        stats = self._call(titles)
        drama = next(s for s in stats if s.name == "Drama")
        assert drama.mean_rating == pytest.approx(7.0)
        assert drama.count == 2

    def test_multi_genre_title_counted_in_each_genre(self):
        titles = [_rt(genres=["Drama", "Thriller"], user_rating=9)]
        stats = self._call(titles)
        names = [s.name for s in stats]
        assert "Drama" in names
        assert "Thriller" in names

    def test_sorted_by_mean_rating(self):
        titles = [
            _rt(genres=["Drama"], user_rating=5),
            _rt(genres=["Horror"], user_rating=9),
        ]
        stats = self._call(titles)
        assert stats[0].name == "Horror"

    def test_empty_titles_returns_empty(self):
        assert self._call([]) == []

    def test_top_n_respected(self):
        titles = [_rt(genres=[f"Genre{i}"], user_rating=7) for i in range(10)]
        stats = self._call(titles, top_n=5)
        assert len(stats) <= 5


# ---------------------------------------------------------------------------
# _decade_stats
# ---------------------------------------------------------------------------


class TestDecadeStats:
    def _call(self, titles):
        from app.services.profile import _decade_stats

        return _decade_stats(titles)

    def test_groups_by_decade(self):
        titles = [_rt(year=2015, user_rating=8), _rt(year=2018, user_rating=6)]
        stats = self._call(titles)
        assert len(stats) == 1
        assert stats[0].decade == 2010
        assert stats[0].mean_rating == pytest.approx(7.0)

    def test_sorted_by_decade(self):
        titles = [_rt(year=2000), _rt(year=1990), _rt(year=2010)]
        stats = self._call(titles)
        decades = [s.decade for s in stats]
        assert decades == sorted(decades)

    def test_title_without_year_skipped(self):
        # RatedTitle.year is int — use 0 which is falsy (same code path as None)
        t = _rt(year=0)
        stats = self._call([t])
        assert stats == []

    def test_multiple_decades(self):
        titles = [_rt(year=1990), _rt(year=2010)]
        stats = self._call(titles)
        assert len(stats) == 2


# ---------------------------------------------------------------------------
# _language_stats
# ---------------------------------------------------------------------------


class TestLanguageStats:
    def _call(self, titles, top_n=10):
        from app.services.profile import _language_stats

        return _language_stats(titles, top_n=top_n)

    def test_counts_languages(self):
        titles = [_rt(language="English"), _rt(language="English"), _rt(language="French")]
        stats = self._call(titles)
        en = next(s for s in stats if s.language == "English")
        assert en.count == 2

    def test_none_language_skipped(self):
        titles = [_rt(language=None), _rt(language="English")]
        stats = self._call(titles)
        assert all(s.language is not None for s in stats)

    def test_top_n_respected(self):
        titles = [_rt(language=f"Lang{i}") for i in range(20)]
        stats = self._call(titles, top_n=5)
        assert len(stats) <= 5


# ---------------------------------------------------------------------------
# _runtime_histogram
# ---------------------------------------------------------------------------


class TestRuntimeHistogram:
    def _call(self, titles):
        from app.services.profile import _runtime_histogram

        return _runtime_histogram(titles)

    def test_bucketing_short_film(self):
        buckets = self._call([_rt(runtime_mins=45)])
        under60 = next(b for b in buckets if b.label == "Under 60m")
        assert under60.count == 1

    def test_bucketing_standard(self):
        buckets = self._call([_rt(runtime_mins=100)])
        bucket = next(b for b in buckets if b.label == "90-120m")
        assert bucket.count == 1

    def test_none_runtime_skipped(self):
        buckets = self._call([_rt(runtime_mins=None)])
        assert all(b.count == 0 for b in buckets)

    def test_always_returns_all_buckets(self):
        from app.services.profile import _RUNTIME_BUCKETS

        buckets = self._call([])
        assert len(buckets) == len(_RUNTIME_BUCKETS)

    def test_long_film_in_last_bucket(self):
        buckets = self._call([_rt(runtime_mins=220)])
        last = next(b for b in buckets if b.label == "3h+")
        assert last.count == 1


# ---------------------------------------------------------------------------
# _rating_distribution
# ---------------------------------------------------------------------------


class TestRatingDistribution:
    def _call(self, titles):
        from app.services.profile import _rating_distribution

        return _rating_distribution(titles)

    def test_all_keys_1_to_10_present(self):
        dist = self._call([_rt(user_rating=7)])
        assert set(dist.keys()) == set(range(1, 11))

    def test_zero_fill_for_missing_ratings(self):
        dist = self._call([_rt(user_rating=7)])
        for k in range(1, 11):
            if k != 7:
                assert dist[k] == 0

    def test_correct_count(self):
        titles = [_rt(user_rating=7), _rt(user_rating=7), _rt(user_rating=9)]
        dist = self._call(titles)
        assert dist[7] == 2
        assert dist[9] == 1

    def test_empty_input_all_zeros(self):
        dist = self._call([])
        assert all(v == 0 for v in dist.values())


# ---------------------------------------------------------------------------
# build_taste_profile
# ---------------------------------------------------------------------------


class TestBuildTasteProfile:
    @pytest.fixture(autouse=True)
    def _no_model(self):
        """Avoid needing a trained model file on disk."""
        with patch("app.services.profile.load_model_bundle", return_value=None):
            yield

    def test_empty_titles_returns_empty_response(self):
        from app.services.profile import build_taste_profile

        result = build_taste_profile([])
        assert result.rated_count == 0
        assert result.top_genres == []

    def test_rated_count_correct(self):
        from app.services.profile import build_taste_profile

        titles = [_rt(imdb_id=f"tt{i:07d}") for i in range(5)]
        result = build_taste_profile(titles)
        assert result.rated_count == 5

    def test_returns_taste_profile_response_type(self):
        from app.models.schemas import TasteProfileResponse
        from app.services.profile import build_taste_profile

        result = build_taste_profile([_rt()])
        assert isinstance(result, TasteProfileResponse)

    def test_genre_stats_populated(self):
        from app.services.profile import build_taste_profile

        titles = [_rt(genres=["Drama", "Thriller"]) for _ in range(3)]
        result = build_taste_profile(titles)
        genre_names = [g.name for g in result.top_genres]
        assert "Drama" in genre_names

    def test_rating_distribution_has_all_keys(self):
        from app.services.profile import build_taste_profile

        titles = [_rt(user_rating=i % 10 + 1) for i in range(20)]
        result = build_taste_profile(titles)
        assert set(result.rating_distribution.keys()) == set(range(1, 11))

    def test_director_stats_populated_from_titles(self):
        from app.services.profile import build_taste_profile

        titles = [
            _rt(imdb_id=f"tt{i:07d}", directors=["Kubrick"]) for i in range(3)
        ]
        result = build_taste_profile(titles)
        directors = [d.name for d in result.top_directors]
        assert "Kubrick" in directors

    def test_decade_distribution_populated(self):
        from app.services.profile import build_taste_profile

        titles = [_rt(year=2010 + i, imdb_id=f"tt{i:07d}") for i in range(5)]
        result = build_taste_profile(titles)
        assert len(result.decade_distribution) >= 1

    def test_runtime_histogram_always_present(self):
        from app.services.profile import build_taste_profile

        result = build_taste_profile([_rt()])
        assert len(result.runtime_histogram) > 0

    def test_health_no_model_returns_empty_health(self):
        from app.services.profile import build_taste_profile

        result = build_taste_profile([_rt()])
        assert result.health.trained_at is None

    def test_health_with_model_bundle(self):
        from app.services.profile import build_taste_profile

        mock_bundle = {
            "trained_at": "2026-05-01T12:00:00Z",
            "objective": "lambdarank",
            "metrics": {"ndcg_at_10": 0.82, "map_at_10": 0.71, "spearman": 0.75},
            "feature_names": ["f1", "f2"],
            "best_params": {},
        }
        with patch("app.services.profile.load_model_bundle", return_value=mock_bundle):
            result = build_taste_profile([_rt()])
        assert result.health.trained_at == "2026-05-01T12:00:00Z"
        assert result.health.ndcg_at_k == pytest.approx(0.82)
        assert result.health.feature_count == 2


# ---------------------------------------------------------------------------
# API: GET /profile
# ---------------------------------------------------------------------------


class TestProfileEndpoint:
    @pytest.fixture()
    def api_client(self, tmp_path):
        from app.api.routes import router
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        test_app = FastAPI()
        test_app.include_router(router, prefix="/api/v1")

        import app.services.profile as prof_mod

        with (
            patch.object(prof_mod, "load_model_bundle", return_value=None),
            patch("app.api.routes.get_profile.__wrapped__", None, create=True),
        ):
            yield TestClient(test_app)

    def _make_client(self):
        from app.api.routes import router
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        test_app = FastAPI()
        test_app.include_router(router, prefix="/api/v1")
        return TestClient(test_app)

    def test_returns_200(self):
        import app.services.ingest as ingest_mod
        import app.services.profile as prof_mod
        import app.services.pipeline as pipeline_mod

        with (
            patch.object(prof_mod, "load_model_bundle", return_value=None),
            patch.object(ingest_mod, "load_watchlist", return_value=[]),
            patch.dict(pipeline_mod._state, {}, clear=True),
        ):
            res = self._make_client().get("/api/v1/profile")

        assert res.status_code == 200

    def test_response_has_required_fields(self):
        import app.services.ingest as ingest_mod
        import app.services.profile as prof_mod
        import app.services.pipeline as pipeline_mod

        with (
            patch.object(prof_mod, "load_model_bundle", return_value=None),
            patch.object(ingest_mod, "load_watchlist", return_value=[]),
            patch.dict(pipeline_mod._state, {}, clear=True),
        ):
            body = self._make_client().get("/api/v1/profile").json()

        assert "rated_count" in body
        assert "top_genres" in body
        assert "rating_distribution" in body
        assert "health" in body
