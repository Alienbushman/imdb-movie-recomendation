"""Unit tests for app.services.dismissed — file-based dismiss/restore logic."""

import json
from unittest.mock import patch

import pytest

from app.services.dismissed import (
    _load_dismissed_ids,
    _save_dismissed_ids,
    dismiss_title,
    get_dismissed_ids,
    restore_title,
)


@pytest.fixture()
def dismissed_file(tmp_path):
    """Patch DISMISSED_PATH to use a temp directory."""
    path = tmp_path / "dismissed.json"
    with patch("app.services.dismissed.DISMISSED_PATH", path):
        yield path


class TestLoadSaveDismissedIds:
    def test_load_no_file(self, dismissed_file):
        ids = _load_dismissed_ids()
        assert ids == set()

    def test_save_and_load_round_trip(self, dismissed_file):
        _save_dismissed_ids({"tt001", "tt002"})
        loaded = _load_dismissed_ids()
        assert loaded == {"tt001", "tt002"}

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "nested" / "deep" / "dismissed.json"
        with patch("app.services.dismissed.DISMISSED_PATH", path):
            _save_dismissed_ids({"tt001"})
        assert path.exists()
        assert json.loads(path.read_text()) == ["tt001"]

    def test_saved_json_is_sorted(self, dismissed_file):
        _save_dismissed_ids({"tt003", "tt001", "tt002"})
        data = json.loads(dismissed_file.read_text())
        assert data == ["tt001", "tt002", "tt003"]


class TestDismissTitle:
    def test_dismiss_new_title(self, dismissed_file):
        assert dismiss_title("tt001") is True
        assert "tt001" in _load_dismissed_ids()

    def test_dismiss_duplicate_returns_false(self, dismissed_file):
        dismiss_title("tt001")
        assert dismiss_title("tt001") is False

    def test_dismiss_multiple_titles(self, dismissed_file):
        dismiss_title("tt001")
        dismiss_title("tt002")
        ids = _load_dismissed_ids()
        assert ids == {"tt001", "tt002"}


class TestRestoreTitle:
    def test_restore_existing_title(self, dismissed_file):
        dismiss_title("tt001")
        assert restore_title("tt001") is True
        assert "tt001" not in _load_dismissed_ids()

    def test_restore_nonexistent_returns_false(self, dismissed_file):
        assert restore_title("tt001") is False

    def test_restore_preserves_other_ids(self, dismissed_file):
        dismiss_title("tt001")
        dismiss_title("tt002")
        restore_title("tt001")
        ids = _load_dismissed_ids()
        assert ids == {"tt002"}


class TestGetDismissedIds:
    def test_returns_empty_set_when_no_file(self, dismissed_file):
        assert get_dismissed_ids() == set()

    def test_returns_dismissed_ids(self, dismissed_file):
        dismiss_title("tt001")
        dismiss_title("tt002")
        assert get_dismissed_ids() == {"tt001", "tt002"}
