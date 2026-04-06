"""Unit tests for app.services.ingest — watchlist parsing helpers."""

from app.models.schemas import RatedTitle
from app.services.ingest import get_seen_imdb_ids


def _make_rated(imdb_id: str) -> RatedTitle:
    return RatedTitle(
        imdb_id=imdb_id,
        title="Test",
        original_title="Test",
        title_type="movie",
        user_rating=7,
        date_rated="2024-01-01",
        imdb_rating=7.0,
        runtime_mins=120,
        year=2020,
        genres=["Drama"],
        num_votes=10_000,
        release_date="2020-01-01",
        directors=[],
        url="https://www.imdb.com/title/tt0000001/",
    )


class TestGetSeenImdbIds:
    def test_extracts_ids(self):
        titles = [_make_rated("tt001"), _make_rated("tt002"), _make_rated("tt003")]
        assert get_seen_imdb_ids(titles) == {"tt001", "tt002", "tt003"}

    def test_empty_list(self):
        assert get_seen_imdb_ids([]) == set()

    def test_deduplicates(self):
        titles = [_make_rated("tt001"), _make_rated("tt001")]
        assert get_seen_imdb_ids(titles) == {"tt001"}
