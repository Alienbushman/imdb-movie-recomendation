import json
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile

from app.core.config import PROJECT_ROOT, get_settings
from app.models.schemas import (
    DatasetDownloadResponse,
    DismissedListResponse,
    DismissResponse,
    PersonSearchResult,
    PersonTitleResult,
    PersonTitlesResponse,
    PipelineStatus,
    Recommendation,
    RecommendationFilters,
    RecommendationResponse,
    SimilarResponse,
    TitleSearchResult,
)
from app.services.dismissed import (
    dismiss_title,
    get_dismissed_ids,
    get_dismissed_with_metadata,
    restore_title,
)
from app.services.pipeline import (
    ensure_datasets,
    get_pipeline_status,
    get_recommendations_from_db,
    run_pipeline,
)
from app.services.scored_store import (
    get_person,
    has_scored_results,
    query_titles_by_person,
    search_people,
    search_titles,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


@router.post(
    "/download-datasets",
    response_model=DatasetDownloadResponse,
    summary="Download IMDB dataset files",
    tags=["Setup"],
    responses={
        200: {"description": "Datasets are already present or were downloaded successfully."},
        500: {"description": "Download failed (network error or disk issue)."},
    },
)
def download_datasets():
    """Download the two IMDB bulk dataset files needed to generate recommendations.

    - **title.basics.tsv.gz** (~210 MB compressed) — title metadata: type, year, runtime, genres
    - **title.ratings.tsv.gz** (~8 MB compressed) — community ratings and vote counts

    Files are saved to `data/datasets/` and only downloaded if not already present,
    so this endpoint is safe to call repeatedly. Re-call it whenever you want to refresh
    the datasets with the latest IMDB data.

    **This must be run before calling any `/recommendations` endpoint.**
    """
    logger.info("POST /download-datasets — starting dataset download")
    try:
        msg = ensure_datasets()
        logger.info("POST /download-datasets — completed: %s", msg)
        return {"status": msg}
    except Exception as e:
        logger.exception("POST /download-datasets — failed")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get(
    "/status",
    response_model=PipelineStatus,
    summary="Pipeline status",
    tags=["Setup"],
    responses={
        200: {"description": "Current pipeline state."},
    },
)
def get_status():
    """Return the current state of the recommendation pipeline.

    Useful for checking whether the model has been trained and how many
    candidates are loaded, without triggering a full pipeline run.
    `last_run` is `null` if the pipeline has not been run since the server started.
    """
    return get_pipeline_status()


# ---------------------------------------------------------------------------
# Person Browse — Search
# ---------------------------------------------------------------------------


@router.get(
    "/people/search",
    response_model=list[PersonSearchResult],
    summary="Search for a director or actor by name",
    tags=["Person Browse"],
)
def search_people_endpoint(
    q: str = Query(..., min_length=2, description="Name search query (min 2 characters)"),
    limit: int = Query(20, ge=1, le=50),
):
    """Return people (directors/actors/writers) whose name contains the query string."""
    if not has_scored_results():
        return []
    rows = search_people(q, limit)
    return [PersonSearchResult(**r) for r in rows]


@router.get(
    "/people/{name_id:path}",
    response_model=PersonTitlesResponse,
    summary="Get top-scored titles featuring a director or actor",
    tags=["Person Browse"],
    responses={
        200: {"description": "Titles featuring this person, ranked by predicted score."},
        404: {"description": "Person not found."},
        503: {"description": "Pipeline has not been run yet."},
    },
)
def titles_by_person(
    name_id: str,
    limit: int = Query(100, ge=1, le=500),
    min_year: int | None = Query(None, description="Exclude titles released before this year."),
    max_year: int | None = Query(None, description="Exclude titles released after this year."),
    min_rating: float | None = Query(None, description="Minimum IMDB rating.", ge=0.0, le=10.0),
    min_votes: int | None = Query(None, description="Minimum IMDB vote count.", ge=0),
    max_runtime: int | None = Query(None, description="Maximum runtime in minutes.", ge=0),
):
    """Return scored titles featuring the given person, ranked by predicted taste score."""
    if not has_scored_results():
        raise HTTPException(status_code=503, detail="Pipeline has not been run yet.")

    person = get_person(name_id)
    if person is None:
        raise HTTPException(status_code=404, detail=f"Person {name_id!r} not found.")

    dismissed = get_dismissed_ids()
    total, rows = query_titles_by_person(
        name_id=name_id,
        limit=limit,
        min_year=min_year,
        max_year=max_year,
        min_rating=min_rating,
        min_votes=min_votes,
        max_runtime=max_runtime,
        dismissed_ids=dismissed,
    )

    results = [
        PersonTitleResult(
            imdb_id=row["imdb_id"],
            title=row["title"],
            year=row["year"],
            title_type=row["title_type"],
            imdb_rating=row["imdb_rating"],
            num_votes=row["num_votes"],
            runtime_mins=row["runtime_mins"],
            genres=json.loads(row["genres"]),
            predicted_score=row["predicted_score"],
            languages=json.loads(row["languages"] or "[]"),
            roles=row["roles_csv"].split(",") if row.get("roles_csv") else [],
            is_rated=bool(row["is_rated"]),
        )
        for row in rows
    ]
    return PersonTitlesResponse(
        name_id=person["name_id"],
        name=person["name"],
        primary_profession=person.get("primary_profession"),
        total=total,
        results=results,
    )


# ---------------------------------------------------------------------------
# Similar — Title Search
# ---------------------------------------------------------------------------


@router.get(
    "/search",
    response_model=list[TitleSearchResult],
    summary="Search titles by name",
    tags=["Similar"],
)
def search_titles_endpoint(
    q: str = Query(..., min_length=2, description="Search query (minimum 2 characters)"),
    limit: int = Query(20, ge=1, le=50, description="Max results to return"),
):
    """Search for titles by name substring. Returns lightweight results for autocomplete.

    Searches both the scored candidates database and the user's rated watchlist.
    Rated titles are marked with `is_rated=True` and sorted first.
    """
    from app.services.pipeline import _state

    # 1. Search scored candidates DB
    db_hits = search_titles(q, limit)
    results_by_id: dict[str, TitleSearchResult] = {}
    for row in db_hits:
        results_by_id[row["imdb_id"]] = TitleSearchResult(
            imdb_id=row["imdb_id"],
            title=row["title"],
            year=row["year"],
            title_type=row["title_type"],
            is_rated=bool(row["is_rated"]),
        )

    # 2. Search rated titles (if pipeline has been run)
    rated_titles = _state.get("titles") or []
    q_lower = q.lower()
    for rt in rated_titles:
        if q_lower in rt.title.lower():
            results_by_id[rt.imdb_id] = TitleSearchResult(
                imdb_id=rt.imdb_id,
                title=rt.title,
                year=rt.year,
                title_type=rt.title_type,
                is_rated=True,
            )

    # 3. Sort: rated first, then by title length (shorter = more relevant)
    results = sorted(
        results_by_id.values(),
        key=lambda r: (not r.is_rated, len(r.title)),
    )
    return results[:limit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_filters(
    min_year: int | None = Query(None, description="Exclude titles released before this year."),
    max_year: int | None = Query(None, description="Exclude titles released after this year."),
    genres: list[str] | None = Query(
        None,
        description="Include titles matching any of these genres.",
    ),
    exclude_genres: list[str] | None = Query(
        None,
        description="Exclude titles matching any of these genres.",
    ),
    language: str | None = Query(
        None,
        description="Only include titles in this language.",
    ),
    exclude_languages: list[str] | None = Query(
        None,
        description="Exclude titles in any of these languages.",
    ),
    min_imdb_rating: float | None = Query(
        None,
        description="Minimum IMDB rating.",
        ge=0.0,
        le=10.0,
    ),
    max_runtime: int | None = Query(None, description="Maximum runtime in minutes.", ge=0),
    min_predicted_score: float | None = Query(
        None,
        description="Override min predicted score.",
        ge=1.0,
        le=10.0,
    ),
    top_n_movies: int | None = Query(
        None,
        description="Override number of movie recommendations.",
        ge=0,
        le=100,
    ),
    top_n_series: int | None = Query(
        None,
        description="Override number of series recommendations.",
        ge=0,
        le=100,
    ),
    top_n_anime: int | None = Query(
        None,
        description="Override number of anime recommendations.",
        ge=0,
        le=100,
    ),
    country_code: str | None = Query(
        None,
        description="Only include titles from this country (e.g. 'US', 'JP'). Case-insensitive.",
    ),
    min_vote_count: int | None = Query(
        None,
        description="Minimum IMDB vote count.",
        ge=0,
    ),
) -> RecommendationFilters | None:
    """Shared dependency: assemble RecommendationFilters from query params, or None."""
    f = RecommendationFilters(
        min_year=min_year,
        max_year=max_year,
        genres=genres,
        exclude_genres=exclude_genres,
        language=language,
        exclude_languages=exclude_languages,
        min_imdb_rating=min_imdb_rating,
        max_runtime=max_runtime,
        min_predicted_score=min_predicted_score,
        top_n_movies=top_n_movies,
        top_n_series=top_n_series,
        top_n_anime=top_n_anime,
        country_code=country_code,
        min_vote_count=min_vote_count,
    )
    if all(v is None for v in f.model_dump().values()):
        return None
    return f


FilterDeps = Annotated[RecommendationFilters | None, Depends(_parse_filters)]


# ---------------------------------------------------------------------------
# Similar — Find Similar Titles
# ---------------------------------------------------------------------------


@router.get(
    "/similar/{imdb_id}",
    response_model=SimilarResponse,
    summary="Find titles similar to a given title",
    tags=["Similar"],
    responses={
        200: {"description": "Similar titles found."},
        404: {"description": "Seed title not found."},
        409: {"description": "Pipeline has not been run yet — no scored data."},
    },
)
def get_similar_titles(
    imdb_id: str = Path(description="IMDB ID of the seed title", pattern=r"^tt\d+$"),
    filters: FilterDeps = None,
    top_n: int = Query(50, ge=1, le=200, description="Max similar titles to return"),
    seen: bool | None = Query(
        None,
        description="Filter by seen status: true=only rated, false=only unrated, null=all",
    ),
):
    """Find titles most similar to a given seed title.

    Similarity is computed using genre overlap, shared directors/actors,
    language match, era proximity, and IMDB rating proximity. Results include
    a similarity score (0-1) and human-readable explanations.

    Use the `seen` parameter to filter by whether the user has rated the title.
    """
    from app.services.similar import find_similar

    try:
        return find_similar(imdb_id, filters, top_n, seen)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


@router.post(
    "/recommendations",
    response_model=RecommendationResponse,
    summary="Generate all recommendations",
    tags=["Recommendations"],
    responses={
        200: {"description": "Recommendations generated successfully."},
        404: {
            "description": "IMDB dataset files not found. Call `/download-datasets` first.",
        },
        400: {"description": "Invalid input or configuration error."},
    },
)
def generate_recommendations(
    filters: FilterDeps,
    retrain: bool = Query(
        False,
        description=(
            "Force retraining the LightGBM taste model from scratch, even if a saved "
            "model already exists on disk. Use this after re-exporting your IMDB watchlist "
            "to incorporate new ratings."
        ),
    ),
    imdb_url: str | None = Query(
        None,
        description=(
            "IMDB user ratings URL (e.g. https://www.imdb.com/user/ur38228117/ratings/). "
            "If provided, ratings are fetched from IMDB instead of reading the local CSV."
        ),
    ),
    force: bool = Query(
        False,
        description="Force a full pipeline re-run even if cached scores exist.",
    ),
):
    """Run the full recommendation pipeline and return results for all categories.

    The pipeline executes four steps:

    1. **Ingest** — acquire ratings via IMDB URL fetch, local CSV, or prior upload
    2. **Model** — load or train a LightGBM model that predicts your rating for any title,
       using features like IMDb rating, genres, year, runtime, and vote count
    3. **Candidates** — load unseen titles from the IMDB bulk datasets, filtered by
       vote count, rating floor, and year floor (all configurable in `config.yaml`)
    4. **Score & rank** — predict a score for each candidate and return the top-N
       per category

    Results are split into `movies`, `series`, and `anime`.
    The `model_accuracy` field shows the Mean Absolute Error on a held-out test set
    (only present when `retrain=true` or on first run).
    """
    logger.info(
        "POST /recommendations — retrain=%s imdb_url=%s filters=%s",
        retrain,
        imdb_url,
        filters.model_dump(exclude_none=True) if filters else None,
    )
    try:
        result = run_pipeline(retrain=retrain, filters=filters, imdb_url=imdb_url, force=force)
        logger.info(
            "POST /recommendations — done: %d movies, %d series, %d anime",
            len(result.movies),
            len(result.series),
            len(result.anime),
        )
        return result
    except FileNotFoundError as e:
        logger.error("POST /recommendations — datasets not found: %s", e)
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        logger.error("POST /recommendations — bad input: %s", e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        logger.error("POST /recommendations — IMDB fetch error: %s", e)
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        # Catch Playwright timeout / connection errors and any other unexpected errors
        logger.error("POST /recommendations — unexpected error: %s", e)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to fetch ratings: {e}",
        )


@router.post(
    "/recommendations/filter",
    response_model=RecommendationResponse,
    summary="Re-filter cached recommendations",
    tags=["Recommendations"],
    responses={
        200: {"description": "Recommendations re-filtered from cached scores."},
        409: {"description": "Pipeline has not been run yet — no cached scores."},
    },
)
def filter_cached_recommendations(filters: FilterDeps):
    """Re-filter previously scored candidates with new filter parameters.

    Queries the SQLite scored-candidates store — no model re-run needed.
    Response time is under a second for typical result sets.

    Returns `409` if the pipeline has not been run yet.
    """
    logger.info(
        "POST /recommendations/filter — filters=%s",
        filters.model_dump(exclude_none=True) if filters else None,
    )
    if not has_scored_results():
        raise HTTPException(
            status_code=409,
            detail="No scored results available. Run POST /recommendations first.",
        )
    return get_recommendations_from_db(filters=filters)


@router.get(
    "/recommendations/movies",
    response_model=list[Recommendation],
    summary="Get movie recommendations",
    tags=["Recommendations"],
    responses={
        200: {"description": "List of movie recommendations sorted by predicted score."},
        404: {"description": "IMDB dataset files not found."},
    },
)
def get_movie_recommendations(filters: FilterDeps):
    """Return only the movie recommendations from the pipeline.

    Includes `movie` and `tvMovie` title types. Animation films are **excluded**
    here and appear in `/recommendations/anime` instead.

    Runs the full pipeline on first call; subsequent calls within the same
    server session reuse the cached model and candidates.
    """
    logger.info(
        "GET /recommendations/movies — filters=%s",
        filters.model_dump(exclude_none=True) if filters else None,
    )
    try:
        if has_scored_results():
            movies = get_recommendations_from_db(filters=filters).movies
        else:
            movies = run_pipeline(filters=filters).movies
        logger.info("GET /recommendations/movies — returning %d movies", len(movies))
        return movies
    except FileNotFoundError as e:
        logger.error("GET /recommendations/movies — datasets not found: %s", e)
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get(
    "/recommendations/series",
    response_model=list[Recommendation],
    summary="Get series recommendations",
    tags=["Recommendations"],
    responses={
        200: {"description": "List of series recommendations sorted by predicted score."},
        404: {"description": "IMDB dataset files not found."},
    },
)
def get_series_recommendations(filters: FilterDeps):
    """Return only the series recommendations from the pipeline.

    Includes `tvSeries` and `tvMiniSeries` title types. Animated series are
    **excluded** here and appear in `/recommendations/anime` instead.
    """
    logger.info(
        "GET /recommendations/series — filters=%s",
        filters.model_dump(exclude_none=True) if filters else None,
    )
    try:
        if has_scored_results():
            series = get_recommendations_from_db(filters=filters).series
        else:
            series = run_pipeline(filters=filters).series
        logger.info("GET /recommendations/series — returning %d series", len(series))
        return series
    except FileNotFoundError as e:
        logger.error("GET /recommendations/series — datasets not found: %s", e)
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get(
    "/recommendations/anime",
    response_model=list[Recommendation],
    summary="Get anime recommendations",
    tags=["Recommendations"],
    responses={
        200: {"description": "List of anime recommendations sorted by predicted score."},
        404: {"description": "IMDB dataset files not found."},
    },
)
def get_anime_recommendations(filters: FilterDeps):
    """Return only anime recommendations from the pipeline.

    Matches titles identified as anime via the Fribb/anime-lists whitelist,
    with a fallback to JP country/Japanese language + Animation genre for titles
    not yet in the whitelist.
    """
    logger.info(
        "GET /recommendations/anime — filters=%s",
        filters.model_dump(exclude_none=True) if filters else None,
    )
    try:
        if has_scored_results():
            anime = get_recommendations_from_db(filters=filters).anime
        else:
            anime = run_pipeline(filters=filters).anime
        logger.info("GET /recommendations/anime — returning %d titles", len(anime))
        return anime
    except FileNotFoundError as e:
        logger.error("GET /recommendations/anime — datasets not found: %s", e)
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Watchlist upload
# ---------------------------------------------------------------------------


@router.post(
    "/upload-watchlist",
    summary="Upload IMDB ratings CSV",
    tags=["Setup"],
    responses={
        200: {"description": "Watchlist uploaded and saved successfully."},
        400: {"description": "File is not a .csv file."},
        422: {"description": "File does not look like an IMDB ratings export."},
    },
)
async def upload_watchlist(file: UploadFile = File(...)) -> dict:
    """Accept a manually exported IMDB ratings CSV and save it as the active watchlist.

    The file is saved to `data/watchlist.csv`. No pipeline run is triggered —
    click **Generate** after uploading to get fresh recommendations from the uploaded data.

    Use this as a fallback when the URL-based fetch is unavailable (e.g. private ratings).
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv file.")

    content = await file.read()
    text = content.decode("utf-8", errors="replace")

    if "Const" not in text or "Your Rating" not in text:
        raise HTTPException(
            status_code=422,
            detail=(
                "File does not appear to be an IMDB ratings export. "
                "Expected columns: Const, Your Rating."
            ),
        )

    settings = get_settings()
    watchlist_path = PROJECT_ROOT / settings.data.watchlist_path
    watchlist_path.parent.mkdir(parents=True, exist_ok=True)
    watchlist_path.write_text(text, encoding="utf-8")

    logger.info("POST /upload-watchlist — saved %s to %s", file.filename, watchlist_path)
    return {"message": "Watchlist uploaded successfully.", "filename": file.filename}


# ---------------------------------------------------------------------------
# Dismiss
# ---------------------------------------------------------------------------


@router.post(
    "/dismiss/{imdb_id}",
    response_model=DismissResponse,
    summary="Dismiss a recommendation",
    tags=["Dismiss"],
    responses={
        200: {"description": "Title dismissed successfully."},
        409: {"description": "Title was already dismissed."},
    },
)
def dismiss_recommendation(
    imdb_id: str = Path(description="IMDB title ID to dismiss.", pattern=r"^tt\d+$"),
):
    """Permanently dismiss a recommendation so it never appears again.

    The dismissed ID is persisted to `data/dismissed.json` and survives server restarts.
    Use `DELETE /dismiss/{imdb_id}` to restore a dismissed title.
    """
    logger.info("POST /dismiss/%s", imdb_id)
    added = dismiss_title(imdb_id)
    if not added:
        raise HTTPException(status_code=409, detail=f"{imdb_id} is already dismissed.")
    return DismissResponse(imdb_id=imdb_id, action="dismissed")


@router.delete(
    "/dismiss/{imdb_id}",
    response_model=DismissResponse,
    summary="Restore a dismissed recommendation",
    tags=["Dismiss"],
    responses={
        200: {"description": "Title restored successfully."},
        404: {"description": "Title was not in the dismissed list."},
    },
)
def restore_recommendation(
    imdb_id: str = Path(description="IMDB title ID to restore.", pattern=r"^tt\d+$"),
):
    """Remove a title from the dismissed list so it can be recommended again."""
    logger.info("DELETE /dismiss/%s", imdb_id)
    removed = restore_title(imdb_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"{imdb_id} is not dismissed.")
    return DismissResponse(imdb_id=imdb_id, action="restored")


@router.get(
    "/dismissed",
    response_model=DismissedListResponse,
    summary="List dismissed recommendations",
    tags=["Dismiss"],
    responses={
        200: {"description": "All currently dismissed IMDB IDs."},
    },
)
def list_dismissed():
    """Return all IMDB IDs that have been dismissed, enriched with title metadata."""
    ids = sorted(get_dismissed_ids())
    titles = get_dismissed_with_metadata()
    return DismissedListResponse(dismissed_ids=ids, dismissed_titles=titles, count=len(ids))
