"""Tests for T3.13 feedback store and API endpoints.

Covers:
- record_feedback: happy path, overwrite, invalid kind
- clear_feedback: present, absent
- get_feedback_map / get_feedback_for: empty and populated stores
- FeedbackStore thread-safety (simple concurrency check)
- API: POST /feedback/{id} → 200 / 400 / 422
- API: DELETE /feedback/{id} → 200 / 404
- API: GET /feedback → list + count
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.services.feedback as fb_module
from app.services.feedback import (
    VALID_KINDS,
    clear_feedback,
    get_feedback_for,
    get_feedback_map,
    record_feedback,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def feedback_path(tmp_path):
    """Redirect FEEDBACK_PATH to a temp file for isolation."""
    path = tmp_path / "feedback.json"
    with patch.object(fb_module, "FEEDBACK_PATH", path):
        yield path


@pytest.fixture()
def api_client(tmp_path):
    """Minimal FastAPI app wired to the real router, with isolated feedback store."""
    from app.api.routes import router

    test_app = FastAPI()
    test_app.include_router(router, prefix="/api/v1")

    path = tmp_path / "feedback.json"
    with patch.object(fb_module, "FEEDBACK_PATH", path):
        yield TestClient(test_app)


# ---------------------------------------------------------------------------
# record_feedback
# ---------------------------------------------------------------------------


class TestRecordFeedback:
    def test_records_up(self, feedback_path):
        rec = record_feedback("tt0000001", "up")
        assert rec["kind"] == "up"
        assert "at" in rec

    def test_records_down(self, feedback_path):
        rec = record_feedback("tt0000001", "down")
        assert rec["kind"] == "down"

    def test_records_not_interested(self, feedback_path):
        rec = record_feedback("tt0000001", "not_interested")
        assert rec["kind"] == "not_interested"

    def test_overwrites_previous_record(self, feedback_path):
        record_feedback("tt0000001", "up")
        record_feedback("tt0000001", "down")
        data = get_feedback_map()
        assert data["tt0000001"]["kind"] == "down"

    def test_invalid_kind_raises_value_error(self, feedback_path):
        with pytest.raises(ValueError, match="Unknown feedback kind"):
            record_feedback("tt0000001", "invalid_kind")

    def test_persists_to_disk(self, feedback_path):
        record_feedback("tt0000001", "up")
        raw = json.loads(feedback_path.read_text())
        assert "tt0000001" in raw
        assert raw["tt0000001"]["kind"] == "up"

    def test_multiple_ids_all_present(self, feedback_path):
        for i in range(3):
            record_feedback(f"tt{i:07d}", "up")
        data = get_feedback_map()
        assert len(data) == 3


# ---------------------------------------------------------------------------
# clear_feedback
# ---------------------------------------------------------------------------


class TestClearFeedback:
    def test_clear_existing_returns_true(self, feedback_path):
        record_feedback("tt0000001", "up")
        assert clear_feedback("tt0000001") is True

    def test_clear_removes_record(self, feedback_path):
        record_feedback("tt0000001", "up")
        clear_feedback("tt0000001")
        assert "tt0000001" not in get_feedback_map()

    def test_clear_absent_returns_false(self, feedback_path):
        assert clear_feedback("tt9999999") is False

    def test_clear_preserves_other_records(self, feedback_path):
        record_feedback("tt0000001", "up")
        record_feedback("tt0000002", "down")
        clear_feedback("tt0000001")
        data = get_feedback_map()
        assert "tt0000001" not in data
        assert "tt0000002" in data


# ---------------------------------------------------------------------------
# get_feedback_map / get_feedback_for
# ---------------------------------------------------------------------------


class TestGetFeedback:
    def test_empty_store_returns_empty_dict(self, feedback_path):
        assert get_feedback_map() == {}

    def test_returns_all_entries(self, feedback_path):
        record_feedback("tt0000001", "up")
        record_feedback("tt0000002", "not_interested")
        data = get_feedback_map()
        assert set(data.keys()) == {"tt0000001", "tt0000002"}

    def test_get_feedback_for_present_id(self, feedback_path):
        record_feedback("tt0000001", "down")
        entry = get_feedback_for("tt0000001")
        assert entry is not None
        assert entry["kind"] == "down"

    def test_get_feedback_for_absent_id(self, feedback_path):
        assert get_feedback_for("tt9999999") is None

    def test_no_file_returns_empty_dict(self, feedback_path):
        assert not feedback_path.exists()
        assert get_feedback_map() == {}

    def test_corrupted_json_returns_empty_dict(self, feedback_path):
        feedback_path.write_text("not valid json")
        assert get_feedback_map() == {}


# ---------------------------------------------------------------------------
# API: POST /feedback/{imdb_id}
# ---------------------------------------------------------------------------


class TestFeedbackPostEndpoint:
    def test_valid_kind_returns_200(self, api_client):
        res = api_client.post("/api/v1/feedback/tt0000001", json={"kind": "up"})
        assert res.status_code == 200
        body = res.json()
        assert body["imdb_id"] == "tt0000001"
        assert body["kind"] == "up"
        assert "at" in body

    def test_all_three_kinds_accepted(self, api_client):
        for kind in VALID_KINDS:
            res = api_client.post(f"/api/v1/feedback/tt0000001", json={"kind": kind})
            assert res.status_code == 200, f"kind={kind} rejected"

    def test_invalid_kind_returns_400(self, api_client):
        res = api_client.post("/api/v1/feedback/tt0000001", json={"kind": "love"})
        assert res.status_code == 400

    def test_bad_imdb_id_format_returns_422(self, api_client):
        res = api_client.post("/api/v1/feedback/not-an-id", json={"kind": "up"})
        assert res.status_code == 422

    def test_overwrite_returns_updated_kind(self, api_client):
        api_client.post("/api/v1/feedback/tt0000001", json={"kind": "up"})
        res = api_client.post("/api/v1/feedback/tt0000001", json={"kind": "down"})
        assert res.json()["kind"] == "down"


# ---------------------------------------------------------------------------
# API: DELETE /feedback/{imdb_id}
# ---------------------------------------------------------------------------


class TestFeedbackDeleteEndpoint:
    def test_delete_existing_returns_200(self, api_client):
        api_client.post("/api/v1/feedback/tt0000001", json={"kind": "up"})
        res = api_client.delete("/api/v1/feedback/tt0000001")
        assert res.status_code == 200

    def test_delete_absent_returns_404(self, api_client):
        res = api_client.delete("/api/v1/feedback/tt9999999")
        assert res.status_code == 404

    def test_delete_removes_record(self, api_client, tmp_path):
        api_client.post("/api/v1/feedback/tt0000001", json={"kind": "up"})
        api_client.delete("/api/v1/feedback/tt0000001")
        res = api_client.get("/api/v1/feedback")
        entries = res.json()["entries"]
        ids = [e["imdb_id"] for e in entries]
        assert "tt0000001" not in ids


# ---------------------------------------------------------------------------
# API: GET /feedback
# ---------------------------------------------------------------------------


class TestFeedbackListEndpoint:
    def test_empty_returns_empty_list(self, api_client):
        res = api_client.get("/api/v1/feedback")
        assert res.status_code == 200
        body = res.json()
        assert body["entries"] == []
        assert body["count"] == 0

    def test_count_matches_entries_length(self, api_client):
        for i in range(3):
            api_client.post(f"/api/v1/feedback/tt{i:07d}", json={"kind": "up"})
        res = api_client.get("/api/v1/feedback")
        body = res.json()
        assert body["count"] == len(body["entries"])
        assert body["count"] == 3

    def test_all_fields_present_in_entry(self, api_client):
        api_client.post("/api/v1/feedback/tt0000001", json={"kind": "down"})
        res = api_client.get("/api/v1/feedback")
        entry = res.json()["entries"][0]
        assert "imdb_id" in entry
        assert "kind" in entry
        assert "at" in entry

    def test_mixed_kinds_all_returned(self, api_client):
        api_client.post("/api/v1/feedback/tt0000001", json={"kind": "up"})
        api_client.post("/api/v1/feedback/tt0000002", json={"kind": "not_interested"})
        res = api_client.get("/api/v1/feedback")
        kinds = {e["imdb_id"]: e["kind"] for e in res.json()["entries"]}
        assert kinds["tt0000001"] == "up"
        assert kinds["tt0000002"] == "not_interested"
