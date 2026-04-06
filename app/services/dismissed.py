import json
import logging
import sqlite3
import threading

from app.core.config import PROJECT_ROOT
from app.models.schemas import DismissedTitle

logger = logging.getLogger(__name__)

DISMISSED_PATH = PROJECT_ROOT / "data" / "dismissed.json"

_lock = threading.Lock()


def _load_dismissed_ids() -> set[str]:
    """Load dismissed IMDB IDs from disk."""
    if not DISMISSED_PATH.exists():
        return set()
    with open(DISMISSED_PATH) as f:
        data = json.load(f)
    return set(data)


def _save_dismissed_ids(ids: set[str]) -> None:
    """Persist dismissed IMDB IDs to disk."""
    DISMISSED_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DISMISSED_PATH, "w") as f:
        json.dump(sorted(ids), f, indent=2)


def get_dismissed_ids() -> set[str]:
    """Return the current set of dismissed IMDB IDs."""
    with _lock:
        return _load_dismissed_ids()


def dismiss_title(imdb_id: str) -> bool:
    """Add an IMDB ID to the dismissed set. Returns True if newly added."""
    with _lock:
        ids = _load_dismissed_ids()
        if imdb_id in ids:
            return False
        ids.add(imdb_id)
        _save_dismissed_ids(ids)
        logger.info("Dismissed %s (total: %d)", imdb_id, len(ids))
        return True


def restore_title(imdb_id: str) -> bool:
    """Remove an IMDB ID from the dismissed set. Returns True if it was present."""
    with _lock:
        ids = _load_dismissed_ids()
        if imdb_id not in ids:
            return False
        ids.discard(imdb_id)
        _save_dismissed_ids(ids)
        logger.info("Restored %s (total: %d)", imdb_id, len(ids))
        return True


def get_dismissed_with_metadata() -> list[DismissedTitle]:
    """Return dismissed IDs enriched with title metadata where available."""
    ids = sorted(get_dismissed_ids())
    if not ids:
        return []

    # Try to resolve from scored SQLite DB first, then fall back to candidate cache
    lookup: dict[str, dict] = {}
    db_path = PROJECT_ROOT / "data" / "cache" / "scored_candidates.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            ph = ",".join("?" * len(ids))
            sql = (
                "SELECT imdb_id, title, year, title_type, genres "
                f"FROM scored_candidates WHERE imdb_id IN ({ph})"
            )
            rows = conn.execute(sql, ids).fetchall()
            conn.close()
            for row in rows:
                lookup[row["imdb_id"]] = {
                    "imdb_id": row["imdb_id"],
                    "title": row["title"],
                    "year": row["year"],
                    "title_type": row["title_type"],
                    "genres": json.loads(row["genres"]),
                }
            logger.info("Resolved %d/%d dismissed titles from scored DB", len(lookup), len(ids))
        except Exception:
            logger.warning("Failed to read scored DB for dismissed metadata")

    # Fill remaining from candidate JSON cache
    remaining = set(ids) - set(lookup)
    if remaining:
        cache_path = PROJECT_ROOT / "data" / "cache" / "imdb_candidates.json"
        if cache_path.exists():
            try:
                with open(cache_path) as f:
                    candidates = json.load(f)
                for c in candidates:
                    cid = c.get("imdb_id")
                    if cid in remaining:
                        lookup[cid] = c
                found = len(lookup) - (len(ids) - len(remaining))
                logger.info(
                    "Resolved %d additional dismissed titles from cache", found
                )
            except Exception:
                logger.warning("Failed to read candidate cache for dismissed metadata")

    result = []
    for imdb_id in ids:
        if imdb_id in lookup:
            c = lookup[imdb_id]
            result.append(
                DismissedTitle(
                    imdb_id=imdb_id,
                    title=c.get("title"),
                    year=c.get("year"),
                    title_type=c.get("title_type"),
                    genres=c.get("genres", []),
                    imdb_url=f"https://www.imdb.com/title/{imdb_id}",
                )
            )
        else:
            result.append(
                DismissedTitle(
                    imdb_id=imdb_id,
                    imdb_url=f"https://www.imdb.com/title/{imdb_id}",
                )
            )
    return result
