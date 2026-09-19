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


# --- seen-ID ledger survives IMDB's moving export window ---


class TestSeenLedger:
    """IMDB's paginated ratings view stops at 2250 while reporting a higher
    total, so the export is a moving window and the oldest ratings drop out.
    Observed 2026-09-19: titles rated in 2012-13 were being recommended back."""

    def test_ledger_accumulates_across_scrapes(self, monkeypatch, tmp_path):
        from app.services import ingest as I

        monkeypatch.setattr(I, "_seen_ledger_path", lambda: tmp_path / "seen_ids.json")
        assert I.merge_seen_ledger({"tt1", "tt2"}) == {"tt1", "tt2"}
        # Next scrape has lost tt1 (fell outside the window) and gained tt3.
        assert I.merge_seen_ledger({"tt2", "tt3"}) == {"tt1", "tt2", "tt3"}

    def test_dropped_titles_are_reported(self, monkeypatch, tmp_path, caplog):
        from app.services import ingest as I

        monkeypatch.setattr(I, "_seen_ledger_path", lambda: tmp_path / "seen_ids.json")
        I.merge_seen_ledger({"tt1", "tt2"})
        with caplog.at_level("WARNING"):
            I.merge_seen_ledger({"tt2"})
        assert any("missing from the latest export" in r.message for r in caplog.records)

    def test_corrupt_ledger_does_not_lose_current_scrape(self, monkeypatch, tmp_path):
        from app.services import ingest as I

        p = tmp_path / "seen_ids.json"
        monkeypatch.setattr(I, "_seen_ledger_path", lambda: p)
        p.write_text("{not json")
        assert I.merge_seen_ledger({"tt9"}) == {"tt9"}

    def test_get_seen_imdb_ids_stays_pure(self, tmp_path, monkeypatch):
        from app.services import ingest as I

        monkeypatch.setattr(I, "_seen_ledger_path", lambda: tmp_path / "seen_ids.json")
        titles = [_make_rated("tt5")]
        assert I.get_seen_imdb_ids(titles) == {"tt5"}
        assert not (tmp_path / "seen_ids.json").exists(), "the getter must not write"

    def test_cold_start_reads_ledger_from_disk(self, monkeypatch, tmp_path):
        """The fast recommendation path used to read seen IDs from in-process
        state, which is empty on a cold start — so a freshly restarted process
        excluded nothing and recommended already-rated films."""
        import json as _json

        from app.services import ingest as I

        p = tmp_path / "seen_ids.json"
        monkeypatch.setattr(I, "_seen_ledger_path", lambda: p)
        assert I.load_seen_ledger() == set()
        p.write_text(_json.dumps(["tt1", "tt2"]))
        assert I.load_seen_ledger() == {"tt1", "tt2"}

    def test_corrupt_ledger_reads_as_empty(self, monkeypatch, tmp_path):
        from app.services import ingest as I

        p = tmp_path / "seen_ids.json"
        monkeypatch.setattr(I, "_seen_ledger_path", lambda: p)
        p.write_text("{nope")
        assert I.load_seen_ledger() == set()
