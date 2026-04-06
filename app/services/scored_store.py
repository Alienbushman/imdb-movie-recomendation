import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import PROJECT_ROOT, get_settings
from app.models.schemas import CandidateTitle, RecommendationFilters

logger = logging.getLogger(__name__)


def _db_path() -> Path:
    settings = get_settings()
    cache_dir = PROJECT_ROOT / settings.data.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "scored_candidates.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scored_candidates (
            imdb_id             TEXT PRIMARY KEY,
            title               TEXT NOT NULL,
            original_title      TEXT,
            title_type          TEXT NOT NULL,
            year                INTEGER,
            genres              TEXT NOT NULL,
            imdb_rating         REAL NOT NULL,
            num_votes           INTEGER NOT NULL,
            runtime_mins        INTEGER,
            language            TEXT,
            languages           TEXT NOT NULL DEFAULT '[]',
            country_code        TEXT,
            directors           TEXT NOT NULL,
            actors              TEXT NOT NULL,
            writers             TEXT NOT NULL,
            composers           TEXT NOT NULL,
            cinematographers    TEXT NOT NULL,
            is_anime            INTEGER NOT NULL DEFAULT 0,
            predicted_score     REAL NOT NULL,
            scored_at           TEXT NOT NULL
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_score ON scored_candidates(predicted_score DESC)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON scored_candidates(title_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_lang ON scored_candidates(language)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_year ON scored_candidates(year)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_anime "
        "ON scored_candidates(is_anime, predicted_score DESC)"
    )
    conn.commit()


def save_scored(scored: list[tuple[CandidateTitle, float]]) -> None:
    """Persist all scored candidates to SQLite, replacing any prior results.

    The is_anime flag uses CandidateTitle.is_anime when present (after TICKET-004);
    otherwise falls back to 1 for any title with "Animation" in genres.
    """
    now = datetime.now(UTC).isoformat()
    conn = _connect()
    try:
        _ensure_schema(conn)
        conn.execute("DELETE FROM scored_candidates")
        rows = [
            (
                c.imdb_id,
                c.title,
                c.original_title,
                c.title_type,
                c.year,
                json.dumps(c.genres),
                c.imdb_rating,
                c.num_votes,
                c.runtime_mins,
                c.language,
                json.dumps(getattr(c, "languages", [])),
                c.country_code,
                json.dumps(c.directors),
                json.dumps(c.actors),
                json.dumps(c.writers),
                json.dumps(c.composers),
                json.dumps(c.cinematographers),
                int(c.is_anime),
                score,
                now,
            )
            for c, score in scored
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO scored_candidates "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        conn.commit()
        logger.info("Saved %d scored candidates to %s", len(rows), _db_path())
    finally:
        conn.close()


def has_scored_results() -> bool:
    """Return True if the scored_candidates table has any rows."""
    db = _db_path()
    if not db.exists():
        return False
    try:
        conn = _connect()
        try:
            row = conn.execute("SELECT 1 FROM scored_candidates LIMIT 1").fetchone()
            return row is not None
        except sqlite3.OperationalError:
            return False
        finally:
            conn.close()
    except Exception:
        return False


def get_scored_count() -> int:
    """Return the number of rows in scored_candidates (for the status endpoint)."""
    db = _db_path()
    if not db.exists():
        return 0
    try:
        conn = _connect()
        try:
            row = conn.execute("SELECT COUNT(*) FROM scored_candidates").fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()
    except Exception:
        return 0


def search_titles(query: str, limit: int = 20) -> list[dict]:
    """Search scored_candidates by title substring (case-insensitive).

    Returns dicts with keys: imdb_id, title, year, title_type.
    """
    db = _db_path()
    if not db.exists():
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT imdb_id, title, year, title_type FROM scored_candidates "
            "WHERE title LIKE ? COLLATE NOCASE "
            "ORDER BY num_votes DESC "
            "LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def query_candidates(
    filters: RecommendationFilters | None,
    title_types: list[str] | None,
    anime_only: bool,
    top_n: int,
    dismissed_ids: set[str],
    min_score: float,
) -> list[tuple[CandidateTitle, float]]:
    """Query scored candidates from SQLite with optional filters.

    Args:
        title_types: restrict to these IMDB title types; None means any type.
        anime_only: if True, add WHERE is_anime = 1 (for the animation/anime category).
        dismissed_ids: IDs to exclude — applied in SQL for small sets, Python for large.
    """
    conn = _connect()
    try:
        params: list = [min_score]
        where = ["predicted_score >= ?"]

        if title_types is not None:
            type_ph = ",".join("?" * len(title_types))
            where.append(f"title_type IN ({type_ph})")
            params.extend(title_types)

        if anime_only:
            where.append("is_anime = 1")

        if filters:
            if filters.min_year is not None:
                where.append("year >= ?")
                params.append(filters.min_year)
            if filters.max_year is not None:
                where.append("year <= ?")
                params.append(filters.max_year)
            if filters.languages:
                incl_ph = ",".join("?" * len(filters.languages))
                where.append(f"language IN ({incl_ph})")
                params.extend(filters.languages)
            if filters.min_imdb_rating is not None:
                where.append("imdb_rating >= ?")
                params.append(filters.min_imdb_rating)
            if filters.max_runtime is not None:
                where.append("(runtime_mins IS NULL OR runtime_mins <= ?)")
                params.append(filters.max_runtime)
            if filters.exclude_languages:
                excl_ph = ",".join("?" * len(filters.exclude_languages))
                where.append(f"(language IS NULL OR language NOT IN ({excl_ph}))")
                params.extend(filters.exclude_languages)
            if filters.min_vote_count is not None:
                where.append("num_votes >= ?")
                params.append(filters.min_vote_count)
            if filters.country_code is not None:
                where.append("UPPER(country_code) = UPPER(?)")
                params.append(filters.country_code)

        if dismissed_ids and len(dismissed_ids) <= 500:
            d_ph = ",".join("?" * len(dismissed_ids))
            where.append(f"imdb_id NOT IN ({d_ph})")
            params.extend(sorted(dismissed_ids))

        sql = (
            f"SELECT * FROM scored_candidates "
            f"WHERE {' AND '.join(where)} "
            f"ORDER BY predicted_score DESC"
        )
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    large_dismissed = dismissed_ids if len(dismissed_ids) > 500 else set()
    results: list[tuple[CandidateTitle, float]] = []

    for row in rows:
        if large_dismissed and row["imdb_id"] in large_dismissed:
            continue

        genres = json.loads(row["genres"])

        if filters:
            if filters.genres:
                genre_set = {g.strip() for g in filters.genres}
                if not genre_set & set(genres):
                    continue
            if filters.exclude_genres:
                excl_set = {g.strip() for g in filters.exclude_genres}
                if excl_set & set(genres):
                    continue

        candidate = CandidateTitle(
            imdb_id=row["imdb_id"],
            title=row["title"],
            original_title=row["original_title"] or row["title"],
            title_type=row["title_type"],
            year=row["year"],
            genres=genres,
            imdb_rating=row["imdb_rating"],
            num_votes=row["num_votes"],
            runtime_mins=row["runtime_mins"],
            language=row["language"],
            languages=json.loads(row["languages"] or "[]"),
            country_code=row["country_code"],
            directors=json.loads(row["directors"]),
            actors=json.loads(row["actors"]),
            writers=json.loads(row["writers"]),
            composers=json.loads(row["composers"]),
            cinematographers=json.loads(row["cinematographers"]),
        )
        results.append((candidate, row["predicted_score"]))

    return results[:top_n]
