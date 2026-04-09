"""End-to-end tests for ticket 018 — person browse shows rated + unrated titles.

These tests seed a real SQLite file (via the public write_* helpers) and then
query via query_titles_by_person to verify the UNION path end-to-end. They
cover the Paul Newman scenario: an actor whose films are all in the user's
watchlist and therefore only appear in rated_titles, not scored_candidates.
"""

import sqlite3
from unittest.mock import patch

import pytest

from app.models.schemas import CandidateTitle, RatedTitle
from app.services.scored_store import (
    _ensure_schema,
    query_titles_by_person,
    save_scored,
    search_people,
    write_people,
    write_rated_titles,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def isolated_db(tmp_path):
    """Point scored_store at a throwaway SQLite file for the duration of the test.

    Unlike test_scored_store.py which shares a single connection (breaks once
    close() runs), we patch _db_path so every _connect() call opens a fresh
    connection against the same file — matching production behaviour.
    """
    db_file = tmp_path / "scored_candidates.db"
    with patch("app.services.scored_store._db_path", return_value=db_file):
        # Ensure schema exists so write_* helpers work immediately
        conn = sqlite3.connect(str(db_file))
        _ensure_schema(conn)
        conn.close()
        yield db_file


def _make_rated(
    imdb_id: str,
    title: str,
    user_rating: int = 9,
    year: int = 1967,
    genres: list[str] | None = None,
    imdb_rating: float = 8.0,
    num_votes: int = 100_000,
    runtime_mins: int = 120,
    language: str = "English",
    directors: list[str] | None = None,
    writers: list[str] | None = None,
) -> RatedTitle:
    return RatedTitle(
        imdb_id=imdb_id,
        title=title,
        original_title=title,
        title_type="movie",
        user_rating=user_rating,
        date_rated="2020-01-01",
        imdb_rating=imdb_rating,
        runtime_mins=runtime_mins,
        year=year,
        genres=genres or ["Drama"],
        num_votes=num_votes,
        release_date=f"{year}-01-01",
        directors=directors or [],
        url=f"https://www.imdb.com/title/{imdb_id}/",
        language=language,
        writers=writers or [],
    )


def _make_candidate(
    imdb_id: str,
    title: str,
    year: int = 2020,
    genres: list[str] | None = None,
    imdb_rating: float = 7.5,
    num_votes: int = 50_000,
    actors: list[str] | None = None,
    directors: list[str] | None = None,
) -> CandidateTitle:
    return CandidateTitle(
        imdb_id=imdb_id,
        title=title,
        original_title=title,
        title_type="movie",
        imdb_rating=imdb_rating,
        runtime_mins=120,
        year=year,
        genres=genres or ["Drama"],
        num_votes=num_votes,
        directors=directors or [],
        actors=actors or [],
        language="English",
        languages=["English"],
        country_code="US",
    )


def _index_people_like_pipeline(
    rated_titles: list[RatedTitle],
    scored_candidates: list[tuple[CandidateTitle, float]],
    rated_actors: dict[str, list[str]] | None = None,
) -> None:
    """Mirror pipeline.py's people-writing loop for the isolated DB."""
    people_map: dict[str, dict] = {}
    title_people_rows: list[dict] = []

    for candidate, _score in scored_candidates:
        for role, names in [
            ("director", candidate.directors),
            ("actor", candidate.actors),
            ("writer", candidate.writers),
        ]:
            for name in names:
                name_id = name.lower()
                if name_id not in people_map:
                    people_map[name_id] = {"name_id": name_id, "name": name}
                title_people_rows.append(
                    {"imdb_id": candidate.imdb_id, "name_id": name_id, "role": role}
                )

    for rated in rated_titles:
        rated_role_lists: list[tuple[str, list[str]]] = [
            ("director", rated.directors),
            ("writer", rated.writers),
        ]
        if rated_actors is not None:
            rated_role_lists.append(("actor", rated_actors.get(rated.imdb_id, [])))
        for role, names in rated_role_lists:
            for name in names:
                name_id = name.lower()
                if name_id not in people_map:
                    people_map[name_id] = {"name_id": name_id, "name": name}
                title_people_rows.append(
                    {"imdb_id": rated.imdb_id, "name_id": name_id, "role": role}
                )

    write_people(list(people_map.values()), title_people_rows)


# ---------------------------------------------------------------------------
# The Paul Newman scenario — actor whose films are all rated
# ---------------------------------------------------------------------------


def test_paul_newman_rated_only_actor_appears_in_person_browse(isolated_db):
    """Actor whose films are all in the watchlist must still appear in person browse.

    This is the core ticket 018 regression: before the fix, rated-only actors
    had zero title_people rows and query_titles_by_person returned nothing.
    """
    rated = [
        _make_rated(
            "tt0061512",
            "Cool Hand Luke",
            user_rating=9,
            year=1967,
            imdb_rating=8.1,
            directors=["Stuart Rosenberg"],
        ),
        _make_rated(
            "tt0066249",
            "Butch Cassidy and the Sundance Kid",
            user_rating=10,
            year=1969,
            imdb_rating=8.0,
            directors=["George Roy Hill"],
        ),
    ]
    rated_actors = {
        "tt0061512": ["Paul Newman", "George Kennedy"],
        "tt0066249": ["Paul Newman", "Robert Redford"],
    }

    write_rated_titles(rated)
    _index_people_like_pipeline(rated, [], rated_actors=rated_actors)

    total, rows = query_titles_by_person("paul newman")

    assert total == 2, "Paul Newman should have 2 rated titles indexed"
    titles = {r["title"] for r in rows}
    assert titles == {"Cool Hand Luke", "Butch Cassidy and the Sundance Kid"}
    assert all(r["is_rated"] == 1 for r in rows), "All Paul Newman titles in this fixture are rated"


def test_paul_newman_shows_up_in_people_search(isolated_db):
    """search_people must return Paul Newman once his films are indexed.

    This guards the `/people/search` endpoint — before ST-001, actors from
    rated titles had no rows in title_people and the JOIN in search_people
    filtered them out.
    """
    rated = [_make_rated("tt0061512", "Cool Hand Luke")]
    rated_actors = {"tt0061512": ["Paul Newman"]}

    write_rated_titles(rated)
    _index_people_like_pipeline(rated, [], rated_actors=rated_actors)

    results = search_people("paul newman")
    assert len(results) == 1
    assert results[0]["name"] == "Paul Newman"
    assert results[0]["title_count"] == 1


# ---------------------------------------------------------------------------
# Mixed case — person appears in both rated and scored tables
# ---------------------------------------------------------------------------


def test_union_returns_both_rated_and_unrated_titles(isolated_db):
    """A director with some rated and some unrated films gets both in person browse."""
    rated = [
        _make_rated(
            "tt0109830",
            "Forrest Gump",
            user_rating=10,
            year=1994,
            imdb_rating=8.8,
            directors=["Robert Zemeckis"],
        ),
    ]
    candidates = [
        (
            _make_candidate(
                "tt0099674",
                "Back to the Future Part III",
                year=1990,
                imdb_rating=7.4,
                directors=["Robert Zemeckis"],
            ),
            8.2,  # predicted_score
        ),
    ]

    write_rated_titles(rated)
    save_scored(candidates)
    _index_people_like_pipeline(rated, candidates)

    total, rows = query_titles_by_person("robert zemeckis")

    assert total == 2
    by_id = {r["imdb_id"]: r for r in rows}
    assert by_id["tt0109830"]["is_rated"] == 1  # rated (Forrest Gump)
    assert by_id["tt0099674"]["is_rated"] == 0  # unrated (Back to the Future III)
    # Rated title's predicted_score should be the user's own rating
    assert by_id["tt0109830"]["predicted_score"] == 10.0
    assert by_id["tt0099674"]["predicted_score"] == 8.2


def test_union_results_include_display_columns(isolated_db):
    """Rated-branch rows must include genres/languages/imdb_rating for the card UI."""
    rated = [
        _make_rated(
            "tt0061512",
            "Cool Hand Luke",
            year=1967,
            imdb_rating=8.1,
            genres=["Crime", "Drama"],
            language="English",
            directors=["Stuart Rosenberg"],
        ),
    ]
    write_rated_titles(rated)
    _index_people_like_pipeline(rated, [])

    _, rows = query_titles_by_person("stuart rosenberg")
    assert len(rows) == 1
    row = rows[0]
    # Display columns required by the frontend card
    assert row["imdb_rating"] == 8.1
    assert row["year"] == 1967
    assert '"Crime"' in row["genres"]
    assert '"Drama"' in row["genres"]
    assert '"English"' in row["languages"]
    assert row["roles_csv"] == "director"


# ---------------------------------------------------------------------------
# Filter parity — filters must apply to both union branches
# ---------------------------------------------------------------------------


def test_min_year_filter_applies_to_rated_branch(isolated_db):
    """min_year must filter the rated branch the same as the scored branch."""
    rated = [
        _make_rated("tt0061512", "Cool Hand Luke", year=1967, directors=["X"]),
        _make_rated("tt0066249", "Butch Cassidy", year=1969, directors=["X"]),
        _make_rated("tt0082971", "Raiders", year=1981, directors=["X"]),
    ]
    write_rated_titles(rated)
    _index_people_like_pipeline(rated, [])

    total, rows = query_titles_by_person("x", min_year=1970)
    assert total == 1
    assert rows[0]["imdb_id"] == "tt0082971"


def test_min_rating_filter_applies_to_rated_branch(isolated_db):
    """min_rating must filter the rated branch by imdb_rating (not user_rating)."""
    rated = [
        _make_rated("tt1", "Low", imdb_rating=6.5, directors=["X"]),
        _make_rated("tt2", "High", imdb_rating=8.5, directors=["X"]),
    ]
    write_rated_titles(rated)
    _index_people_like_pipeline(rated, [])

    total, rows = query_titles_by_person("x", min_rating=7.0)
    assert total == 1
    assert rows[0]["imdb_id"] == "tt2"


# ---------------------------------------------------------------------------
# rated_titles schema enrichment
# ---------------------------------------------------------------------------


def test_write_rated_titles_persists_display_columns(isolated_db):
    """write_rated_titles must populate the new display columns added in ST-002."""
    rated = [
        _make_rated(
            "tt0061512",
            "Cool Hand Luke",
            year=1967,
            imdb_rating=8.1,
            num_votes=175_000,
            runtime_mins=127,
            genres=["Crime", "Drama"],
            language="English",
            user_rating=9,
        ),
    ]
    write_rated_titles(rated)

    conn = sqlite3.connect(str(isolated_db))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM rated_titles WHERE imdb_id = ?", ("tt0061512",)).fetchone()
    conn.close()

    assert row is not None
    assert row["imdb_rating"] == 8.1
    assert row["num_votes"] == 175_000
    assert row["runtime_mins"] == 127
    assert '"Crime"' in row["genres"]
    assert '"English"' in row["languages"]
    assert row["user_rating"] == 9.0


def test_schema_migration_adds_columns_to_existing_legacy_table(tmp_path):
    """Existing databases with the old 4-column rated_titles must migrate cleanly.

    Simulates a user who had the pre-ST-002 schema and upgrades without
    deleting their DB.
    """
    db_file = tmp_path / "legacy.db"
    # Legacy schema (before ST-002): 4 columns only
    legacy = sqlite3.connect(str(db_file))
    legacy.execute("""
        CREATE TABLE rated_titles (
            imdb_id    TEXT PRIMARY KEY,
            title      TEXT NOT NULL,
            year       INTEGER,
            title_type TEXT NOT NULL
        )
    """)
    legacy.execute(
        "INSERT INTO rated_titles VALUES (?, ?, ?, ?)",
        ("tt0061512", "Cool Hand Luke", 1967, "movie"),
    )
    legacy.commit()
    legacy.close()

    with patch("app.services.scored_store._db_path", return_value=db_file):
        conn = sqlite3.connect(str(db_file))
        _ensure_schema(conn)
        conn.close()

    # Verify new columns exist
    conn = sqlite3.connect(str(db_file))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(rated_titles)").fetchall()}
    conn.close()

    expected = {"imdb_rating", "num_votes", "runtime_mins", "genres", "languages", "user_rating"}
    assert expected <= cols
    assert "title" in cols  # legacy columns preserved


# ---------------------------------------------------------------------------
# is_rated flag — must reach the result rows
# ---------------------------------------------------------------------------


def test_is_rated_flag_is_int_zero_or_one(isolated_db):
    """is_rated comes through as 1 for rated branch, 0 for scored branch."""
    rated = [_make_rated("tt1", "Rated", directors=["Shared Person"])]
    candidates = [
        (_make_candidate("tt2", "Unrated", directors=["Shared Person"]), 7.5),
    ]
    write_rated_titles(rated)
    save_scored(candidates)
    _index_people_like_pipeline(rated, candidates)

    _, rows = query_titles_by_person("shared person")
    by_id = {r["imdb_id"]: r["is_rated"] for r in rows}
    assert by_id["tt1"] == 1
    assert by_id["tt2"] == 0


# ---------------------------------------------------------------------------
# Empty / unknown person
# ---------------------------------------------------------------------------


def test_unknown_person_returns_empty(isolated_db):
    total, rows = query_titles_by_person("nobody at all")
    assert total == 0
    assert rows == []
