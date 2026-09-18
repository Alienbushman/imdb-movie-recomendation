"""Unit tests for app.services.candidates — crew loading, name resolution, writer lookup."""

import gzip
import io
from pathlib import Path

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


# --- candidate cache is keyed on the filters that produced it ---


class TestCacheFingerprint:
    """Regression: editing min_rating/min_year in config.yaml used to be a
    silent no-op — the pipeline reloaded a cache built under the old filters and
    logged a normal-looking candidate count."""

    def test_fingerprint_tracks_filter_config(self, monkeypatch, tmp_path):
        from app.services import candidates as C

        monkeypatch.setattr(C, "_cache_path", lambda: tmp_path / "imdb_candidates.json")
        rows = [{"imdb_id": "tt1"}]
        C._save_cache(rows)
        assert C._load_cache() == rows

        original = C._filter_fingerprint()
        monkeypatch.setattr(C, "_filter_fingerprint", lambda: {**original, "min_rating": 1.0})
        assert C._load_cache() is None, "changed filters must invalidate the cache"

    def test_missing_fingerprint_invalidates(self, monkeypatch, tmp_path):
        from app.services import candidates as C

        monkeypatch.setattr(C, "_cache_path", lambda: tmp_path / "imdb_candidates.json")
        C._save_cache([{"imdb_id": "tt1"}])
        C._fingerprint_path().unlink()
        assert C._load_cache() is None

    def test_fingerprint_tracks_dataset_freshness(self, monkeypatch, tmp_path):
        """A dataset refresh must invalidate the cache too. The filters are
        unchanged by a refresh, so keying on them alone left five months of new
        titles outside the pool with everything looking healthy."""
        from app.services import candidates as C

        ds_dir = tmp_path / "datasets"
        ds_dir.mkdir()
        monkeypatch.setattr(C, "_dataset_dir", lambda: ds_dir)
        monkeypatch.setattr(C, "_cache_path", lambda: tmp_path / "imdb_candidates.json")
        for name in C.DATASET_URLS:
            (ds_dir / name).write_text("v1")

        C._save_cache([{"imdb_id": "tt1"}])
        assert C._load_cache() is not None

        first = next(iter(sorted(C.DATASET_URLS)))
        (ds_dir / first).write_text("v2-is-a-different-size")
        assert C._load_cache() is None, "a refreshed dataset must invalidate the cache"


# --- dataset refresh requires force ---


class TestDatasetForceDownload:
    """Regression: there was no way to refresh the IMDB dumps. download_datasets()
    skipped every file already on disk, so the scheduled refresh job returned OK
    in under a second having done nothing and the datasets sat 4.5 months stale
    while reporting success (2026-09-08)."""

    def test_existing_file_skipped_without_force(self, monkeypatch, tmp_path):
        from app.services import candidates as C

        monkeypatch.setattr(C, "_dataset_dir", lambda: tmp_path)
        monkeypatch.setattr(C, "_download_anime_list", lambda force=False: None)
        for name in C.DATASET_URLS:
            (tmp_path / name).write_text("old")
        calls = []
        monkeypatch.setattr(C.subprocess, "run", lambda *a, **k: calls.append(a))
        C.download_datasets()
        assert calls == [], "existing files must not be re-fetched by default"

    def test_force_redownloads_via_tempfile(self, monkeypatch, tmp_path):
        from app.services import candidates as C

        monkeypatch.setattr(C, "_dataset_dir", lambda: tmp_path)
        monkeypatch.setattr(C, "_download_anime_list", lambda force=False: None)
        for name in C.DATASET_URLS:
            (tmp_path / name).write_text("old")

        targets = []

        def fake_run(cmd, **kwargs):
            out = Path(cmd[cmd.index("-o") + 1])
            targets.append(out.name)
            out.write_text("new")
            return None

        monkeypatch.setattr(C.subprocess, "run", fake_run)
        C.download_datasets(force=True)

        assert targets, "force must re-fetch"
        assert all(t.endswith(".tmp") for t in targets), "must download to a temp file"
        for name in C.DATASET_URLS:
            assert (tmp_path / name).read_text() == "new"
            assert not (tmp_path / (name + ".tmp")).exists(), "temp file must be moved, not left"


# --- anime whitelist accepts both upstream shapes ---


class TestAnimeIdParsing:
    """Regression: upstream Fribb/anime-lists moved imdb_id from a string to a
    list. Discovered 2026-09-18 when the file refreshed for the first time since
    April and the pipeline died with "unhashable type: 'list'". The file is now
    100% lists/nulls, so the string-only parser would have yielded an empty set
    even without the crash."""

    @staticmethod
    def _write(tmp_path, entries):
        import json

        (tmp_path / "anime-list-mini.json").write_text(json.dumps(entries))

    def test_list_shape(self, monkeypatch, tmp_path):
        from app.services import candidates as C

        monkeypatch.setattr(C, "_dataset_dir", lambda: tmp_path)
        self._write(tmp_path, [{"imdb_id": ["tt1", "tt2"]}, {"imdb_id": None}])
        assert C._load_anime_ids() == {"tt1", "tt2"}

    def test_string_shape_still_supported(self, monkeypatch, tmp_path):
        from app.services import candidates as C

        monkeypatch.setattr(C, "_dataset_dir", lambda: tmp_path)
        self._write(tmp_path, [{"imdb_id": "tt1"}, {"imdb_id": ""}])
        assert C._load_anime_ids() == {"tt1"}

    def test_mixed_and_malformed(self, monkeypatch, tmp_path):
        from app.services import candidates as C

        monkeypatch.setattr(C, "_dataset_dir", lambda: tmp_path)
        self._write(tmp_path, [{"imdb_id": ["tt1", None, 7]}, {"imdb_id": "tt2"}, {}])
        assert C._load_anime_ids() == {"tt1", "tt2"}

    def test_empty_result_is_logged_as_error(self, monkeypatch, tmp_path, caplog):
        from app.services import candidates as C

        monkeypatch.setattr(C, "_dataset_dir", lambda: tmp_path)
        self._write(tmp_path, [{"imdb_id": None}, {"imdb_id": []}])
        with caplog.at_level("ERROR"):
            assert C._load_anime_ids() == set()
        assert any("parsed to 0 IDs" in r.message for r in caplog.records)
