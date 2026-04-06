"""Tests for scored_store.query_candidates — genre filtering and min_vote_count."""

import json
import sqlite3
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from app.models.schemas import CandidateTitle, RecommendationFilters
from app.services.scored_store import query_candidates


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(
    imdb_id: str,
    title: str,
    genres: list[str],
    num_votes: int = 50_000,
    predicted_score: float = 7.5,
    title_type: str = "movie",
    is_anime: int = 0,
    year: int = 2020,
    imdb_rating: float = 7.0,
) -> dict:
    return dict(
        imdb_id=imdb_id,
        title=title,
        original_title=title,
        title_type=title_type,
        year=year,
        genres=json.dumps(genres),
        imdb_rating=imdb_rating,
        num_votes=num_votes,
        runtime_mins=120,
        language="English",
        languages=json.dumps(["English"]),
        country_code="US",
        directors=json.dumps([]),
        actors=json.dumps([]),
        writers=json.dumps([]),
        composers=json.dumps([]),
        cinematographers=json.dumps([]),
        is_anime=is_anime,
        predicted_score=predicted_score,
        scored_at=datetime.now(UTC).isoformat(),
    )


def _seed_db(conn: sqlite3.Connection, rows: list[dict]) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scored_candidates (
            imdb_id TEXT PRIMARY KEY, title TEXT NOT NULL, original_title TEXT,
            title_type TEXT NOT NULL, year INTEGER, genres TEXT NOT NULL,
            imdb_rating REAL NOT NULL, num_votes INTEGER NOT NULL,
            runtime_mins INTEGER, language TEXT,
            languages TEXT NOT NULL DEFAULT '[]',
            country_code TEXT,
            directors TEXT NOT NULL, actors TEXT NOT NULL, writers TEXT NOT NULL,
            composers TEXT NOT NULL, cinematographers TEXT NOT NULL,
            is_anime INTEGER NOT NULL DEFAULT 0,
            predicted_score REAL NOT NULL, scored_at TEXT NOT NULL
        )
    """)
    for row in rows:
        conn.execute(
            f"INSERT INTO scored_candidates VALUES ({','.join('?' * len(row))})",
            list(row.values()),
        )
    conn.commit()


@pytest.fixture()
def seeded_conn(tmp_path):
    """In-memory SQLite DB seeded with test candidates, patched into scored_store."""
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    _seed_db(conn, [
        _make_row("tt0000001", "Sci-Fi Popular",  ["Sci-Fi", "Action"],  num_votes=100_000, predicted_score=8.0),
        _make_row("tt0000002", "Sci-Fi Obscure",  ["Sci-Fi", "Drama"],   num_votes=500,     predicted_score=7.8),
        _make_row("tt0000003", "Drama Popular",   ["Drama"],             num_votes=80_000,  predicted_score=7.5),
        _make_row("tt0000004", "Horror Low",      ["Horror"],            num_votes=200,     predicted_score=7.0),
        _make_row("tt0000005", "Sci-Fi Mid",      ["Sci-Fi"],            num_votes=5_000,   predicted_score=7.2),
    ])
    conn.close()

    real_conn = sqlite3.connect(str(db_file))
    real_conn.row_factory = sqlite3.Row

    with patch("app.services.scored_store._connect", return_value=real_conn):
        yield real_conn


# ---------------------------------------------------------------------------
# min_vote_count tests
# ---------------------------------------------------------------------------

def test_min_vote_count_excludes_low_vote_titles(seeded_conn):
    results = query_candidates(
        filters=RecommendationFilters(min_vote_count=10_000),
        title_types=None,
        anime_only=False,
        top_n=10,
        dismissed_ids=set(),
        min_score=0.0,
    )
    ids = {c.imdb_id for c, _ in results}
    assert "tt0000001" in ids   # 100k votes — passes
    assert "tt0000003" in ids   # 80k votes — passes
    assert "tt0000002" not in ids  # 500 votes — excluded
    assert "tt0000004" not in ids  # 200 votes — excluded
    assert "tt0000005" not in ids  # 5k votes — excluded


def test_min_vote_count_zero_returns_all(seeded_conn):
    results = query_candidates(
        filters=RecommendationFilters(min_vote_count=0),
        title_types=None,
        anime_only=False,
        top_n=10,
        dismissed_ids=set(),
        min_score=0.0,
    )
    assert len(results) == 5


def test_min_vote_count_none_returns_all(seeded_conn):
    results = query_candidates(
        filters=None,
        title_types=None,
        anime_only=False,
        top_n=10,
        dismissed_ids=set(),
        min_score=0.0,
    )
    assert len(results) == 5


def test_min_vote_count_combined_with_genre(seeded_conn):
    """Genre filter + vote count: only Sci-Fi titles with >= 5000 votes."""
    results = query_candidates(
        filters=RecommendationFilters(genres=["Sci-Fi"], min_vote_count=5_000),
        title_types=None,
        anime_only=False,
        top_n=10,
        dismissed_ids=set(),
        min_score=0.0,
    )
    ids = {c.imdb_id for c, _ in results}
    assert ids == {"tt0000001", "tt0000005"}  # 100k and 5k votes, both Sci-Fi


# ---------------------------------------------------------------------------
# top_n slice tests
# ---------------------------------------------------------------------------

def test_top_n_limits_results(seeded_conn):
    results = query_candidates(
        filters=None,
        title_types=None,
        anime_only=False,
        top_n=2,
        dismissed_ids=set(),
        min_score=0.0,
    )
    assert len(results) == 2
    # Should be the two highest-scoring titles
    assert results[0][1] == 8.0
    assert results[1][1] == 7.8


def test_top_n_with_genre_filter_still_respects_limit(seeded_conn):
    results = query_candidates(
        filters=RecommendationFilters(genres=["Sci-Fi"]),
        title_types=None,
        anime_only=False,
        top_n=2,
        dismissed_ids=set(),
        min_score=0.0,
    )
    assert len(results) == 2
