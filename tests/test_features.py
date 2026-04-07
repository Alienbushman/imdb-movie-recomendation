"""Unit tests for app.services.features — feature engineering logic."""

import numpy as np
import pytest

from app.models.schemas import CandidateTitle, RatedTitle, TasteProfile
from app.services.features import (
    ALL_GENRES,
    _build_genre_flags,
    _build_genre_affinity,
    _build_language_flags,
    _build_type_flags,
    _build_genre_pair_flags,
    _compute_derived_features,
    _compute_popularity_features,
    _compute_taste_features,
    build_taste_profile,
    candidate_to_features,
    feature_vector_to_array,
    features_to_dataframe,
    rated_title_to_features,
)

# --- Helpers ---

def _make_rated(
    imdb_id="tt0000001",
    title="Test Movie",
    user_rating=7,
    genres=None,
    directors=None,
    **kwargs,
) -> RatedTitle:
    defaults = dict(
        imdb_id=imdb_id,
        title=title,
        original_title=title,
        title_type="movie",
        user_rating=user_rating,
        date_rated="2024-01-01",
        imdb_rating=7.5,
        runtime_mins=120,
        year=2020,
        genres=genres or ["Drama"],
        num_votes=100_000,
        release_date="2020-01-01",
        directors=directors or ["Director A"],
        url="https://www.imdb.com/title/tt0000001/",
    )
    defaults.update(kwargs)
    return RatedTitle(**defaults)


def _make_candidate(
    imdb_id="tt9999999",
    title="Candidate Movie",
    genres=None,
    directors=None,
    actors=None,
    **kwargs,
) -> CandidateTitle:
    defaults = dict(
        imdb_id=imdb_id,
        title=title,
        original_title=title,
        title_type="movie",
        imdb_rating=8.0,
        year=2022,
        genres=genres or ["Action", "Sci-Fi"],
        num_votes=500_000,
        directors=directors or [],
        actors=actors or [],
    )
    defaults.update(kwargs)
    return CandidateTitle(**defaults)


# --- _build_genre_flags ---


class TestBuildGenreFlags:
    def test_known_genres_flagged(self):
        flags = _build_genre_flags(["Action", "Drama"])
        assert flags["genre_action"] == 1
        assert flags["genre_drama"] == 1
        assert flags["genre_comedy"] == 0

    def test_empty_list(self):
        flags = _build_genre_flags([])
        assert all(v == 0 for v in flags.values())
        assert len(flags) == len(ALL_GENRES)

    def test_all_genres_present_as_keys(self):
        flags = _build_genre_flags(["Comedy"])
        for genre in ALL_GENRES:
            key = f"genre_{genre.lower().replace('-', '_')}"
            assert key in flags

    def test_hyphenated_genre(self):
        flags = _build_genre_flags(["Film-Noir", "Sci-Fi"])
        assert flags["genre_film_noir"] == 1
        assert flags["genre_sci_fi"] == 1

    def test_unknown_genre_ignored(self):
        flags = _build_genre_flags(["Action", "NotAGenre"])
        assert flags["genre_action"] == 1
        assert len(flags) == len(ALL_GENRES)


# --- _compute_derived_features ---


class TestComputeDerivedFeatures:
    def test_normal_values(self):
        result = _compute_derived_features(8.0, 100_000, 2020, 120)
        assert result["decade"] == 2020
        assert result["runtime_mins"] == 120.0
        assert result["rating_vote_ratio"] == pytest.approx(8.0 / np.log1p(100_000), rel=1e-6)

    def test_none_year_defaults_to_2000(self):
        result = _compute_derived_features(7.0, 50_000, None, 90)
        assert result["decade"] == 2000

    def test_none_runtime_defaults_to_zero(self):
        result = _compute_derived_features(7.0, 50_000, 2010, None)
        assert result["runtime_mins"] == 0.0

    def test_decade_rounding(self):
        assert _compute_derived_features(7.0, 1000, 1999, 90)["decade"] == 1990
        assert _compute_derived_features(7.0, 1000, 2000, 90)["decade"] == 2000
        assert _compute_derived_features(7.0, 1000, 2005, 90)["decade"] == 2000


# --- _compute_taste_features ---


class TestComputeTasteFeatures:
    def test_no_taste_profile(self):
        result = _compute_taste_features(["Director A"], ["Actor X"], None)
        assert result["director_taste_score"] == 0.0
        assert result["has_known_director"] is False
        assert result["director_taste_count"] == 0
        assert result["director_taste_mean"] == 0.0
        assert result["actor_taste_score"] == 0.0
        assert result["has_known_actor"] is False
        assert result["actor_taste_count"] == 0
        assert result["actor_taste_mean"] == 0.0

    def test_known_director(self):
        taste = TasteProfile(director_avg={"Director A": 8.5})
        result = _compute_taste_features(["Director A"], [], taste)
        assert result["director_taste_score"] == 8.5
        assert result["has_known_director"] is True
        assert result["director_taste_count"] == 1
        assert result["director_taste_mean"] == pytest.approx(8.5)

    def test_unknown_director(self):
        taste = TasteProfile(director_avg={"Director B": 8.5})
        result = _compute_taste_features(["Director A"], [], taste)
        assert result["director_taste_score"] == 0.0
        assert result["has_known_director"] is False

    def test_known_actor(self):
        taste = TasteProfile(actor_avg={"Actor X": 9.0})
        result = _compute_taste_features([], ["Actor X"], taste)
        assert result["actor_taste_score"] == 9.0
        assert result["has_known_actor"] is True
        assert result["actor_taste_count"] == 1
        assert result["actor_taste_mean"] == pytest.approx(9.0)

    def test_multiple_directors_takes_max_and_mean(self):
        taste = TasteProfile(director_avg={"Dir A": 6.0, "Dir B": 9.0})
        result = _compute_taste_features(["Dir A", "Dir B"], [], taste)
        assert result["director_taste_score"] == 9.0
        assert result["director_taste_count"] == 2
        assert result["director_taste_mean"] == pytest.approx(7.5)

    def test_multiple_actors_takes_max(self):
        taste = TasteProfile(actor_avg={"Act A": 5.0, "Act B": 8.0, "Act C": 7.0})
        result = _compute_taste_features([], ["Act A", "Act B", "Act C"], taste)
        assert result["actor_taste_score"] == 8.0
        assert result["actor_taste_count"] == 3

    def test_writer_taste_features(self):
        taste = TasteProfile(writer_avg={"Writer X": 9.0, "Writer Y": 7.0})
        result = _compute_taste_features([], [], taste, writers=["Writer X", "Writer Y"])
        assert result["writer_taste_score"] == 9.0
        assert result["has_known_writer"] is True
        assert result["writer_taste_count"] == 2
        assert result["writer_taste_mean"] == pytest.approx(8.0)

    def test_unknown_writer(self):
        taste = TasteProfile(writer_avg={"Writer Z": 8.0})
        result = _compute_taste_features([], [], taste, writers=["Writer A"])
        assert result["writer_taste_score"] == 0.0
        assert result["has_known_writer"] is False

    def test_composer_and_cinematographer(self):
        taste = TasteProfile(
            composer_avg={"Hans Zimmer": 9.0},
            cinematographer_avg={"Roger Deakins": 8.5},
        )
        result = _compute_taste_features(
            [], [], taste, composers=["Hans Zimmer"], cinematographers=["Roger Deakins"]
        )
        assert result["composer_taste_score"] == 9.0
        assert result["has_known_composer"] is True
        assert result["cinematographer_taste_score"] == 8.5
        assert result["has_known_cinematographer"] is True


# --- _build_genre_affinity ---


class TestBuildGenreAffinity:
    def test_no_taste_profile(self):
        affinity = _build_genre_affinity(["Action", "Drama"], None)
        assert all(v == 0.0 for v in affinity.values())
        assert len(affinity) == len(ALL_GENRES)

    def test_known_genre_affinity(self):
        taste = TasteProfile(genre_avg={"Action": 8.5, "Drama": 6.0})
        affinity = _build_genre_affinity(["Action", "Drama"], taste)
        assert affinity["genre_action_affinity"] == pytest.approx(8.5)
        assert affinity["genre_drama_affinity"] == pytest.approx(6.0)
        assert affinity["genre_comedy_affinity"] == 0.0

    def test_all_genres_present(self):
        taste = TasteProfile(genre_avg={"Action": 7.0})
        affinity = _build_genre_affinity(["Action"], taste)
        assert len(affinity) == len(ALL_GENRES)

    def test_hyphenated_genre(self):
        taste = TasteProfile(genre_avg={"Sci-Fi": 9.0, "Film-Noir": 7.5})
        affinity = _build_genre_affinity(["Sci-Fi"], taste)
        assert affinity["genre_sci_fi_affinity"] == pytest.approx(9.0)


# --- _build_language_flags ---


class TestBuildLanguageFlags:
    def test_known_language(self):
        flags = _build_language_flags("English", ["English", "French", "German"])
        assert flags["lang_english"] == 1
        assert flags["lang_french"] == 0

    def test_unknown_language(self):
        flags = _build_language_flags("Klingon", ["English", "French"])
        assert all(v == 0 for v in flags.values())

    def test_none_language(self):
        flags = _build_language_flags(None, ["English", "French"])
        assert all(v == 0 for v in flags.values())


# --- _build_type_flags ---


class TestBuildTypeFlags:
    def test_movie_type(self):
        flags = _build_type_flags("movie")
        assert flags["type_movie"] == 1
        assert flags["type_tvseries"] == 0

    def test_tvseries_type(self):
        flags = _build_type_flags("tvSeries")
        assert flags["type_tvseries"] == 1
        assert flags["type_movie"] == 0

    def test_all_types_present(self):
        flags = _build_type_flags("movie")
        assert len(flags) == 4


# --- _build_genre_pair_flags ---


class TestBuildGenrePairFlags:
    def test_matching_pair(self):
        flags = _build_genre_pair_flags(["Action", "Thriller"], ["action_x_thriller"])
        assert flags["gpair_action_x_thriller"] == 1

    def test_non_matching_pair(self):
        flags = _build_genre_pair_flags(["Action", "Drama"], ["action_x_thriller"])
        assert flags["gpair_action_x_thriller"] == 0

    def test_empty_pairs(self):
        flags = _build_genre_pair_flags(["Action", "Thriller"], [])
        assert flags == {}


# --- _compute_popularity_features ---


class TestComputePopularityFeatures:
    def test_indie_tier(self):
        result = _compute_popularity_features(10_000, 2020)
        assert result["popularity_tier"] == 0

    def test_niche_tier(self):
        result = _compute_popularity_features(50_000, 2020)
        assert result["popularity_tier"] == 1

    def test_mainstream_tier(self):
        result = _compute_popularity_features(200_000, 2020)
        assert result["popularity_tier"] == 2

    def test_blockbuster_tier(self):
        result = _compute_popularity_features(1_000_000, 2020)
        assert result["popularity_tier"] == 3

    def test_title_age(self):
        result = _compute_popularity_features(100_000, 2016)
        assert result["title_age"] == 10  # 2026 - 2016

    def test_log_votes(self):
        result = _compute_popularity_features(100_000, 2020)
        assert result["log_votes"] == pytest.approx(5.0)

    def test_zero_votes(self):
        result = _compute_popularity_features(0, 2020)
        assert result["log_votes"] == 0.0
        assert result["popularity_tier"] == 0


# --- build_taste_profile ---


class TestBuildTasteProfile:
    def test_director_averages(self):
        titles = [
            _make_rated(imdb_id="tt1", directors=["Nolan"], user_rating=9),
            _make_rated(imdb_id="tt2", directors=["Nolan"], user_rating=7),
            _make_rated(imdb_id="tt3", directors=["Spielberg"], user_rating=8),
        ]
        profile = build_taste_profile(titles)
        assert profile.director_avg["Nolan"] == pytest.approx(8.0)
        assert profile.director_avg["Spielberg"] == pytest.approx(8.0)

    def test_no_actors_without_data(self):
        titles = [_make_rated()]
        profile = build_taste_profile(titles)
        assert profile.actor_avg == {}

    def test_actor_averages_with_data(self):
        titles = [
            _make_rated(imdb_id="tt1", user_rating=9),
            _make_rated(imdb_id="tt2", user_rating=5),
        ]
        rated_actors = {
            "tt1": ["DiCaprio", "Cotillard"],
            "tt2": ["DiCaprio"],
        }
        profile = build_taste_profile(titles, rated_actors)
        # global_mean=7.0, C=5; DiCaprio 2 ratings: (14+35)/7=7.0; Cotillard 1 rating: (9+35)/6
        assert profile.actor_avg["DiCaprio"] == pytest.approx(7.0)
        assert profile.actor_avg["Cotillard"] == pytest.approx(44 / 6)
        assert profile.actor_avg["Cotillard"] < 9.0  # pulled toward global mean

    def test_actor_data_for_unknown_title_ignored(self):
        titles = [_make_rated(imdb_id="tt1", user_rating=8)]
        rated_actors = {"tt_unknown": ["Actor Z"]}
        profile = build_taste_profile(titles, rated_actors)
        assert "Actor Z" not in profile.actor_avg

    def test_empty_titles(self):
        profile = build_taste_profile([])
        assert profile.director_avg == {}
        assert profile.actor_avg == {}
        assert profile.genre_avg == {}

    def test_genre_averages(self):
        titles = [
            _make_rated(genres=["Action", "Drama"], user_rating=9),
            _make_rated(imdb_id="tt2", genres=["Action"], user_rating=7),
            _make_rated(imdb_id="tt3", genres=["Drama"], user_rating=5),
        ]
        profile = build_taste_profile(titles)
        # global_mean=7.0, C=5; Action 2 ratings: (16+35)/7=51/7; Drama 2 ratings: (14+35)/7=7.0
        assert profile.genre_avg["Action"] == pytest.approx(51 / 7)
        assert profile.genre_avg["Drama"] == pytest.approx(7.0)

    def test_genre_pairs_computed(self):
        titles = [
            _make_rated(imdb_id=f"tt{i}", genres=["Action", "Thriller"])
            for i in range(5)
        ]
        profile = build_taste_profile(titles)
        assert "action_x_thriller" in profile.genre_pairs

    def test_writer_averages(self):
        titles = [
            _make_rated(imdb_id="tt1", user_rating=9),
            _make_rated(imdb_id="tt2", user_rating=7),
        ]
        rated_writers = {
            "tt1": ["Writer A"],
            "tt2": ["Writer A", "Writer B"],
        }
        profile = build_taste_profile(titles, rated_writers=rated_writers)
        # global_mean=8.0, C=5; Writer A 2 ratings: (16+40)/7=8.0; Writer B 1 rating: (7+40)/6
        assert profile.writer_avg["Writer A"] == pytest.approx(8.0)
        assert profile.writer_avg["Writer B"] == pytest.approx(47 / 6)
        assert profile.writer_avg["Writer B"] < 8.0  # pulled toward global mean


# --- rated_title_to_features / candidate_to_features ---


class TestTitleToFeatures:
    def test_rated_title_basic(self):
        title = _make_rated(genres=["Action", "Sci-Fi"], year=2015, runtime_mins=148)
        fv = rated_title_to_features(title)
        assert fv.imdb_id == title.imdb_id
        assert fv.genre_flags["genre_action"] == 1
        assert fv.genre_flags["genre_sci_fi"] == 1
        assert fv.genre_flags["genre_drama"] == 0
        assert fv.decade == 2010
        assert fv.runtime_mins == 148.0
        assert fv.is_anime is False

    def test_rated_title_animation_flag(self):
        title = _make_rated(genres=["Animation", "Comedy"])
        fv = rated_title_to_features(title)
        assert fv.is_anime is True

    def test_rated_title_with_taste(self):
        taste = TasteProfile(director_avg={"Director A": 9.0}, actor_avg={})
        title = _make_rated(directors=["Director A"])
        fv = rated_title_to_features(title, taste)
        assert fv.has_known_director is True
        assert fv.director_taste_score == 9.0

    def test_candidate_basic(self):
        candidate = _make_candidate(genres=["Drama"], year=1995, runtime_mins=142)
        fv = candidate_to_features(candidate)
        assert fv.genre_flags["genre_drama"] == 1
        assert fv.decade == 1990
        assert fv.runtime_mins == 142.0

    def test_candidate_none_fields_default(self):
        candidate = _make_candidate(year=None, runtime_mins=None)
        fv = candidate_to_features(candidate)
        assert fv.year == 2000
        assert fv.runtime_mins == 0.0

    def test_candidate_with_actors_and_taste(self):
        taste = TasteProfile(director_avg={}, actor_avg={"Actor X": 8.5})
        candidate = _make_candidate(actors=["Actor X", "Actor Y"])
        fv = candidate_to_features(candidate, taste)
        assert fv.has_known_actor is True
        assert fv.actor_taste_score == 8.5


# --- features_to_dataframe ---


class TestFeaturesToDataframe:
    def test_single_feature_vector(self):
        fv = rated_title_to_features(_make_rated())
        df = features_to_dataframe([fv])
        assert len(df) == 1
        assert "imdb_rating" in df.columns
        assert "genre_action" in df.columns
        assert "director_taste_score" in df.columns

    def test_column_count(self):
        fv = rated_title_to_features(_make_rated())
        df = features_to_dataframe([fv])
        # Must contain at minimum the original 11 scalars + 23 genre flags
        assert len(df.columns) >= 11 + len(ALL_GENRES)
        # New columns from subtasks should be present
        assert "genre_action_affinity" in df.columns  # subtask 1
        assert "director_taste_count" in df.columns   # subtask 2
        assert "type_movie" in df.columns             # subtask 5
        assert "popularity_tier" in df.columns        # subtask 7
        assert "log_votes" in df.columns              # subtask 7
        assert "writer_taste_score" in df.columns     # subtask 4

    def test_multiple_rows(self):
        fvs = [
            rated_title_to_features(_make_rated(imdb_id="tt1")),
            rated_title_to_features(_make_rated(imdb_id="tt2")),
        ]
        df = features_to_dataframe(fvs)
        assert len(df) == 2


# --- feature_vector_to_array ---


class TestFeatureVectorToArray:
    def test_matches_feature_names_order(self):
        fv = rated_title_to_features(_make_rated(genres=["Action"], imdb_rating=8.0))
        df = features_to_dataframe([fv])
        feature_names = list(df.columns)

        arr = feature_vector_to_array(fv, feature_names)
        assert len(arr) == len(feature_names)

        # Check a specific value matches
        idx = feature_names.index("imdb_rating")
        assert arr[idx] == pytest.approx(8.0)

        idx = feature_names.index("genre_action")
        assert arr[idx] == 1.0

    def test_missing_feature_raises(self):
        fv = rated_title_to_features(_make_rated())
        with pytest.raises(AssertionError, match="missing keys"):
            feature_vector_to_array(fv, ["imdb_rating", "nonexistent_feature"])

    def test_returns_float_array(self):
        fv = rated_title_to_features(_make_rated())
        df = features_to_dataframe([fv])
        arr = feature_vector_to_array(fv, list(df.columns))
        assert arr.dtype == float
