"""Scoring, filtering, ranking, and explanation generation for recommendations.

Takes a trained LightGBM model and a list of candidate titles, predicts a score
for each, applies runtime filters, and returns ranked results with human-readable
explanations.

Key functions:
- ``score_candidates`` — batch-predict scores for all candidates using the model
- ``filter_candidates`` — apply scalar filters (min votes, year, rating) from config
- ``build_recommendations`` — convert scored candidates into ``Recommendation`` objects
  with explanation strings (genre matches, director affinity, etc.)
- ``get_recommendations`` — top-level orchestrator called by the pipeline

Results are persisted to SQLite by ``scored_store.write_candidates`` immediately after
scoring; GET endpoints query the DB directly and do not call this module at serve time.
"""
import logging
import time

from app.core.config import get_settings
from app.models.schemas import (
    CandidateTitle,
    FeatureVector,
    RatedTitle,
    Recommendation,
    RecommendationFilters,
    RecommendationResponse,
    TasteProfile,
)
from app.services.features import candidate_to_features
from app.services.model import get_feature_importances, predict_scores

logger = logging.getLogger(__name__)


def _apply_runtime_filters(
    scored: list[tuple[CandidateTitle, FeatureVector, float]],
    filters: RecommendationFilters,
) -> list[tuple[CandidateTitle, FeatureVector, float]]:
    """Apply user-supplied runtime filters to scored candidates."""
    before = len(scored)
    result = scored
    if filters.min_year is not None:
        min_y = filters.min_year
        result = [(c, fv, s) for c, fv, s in result if c.year is not None and c.year >= min_y]
        logger.info("  Filter min_year>=%d: %d → %d candidates", min_y, before, len(result))
        before = len(result)
    if filters.max_year is not None:
        max_y = filters.max_year
        result = [(c, fv, s) for c, fv, s in result if c.year is not None and c.year <= max_y]
        logger.info("  Filter max_year<=%d: %d → %d candidates", max_y, before, len(result))
        before = len(result)
    if filters.genres is not None:
        genre_set = {g.strip() for g in filters.genres}
        result = [(c, fv, s) for c, fv, s in result if genre_set & set(c.genres)]
        logger.info("  Filter genres=%s: %d → %d candidates", genre_set, before, len(result))
        before = len(result)
    if filters.exclude_genres is not None:
        exclude_set = {g.strip() for g in filters.exclude_genres}
        result = [(c, fv, s) for c, fv, s in result if not (exclude_set & set(c.genres))]
        logger.info(
            "  Filter exclude_genres=%s: %d → %d candidates",
            exclude_set,
            before,
            len(result),
        )
        before = len(result)
    if filters.languages:
        lang_set = {lang.strip() for lang in filters.languages}
        result = [
            (c, fv, s) for c, fv, s in result if c.language is not None and c.language in lang_set
        ]
        logger.info("  Filter languages=%s: %d → %d candidates", lang_set, before, len(result))
        before = len(result)
    if filters.exclude_languages is not None:
        exclude_langs = {lang.strip() for lang in filters.exclude_languages}
        result = [
            (c, fv, s)
            for c, fv, s in result
            if c.language is None or c.language not in exclude_langs
        ]
        logger.info(
            "  Filter exclude_languages=%s: %d → %d candidates",
            exclude_langs,
            before,
            len(result),
        )
        before = len(result)
    if filters.min_imdb_rating is not None:
        min_r = filters.min_imdb_rating
        result = [(c, fv, s) for c, fv, s in result if c.imdb_rating >= min_r]
        logger.info(
            "  Filter min_imdb_rating>=%.1f: %d → %d candidates",
            min_r,
            before,
            len(result),
        )
        before = len(result)
    if filters.max_runtime is not None:
        max_rt = filters.max_runtime
        result = [
            (c, fv, s)
            for c, fv, s in result
            if c.runtime_mins is not None and c.runtime_mins <= max_rt
        ]
        logger.info("  Filter max_runtime<=%d: %d → %d candidates", max_rt, before, len(result))
        before = len(result)
    if filters.country_code is not None:
        cc = filters.country_code.upper()
        result = [
            (c, fv, s)
            for c, fv, s in result
            if c.country_code is not None and c.country_code.upper() == cc
        ]
        logger.info("  Filter country_code=%s: %d → %d candidates", cc, before, len(result))
        before = len(result)
    if filters.min_vote_count is not None:
        min_v = filters.min_vote_count
        result = [(c, fv, s) for c, fv, s in result if c.num_votes >= min_v]
        logger.info("  Filter min_vote_count>=%d: %d → %d candidates", min_v, before, len(result))
    return result


def _find_similar_rated(
    candidate_genres: list[str],
    rated_titles: list[RatedTitle],
    top_k: int = 3,
    min_rating: int = 7,
) -> list[str]:
    """Find highly-rated titles most similar to the candidate by genre overlap.

    Uses Jaccard similarity on genre sets so results reflect content similarity,
    not inflated taste-profile scores. Falls back to all rated titles if none
    meet the rating threshold.
    """
    pool = [rt for rt in rated_titles if rt.user_rating >= min_rating] or rated_titles
    if not pool:
        return []

    candidate_set = set(candidate_genres)
    sims: list[tuple[float, str]] = []
    for rt in pool:
        rated_set = set(rt.genres)
        union = candidate_set | rated_set
        jaccard = len(candidate_set & rated_set) / len(union) if union else 0.0
        sims.append((jaccard, rt.title))

    sims.sort(reverse=True, key=lambda x: x[0])
    return [title for sim, title in sims[:top_k] if sim > 0]


def _find_director_match(
    candidate: CandidateTitle,
    rated_titles: list[RatedTitle],
) -> str | None:
    """Check if the candidate's director also directed a title the user rated highly."""
    if not candidate.directors:
        return None
    rated_by_director: dict[str, list[str]] = {}
    for rt in rated_titles:
        for d in rt.directors:
            rated_by_director.setdefault(d, []).append(rt.title)
    for director in candidate.directors:
        if director in rated_by_director:
            return f"Directed by {director}, who also directed {rated_by_director[director][0]}"
    return None


def _explain_prediction(
    feature_vec: FeatureVector,
    feature_importances: dict[str, float],
    candidate: CandidateTitle,
    rated_titles: list[RatedTitle],
    similar_titles: list[str],
    top_k: int = 5,
) -> list[str]:
    """Generate human-readable explanations for why a title was recommended."""
    explanations = []

    # Director match
    director_match = _find_director_match(candidate, rated_titles)
    if director_match:
        explanations.append(director_match)

    # Known director/actor taste signals
    if feature_vec.has_known_director and not director_match:
        explanations.append("Director matches your taste profile")
    if feature_vec.has_known_actor:
        explanations.append("Features actors from titles you enjoyed")

    # Find the most important genre features that are active for this title
    active_genres = [
        (name.replace("genre_", "").replace("_", "-").title(), imp)
        for name, imp in feature_importances.items()
        if name.startswith("genre_") and feature_vec.genre_flags.get(name, 0) == 1
    ]
    active_genres.sort(key=lambda x: x[1], reverse=True)

    if active_genres:
        top_genre = active_genres[0][0]
        explanations.append(f"Strong match on {top_genre} genre preference")

    if feature_vec.imdb_rating >= 7.5:
        explanations.append(f"High IMDb rating ({feature_vec.imdb_rating})")

    if feature_vec.is_anime:
        explanations.append("Matches your anime interest")

    # Actors
    if candidate.actors:
        explanations.append(f"Stars {', '.join(candidate.actors[:3])}")

    # Similar titles
    if similar_titles:
        explanations.append(f"Similar to {', '.join(similar_titles)} that you rated highly")

    if not explanations:
        explanations.append("Matches your general taste profile")

    return explanations[:top_k]


def score_and_rank_candidates(
    model,
    feature_names: list[str],
    candidates: list[CandidateTitle],
    taste: TasteProfile | None = None,
) -> list[tuple[CandidateTitle, FeatureVector, float]]:
    """Score all candidates and return them sorted by predicted rating."""
    if not candidates:
        logger.info("No candidates to score")
        return []

    logger.info("Scoring %d candidates", len(candidates))
    t0 = time.perf_counter()
    features = [candidate_to_features(c, taste) for c in candidates]
    logger.info("  Feature extraction completed in %.2fs", time.perf_counter() - t0)

    scores = predict_scores(model, feature_names, features)

    scored = list(zip(candidates, features, scores))
    scored.sort(key=lambda x: x[2], reverse=True)
    logger.info(
        "  Ranking complete — top score: %.2f (%s), bottom score: %.2f (%s)",
        scored[0][2],
        scored[0][0].title,
        scored[-1][2],
        scored[-1][0].title,
    )
    return scored


def build_recommendations_from_scored(
    scored: list[tuple[CandidateTitle, FeatureVector, float]],
    importances: dict[str, float],
    seen_ids: set[str],
    model_mae: float | None,
    filters: RecommendationFilters | None,
    rated_titles: list[RatedTitle],
) -> RecommendationResponse:
    """Build recommendation response from pre-scored candidates.

    This is the fast path: scored results are reused across filter-only changes.
    """
    from app.services.dismissed import get_dismissed_ids

    settings = get_settings()
    rec_cfg = settings.recommendations
    cat_cfg = settings.categories

    t0 = time.perf_counter()

    # Apply runtime filters
    filtered = scored
    if filters:
        pre_filter = len(filtered)
        filtered = _apply_runtime_filters(filtered, filters)
        logger.info("Runtime filters: %d → %d candidates", pre_filter, len(filtered))
    else:
        logger.info("No runtime filters applied")

    has_filter_score = filters and filters.min_predicted_score is not None
    min_score = filters.min_predicted_score if has_filter_score else rec_cfg.min_predicted_score
    logger.info("Min predicted score threshold: %.2f", min_score)

    # Merge seen + dismissed
    dismissed = get_dismissed_ids()
    excluded_ids = seen_ids | dismissed
    logger.info(
        "Excluding %d IDs (%d seen + %d dismissed)",
        len(excluded_ids),
        len(seen_ids),
        len(dismissed),
    )

    movies: list[Recommendation] = []
    series: list[Recommendation] = []
    anime: list[Recommendation] = []

    max_movies = (
        filters.top_n_movies
        if filters and filters.top_n_movies is not None
        else rec_cfg.top_n_movies
    )
    max_series = (
        filters.top_n_series
        if filters and filters.top_n_series is not None
        else rec_cfg.top_n_series
    )
    max_anime = (
        filters.top_n_anime
        if filters and filters.top_n_anime is not None
        else rec_cfg.top_n_anime
    )

    for candidate, fv, score in filtered:
        if candidate.imdb_id in excluded_ids:
            continue
        if score < min_score:
            continue

        similar = _find_similar_rated(candidate.genres, rated_titles)

        rec = Recommendation(
            title=candidate.title,
            title_type=candidate.title_type,
            year=candidate.year,
            genres=candidate.genres,
            predicted_score=round(score, 2),
            imdb_rating=candidate.imdb_rating,
            explanation=_explain_prediction(fv, importances, candidate, rated_titles, similar),
            actors=candidate.actors[:3],
            director=candidate.directors[0] if candidate.directors else None,
            similar_to=similar,
            language=candidate.language,
            imdb_id=candidate.imdb_id,
            imdb_url=f"https://www.imdb.com/title/{candidate.imdb_id}",
            num_votes=candidate.num_votes,
            country_code=candidate.country_code,
        )

        # Categorize: anime first (it overlaps with movies/series)
        if candidate.is_anime and len(anime) < max_anime:
            anime.append(rec)
        elif candidate.title_type in cat_cfg.get("movie", {}).title_types:
            if len(movies) < max_movies:
                movies.append(rec)
        elif candidate.title_type in cat_cfg.get("series", {}).title_types:
            if len(series) < max_series:
                series.append(rec)

        # Early termination when all categories are full
        if (
            len(movies) >= max_movies
            and len(series) >= max_series
            and len(anime) >= max_anime
        ):
            break

    logger.info(
        "Recommendations built in %.2fs — %d movies, %d series, %d anime",
        time.perf_counter() - t0,
        len(movies),
        len(series),
        len(anime),
    )

    return RecommendationResponse(
        movies=movies,
        series=series,
        anime=anime,
        model_accuracy=round(model_mae, 3) if model_mae else None,
    )


def build_recommendations(
    model,
    feature_names: list[str],
    candidates: list[CandidateTitle],
    seen_ids: set[str],
    model_mae: float | None = None,
    filters: RecommendationFilters | None = None,
    rated_titles: list[RatedTitle] | None = None,
    taste: TasteProfile | None = None,
) -> tuple[
    RecommendationResponse,
    list[tuple[CandidateTitle, FeatureVector, float]],
    dict[str, float],
]:
    """Full pipeline: score candidates, then build recommendations.

    Returns (response, scored, importances).
    """
    scored = score_and_rank_candidates(model, feature_names, candidates, taste)
    importances = get_feature_importances(model, feature_names)
    top_features = list(importances.items())[:5]
    logger.info("Top 5 feature importances: %s", [(n, f"{v:.3f}") for n, v in top_features])

    response = build_recommendations_from_scored(
        scored,
        importances,
        seen_ids,
        model_mae,
        filters,
        rated_titles or [],
    )
    return response, scored, importances
