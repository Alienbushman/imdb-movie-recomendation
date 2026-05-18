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
    SimilarToRef,
    TasteProfile,
)
from app.services.features import candidate_to_features
from app.services.model import explain_predictions, get_feature_importances, predict_scores

logger = logging.getLogger(__name__)


# T1.5: human-friendly labels for SHAP feature names. Any prefix-match below
# wins; remaining text after the prefix is title-cased.
_FEATURE_LABELS = {
    "genre_affinity_": "matches your taste in {0}",
    "genre_": "is a {0} title",
    "lang_": "is in {0}",
    "gpair_": "combines {0}",
    "type_": "is a {0}",
    "director_taste_score": "directors you've liked before",
    "director_taste_mean": "your director track record",
    "director_taste_count": "track record with these directors",
    "has_known_director": "a director you've rated before",
    "actor_taste_score": "actors you've liked",
    "actor_taste_mean": "your actor track record",
    "actor_taste_count": "multiple actors you've rated",
    "has_known_actor": "an actor you've rated before",
    "writer_taste_score": "writers you've liked",
    "writer_taste_mean": "your writer track record",
    "writer_taste_count": "multiple writers you've rated",
    "has_known_writer": "a writer you've rated before",
    "composer_taste_score": "composers you've liked",
    "has_known_composer": "a composer you've rated before",
    "cinematographer_taste_score": "cinematographers you've liked",
    "has_known_cinematographer": "a cinematographer you've rated before",
    "keyword_affinity_score": "themes/keywords you've enjoyed",
    "has_known_keywords": "known themes from your watchlist",
    "keyword_overlap_count": "multiple themes you've enjoyed",
    "rt_score": "Rotten Tomatoes critics' verdict",
    "metacritic_score": "Metacritic critics' verdict",
    "imdb_rt_gap": "audience-critic split",
    "imdb_metacritic_gap": "audience-critic split",
    "imdb_rating": "high community rating",
    "log_votes": "popularity",
    "popularity_tier": "popularity tier",
    "num_votes": "number of votes",
    "title_age": "release era",
    "decade": "decade",
    "is_anime": "anime",
    "rating_vote_ratio": "rating-to-votes balance",
    "runtime_mins": "runtime",
    "year": "release year",
}


def _humanize_feature(name: str) -> str | None:
    """Return a short human phrase for a feature name, or None if unknown."""
    if name in _FEATURE_LABELS:
        return _FEATURE_LABELS[name]
    for prefix, template in _FEATURE_LABELS.items():
        if prefix.endswith("_") and name.startswith(prefix):
            tail = name[len(prefix) :].replace("_", " ").title()
            if "{0}" in template:
                return template.format(tail)
            return template
    return None


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
    if filters.min_runtime is not None:
        min_rt = filters.min_runtime
        result = [
            (c, fv, s)
            for c, fv, s in result
            if c.runtime_mins is not None and c.runtime_mins >= min_rt
        ]
        logger.info("  Filter min_runtime>=%d: %d → %d candidates", min_rt, before, len(result))
        before = len(result)
    if filters.keywords:
        kw_incl = {k.lower() for k in filters.keywords}
        result = [
            (c, fv, s) for c, fv, s in result if kw_incl & {k.lower() for k in (c.keywords or [])}
        ]
        logger.info("  Filter keywords=%s: %d → %d candidates", kw_incl, before, len(result))
        before = len(result)
    if filters.exclude_keywords:
        kw_excl = {k.lower() for k in filters.exclude_keywords}
        result = [
            (c, fv, s)
            for c, fv, s in result
            if not (kw_excl & {k.lower() for k in (c.keywords or [])})
        ]
        logger.info(
            "  Filter exclude_keywords=%s: %d → %d candidates",
            kw_excl,
            before,
            len(result),
        )
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
    candidate: "CandidateTitle | list[str]",
    rated_titles: list[RatedTitle],
    top_k: int = 3,
    min_rating: int = 7,
) -> list[SimilarToRef]:
    """Find highly-rated titles that share strong signals with ``candidate``.

    Multi-signal similarity: genre Jaccard + director match + language match +
    decade proximity. Each ref carries a short ``reasons`` list describing why
    it was cited, and the user's personal rating so the UI can show
    "Because you rated X 9/10".

    Accepts either a full ``CandidateTitle`` (preferred, enables director /
    language signals) or a bare genre list for backwards compatibility.
    """
    if isinstance(candidate, list):
        candidate_genres = candidate
        candidate_directors: list[str] = []
        candidate_language: str | None = None
        candidate_year: int | None = None
    else:
        candidate_genres = candidate.genres
        candidate_directors = candidate.directors
        candidate_language = candidate.language
        candidate_year = candidate.year

    pool = [rt for rt in rated_titles if rt.user_rating >= min_rating] or rated_titles
    if not pool:
        return []

    candidate_set = set(candidate_genres)
    director_set = {d.lower() for d in candidate_directors}

    scored: list[tuple[float, RatedTitle, list[str]]] = []
    for rt in pool:
        reasons: list[str] = []
        rated_set = set(rt.genres)
        union = candidate_set | rated_set
        jaccard = len(candidate_set & rated_set) / len(union) if union else 0.0
        score = jaccard

        if director_set and any(d.lower() in director_set for d in rt.directors):
            shared = next(
                (d for d in rt.directors if d.lower() in director_set),
                None,
            )
            if shared:
                reasons.append(f"Same director: {shared}")
                score += 0.6

        if candidate_language and rt.language and candidate_language == rt.language:
            score += 0.1

        if candidate_year and rt.year:
            year_gap = abs(candidate_year - rt.year)
            if year_gap <= 5:
                score += 0.08
            elif year_gap <= 15:
                score += 0.04

        shared_genres = candidate_set & rated_set
        if shared_genres:
            top_genre = ", ".join(sorted(shared_genres)[:2])
            reasons.append(f"Shares {top_genre}")

        user_rating_label = f"rated {rt.user_rating}/10"
        reasons.insert(0, f"You {user_rating_label}")

        scored.append((score, rt, reasons))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [
        SimilarToRef(
            imdb_id=rt.imdb_id,
            title=rt.title,
            title_type=rt.title_type,
            year=rt.year,
            user_rating=int(rt.user_rating) if rt.user_rating is not None else None,
            reasons=reasons,
        )
        for sim, rt, reasons in scored[:top_k]
        if sim > 0
    ]


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
    similar_titles: list[SimilarToRef],
    top_k: int = 5,
    shap_contribs: list[tuple[str, float]] | None = None,
) -> list[str]:
    """Generate human-readable explanations for why a title was recommended.

    T1.5: when ``shap_contribs`` is supplied, the top positive feature
    attributions drive the first few bullets (so the order reflects actual
    score impact, not a hard-coded priority ladder). The original heuristic
    bullets are appended afterwards for color and as a fallback when SHAP is
    unavailable.
    """
    explanations: list[str] = []

    # T1.5: SHAP-driven leading bullets ------------------------------------
    if shap_contribs:
        for name, contrib in shap_contribs:
            if contrib <= 0:
                continue
            phrase = _humanize_feature(name)
            if phrase is None:
                continue
            explanations.append(f"{phrase.capitalize()} (+{contrib:.2f})")
            if len(explanations) >= max(1, top_k - 2):
                # Leave room for the personal "because you rated X" line.
                break

    # Director match
    director_match = _find_director_match(candidate, rated_titles)
    if director_match and director_match not in explanations:
        explanations.append(director_match)

    # Known director/actor taste signals — only when SHAP didn't already
    # surface them.
    if feature_vec.has_known_director and not any("director" in e.lower() for e in explanations):
        explanations.append("Director matches your taste profile")
    if feature_vec.has_known_actor and not any("actor" in e.lower() for e in explanations):
        explanations.append("Features actors from titles you enjoyed")

    # Find the most important genre features that are active for this title.
    # Still useful as a top-level signal when SHAP didn't pick a genre.
    if not any("taste in" in e.lower() or "is a " in e.lower() for e in explanations):
        active_genres = [
            (name.replace("genre_", "").replace("_", "-").title(), imp)
            for name, imp in feature_importances.items()
            if name.startswith("genre_") and feature_vec.genre_flags.get(name, 0) == 1
        ]
        active_genres.sort(key=lambda x: x[1], reverse=True)
        if active_genres:
            top_genre = active_genres[0][0]
            explanations.append(f"Strong match on {top_genre} genre preference")

    if feature_vec.imdb_rating >= 7.5 and not any(
        "community rating" in e.lower() for e in explanations
    ):
        explanations.append(f"High IMDb rating ({feature_vec.imdb_rating})")

    if feature_vec.is_anime and not any("anime" in e.lower() for e in explanations):
        explanations.append("Matches your anime interest")

    # Actors
    if candidate.actors and not any(a in " ".join(explanations) for a in candidate.actors[:3]):
        explanations.append(f"Stars {', '.join(candidate.actors[:3])}")

    # Similar titles — always include if available; this is the most personal
    # signal we can show.
    if similar_titles:
        top = similar_titles[0]
        if top.user_rating:
            explanations.append(f"Because you rated {top.title} {top.user_rating}/10")
        else:
            explanations.append(f"Similar to {top.title} that you enjoyed")
        if len(similar_titles) > 1:
            rest = ", ".join(s.title for s in similar_titles[1:])
            explanations.append(f"Also reminiscent of {rest}")

    if not explanations:
        explanations.append("Matches your general taste profile")

    return explanations[:top_k]


def _apply_mmr(
    scored: list[tuple[CandidateTitle, FeatureVector, float]],
) -> list[tuple[CandidateTitle, FeatureVector, float]]:
    """T2.6: re-order scored list with MMR for diversity.

    Operates per category at call sites (movies/series/anime get re-ranked
    independently after categorisation). Here we re-rank the global list once
    so the eventual category split inherits the diversified ordering.
    """
    settings = get_settings()
    if not settings.mmr.enabled or len(scored) < 3:
        return scored

    from app.services.mmr import mmr_rerank
    from app.services.similar import compute_similarity_for_candidates

    items = [c for c, _, _ in scored]
    scores = [s for _, _, s in scored]
    t0 = time.perf_counter()
    new_order = mmr_rerank(
        items,
        scores,
        similarity_fn=compute_similarity_for_candidates,
        lambda_=settings.mmr.lambda_,
        pool_size=settings.mmr.pool_size,
    )
    reranked = [scored[i] for i in new_order]
    logger.info(
        "MMR re-ranked top %d candidates in %.2fs (lambda=%.2f, pool=%d)",
        min(settings.mmr.pool_size, len(scored)),
        time.perf_counter() - t0,
        settings.mmr.lambda_,
        settings.mmr.pool_size,
    )
    return reranked


def score_and_rank_candidates(
    model,
    feature_names: list[str],
    candidates: list[CandidateTitle],
    taste: TasteProfile | None = None,
) -> list[tuple[CandidateTitle, FeatureVector, float]]:
    """Score all candidates and return them sorted by predicted rating.

    T2.6: applies MMR diversity re-ranking to the top-N (configurable via
    ``settings.mmr``).
    """
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

    scored = _apply_mmr(scored)
    return scored


def _shap_contribs_for(
    bundle: dict | None,
    feature_vecs: list[FeatureVector],
    top_k: int,
) -> list[list[tuple[str, float]]] | None:
    """T1.5: compute per-row top-k SHAP contributions, or None if unavailable."""
    if bundle is None or not feature_vecs:
        return None
    if bundle.get("shap_explainer") is None:
        return None
    try:
        return explain_predictions(bundle, feature_vecs, top_k=top_k)
    except Exception as e:  # noqa: BLE001
        logger.warning("SHAP explanation failed, falling back to heuristic: %s", e)
        return None


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
    from app.services.model import load_model_bundle

    settings = get_settings()
    rec_cfg = settings.recommendations
    cat_cfg = settings.categories
    shap_cfg = settings.model.shap

    # T1.5: load the model bundle once so we can compute SHAP attributions.
    bundle = load_model_bundle() if shap_cfg.enabled else None

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
        filters.top_n_anime if filters and filters.top_n_anime is not None else rec_cfg.top_n_anime
    )

    # T1.5: compute SHAP once for the top-N candidates we'll likely surface.
    # We cap at (max_movies+max_series+max_anime)*3 to amortise the cost — SHAP
    # for thousands of unused candidates would dominate the request time.
    shap_pool_cap = max(50, (max_movies + max_series + max_anime) * 3)
    shap_pool = filtered[:shap_pool_cap]
    shap_contribs_pool = _shap_contribs_for(
        bundle, [fv for _, fv, _ in shap_pool], top_k=shap_cfg.top_k
    )
    shap_by_id: dict[str, list[tuple[str, float]]] = {}
    if shap_contribs_pool:
        for (cand, _, _), contribs in zip(shap_pool, shap_contribs_pool):
            shap_by_id[cand.imdb_id] = contribs

    for candidate, fv, score in filtered:
        if candidate.imdb_id in excluded_ids:
            continue
        if score < min_score:
            continue

        similar = _find_similar_rated(candidate, rated_titles)

        rec = Recommendation(
            title=candidate.title,
            title_type=candidate.title_type,
            year=candidate.year,
            genres=candidate.genres,
            predicted_score=round(score, 2),
            imdb_rating=candidate.imdb_rating,
            explanation=_explain_prediction(
                fv,
                importances,
                candidate,
                rated_titles,
                similar,
                shap_contribs=shap_by_id.get(candidate.imdb_id),
            ),
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
        if len(movies) >= max_movies and len(series) >= max_series and len(anime) >= max_anime:
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
