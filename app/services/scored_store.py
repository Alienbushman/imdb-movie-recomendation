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
import csv
import gzip
import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import PROJECT_ROOT, get_settings
from app.models.schemas import CandidateTitle, RecommendationFilters

logger = logging.getLogger(__name__)


def _fts5_query(query: str) -> str:
    """Convert a user search string to an FTS5 prefix query.

    Each word gets a trailing * for prefix matching.
    Example: "martin scor" -> "martin* scor*"
    """
    tokens = query.strip().split()
    if not tokens:
        return ""
    return " ".join(f"{t}*" for t in tokens)


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
            scored_at           TEXT NOT NULL,
            keywords            TEXT NOT NULL DEFAULT '[]'
        )
    """)
    # Additive migration for databases that pre-date the keywords column
    try:
        conn.execute("ALTER TABLE scored_candidates ADD COLUMN keywords TEXT NOT NULL DEFAULT '[]'")
    except sqlite3.OperationalError:
        pass  # column already exists
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
            name_id            TEXT PRIMARY KEY,
            name               TEXT NOT NULL,
            primary_profession TEXT,
            title_count        INTEGER NOT NULL DEFAULT 0,
            rated_count        INTEGER NOT NULL DEFAULT 0
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
    # Additive migration for existing people databases missing count columns
    for col, ddl in [
        ("title_count", "INTEGER NOT NULL DEFAULT 0"),
        ("rated_count", "INTEGER NOT NULL DEFAULT 0"),
    ]:
        try:
            conn.execute(f"ALTER TABLE people ADD COLUMN {col} {ddl}")
        except sqlite3.OperationalError:
            pass  # column already exists
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
    # FTS5 virtual tables for fast full-text search
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS people_fts USING fts5(
            name,
            content='people',
            content_rowid='rowid'
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS scored_candidates_fts USING fts5(
            title,
            content='scored_candidates',
            content_rowid='rowid'
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS rated_titles_fts USING fts5(
            title,
            content='rated_titles',
            content_rowid='rowid'
        )
    """)
    # Persistent lookup table — never cleared, accumulates title names across runs.
    # Used to resolve dismissed title names even after they leave scored_candidates.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS title_lookup (
            imdb_id    TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            year       INTEGER,
            title_type TEXT,
            genres     TEXT NOT NULL DEFAULT '[]'
        )
    """)
    # Backfill title_lookup from scored_candidates on first run
    row = conn.execute("SELECT COUNT(*) FROM title_lookup").fetchone()
    if row[0] == 0:
        conn.execute("""
            INSERT OR IGNORE INTO title_lookup
                (imdb_id, title, year, title_type, genres)
            SELECT imdb_id, title, year, title_type, genres
            FROM scored_candidates
        """)
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
                json.dumps(getattr(c, "keywords", [])),
            )
            for c, score in scored
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO scored_candidates ("
            "imdb_id, title, original_title, title_type, year, genres, "
            "imdb_rating, num_votes, runtime_mins, language, languages, "
            "country_code, directors, actors, writers, composers, cinematographers, "
            "is_anime, predicted_score, scored_at, keywords) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        # Rebuild FTS index for title search
        conn.execute(
            "INSERT INTO scored_candidates_fts(scored_candidates_fts) VALUES('rebuild')"
        )
        # Accumulate title names in the persistent lookup table (never cleared)
        # so dismissed titles remain resolvable by name across pipeline runs.
        conn.executemany(
            "INSERT OR IGNORE INTO title_lookup (imdb_id, title, year, title_type, genres) "
            "VALUES (?,?,?,?,?)",
            [(c.imdb_id, c.title, c.year, c.title_type, json.dumps(c.genres)) for c, _ in scored],
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


def _resolve_from_basics(imdb_ids: set[str]) -> list[dict]:
    """Resolve title metadata from title.basics.tsv.gz for IDs not in the DB.

    Streams the file so we never load it entirely into memory.
    """
    settings = get_settings()
    basics_path = PROJECT_ROOT / settings.imdb_datasets.title_basics
    if not basics_path.exists():
        return []
    found = []
    with gzip.open(str(basics_path), "rt", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row["tconst"] in imdb_ids:
                year = None
                if row.get("startYear") and row["startYear"] != "\\N":
                    try:
                        year = int(row["startYear"])
                    except ValueError:
                        pass
                genres = []
                if row.get("genres") and row["genres"] != "\\N":
                    genres = [g.strip() for g in row["genres"].split(",")]
                found.append({
                    "imdb_id": row["tconst"],
                    "title": row["primaryTitle"],
                    "year": year,
                    "title_type": row.get("titleType"),
                    "genres": genres,
                })
                if len(found) == len(imdb_ids):
                    break
    return found


def get_titles_from_lookup(imdb_ids: list[str]) -> dict[str, dict]:
    """Look up title metadata from the persistent title_lookup table.

    If any IDs are missing, resolves them from title.basics.tsv.gz and
    inserts into title_lookup for future lookups.

    Returns a dict keyed by imdb_id with keys: title, year, title_type, genres.
    Only IDs found are included.
    """
    if not imdb_ids:
        return {}
    conn = _connect()
    try:
        _ensure_schema(conn)
        ph = ",".join("?" * len(imdb_ids))
        rows = conn.execute(
            "SELECT imdb_id, title, year, title_type, genres "
            f"FROM title_lookup WHERE imdb_id IN ({ph})",
            imdb_ids,
        ).fetchall()
        result = {
            row["imdb_id"]: {
                "title": row["title"],
                "year": row["year"],
                "title_type": row["title_type"],
                "genres": json.loads(row["genres"]),
            }
            for row in rows
        }

        # Resolve missing IDs from the raw IMDB dataset
        missing = set(imdb_ids) - set(result)
        if missing:
            resolved = _resolve_from_basics(missing)
            if resolved:
                conn.executemany(
                    "INSERT OR IGNORE INTO title_lookup "
                    "(imdb_id, title, year, title_type, genres) "
                    "VALUES (?,?,?,?,?)",
                    [
                        (r["imdb_id"], r["title"], r["year"],
                         r["title_type"], json.dumps(r["genres"]))
                        for r in resolved
                    ],
                )
                conn.commit()
                for r in resolved:
                    result[r["imdb_id"]] = r
                logger.info(
                    "Resolved %d/%d missing titles from IMDB basics",
                    len(resolved), len(missing),
                )

        return result
    except sqlite3.OperationalError:
        return {}
    finally:
        conn.close()


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
            if filters.min_runtime is not None:
                where.append("runtime_mins >= ?")
                params.append(filters.min_runtime)
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

    # Apply genre + keyword filters in Python (same pattern as query_candidates)
    needs_python_filter = filters and (
        filters.genres
        or filters.exclude_genres
        or filters.keywords
        or filters.exclude_keywords
    )
    if needs_python_filter:
        keyword_incl = (
            {k.lower() for k in filters.keywords} if filters.keywords else set()
        )
        keyword_excl = (
            {k.lower() for k in filters.exclude_keywords}
            if filters.exclude_keywords
            else set()
        )
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
            if keyword_incl or keyword_excl:
                try:
                    kw_lower = {k.lower() for k in json.loads(row["keywords"] or "[]")}
                except (IndexError, KeyError):
                    kw_lower = set()
                if keyword_incl and not (keyword_incl & kw_lower):
                    continue
                if keyword_excl and (keyword_excl & kw_lower):
                    continue
            filtered.append(row)
        return filtered

    return rows


def search_titles(query: str, limit: int = 20) -> list[dict]:
    """Search scored_candidates and rated_titles using FTS5 with LIKE fallback.

    Returns dicts with keys: imdb_id, title, year, title_type, is_rated.
    Rated titles are sorted first; within each group, results are ordered by
    vote count descending (num_votes is 0 for rated_titles rows).
    """
    db = _db_path()
    if not db.exists():
        return []
    conn = _connect()
    try:
        fts_q = _fts5_query(query)
        # Try FTS5 first (tables may not exist if no pipeline run yet)
        if fts_q:
            try:
                rows = conn.execute(
                    """
                    SELECT r.imdb_id, r.title, r.year, r.title_type,
                           1 AS is_rated, 0 AS num_votes
                    FROM rated_titles r
                    JOIN rated_titles_fts fts ON fts.rowid = r.rowid
                    WHERE rated_titles_fts MATCH ?
                    UNION
                    SELECT s.imdb_id, s.title, s.year, s.title_type,
                           0 AS is_rated, s.num_votes
                    FROM scored_candidates s
                    JOIN scored_candidates_fts fts ON fts.rowid = s.rowid
                    WHERE scored_candidates_fts MATCH ?
                    ORDER BY is_rated DESC, num_votes DESC
                    LIMIT ?
                    """,
                    (fts_q, fts_q, limit),
                ).fetchall()
                if rows:
                    return [dict(r) for r in rows]
            except sqlite3.OperationalError:
                pass  # FTS tables not yet created; fall through to LIKE
        # Fallback to LIKE for substring matches
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
            if filters.min_runtime is not None:
                where.append("runtime_mins >= ?")
                params.append(filters.min_runtime)
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

    keyword_incl_lower = (
        {k.strip().lower() for k in filters.keywords}
        if filters and filters.keywords
        else set()
    )
    keyword_excl_lower = (
        {k.strip().lower() for k in filters.exclude_keywords}
        if filters and filters.exclude_keywords
        else set()
    )

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

        try:
            keywords = json.loads(row["keywords"] or "[]")
        except (IndexError, KeyError):
            keywords = []

        if keyword_incl_lower or keyword_excl_lower:
            kw_lower = {k.lower() for k in keywords}
            if keyword_incl_lower and not (keyword_incl_lower & kw_lower):
                continue
            if keyword_excl_lower and (keyword_excl_lower & kw_lower):
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
            keywords=keywords,
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
            "SELECT name_id, name, primary_profession, title_count FROM people WHERE name_id = ?",
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
        # Denormalize counts so search_people() avoids expensive JOINs
        conn.execute("""
            UPDATE people SET
                title_count = (
                    SELECT COUNT(DISTINCT tp.imdb_id)
                    FROM title_people tp
                    WHERE tp.name_id = people.name_id
                ),
                rated_count = (
                    SELECT COUNT(DISTINCT rt.imdb_id)
                    FROM title_people tp
                    JOIN rated_titles rt ON rt.imdb_id = tp.imdb_id
                    WHERE tp.name_id = people.name_id
                )
        """)
        # Rebuild FTS index for people name search
        conn.execute("INSERT INTO people_fts(people_fts) VALUES('rebuild')")
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
        # Rebuild FTS index for title search
        conn.execute(
            "INSERT INTO rated_titles_fts(rated_titles_fts) VALUES('rebuild')"
        )
        conn.commit()
        logger.info("Saved %d rated titles to rated_titles table", len(titles))
    finally:
        conn.close()


def load_rated_titles() -> list:
    """Load rated titles from SQLite for similarity computation.

    Used by ``get_recommendations_from_db`` after a server restart, when
    ``_state["titles"]`` is None because the pipeline hasn't been run in this
    process.  Only the fields required by ``_find_similar_rated`` are needed
    (``user_rating``, ``genres``, ``imdb_id``, ``title``, ``title_type``,
    ``year``); the remaining ``RatedTitle`` fields are filled with safe defaults.
    """
    from app.models.schemas import RatedTitle

    db = _db_path()
    if not db.exists():
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT imdb_id, title, year, title_type, imdb_rating, num_votes, "
            "runtime_mins, genres, languages, user_rating FROM rated_titles"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    titles = []
    for row in rows:
        genres = json.loads(row["genres"]) if row["genres"] else []
        languages = json.loads(row["languages"]) if row["languages"] else []
        language = languages[0] if languages else None
        try:
            titles.append(
                RatedTitle(
                    imdb_id=row["imdb_id"],
                    title=row["title"],
                    original_title=row["title"],
                    title_type=row["title_type"],
                    user_rating=int(row["user_rating"] or 0),
                    date_rated="",
                    imdb_rating=float(row["imdb_rating"] or 0.0),
                    runtime_mins=row["runtime_mins"],
                    year=int(row["year"] or 0),
                    genres=genres,
                    num_votes=int(row["num_votes"] or 0),
                    release_date="",
                    directors=[],
                    url="",
                    language=language,
                )
            )
        except Exception:
            continue
    logger.info("Loaded %d rated titles from DB for similarity computation", len(titles))
    return titles


def search_people(query: str, limit: int = 20) -> list[dict]:
    """Search people by name using FTS5 with LIKE fallback.

    Returns dicts with keys: name_id, name, primary_profession, title_count.

    Uses FTS5 for fast word-prefix matching (e.g. "scor" finds "Scorsese").
    Falls back to LIKE for substring matches if FTS5 returns no results.
    Results are ordered by rated_count DESC, then title_count DESC.
    """
    db = _db_path()
    if not db.exists():
        return []
    conn = _connect()
    try:
        _ensure_schema(conn)  # applies additive migrations (title_count/rated_count columns)
        fts_q = _fts5_query(query)
        # Try FTS5 first (table may not exist if no pipeline run yet)
        if fts_q:
            try:
                rows = conn.execute(
                    "SELECT p.name_id, p.name, p.primary_profession, p.title_count "
                    "FROM people p "
                    "JOIN people_fts fts ON fts.rowid = p.rowid "
                    "WHERE people_fts MATCH ? "
                    "ORDER BY p.rated_count DESC, p.title_count DESC "
                    "LIMIT ?",
                    (fts_q, limit),
                ).fetchall()
                if rows:
                    return [dict(r) for r in rows]
            except sqlite3.OperationalError:
                pass  # FTS table not yet created; fall through to LIKE
        # Fallback to LIKE for substring matches
        rows = conn.execute(
            "SELECT name_id, name, primary_profession, title_count "
            "FROM people "
            "WHERE name LIKE ? COLLATE NOCASE "
            "ORDER BY rated_count DESC, title_count DESC "
            "LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()
