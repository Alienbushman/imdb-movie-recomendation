"""Smoke tests — verify app imports and core schemas parse correctly.

These tests require no external files (no CSV, no datasets, no model).
They give agents a fast pass/fail signal after making changes.
Run with: uv run pytest tests/ -q
"""


from app.models.schemas import (
    CandidateTitle,
    FeatureVector,
    RatedTitle,
    RecommendationFilters,
    TasteProfile,
)
from app.services.ingest import _parse_list_field

# --- Schema construction ---


def test_rated_title_construction():
    title = RatedTitle(
        imdb_id="tt1375666",
        title="Inception",
        original_title="Inception",
        title_type="movie",
        user_rating=9,
        date_rated="2021-01-01",
        imdb_rating=8.8,
        runtime_mins=148,
        year=2010,
        genres=["Action", "Sci-Fi"],
        num_votes=2_000_000,
        release_date="2010-07-16",
        directors=["Christopher Nolan"],
        url="https://www.imdb.com/title/tt1375666/",
    )
    assert title.imdb_id == "tt1375666"
    assert title.user_rating == 9
    assert title.genres == ["Action", "Sci-Fi"]


def test_candidate_title_construction():
    title = CandidateTitle(
        imdb_id="tt0111161",
        title="The Shawshank Redemption",
        original_title="The Shawshank Redemption",
        title_type="movie",
        imdb_rating=9.3,
        year=1994,
        genres=["Drama"],
        num_votes=2_800_000,
    )
    assert title.imdb_id == "tt0111161"
    assert title.language is None
    assert title.directors == []
    assert title.actors == []
    assert title.writers == []
    assert title.composers == []
    assert title.cinematographers == []


def test_taste_profile_defaults():
    profile = TasteProfile()
    assert profile.director_avg == {}
    assert profile.actor_avg == {}
    assert profile.genre_avg == {}
    assert profile.writer_avg == {}
    assert profile.composer_avg == {}
    assert profile.cinematographer_avg == {}
    assert profile.genre_pairs == []


def test_recommendation_filters_defaults():
    filters = RecommendationFilters()
    assert filters.min_year is None
    assert filters.genres is None
    assert filters.languages is None


def test_feature_vector_construction():
    fv = FeatureVector(
        imdb_id="tt1375666",
        title="Inception",
        title_type="movie",
        imdb_rating=8.8,
        runtime_mins=148.0,
        year=2010,
        num_votes=2_000_000,
        genre_flags={"Action": 1, "Sci-Fi": 1},
    )
    assert fv.director_taste_score == 0.0
    assert fv.has_known_director is False
    assert fv.actor_taste_score == 0.0
    assert fv.decade == 2000


# --- Ingest helpers ---


def test_parse_list_field_normal():
    assert _parse_list_field("Action, Sci-Fi, Thriller") == ["Action", "Sci-Fi", "Thriller"]


def test_parse_list_field_single():
    assert _parse_list_field("Drama") == ["Drama"]


def test_parse_list_field_empty_string():
    assert _parse_list_field("") == []


def test_parse_list_field_nan():

    assert _parse_list_field(float("nan")) == []


def test_parse_list_field_strips_whitespace():
    assert _parse_list_field("  Action ,  Comedy  ") == ["Action", "Comedy"]
