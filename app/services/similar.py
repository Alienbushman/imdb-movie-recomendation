"""Similarity engine for finding titles similar to a given seed.

T2.7: ``find_similar`` dispatches by ``settings.similarity.method``. The
``"leaves"`` path uses tree-leaf embeddings from the trained LightGBM model
(see ``leaf_similarity.py``) and ``"jaccard"`` is the legacy heuristic kept
as a fallback for when no model is available.
"""

import json
import logging
import sqlite3

from app.models.schemas import (
    CandidateTitle,
    RecommendationFilters,
    SimilarResponse,
    SimilarTitle,
)
from app.services.scored_store import (
    get_title_by_id,
    has_scored_results,
    query_all_candidates_lightweight,
)

logger = logging.getLogger(__name__)


def _parse_json_field(row: sqlite3.Row, field: str) -> list[str]:
    """Safely parse a JSON list field from a SQLite row."""
    raw = row[field]
    if not raw:
        return []
    return json.loads(raw)


def compute_similarity(
    seed_genres: set[str],
    seed_directors: list[str],
    seed_actors: list[str],
    seed_language: str | None,
    seed_year: int | None,
    seed_rating: float | None,
    cand_genres: set[str],
    cand_directors: list[str],
    cand_actors: list[str],
    cand_language: str | None,
    cand_year: int | None,
    cand_rating: float | None,
) -> float:
    """Compute weighted similarity score between seed and candidate.

    Returns a float in [0.0, 1.0].
    """
    # Genre Jaccard (weight: 0.4)
    union = seed_genres | cand_genres
    genre_sim = len(seed_genres & cand_genres) / len(union) if union else 0.0

    # Shared director (weight: 0.2)
    seed_dir_set = set(seed_directors)
    director_sim = 1.0 if seed_dir_set & set(cand_directors) else 0.0

    # Shared actors (weight: 0.15)
    seed_actor_set = set(seed_actors)
    shared_actors = seed_actor_set & set(cand_actors)
    actor_denom = max(3, len(seed_actors))
    actor_sim = len(shared_actors) / actor_denom if actor_denom else 0.0

    # Language match (weight: 0.1)
    lang_sim = 0.0
    if seed_language and cand_language:
        lang_sim = 1.0 if seed_language == cand_language else 0.0

    # Era proximity (weight: 0.1)
    era_sim = 0.0
    if seed_year and cand_year:
        era_sim = max(0.0, 1.0 - abs(seed_year - cand_year) / 50.0)

    # Rating proximity (weight: 0.05)
    rating_sim = 0.0
    if seed_rating is not None and cand_rating is not None:
        rating_sim = max(0.0, 1.0 - abs(seed_rating - cand_rating) / 10.0)

    return (
        0.40 * genre_sim
        + 0.20 * director_sim
        + 0.15 * actor_sim
        + 0.10 * lang_sim
        + 0.10 * era_sim
        + 0.05 * rating_sim
    )


def explain_similarity(
    seed_genres: set[str],
    seed_directors: list[str],
    seed_actors: list[str],
    seed_language: str | None,
    seed_year: int | None,
    cand_genres: set[str],
    cand_directors: list[str],
    cand_actors: list[str],
    cand_language: str | None,
    cand_year: int | None,
) -> list[str]:
    """Generate human-readable explanations for why titles are similar."""
    reasons: list[str] = []

    shared_genres = seed_genres & cand_genres
    if shared_genres:
        reasons.append(f"Shares genres: {', '.join(sorted(shared_genres))}")

    shared_dirs = set(seed_directors) & set(cand_directors)
    for d in sorted(shared_dirs):
        reasons.append(f"Same director: {d}")

    shared_actors = set(seed_actors) & set(cand_actors)
    for a in sorted(shared_actors):
        reasons.append(f"Features shared actor: {a}")

    if seed_language and cand_language and seed_language == cand_language:
        reasons.append(f"Both in {seed_language}")

    if seed_year and cand_year:
        diff = abs(seed_year - cand_year)
        if diff == 0:
            reasons.append("Released the same year")
        elif diff <= 5:
            reasons.append(f"Released within {diff} year{'s' if diff > 1 else ''} of each other")

    return reasons


def compute_similarity_for_candidates(a: CandidateTitle, b: CandidateTitle) -> float:
    """T2.6: Wrap ``compute_similarity`` for CandidateTitle pairs.

    Used by MMR (recommend.py) when re-ranking the scored top-N.
    """
    return compute_similarity(
        set(a.genres),
        a.directors,
        a.actors,
        a.language,
        a.year,
        a.imdb_rating,
        set(b.genres),
        b.directors,
        b.actors,
        b.language,
        b.year,
        b.imdb_rating,
    )


def compute_similarity_by_id(a_id: str, b_id: str) -> float:
    """T2.7 + T3.15: Public single-pair similarity by ID for the eval harness.

    Prefers the leaf-embedding path when a model is available; falls back to
    the heuristic ``compute_similarity`` via a scored-DB lookup.
    """
    from app.services.leaf_similarity import pairwise_similarity_by_id

    sim = pairwise_similarity_by_id(a_id, b_id)
    if sim > 0.0:
        return sim
    # Fallback path
    a_row = get_title_by_id(a_id)
    b_row = get_title_by_id(b_id)
    if a_row is None or b_row is None:
        return 0.0
    return compute_similarity(
        set(json.loads(a_row["genres"])),
        json.loads(a_row["directors"]),
        json.loads(a_row["actors"]),
        a_row["language"],
        a_row["year"],
        a_row["imdb_rating"],
        set(json.loads(b_row["genres"])),
        json.loads(b_row["directors"]),
        json.loads(b_row["actors"]),
        b_row["language"],
        b_row["year"],
        b_row["imdb_rating"],
    )


def find_similar(
    imdb_id: str,
    filters: RecommendationFilters | None,
    top_n: int,
    include_rated: bool | None,
) -> SimilarResponse:
    """Find titles most similar to the given seed.

    Args:
        imdb_id: IMDB ID of the seed title.
        filters: Optional recommendation filters.
        top_n: Max number of results to return.
        include_rated: None=all, True=only rated, False=only unrated.

    Raises:
        ValueError: If scored DB is empty.
        LookupError: If seed title is not found.

    T2.7: When ``settings.similarity.method == "leaves"`` (the default) and a
    trained model is available, similarities come from tree-leaf overlap. The
    Jaccard heuristic is kept as a fallback so the API never 500s when the
    model is being retrained.
    """
    from app.services.pipeline import _state

    if not has_scored_results():
        raise ValueError("No scored results available. Run POST /recommendations first.")

    # Look up seed title — try scored DB first, then rated titles
    seed_row = get_title_by_id(imdb_id)
    seed_title: str
    seed_genres: set[str]
    seed_directors: list[str]
    seed_actors: list[str]
    seed_language: str | None
    seed_year: int | None
    seed_rating: float | None

    if seed_row is not None:
        seed_title = seed_row["title"]
        seed_genres = set(json.loads(seed_row["genres"]))
        seed_directors = json.loads(seed_row["directors"])
        seed_actors = json.loads(seed_row["actors"])
        seed_language = seed_row["language"]
        seed_year = seed_row["year"]
        seed_rating = seed_row["imdb_rating"]
    else:
        # Try rated titles from in-memory state first, then fall back to watchlist CSV
        rated_titles = _state.get("titles") or []
        rated_match = next((rt for rt in rated_titles if rt.imdb_id == imdb_id), None)
        if rated_match is None:
            from app.core.config import PROJECT_ROOT, get_settings
            from app.services.ingest import load_watchlist

            settings = get_settings()
            watchlist_path = PROJECT_ROOT / settings.data.watchlist_path
            if watchlist_path.exists():
                try:
                    rated_titles = load_watchlist(watchlist_path)
                    rated_match = next((rt for rt in rated_titles if rt.imdb_id == imdb_id), None)
                except Exception:
                    pass
        if rated_match is None:
            raise LookupError(f"Title {imdb_id} not found in scored DB or rated titles.")
        seed_title = rated_match.title
        seed_genres = set(rated_match.genres)
        seed_directors = getattr(rated_match, "directors", [])
        seed_actors = []
        seed_language = rated_match.language
        seed_year = rated_match.year
        seed_rating = rated_match.imdb_rating

    # Build set of rated IDs for is_rated tagging
    rated_titles_list = _state.get("titles") or []
    rated_ids = {rt.imdb_id for rt in rated_titles_list}

    # Query all candidates
    rows = query_all_candidates_lightweight(filters)

    # T2.7: try leaf-embedding similarity first; fall back to Jaccard if the
    # model isn't available or the seed isn't in the leaf cache (e.g. a rated
    # title that never reached the candidate set).
    settings = get_settings()
    leaf_map: dict[str, float] | None = None
    if settings.similarity.method == "leaves":
        from app.services.leaf_similarity import find_similar_by_leaves

        # Pull the full set so we can re-rank the filtered candidates ourselves
        # rather than asking the leaf engine to know about filters.
        leaf_pairs = find_similar_by_leaves(imdb_id, top_n=len(rows) + 1)
        if leaf_pairs is not None:
            leaf_map = {cid: s for cid, s in leaf_pairs}
            logger.info(
                "Using leaf-embedding similarity for %s (cache hits=%d)",
                imdb_id,
                len(leaf_map),
            )

    # Score each candidate
    scored: list[tuple[float, sqlite3.Row]] = []
    for row in rows:
        cand_id = row["imdb_id"]
        if cand_id == imdb_id:
            continue  # skip the seed itself

        if leaf_map is not None and cand_id in leaf_map:
            sim = leaf_map[cand_id]
        else:
            cand_genres = set(json.loads(row["genres"]))
            cand_directors = json.loads(row["directors"])
            cand_actors = json.loads(row["actors"])
            cand_language = row["language"]
            cand_year = row["year"]
            cand_rating = row["imdb_rating"]
            sim = compute_similarity(
                seed_genres,
                seed_directors,
                seed_actors,
                seed_language,
                seed_year,
                seed_rating,
                cand_genres,
                cand_directors,
                cand_actors,
                cand_language,
                cand_year,
                cand_rating,
            )
        scored.append((sim, row))

    # Sort by similarity descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Apply seen/unseen filter
    if include_rated is True:
        scored = [(s, r) for s, r in scored if r["imdb_id"] in rated_ids]
    elif include_rated is False:
        scored = [(s, r) for s, r in scored if r["imdb_id"] not in rated_ids]

    total_candidates = len(scored)

    # Build results
    results: list[SimilarTitle] = []
    for sim_score, row in scored[:top_n]:
        cand_genres = set(json.loads(row["genres"]))
        cand_directors = json.loads(row["directors"])
        cand_actors = json.loads(row["actors"])

        explanation = explain_similarity(
            seed_genres,
            seed_directors,
            seed_actors,
            seed_language,
            seed_year,
            cand_genres,
            cand_directors,
            cand_actors,
            row["language"],
            row["year"],
        )

        results.append(
            SimilarTitle(
                title=row["title"],
                title_type=row["title_type"],
                year=row["year"],
                genres=json.loads(row["genres"]),
                imdb_rating=row["imdb_rating"],
                predicted_score=row["predicted_score"],
                similarity_score=round(sim_score, 4),
                similarity_explanation=explanation,
                actors=cand_actors[:3],
                director=cand_directors[0] if cand_directors else None,
                language=row["language"],
                imdb_id=row["imdb_id"],
                imdb_url=f"https://www.imdb.com/title/{row['imdb_id']}",
                num_votes=row["num_votes"],
                country_code=row["country_code"],
                is_rated=row["imdb_id"] in rated_ids,
            )
        )

    return SimilarResponse(
        seed_title=seed_title,
        seed_imdb_id=imdb_id,
        results=results,
        total_candidates=total_candidates,
    )
