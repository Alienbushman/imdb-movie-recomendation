"""Unit tests for app.services.candidates — crew loading, name resolution, writer lookup."""

import gzip
import io

from app.services.candidates import _load_crew_data, _resolve_names

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tsv_gz(rows: list[str]) -> bytes:
    """Build an in-memory gzipped TSV from a list of header + data lines."""
    content = "\n".join(rows).encode()
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as f:
        f.write(content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# _resolve_names
# ---------------------------------------------------------------------------

class TestResolveNames:
    def test_resolves_known_nconsts(self):
        raw = {"tt001": ["nm001", "nm002"]}
        lookup = {"nm001": "Alice", "nm002": "Bob"}
        result = _resolve_names(raw, lookup)
        assert result == {"tt001": ["Alice", "Bob"]}

    def test_drops_unknown_nconsts(self):
        raw = {"tt001": ["nm001", "nm_unknown"]}
        lookup = {"nm001": "Alice"}
        result = _resolve_names(raw, lookup)
        assert result == {"tt001": ["Alice"]}

    def test_drops_title_if_all_nconsts_unknown(self):
        raw = {"tt001": ["nm_unknown"]}
        lookup = {"nm001": "Alice"}
        result = _resolve_names(raw, lookup)
        assert "tt001" not in result

    def test_empty_raw(self):
        assert _resolve_names({}, {"nm001": "Alice"}) == {}

    def test_empty_lookup(self):
        raw = {"tt001": ["nm001"]}
        result = _resolve_names(raw, {})
        assert result == {}

    def test_multiple_titles(self):
        raw = {"tt001": ["nm001"], "tt002": ["nm002", "nm003"]}
        lookup = {"nm001": "Alice", "nm002": "Bob", "nm003": "Carol"}
        result = _resolve_names(raw, lookup)
        assert result["tt001"] == ["Alice"]
        assert result["tt002"] == ["Bob", "Carol"]


# ---------------------------------------------------------------------------
# _load_crew_data — writer parsing
# ---------------------------------------------------------------------------

class TestLoadCrewData:
    def test_writers_populated_from_crew(self, tmp_path, monkeypatch):
        """Titles with writer nconsts in crew.tsv produce entries in raw_writers."""
        crew_gz = _make_tsv_gz([
            "tconst\tdirectors\twriters",
            "tt001\tnm010\tnm001,nm002",
            "tt002\tnm011\t\\N",          # no writers
            "tt003\t\\N\tnm003",
        ])
        crew_file = tmp_path / "title.crew.tsv.gz"
        crew_file.write_bytes(crew_gz)

        # Patch settings so candidates reads from tmp_path
        from app.core.config import get_settings
        settings = get_settings()
        original_crew = settings.imdb_datasets.title_crew
        settings.imdb_datasets.title_crew = str(
            crew_file.relative_to(crew_file.anchor)
        )

        # Patch PROJECT_ROOT to tmp_path's root so the path resolves
        import app.services.candidates as candidates_mod
        monkeypatch.setattr(candidates_mod, "PROJECT_ROOT", crew_file.parent.parent)

        # Also fix the relative path so PROJECT_ROOT / relative == crew_file
        rel = "title.crew.tsv.gz"
        settings.imdb_datasets.title_crew = rel
        monkeypatch.setattr(
            candidates_mod, "PROJECT_ROOT", crew_file.parent
        )

        title_ids = {"tt001", "tt002", "tt003"}
        raw_writers, raw_directors, needed_nconsts = _load_crew_data(title_ids)

        assert "tt001" in raw_writers
        assert set(raw_writers["tt001"]) == {"nm001", "nm002"}
        assert "tt003" in raw_writers
        assert raw_writers["tt003"] == ["nm003"]
        # tt002 has \\N writers — should not appear
        assert "tt002" not in raw_writers

        # needed_nconsts should include all writer + director nconsts
        assert "nm001" in needed_nconsts
        assert "nm002" in needed_nconsts
        assert "nm003" in needed_nconsts

        # Restore settings
        settings.imdb_datasets.title_crew = original_crew

    def test_missing_crew_file_returns_empty(self, tmp_path, monkeypatch):
        """If crew file doesn't exist, returns empty dicts gracefully."""
        import app.services.candidates as candidates_mod
        monkeypatch.setattr(candidates_mod, "PROJECT_ROOT", tmp_path)

        from app.core.config import get_settings
        settings = get_settings()
        settings.imdb_datasets.title_crew = "nonexistent.tsv.gz"

        raw_writers, raw_directors, needed_nconsts = _load_crew_data({"tt001"})

        assert raw_writers == {}
        assert raw_directors == {}
        assert needed_nconsts == set()

    def test_title_ids_filter_applied(self, tmp_path, monkeypatch):
        """Only rows whose tconst is in title_ids are loaded."""
        crew_gz = _make_tsv_gz([
            "tconst\tdirectors\twriters",
            "tt001\tnm010\tnm001",
            "tt002\tnm011\tnm002",   # not in title_ids
        ])
        crew_file = tmp_path / "title.crew.tsv.gz"
        crew_file.write_bytes(crew_gz)

        import app.services.candidates as candidates_mod
        monkeypatch.setattr(candidates_mod, "PROJECT_ROOT", tmp_path)

        from app.core.config import get_settings
        settings = get_settings()
        settings.imdb_datasets.title_crew = "title.crew.tsv.gz"

        raw_writers, _, _ = _load_crew_data({"tt001"})  # only tt001 requested

        assert "tt001" in raw_writers
        assert "tt002" not in raw_writers


# ---------------------------------------------------------------------------
# Writer lookup round-trip: raw_writers → resolve → rated_writers shape
# ---------------------------------------------------------------------------

class TestWriterRoundTrip:
    def test_resolve_produces_rated_writers_shape(self):
        """After resolving, rated_writers has the shape expected by build_taste_profile."""
        raw_writers = {
            "tt001": ["nm001", "nm002"],
            "tt002": ["nm003"],
        }
        name_lookup = {"nm001": "Writer A", "nm002": "Writer B", "nm003": "Writer C"}
        seen_ids = {"tt001", "tt002"}

        writers_by_title = _resolve_names(raw_writers, name_lookup)
        rated_writers = {
            tid: writers_by_title[tid]
            for tid in seen_ids
            if tid in writers_by_title
        }

        assert rated_writers["tt001"] == ["Writer A", "Writer B"]
        assert rated_writers["tt002"] == ["Writer C"]

    def test_rated_writers_feeds_taste_profile(self):
        """rated_writers dict produces non-empty writer_avg in TasteProfile."""
        from app.models.schemas import RatedTitle
        from app.services.features import build_taste_profile

        titles = [
            RatedTitle(
                imdb_id="tt001", title="Film A", original_title="Film A",
                title_type="movie", user_rating=9, date_rated="2024-01-01",
                imdb_rating=8.0, runtime_mins=120, year=2020,
                genres=["Drama"], num_votes=50000,
                release_date="2020-01-01", directors=[], url="",
            ),
            RatedTitle(
                imdb_id="tt002", title="Film B", original_title="Film B",
                title_type="movie", user_rating=6, date_rated="2024-01-01",
                imdb_rating=7.0, runtime_mins=90, year=2019,
                genres=["Comedy"], num_votes=30000,
                release_date="2019-01-01", directors=[], url="",
            ),
        ]
        rated_writers = {
            "tt001": ["Writer A", "Writer B"],
            "tt002": ["Writer A"],
        }

        profile = build_taste_profile(titles, rated_writers=rated_writers)

        assert "Writer A" in profile.writer_avg, "Writer A should be in taste profile"
        assert "Writer B" in profile.writer_avg, "Writer B should be in taste profile"
        # Writer A appears in a 9-rated and a 6-rated film — avg pulled toward global mean
        assert 6.0 < profile.writer_avg["Writer A"] < 9.0
