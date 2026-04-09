"""SQLite-backed store for LightGBM-scored candidates.

After each pipeline run, all scored candidates are written to
``data/cache/scored_candidates.db``. GET recommendation endpoints query this
database instead of holding all candidates in memory, keeping post-pipeline
RAM under ~500 MB.

The database also serves person-browse and title-search queries; it stores a
``persons`` table alongside the ``candidates`` table for efficient lookups.

Key functions:
- ``write_candidates`` — bulk-insert or replace all scored rows after a pipeline run
- ``query_candidates`` — paginated, filtered query for the recommendation endpoints
- ``search_titles`` — full-text search for the /search endpoint
- ``search_people`` / ``get_person`` / ``query_titles_by_person`` — person-browse support
- ``has_scored_results`` — fast check used by the startup fast-path
"""
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS people (
            name_id TEXT PRIMARY KEY,
            name    TEXT NOT NULL,
            primary_profession TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS title_people (
            imdb_id TEXT NOT NULL,
            name_id TEXT NOT NULL,
            role    TEXT NOT NULL,
            PRIMARY KEY (imdb_id, name_id, role)
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_title_people_name_id ON title_people (name_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_title_people_imdb_id ON title_people (imdb_id)"
    )
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rated_titles (
            imdb_id      TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            year         INTEGER,
            title_type   TEXT NOT NULL,
            imdb_rating  REAL,
            num_votes    INTEGER NOT NULL DEFAULT 0,
            runtime_mins INTEGER,
            genres       TEXT NOT NULL DEFAULT '[]',
            languages    TEXT NOT NULL DEFAULT '[]',
            user_rating  REAL
        )
    """)
    # Additive migration for existing databases that only have the 4-column schema
    for col, ddl in [
        ("imdb_rating",  "REAL"),
        ("num_votes",    "INTEGER NOT NULL DEFAULT 0"),
        ("runtime_mins", "INTEGER"),
        ("genres",       "TEXT NOT NULL DEFAULT '[]'"),
        ("languages",    "TEXT NOT NULL DEFAULT '[]'"),
        ("user_rating",  "REAL"),
    ]:
        try:
            conn.execute(f"ALTER TABLE rated_titles ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            pass  # column already exists
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


def get_title_by_id(imdb_id: str) -> sqlite3.Row | None:
    """Look up a single title from the scored DB by IMDB ID."""
    db = _db_path()
    if not db.exists():
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM scored_candidates WHERE imdb_id = ?", (imdb_id,)
        ).fetchone()
        return row
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def query_all_candidates_lightweight(
    filters: RecommendationFilters | None,
) -> list[sqlite3.Row]:
    """Query all scored candidates with optional filters, returning raw rows.

    Unlike query_candidates(), this returns all matching rows without top-N
    limits or dismissed filtering. Used by the similarity engine which needs
    the full pool to rank by similarity score.
    """
    db = _db_path()
    if not db.exists():
        return []
    conn = _connect()
    try:
        params: list = []
        where: list[str] = []

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

        where_clause = f"WHERE {' AND '.join(where)}" if where else ""
        sql = (
            f"SELECT * FROM scored_candidates {where_clause} "
            f"ORDER BY num_votes DESC"
        )
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    # Apply genre filters in Python (same pattern as query_candidates)
    if filters and (filters.genres or filters.exclude_genres):
        filtered = []
        for row in rows:
            genres = json.loads(row["genres"])
            if filters.genres:
                genre_set = {g.strip() for g in filters.genres}
                if not genre_set & set(genres):
                    continue
            if filters.exclude_genres:
                excl_set = {g.strip() for g in filters.exclude_genres}
                if excl_set & set(genres):
                    continue
            filtered.append(row)
        return filtered

    return rows


def search_titles(query: str, limit: int = 20) -> list[dict]:
    """Search scored_candidates and rated_titles by title substring (case-insensitive).

    Returns dicts with keys: imdb_id, title, year, title_type, is_rated.
    Rated titles are sorted first; within each group, results are ordered by
    vote count descending (num_votes is 0 for rated_titles rows).
    """
    db = _db_path()
    if not db.exists():
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT imdb_id, title, year, title_type, 1 AS is_rated, 0 AS num_votes
            FROM rated_titles
            WHERE title LIKE ? COLLATE NOCASE
            UNION
            SELECT imdb_id, title, year, title_type, 0 AS is_rated, num_votes
            FROM scored_candidates
            WHERE title LIKE ? COLLATE NOCASE
            ORDER BY is_rated DESC, num_votes DESC
            LIMIT ?
            """,
            (f"%{query}%", f"%{query}%", limit),
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


def get_person(name_id: str) -> dict | None:
    """Return the people row for name_id, or None if not found."""
    db = _db_path()
    if not db.exists():
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT name_id, name, primary_profession FROM people WHERE name_id = ?",
            (name_id,),
        ).fetchone()
        return dict(row) if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def query_titles_by_person(
    name_id: str,
    limit: int = 100,
    min_year: int | None = None,
    max_year: int | None = None,
    min_rating: float | None = None,
    min_votes: int | None = None,
    max_runtime: int | None = None,
    dismissed_ids: set[str] | None = None,
) -> tuple[int, list[dict]]:
    """Return (total_count, rows) for titles featuring name_id.

    UNIONs scored candidates (unrated) with rated titles so both appear.
    Rows include display columns plus `roles_csv` and `is_rated`.
    Results are ordered by predicted_score DESC.
    """
    db = _db_path()
    if not db.exists():
        return 0, []
    conn = _connect()
    try:
        # Build filter fragments for each UNION branch
        sc_where: list[str] = ["tp.name_id = ?"]
        sc_params: list = [name_id]
        rt_where: list[str] = ["tp.name_id = ?"]
        rt_params: list = [name_id]

        if min_year is not None:
            sc_where.append("sc.year >= ?")
            sc_params.append(min_year)
            rt_where.append("rt.year >= ?")
            rt_params.append(min_year)
        if max_year is not None:
            sc_where.append("sc.year <= ?")
            sc_params.append(max_year)
            rt_where.append("rt.year <= ?")
            rt_params.append(max_year)
        if min_rating is not None:
            sc_where.append("sc.imdb_rating >= ?")
            sc_params.append(min_rating)
            rt_where.append("rt.imdb_rating >= ?")
            rt_params.append(min_rating)
        if min_votes is not None:
            sc_where.append("sc.num_votes >= ?")
            sc_params.append(min_votes)
            rt_where.append("rt.num_votes >= ?")
            rt_params.append(min_votes)
        if max_runtime is not None:
            sc_where.append("(sc.runtime_mins IS NULL OR sc.runtime_mins <= ?)")
            sc_params.append(max_runtime)
            rt_where.append("(rt.runtime_mins IS NULL OR rt.runtime_mins <= ?)")
            rt_params.append(max_runtime)
        if dismissed_ids and len(dismissed_ids) <= 500:
            d_ph = ",".join("?" * len(dismissed_ids))
            sc_where.append(f"sc.imdb_id NOT IN ({d_ph})")
            sc_params.extend(sorted(dismissed_ids))
            # Rated titles are in the user's watchlist — they are never dismissed

        sc_where_clause = " AND ".join(sc_where)
        rt_where_clause = " AND ".join(rt_where)

        union_sql = f"""
            SELECT sc.imdb_id, sc.title, sc.year, sc.title_type,
                   sc.imdb_rating, sc.num_votes, sc.runtime_mins,
                   sc.genres, sc.languages,
                   sc.predicted_score, 0 AS is_rated,
                   GROUP_CONCAT(DISTINCT tp.role) AS roles_csv
            FROM scored_candidates sc
            JOIN title_people tp ON tp.imdb_id = sc.imdb_id
            WHERE {sc_where_clause}
            GROUP BY sc.imdb_id

            UNION ALL

            SELECT rt.imdb_id, rt.title, rt.year, rt.title_type,
                   rt.imdb_rating, rt.num_votes, rt.runtime_mins,
                   rt.genres, rt.languages,
                   rt.user_rating AS predicted_score, 1 AS is_rated,
                   GROUP_CONCAT(DISTINCT tp.role) AS roles_csv
            FROM rated_titles rt
            JOIN title_people tp ON tp.imdb_id = rt.imdb_id
            WHERE {rt_where_clause}
            GROUP BY rt.imdb_id
        """
        all_params = sc_params + rt_params

        total_row = conn.execute(
            f"SELECT COUNT(*) FROM ({union_sql})", all_params
        ).fetchone()
        total = total_row[0] if total_row else 0

        rows = conn.execute(
            f"SELECT * FROM ({union_sql}) ORDER BY predicted_score DESC LIMIT ?",
            all_params + [limit],
        ).fetchall()
    except sqlite3.OperationalError:
        return 0, []
    finally:
        conn.close()

    large_dismissed = dismissed_ids if dismissed_ids and len(dismissed_ids) > 500 else set()
    result = []
    for row in rows:
        if large_dismissed and row["imdb_id"] in large_dismissed:
            continue
        result.append(dict(row))
    return total, result


def write_people(
    people: list[dict],
    title_people: list[dict],
) -> None:
    """Persist person and title-person rows to the scored DB.

    Replaces existing rows (INSERT OR REPLACE) so re-running the pipeline
    produces a clean slate without requiring a manual DB delete.
    """
    conn = _connect()
    try:
        _ensure_schema(conn)
        conn.executemany(
            "INSERT OR REPLACE INTO people (name_id, name, primary_profession) VALUES (?,?,?)",
            [(p["name_id"], p["name"], p.get("primary_profession")) for p in people],
        )
        conn.executemany(
            "INSERT OR REPLACE INTO title_people (imdb_id, name_id, role) VALUES (?,?,?)",
            [(tp["imdb_id"], tp["name_id"], tp["role"]) for tp in title_people],
        )
        conn.commit()
        logger.info(
            "Saved %d people and %d title-person rows", len(people), len(title_people)
        )
    finally:
        conn.close()


def write_rated_titles(titles: list) -> None:
    """Persist the user's rated titles to SQLite for durable title search.

    Clears and repopulates on every pipeline run so the table always reflects
    the current watchlist. Titles are searchable across server restarts without
    requiring a full pipeline re-run.
    """
    conn = _connect()
    try:
        _ensure_schema(conn)
        conn.execute("DELETE FROM rated_titles")
        conn.executemany(
            "INSERT INTO rated_titles "
            "(imdb_id, title, year, title_type, imdb_rating, num_votes, runtime_mins, "
            "genres, languages, user_rating) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            [
                (
                    t.imdb_id,
                    t.title,
                    t.year,
                    t.title_type,
                    t.imdb_rating,
                    t.num_votes,
                    t.runtime_mins,
                    json.dumps(t.genres),
                    json.dumps([t.language] if t.language else []),
                    float(t.user_rating),
                )
                for t in titles
            ],
        )
        conn.commit()
        logger.info("Saved %d rated titles to rated_titles table", len(titles))
    finally:
        conn.close()


def search_people(query: str, limit: int = 20) -> list[dict]:
    """Search people by name substring (case-insensitive).

    Returns dicts with keys: name_id, name, primary_profession, title_count.
    Only returns people who have at least one row in title_people.

    Results are ordered by rated-title count (how many of this person's titles
    appear in the user's watchlist) DESC, then by total title_count DESC. This
    boosts familiar names — e.g. searching "paul" surfaces Paul Newman above
    prolific but obscure crew members with higher total credits.
    """
    db = _db_path()
    if not db.exists():
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT p.name_id, p.name, p.primary_profession, "
            "COUNT(DISTINCT tp.imdb_id) AS title_count, "
            "COUNT(DISTINCT rt.imdb_id) AS rated_count "
            "FROM people p "
            "JOIN title_people tp ON tp.name_id = p.name_id "
            "LEFT JOIN rated_titles rt ON rt.imdb_id = tp.imdb_id "
            "WHERE p.name LIKE ? COLLATE NOCASE "
            "GROUP BY p.name_id "
            "ORDER BY rated_count DESC, title_count DESC "
            "LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
