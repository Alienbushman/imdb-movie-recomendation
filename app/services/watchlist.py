"""Persistent watchlist of titles the user has saved for later viewing.

Mirrors ``app.services.dismissed`` in shape: a set of IMDB IDs persisted to
``data/watchlist_saved.json`` plus a parallel metadata file so the watchlist
page can render titles without re-querying the candidate cache.

Watchlisted titles are *not* excluded from recommendations — they remain
visible so users can confirm the saved item is the same one being recommended.
"""
import json
import logging
import sqlite3
import threading

from app.core.config import PROJECT_ROOT
from app.models.schemas import WatchlistedTitle

logger = logging.getLogger(__name__)

WATCHLIST_PATH = PROJECT_ROOT / "data" / "watchlist_saved.json"
WATCHLIST_METADATA_PATH = PROJECT_ROOT / "data" / "watchlist_saved_metadata.json"

_lock = threading.Lock()


def _load_watchlist_ids() -> set[str]:
    if not WATCHLIST_PATH.exists():
        return set()
    with open(WATCHLIST_PATH) as f:
        return set(json.load(f))


def _save_watchlist_ids(ids: set[str]) -> None:
    WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(sorted(ids), f, indent=2)


def _load_watchlist_metadata() -> dict[str, dict]:
    if not WATCHLIST_METADATA_PATH.exists():
        return {}
    with open(WATCHLIST_METADATA_PATH) as f:
        return json.load(f)


def _save_watchlist_metadata(metadata: dict[str, dict]) -> None:
    WATCHLIST_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(WATCHLIST_METADATA_PATH, "w") as f:
        json.dump(metadata, f, indent=2)


def get_watchlist_ids() -> set[str]:
    with _lock:
        return _load_watchlist_ids()


def add_to_watchlist(
    imdb_id: str,
    title: str | None = None,
    year: int | None = None,
    title_type: str | None = None,
    genres: list[str] | None = None,
    director: str | None = None,
    actors: list[str] | None = None,
    imdb_rating: float | None = None,
    predicted_score: float | None = None,
) -> bool:
    """Add an IMDB ID to the saved watchlist. Returns True if newly added."""
    with _lock:
        ids = _load_watchlist_ids()
        if imdb_id in ids:
            return False
        ids.add(imdb_id)
        _save_watchlist_ids(ids)

        if title is not None:
            metadata = _load_watchlist_metadata()
            metadata[imdb_id] = {
                "title": title,
                "year": year,
                "title_type": title_type,
                "genres": genres or [],
                "director": director,
                "actors": actors or [],
                "imdb_rating": imdb_rating,
                "predicted_score": predicted_score,
            }
            _save_watchlist_metadata(metadata)

        logger.info("Added %s to watchlist (total: %d)", imdb_id, len(ids))
        return True


def remove_from_watchlist(imdb_id: str) -> bool:
    """Remove an IMDB ID from the saved watchlist. Returns True if it was present."""
    with _lock:
        ids = _load_watchlist_ids()
        if imdb_id not in ids:
            return False
        ids.discard(imdb_id)
        _save_watchlist_ids(ids)

        metadata = _load_watchlist_metadata()
        if imdb_id in metadata:
            del metadata[imdb_id]
            _save_watchlist_metadata(metadata)

        logger.info("Removed %s from watchlist (total: %d)", imdb_id, len(ids))
        return True


def get_watchlist_with_metadata() -> list[WatchlistedTitle]:
    """Return saved watchlist enriched with title metadata where available."""
    ids = sorted(get_watchlist_ids())
    if not ids:
        return []

    from app.services.scored_store import get_titles_from_lookup

    lookup: dict[str, dict] = {}
    saved = _load_watchlist_metadata()
    for imdb_id in ids:
        if imdb_id in saved:
            lookup[imdb_id] = saved[imdb_id]

    remaining = set(ids) - set(lookup)
    if remaining:
        try:
            found = get_titles_from_lookup(sorted(remaining))
            lookup.update(found)
        except Exception:
            logger.warning("Failed to read title_lookup for watchlist metadata")

    # Fall back to scored DB for any still-missing titles
    remaining = set(ids) - set(lookup)
    if remaining:
        db_path = PROJECT_ROOT / "data" / "cache" / "scored_candidates.db"
        if db_path.exists():
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                ph = ",".join("?" * len(remaining))
                rows = conn.execute(
                    "SELECT imdb_id, title, year, title_type, genres, "
                    "directors, actors, imdb_rating, predicted_score "
                    f"FROM scored_candidates WHERE imdb_id IN ({ph})",
                    sorted(remaining),
                ).fetchall()
                conn.close()
                for row in rows:
                    directors = json.loads(row["directors"])
                    actors = json.loads(row["actors"])
                    lookup[row["imdb_id"]] = {
                        "title": row["title"],
                        "year": row["year"],
                        "title_type": row["title_type"],
                        "genres": json.loads(row["genres"]),
                        "director": directors[0] if directors else None,
                        "actors": actors[:3],
                        "imdb_rating": row["imdb_rating"],
                        "predicted_score": row["predicted_score"],
                    }
            except Exception:
                logger.warning("Failed to read scored DB for watchlist metadata")

    result = []
    for imdb_id in ids:
        if imdb_id in lookup:
            c = lookup[imdb_id]
            result.append(
                WatchlistedTitle(
                    imdb_id=imdb_id,
                    title=c.get("title"),
                    year=c.get("year"),
                    title_type=c.get("title_type"),
                    genres=c.get("genres", []),
                    director=c.get("director"),
                    actors=c.get("actors", []),
                    imdb_rating=c.get("imdb_rating"),
                    predicted_score=c.get("predicted_score"),
                    imdb_url=f"https://www.imdb.com/title/{imdb_id}",
                )
            )
        else:
            result.append(
                WatchlistedTitle(
                    imdb_id=imdb_id,
                    imdb_url=f"https://www.imdb.com/title/{imdb_id}",
                )
            )
    return result
