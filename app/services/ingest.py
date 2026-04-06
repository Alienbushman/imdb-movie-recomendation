import io
import logging
import time
from collections import Counter
from pathlib import Path

import pandas as pd

from app.core.config import PROJECT_ROOT, get_settings
from app.models.schemas import RatedTitle

logger = logging.getLogger(__name__)


def _parse_list_field(value: str) -> list[str]:
    """Parse a comma-separated string field into a list of stripped strings."""
    if pd.isna(value) or not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def load_watchlist(
    path: Path | None = None,
    csv_content: str | None = None,
) -> list[RatedTitle]:
    """Load and parse the IMDB watchlist CSV export into typed models."""
    t0 = time.perf_counter()
    if csv_content is not None:
        logger.info("Loading watchlist from CSV content string")
        df = pd.read_csv(io.StringIO(csv_content))
    elif path is None:
        settings = get_settings()
        path = PROJECT_ROOT / settings.data.watchlist_path
        logger.info("Loading watchlist from %s", path)
        df = pd.read_csv(path)
    else:
        logger.info("Loading watchlist from %s", path)
        df = pd.read_csv(path)
    logger.info(
        "Read CSV: %d rows, %d columns in %.2fs",
        len(df),
        len(df.columns),
        time.perf_counter() - t0,
    )

    column_map = {
        "Const": "imdb_id",
        "Your Rating": "user_rating",
        "Date Rated": "date_rated",
        "Title": "title",
        "Original Title": "original_title",
        "URL": "url",
        "Title Type": "title_type",
        "IMDb Rating": "imdb_rating",
        "Runtime (mins)": "runtime_mins",
        "Year": "year",
        "Genres": "genres",
        "Num Votes": "num_votes",
        "Release Date": "release_date",
        "Directors": "directors",
    }
    df = df.rename(columns=column_map)

    titles = []
    skipped = 0
    for _, row in df.iterrows():
        try:
            title = RatedTitle(
                imdb_id=row["imdb_id"],
                title=row["title"],
                original_title=row["original_title"],
                title_type=row["title_type"],
                user_rating=int(row["user_rating"]),
                date_rated=row["date_rated"],
                imdb_rating=float(row["imdb_rating"]),
                runtime_mins=int(row["runtime_mins"]) if pd.notna(row["runtime_mins"]) else None,
                year=int(row["year"]),
                genres=_parse_list_field(row["genres"]),
                num_votes=int(row["num_votes"]),
                release_date=str(row["release_date"]),
                directors=_parse_list_field(row.get("directors", "")),
                url=row["url"],
            )
            titles.append(title)
        except Exception:
            skipped += 1
            logger.warning("Skipping row with imdb_id=%s: parse error", row.get("imdb_id"))

    type_counts = Counter(t.title_type for t in titles)
    rating_avg = sum(t.user_rating for t in titles) / len(titles) if titles else 0
    year_range = (min(t.year for t in titles), max(t.year for t in titles)) if titles else (0, 0)
    logger.info(
        "Loaded %d rated titles (%d skipped) in %.2fs — types: %s, avg rating: %.1f, years: %d–%d",
        len(titles),
        skipped,
        time.perf_counter() - t0,
        dict(type_counts),
        rating_avg,
        year_range[0],
        year_range[1],
    )
    return titles


def get_seen_imdb_ids(titles: list[RatedTitle]) -> set[str]:
    """Extract the set of IMDB IDs the user has already rated."""
    return {t.imdb_id for t in titles}
