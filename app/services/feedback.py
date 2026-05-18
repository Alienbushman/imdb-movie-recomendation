"""T3.13: User feedback store (thumbs up / down / not interested).

Lightweight JSON-backed store living at ``data/feedback.json``. Designed to be
read by ``build_implicit_signals()`` and folded into the next model training
pass, and to flag recommendations the user has already reacted to in the UI.

Schema (data/feedback.json):

    {
        "tt1234567": {"kind": "up", "at": "2026-05-14T19:22:00+00:00"},
        "tt2345678": {"kind": "down", "at": "..."},
        ...
    }

There's exactly one feedback record per imdb_id; later interactions overwrite
the earlier one (which is the natural UX — "actually, I take it back").
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime

from app.core.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

FEEDBACK_PATH = PROJECT_ROOT / "data" / "feedback.json"

# The set of kinds the frontend can emit. Pydantic schemas validate against
# this list — keep both in sync.
VALID_KINDS = ("up", "down", "not_interested")

_lock = threading.Lock()


def _load() -> dict[str, dict]:
    if not FEEDBACK_PATH.exists():
        return {}
    try:
        with open(FEEDBACK_PATH) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read %s — starting fresh.", FEEDBACK_PATH)
        return {}


def _save(data: dict[str, dict]) -> None:
    FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FEEDBACK_PATH, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def record_feedback(imdb_id: str, kind: str) -> dict[str, str]:
    """Persist a feedback record. Returns the stored record."""
    if kind not in VALID_KINDS:
        raise ValueError(f"Unknown feedback kind {kind!r}. Allowed: {VALID_KINDS}")
    record = {"kind": kind, "at": datetime.now(UTC).isoformat()}
    with _lock:
        data = _load()
        data[imdb_id] = record
        _save(data)
    logger.info("Recorded feedback %s=%s (total entries: %d)", imdb_id, kind, len(data))
    return record


def clear_feedback(imdb_id: str) -> bool:
    """Remove a feedback record. Returns True if a record existed."""
    with _lock:
        data = _load()
        if imdb_id not in data:
            return False
        del data[imdb_id]
        _save(data)
    return True


def get_feedback_map() -> dict[str, dict]:
    """Return a copy of the full feedback map."""
    with _lock:
        return _load()


def get_feedback_for(imdb_id: str) -> dict | None:
    """Return the single record for an ID, or None."""
    return get_feedback_map().get(imdb_id)
