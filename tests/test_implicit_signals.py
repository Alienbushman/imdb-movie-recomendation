"""Tests for T2.8 implicit-negative training rows (implicit_signals.py).

Covers:
- _build_rows: happy path, unresolved IDs skipped, empty input
- build_implicit_training_rows: use_dismissals / use_feedback toggles
- ExtraTrainingRow: correct label + weight + source tag
- Integration: dismissed ID wired through to training label
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.schemas import TasteProfile
from app.services.model import ExtraTrainingRow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_taste() -> TasteProfile:
    return TasteProfile()


def _make_candidate_dict(imdb_id: str = "tt0000001", **kwargs) -> dict:
    base = {
        "imdb_id": imdb_id,
        "title": "Test Movie",
        "title_type": "movie",
        "imdb_rating": 7.0,
        "year": 2020,
        "genres": ["Drama"],
        "num_votes": 50_000,
        "runtime_mins": 100,
        "language": "English",
        "country_code": "US",
        "directors": [],
        "actors": [],
        "original_title": "Test Movie",
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# ExtraTrainingRow schema
# ---------------------------------------------------------------------------

class TestExtraTrainingRow:
    def test_label_and_weight_stored(self):
        from app.services.features import ALL_GENRES
        from app.models.schemas import FeatureVector

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
        )
        row = ExtraTrainingRow(feature_vector=fv, label=2.0, weight=0.3, source="dismissal")
        assert row.label == 2.0
        assert row.weight == 0.3
        assert row.source == "dismissal"


# ---------------------------------------------------------------------------
# _build_rows: the internal row-assembly helper
# ---------------------------------------------------------------------------

class TestBuildRows:
    def _patch_lookup(self, imdb_id: str):
        """Patch both lookup helpers so _build_rows can resolve the given ID."""
        from app.models.schemas import CandidateTitle

        cand = CandidateTitle(**_make_candidate_dict(imdb_id=imdb_id))
        return patch(
            "app.services.implicit_signals._lookup_from_db",
            return_value={imdb_id: cand},
        )

    def test_happy_path_returns_row_per_resolved_id(self):
        from app.services.implicit_signals import _build_rows

        with self._patch_lookup("tt0000001"):
            rows = _build_rows(["tt0000001"], _make_taste(), label=2.0, weight=0.3, source="dismissal")
        assert len(rows) == 1
        assert rows[0].label == 2.0
        assert rows[0].weight == 0.3
        assert rows[0].source == "dismissal"

    def test_unresolved_ids_skipped(self):
        from app.services.implicit_signals import _build_rows

        with (
            patch("app.services.implicit_signals._lookup_from_db", return_value={}),
            patch("app.services.implicit_signals._lookup_from_cache", return_value={}),
        ):
            rows = _build_rows(["tt9999999"], _make_taste(), label=2.0, weight=0.3, source="dismissal")
        assert rows == []

    def test_empty_input_returns_empty(self):
        from app.services.implicit_signals import _build_rows

        rows = _build_rows([], _make_taste(), label=2.0, weight=0.3, source="dismissal")
        assert rows == []

    def test_none_id_skipped(self):
        from app.services.implicit_signals import _build_rows

        with (
            patch("app.services.implicit_signals._lookup_from_db", return_value={}),
            patch("app.services.implicit_signals._lookup_from_cache", return_value={}),
        ):
            rows = _build_rows([None, ""], _make_taste(), label=2.0, weight=0.3, source="dismissal")
        assert rows == []

    def test_db_fallback_to_cache(self):
        from app.services.implicit_signals import _build_rows
        from app.models.schemas import CandidateTitle

        cand = CandidateTitle(**_make_candidate_dict(imdb_id="tt0000002"))
        with (
            patch("app.services.implicit_signals._lookup_from_db", return_value={}),
            patch("app.services.implicit_signals._lookup_from_cache", return_value={"tt0000002": cand}),
        ):
            rows = _build_rows(["tt0000002"], _make_taste(), label=3.0, weight=0.5, source="feedback_down")
        assert len(rows) == 1
        assert rows[0].source == "feedback_down"

    def test_multiple_ids_returns_multiple_rows(self):
        from app.services.implicit_signals import _build_rows
        from app.models.schemas import CandidateTitle

        ids = ["tt0000001", "tt0000002"]
        cands = {i: CandidateTitle(**_make_candidate_dict(imdb_id=i)) for i in ids}
        with patch("app.services.implicit_signals._lookup_from_db", return_value=cands):
            rows = _build_rows(ids, _make_taste(), label=2.0, weight=0.3, source="dismissal")
        assert len(rows) == 2

    def test_feature_vector_is_not_none(self):
        from app.services.implicit_signals import _build_rows
        from app.models.schemas import CandidateTitle

        cand = CandidateTitle(**_make_candidate_dict(imdb_id="tt0000001"))
        with patch("app.services.implicit_signals._lookup_from_db", return_value={"tt0000001": cand}):
            rows = _build_rows(["tt0000001"], _make_taste(), label=2.0, weight=0.3, source="dismissal")
        assert rows[0].feature_vector is not None


# ---------------------------------------------------------------------------
# build_implicit_training_rows — config toggles
# ---------------------------------------------------------------------------

class TestBuildImplicitTrainingRows:
    def _mock_cfg(self, use_dismissals=True, use_feedback=True):
        from app.core.config import ModelTrainingConfig
        return ModelTrainingConfig(
            use_dismissals=use_dismissals,
            dismissal_label=2.0,
            dismissal_weight=0.3,
            use_feedback=use_feedback,
            feedback_up_label=9.0,
            feedback_down_label=3.0,
            feedback_not_interested_label=2.0,
            feedback_weight=0.3,
        )

    def test_use_dismissals_false_skips_dismissed(self):
        from app.services.implicit_signals import build_implicit_training_rows

        cfg = self._mock_cfg(use_dismissals=False, use_feedback=False)
        mock_settings = MagicMock()
        mock_settings.model.training = cfg
        with (
            patch("app.services.implicit_signals.get_settings", return_value=mock_settings),
            patch("app.services.implicit_signals.get_dismissed_ids", return_value={"tt0000001"}) as mock_dis,
            patch("app.services.implicit_signals.get_feedback_map", return_value={}),
        ):
            rows = build_implicit_training_rows(_make_taste())
        mock_dis.assert_not_called()
        assert rows == []

    def test_use_feedback_false_skips_feedback(self):
        from app.services.implicit_signals import build_implicit_training_rows

        cfg = self._mock_cfg(use_dismissals=False, use_feedback=False)
        mock_settings = MagicMock()
        mock_settings.model.training = cfg
        with (
            patch("app.services.implicit_signals.get_settings", return_value=mock_settings),
            patch("app.services.implicit_signals.get_dismissed_ids", return_value=set()),
            patch("app.services.implicit_signals.get_feedback_map", return_value={}) as mock_fb,
        ):
            rows = build_implicit_training_rows(_make_taste())
        mock_fb.assert_not_called()
        assert rows == []

    def test_dismissal_rows_tagged_with_source(self):
        from app.services.implicit_signals import build_implicit_training_rows
        from app.models.schemas import CandidateTitle

        cfg = self._mock_cfg(use_dismissals=True, use_feedback=False)
        mock_settings = MagicMock()
        mock_settings.model.training = cfg
        cand = CandidateTitle(**_make_candidate_dict(imdb_id="tt0000001"))
        with (
            patch("app.services.implicit_signals.get_settings", return_value=mock_settings),
            patch("app.services.implicit_signals.get_dismissed_ids", return_value={"tt0000001"}),
            patch("app.services.implicit_signals.get_feedback_map", return_value={}),
            patch("app.services.implicit_signals._lookup_from_db", return_value={"tt0000001": cand}),
        ):
            rows = build_implicit_training_rows(_make_taste())
        sources = [r.source for r in rows]
        assert all(s == "dismissal" for s in sources)

    def test_dismissal_label_and_weight_match_config(self):
        from app.services.implicit_signals import build_implicit_training_rows
        from app.models.schemas import CandidateTitle

        cfg = self._mock_cfg(use_dismissals=True, use_feedback=False)
        cfg.dismissal_label = 1.5
        cfg.dismissal_weight = 0.2
        mock_settings = MagicMock()
        mock_settings.model.training = cfg
        cand = CandidateTitle(**_make_candidate_dict(imdb_id="tt0000001"))
        with (
            patch("app.services.implicit_signals.get_settings", return_value=mock_settings),
            patch("app.services.implicit_signals.get_dismissed_ids", return_value={"tt0000001"}),
            patch("app.services.implicit_signals.get_feedback_map", return_value={}),
            patch("app.services.implicit_signals._lookup_from_db", return_value={"tt0000001": cand}),
        ):
            rows = build_implicit_training_rows(_make_taste())
        assert rows[0].label == 1.5
        assert rows[0].weight == 0.2

    def test_feedback_up_gets_high_label(self):
        from app.services.implicit_signals import build_implicit_training_rows
        from app.models.schemas import CandidateTitle

        cfg = self._mock_cfg(use_dismissals=False, use_feedback=True)
        mock_settings = MagicMock()
        mock_settings.model.training = cfg
        cand = CandidateTitle(**_make_candidate_dict(imdb_id="tt0000002"))
        with (
            patch("app.services.implicit_signals.get_settings", return_value=mock_settings),
            patch("app.services.implicit_signals.get_dismissed_ids", return_value=set()),
            patch("app.services.implicit_signals.get_feedback_map",
                  return_value={"tt0000002": {"kind": "up"}}),
            patch("app.services.implicit_signals._lookup_from_db", return_value={"tt0000002": cand}),
        ):
            rows = build_implicit_training_rows(_make_taste())
        feedback_up = [r for r in rows if r.source == "feedback_up"]
        assert len(feedback_up) == 1
        assert feedback_up[0].label == 9.0

    def test_both_disabled_returns_empty(self):
        from app.services.implicit_signals import build_implicit_training_rows

        cfg = self._mock_cfg(use_dismissals=False, use_feedback=False)
        mock_settings = MagicMock()
        mock_settings.model.training = cfg
        with (
            patch("app.services.implicit_signals.get_settings", return_value=mock_settings),
            patch("app.services.implicit_signals.get_dismissed_ids", return_value=set()),
            patch("app.services.implicit_signals.get_feedback_map", return_value={}),
        ):
            rows = build_implicit_training_rows(_make_taste())
        assert rows == []


# ---------------------------------------------------------------------------
# _lookup_from_db and _lookup_from_cache (no real DB — skip if paths missing)
# ---------------------------------------------------------------------------

class TestLookupHelpers:
    def test_lookup_from_db_missing_db_returns_empty(self):
        from app.services.implicit_signals import _lookup_from_db

        with patch("app.services.implicit_signals._SCORED_DB_PATH", Path("/nonexistent/path.db")):
            result = _lookup_from_db({"tt0000001"})
        assert result == {}

    def test_lookup_from_cache_missing_file_returns_empty(self):
        from app.services.implicit_signals import _lookup_from_cache

        with patch("app.services.implicit_signals._CANDIDATES_CACHE", Path("/nonexistent/cache.json")):
            result = _lookup_from_cache({"tt0000001"})
        assert result == {}

    def test_lookup_from_cache_bad_json_returns_empty(self):
        from app.services.implicit_signals import _lookup_from_cache

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            f.write("not valid json")
            tmp_path = Path(f.name)
        try:
            with patch("app.services.implicit_signals._CANDIDATES_CACHE", tmp_path):
                result = _lookup_from_cache({"tt0000001"})
            assert result == {}
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_lookup_from_cache_resolves_matching_id(self):
        from app.services.implicit_signals import _lookup_from_cache

        cand_dict = _make_candidate_dict(imdb_id="tt0000099")
        with tempfile.NamedTemporaryFile(
            suffix=".json", mode="w", delete=False, encoding="utf-8"
        ) as f:
            json.dump([cand_dict], f)
            tmp_path = Path(f.name)
        try:
            with patch("app.services.implicit_signals._CANDIDATES_CACHE", tmp_path):
                result = _lookup_from_cache({"tt0000099"})
            assert "tt0000099" in result
        finally:
            tmp_path.unlink(missing_ok=True)
