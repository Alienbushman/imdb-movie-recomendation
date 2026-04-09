import logging
import threading
import time
from datetime import UTC, datetime

from app.core.config import PROJECT_ROOT, get_settings
from app.models.schemas import (
    CandidateTitle,
    PipelineStatus,
    Recommendation,
    RecommendationFilters,
    RecommendationResponse,
)
from app.services.candidates import (
    download_datasets,
    load_candidates_from_datasets,
    load_crew_for_rated_titles,
)
from app.services.dismissed import get_dismissed_ids
from app.services.ingest import get_seen_imdb_ids, load_watchlist
from app.services.model import load_taste_model, train_taste_model
from app.services.recommend import build_recommendations
from app.services.scrape import fetch_imdb_ratings_csv, save_ratings_csv

logger = logging.getLogger(__name__)

_lock = threading.Lock()

# In-memory state — lightweight only; large collections live in scored_candidates.db
_state: dict = {
    "model": None,
    "feature_names": None,
    "mae": None,
    "taste_profile": None,
    "titles": None,
    "seen_ids": None,
    "last_run": None,
}


def run_pipeline(
    retrain: bool = False,
    filters: RecommendationFilters | None = None,
    imdb_url: str | None = None,
    force: bool = False,
) -> RecommendationResponse:
    """Execute the full recommendation pipeline.

    1. Ingest IMDB export
    2. Load candidates from IMDB datasets (reordered before model for taste profile)
    3. Train (or load) taste model
    4. Score all candidates, write to SQLite, cache lightweight state
    5. Filter and return grouped recommendations
    """
    if not _lock.acquire(timeout=300):
        raise RuntimeError("Pipeline is already running — try again later.")
    try:
        from app.services.scored_store import has_scored_results

        if not force and not retrain and imdb_url is None:
            if has_scored_results():
                logger.info(
                    "Scored DB already populated and no new data — returning cached results"
                )
                return get_recommendations_from_db(filters=filters)

        pipeline_start = time.perf_counter()
        settings = get_settings()
        logger.info("Pipeline started (retrain=%s, filters=%s)", retrain, filters is not None)

        # Step 1: Ingest
        logger.info("Step 1/4: Ingesting watchlist")
        t0 = time.perf_counter()
        if imdb_url:
            logger.info("Step 1/4: Fetching ratings CSV from IMDB URL")
            csv_content = fetch_imdb_ratings_csv(imdb_url)
            watchlist_path = PROJECT_ROOT / settings.data.watchlist_path
            save_ratings_csv(csv_content, watchlist_path)
            titles = load_watchlist(csv_content=csv_content)
        else:
            titles = load_watchlist()
        seen_ids = get_seen_imdb_ids(titles)

        # Merge dismissed into exclusion set so candidates are skipped before scoring
        dismissed = get_dismissed_ids()
        all_excluded = seen_ids | dismissed
        logger.info(
            "Step 1/4 completed in %.2fs — %d rated titles, %d seen + %d dismissed = %d excluded",
            time.perf_counter() - t0,
            len(titles),
            len(seen_ids),
            len(dismissed),
            len(all_excluded),
        )

        # Step 2: Load candidates (before model so we get rated person data for taste)
        logger.info("Step 2/4: Loading candidates from IMDB datasets")
        t0 = time.perf_counter()
        candidates, rated_actors, rated_writers, rated_composers, rated_cinematographers = (
            load_candidates_from_datasets(all_excluded)
        )
        logger.info(
            "Step 2/4 completed in %.2fs — %d candidates loaded",
            time.perf_counter() - t0,
            len(candidates),
        )

        # On cache hits, rated_actors/composers/cinematographers are None.
        # Load them separately so actors like Paul Newman get indexed in title_people.
        if rated_actors is None:
            logger.info("Step 2/4: Cache hit — loading crew for %d rated titles", len(titles))
            rated_actors, rated_composers, rated_cinematographers = load_crew_for_rated_titles(
                [t.imdb_id for t in titles]
            )

        # Step 3: Train or load model
        logger.info("Step 3/4: Preparing taste model (retrain=%s)", retrain)
        t0 = time.perf_counter()
        loaded = None if retrain else load_taste_model()
        if loaded is not None:
            model, feature_names, taste = loaded
            mae = None
            logger.info(
                "Step 3/4 completed in %.2fs — loaded existing model (%d features)",
                time.perf_counter() - t0,
                len(feature_names),
            )
        else:
            model, mae, feature_names, taste = train_taste_model(
                titles, rated_actors, rated_writers, rated_composers, rated_cinematographers
            )
            logger.info(
                "Step 3/4 completed in %.2fs — trained new model (MAE=%.3f, %d features)",
                time.perf_counter() - t0,
                mae,
                len(feature_names),
            )

        # Step 4: Score and recommend
        logger.info("Step 4/4: Scoring and ranking %d candidates", len(candidates))
        t0 = time.perf_counter()
        response, scored, _importances = build_recommendations(
            model,
            feature_names,
            candidates,
            seen_ids,
            mae,
            filters=filters,
            rated_titles=titles,
            taste=taste,
        )
        logger.info(
            "Step 4/4 completed in %.2fs — %d movies, %d series, %d anime",
            time.perf_counter() - t0,
            len(response.movies),
            len(response.series),
            len(response.anime),
        )

        # Persist all scored candidates to SQLite for subsequent GET requests
        from app.services.scored_store import save_scored, write_people, write_rated_titles

        scored_candidates = [(c, s) for c, _, s in scored]
        save_scored(scored_candidates)
        write_rated_titles(titles)

        # Populate people and title_people tables for the person browse feature
        people_map: dict[str, dict] = {}
        title_people_rows: list[dict] = []
        for candidate, _score in scored_candidates:
            for role, names in [
                ("director", candidate.directors),
                ("actor", candidate.actors),
                ("writer", candidate.writers),
                ("composer", candidate.composers),
                ("cinematographer", candidate.cinematographers),
            ]:
                for name in names:
                    name_id = name.lower()
                    if name_id not in people_map:
                        people_map[name_id] = {"name_id": name_id, "name": name}
                    title_people_rows.append(
                        {"imdb_id": candidate.imdb_id, "name_id": name_id, "role": role}
                    )
        # Index all crew roles from rated titles so person search finds actors/writers/etc.
        # directors and writers come from the IMDB CSV (always available).
        # actors/composers/cinematographers come from the dataset build (None on cache hits).
        for rated in titles:
            rated_role_lists: list[tuple[str, list[str]]] = [
                ("director", rated.directors),
                ("writer", rated.writers),
            ]
            if rated_actors is not None:
                rated_role_lists.append(("actor", rated_actors.get(rated.imdb_id, [])))
            if rated_composers is not None:
                rated_role_lists.append(("composer", rated_composers.get(rated.imdb_id, [])))
            if rated_cinematographers is not None:
                rated_role_lists.append(
                    ("cinematographer", rated_cinematographers.get(rated.imdb_id, []))
                )
            for role, names in rated_role_lists:
                for name in names:
                    name_id = name.lower()
                    if name_id not in people_map:
                        people_map[name_id] = {"name_id": name_id, "name": name}
                    title_people_rows.append(
                        {"imdb_id": rated.imdb_id, "name_id": name_id, "role": role}
                    )

        write_people(list(people_map.values()), title_people_rows)

        # Cache lightweight state only — large collections are in scored_candidates.db
        _state.update(
            model=model,
            feature_names=feature_names,
            mae=mae,
            taste_profile=taste,
            titles=titles,
            seen_ids=seen_ids,
            last_run=datetime.now(UTC).isoformat(),
        )

        total = time.perf_counter() - pipeline_start
        logger.info("Pipeline finished in %.2fs", total)
        return response
    finally:
        _lock.release()


def get_recommendations_from_db(
    filters: RecommendationFilters | None = None,
) -> RecommendationResponse:
    """Build recommendations by querying SQLite + computing explanations for top-N.

    This is the fast path for GET endpoints. It queries scored_candidates.db,
    then computes feature vectors and explanations only for the small result set.
    Falls back to loading the taste model from disk if _state["model"] is None
    (e.g. after a server restart that preserved the DB file).
    """
    from app.services.features import candidate_to_features
    from app.services.model import get_feature_importances
    from app.services.recommend import _explain_prediction, _find_similar_rated
    from app.services.scored_store import query_candidates

    settings = get_settings()
    rec_cfg = settings.recommendations
    cat_cfg = settings.categories

    model = _state["model"]
    feature_names = _state["feature_names"]
    taste = _state["taste_profile"]
    rated_titles = _state["titles"] or []
    seen_ids = _state["seen_ids"] if _state["seen_ids"] is not None else set()
    mae = _state["mae"]

    if model is None:
        loaded = load_taste_model()
        if loaded is None:
            raise ValueError("No scored results available. Run POST /recommendations first.")
        model, feature_names, taste = loaded
        _state.update(model=model, feature_names=feature_names, taste_profile=taste)

    dismissed = get_dismissed_ids()
    all_excluded = seen_ids | dismissed

    min_score = (
        filters.min_predicted_score
        if filters and filters.min_predicted_score is not None
        else rec_cfg.min_predicted_score
    )
    top_n_movies = (
        filters.top_n_movies
        if filters and filters.top_n_movies is not None
        else rec_cfg.top_n_movies
    )
    top_n_series = (
        filters.top_n_series
        if filters and filters.top_n_series is not None
        else rec_cfg.top_n_series
    )
    top_n_animation = (
        filters.top_n_anime
        if filters and filters.top_n_anime is not None
        else rec_cfg.top_n_anime
    )

    movie_cfg = cat_cfg.get("movie")
    series_cfg = cat_cfg.get("series")
    movie_types = movie_cfg.title_types if movie_cfg else ["movie", "tvMovie"]
    series_types = series_cfg.title_types if series_cfg else ["tvSeries", "tvMiniSeries"]

    def _without_animation(f: RecommendationFilters | None) -> RecommendationFilters:
        """Return filters with Animation excluded (movies and series must not be anime)."""
        if f is None:
            return RecommendationFilters(exclude_genres=["Animation"])
        excl = list(set(f.exclude_genres or []) | {"Animation"})
        return f.model_copy(update={"exclude_genres": excl})

    movies_raw = query_candidates(
        filters=_without_animation(filters),
        title_types=movie_types,
        anime_only=False,
        top_n=top_n_movies,
        dismissed_ids=all_excluded,
        min_score=min_score,
    )
    series_raw = query_candidates(
        filters=_without_animation(filters),
        title_types=series_types,
        anime_only=False,
        top_n=top_n_series,
        dismissed_ids=all_excluded,
        min_score=min_score,
    )
    animation_raw = query_candidates(
        filters=filters,
        title_types=None,
        anime_only=True,
        top_n=top_n_animation,
        dismissed_ids=all_excluded,
        min_score=min_score,
    )

    importances = get_feature_importances(model, feature_names)

    def _build(candidates_with_scores: list[tuple[CandidateTitle, float]]) -> list[Recommendation]:
        result = []
        for candidate, score in candidates_with_scores:
            fv = candidate_to_features(candidate, taste)
            similar = _find_similar_rated(candidate.genres, rated_titles)
            result.append(
                Recommendation(
                    title=candidate.title,
                    title_type=candidate.title_type,
                    year=candidate.year,
                    genres=candidate.genres,
                    predicted_score=round(score, 2),
                    imdb_rating=candidate.imdb_rating,
                    explanation=_explain_prediction(
                        fv, importances, candidate, rated_titles, similar
                    ),
                    actors=candidate.actors[:3],
                    director=candidate.directors[0] if candidate.directors else None,
                    similar_to=similar,
                    language=candidate.language,
                    country_code=candidate.country_code,
                    imdb_id=candidate.imdb_id,
                    imdb_url=f"https://www.imdb.com/title/{candidate.imdb_id}",
                    num_votes=candidate.num_votes,
                )
            )
        return result

    return RecommendationResponse(
        movies=_build(movies_raw),
        series=_build(series_raw),
        anime=_build(animation_raw),
        model_accuracy=round(mae, 3) if mae else None,
    )


def ensure_datasets() -> str:
    """Download IMDB datasets if not present. Returns status message."""
    logger.info("Ensuring IMDB datasets are present")
    t0 = time.perf_counter()
    download_datasets()
    logger.info("Dataset check completed in %.2fs", time.perf_counter() - t0)
    return "Datasets ready."


def get_pipeline_status() -> PipelineStatus:
    """Return current pipeline state."""
    from app.services.candidates import datasets_ready as _datasets_ready
    from app.services.candidates import is_datasets_downloading
    from app.services.scored_store import get_scored_count, has_scored_results

    settings = get_settings()
    watchlist_path = PROJECT_ROOT / settings.data.watchlist_path

    return PipelineStatus(
        rated_titles_count=len(_state["titles"]) if _state["titles"] else 0,
        candidates_count=get_scored_count(),
        model_trained=_state["model"] is not None,
        last_run=_state["last_run"],
        datasets_ready=_datasets_ready(),
        datasets_downloading=is_datasets_downloading(),
        watchlist_ready=watchlist_path.exists() and watchlist_path.stat().st_size > 0,
        scored_db_ready=has_scored_results(),
    )
