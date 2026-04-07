"""Feature engineering for the LightGBM taste model.

Converts a ``CandidateTitle`` or ``RatedTitle`` into a flat ``FeatureVector``
dataclass, then serialises it into a numpy array for training and inference.

Feature categories (~100+ total):
- Genre affinity (23 flags) — fraction of user's rated titles that share each genre
- Genre interaction pairs (N) — product of two affinity scores for common genre combos
- Director / actor taste (4) — mean and count of user's ratings for a title's crew
- Writer taste (4) — same as director/actor but for credited writers
- Composer / cinematographer taste (4) — same for below-the-line crew
- Language affinity (14 flags) — fraction of rated titles matching each language
- Title-type flags (4) — movie, short, tvSeries, tvMiniSeries
- Popularity / age (3) — log vote count, title age in years, IMDB average rating
- TMDB keyword affinity (3) — optional; zero-filled when TMDB_API_KEY is absent
- OMDb critic scores (4) — optional; zero-filled when OMDB_API_KEY is absent

IMPORTANT: ``feature_vector_to_array()`` must produce columns in the exact same
order for both training (``features_to_dataframe``) and inference. Adding a new
field requires updating both functions and retraining the model.
"""
import logging
import math
from collections import Counter, defaultdict
from datetime import datetime

import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.models.schemas import CandidateTitle, FeatureVector, RatedTitle, TasteProfile

logger = logging.getLogger(__name__)

ALL_GENRES = [
    "Action",
    "Adventure",
    "Animation",
    "Biography",
    "Comedy",
    "Crime",
    "Documentary",
    "Drama",
    "Family",
    "Fantasy",
    "Film-Noir",
    "History",
    "Horror",
    "Music",
    "Musical",
    "Mystery",
    "Romance",
    "Sci-Fi",
    "Short",
    "Sport",
    "Thriller",
    "War",
    "Western",
]

ALL_TITLE_TYPES = ["movie", "tvseries", "tvminiseries", "tvmovie"]


def _top_genre_pairs(rated_titles: list[RatedTitle], max_pairs: int) -> list[str]:
    """Identify the most common genre co-occurrence pairs from rated titles."""
    pair_counts: Counter = Counter()
    for t in rated_titles:
        genres = sorted(g.lower().replace("-", "_") for g in t.genres if g in ALL_GENRES)
        for i in range(len(genres)):
            for j in range(i + 1, len(genres)):
                pair_counts[f"{genres[i]}_x_{genres[j]}"] += 1
    return [pair for pair, _ in pair_counts.most_common(max_pairs)]


def _bayesian_avg(ratings: list[int], global_mean: float, c: float = 5.0) -> float:
    """Shrink a raw average toward the global mean to reduce noise from sparse data.

    A director with one highly-rated film won't dominate as heavily as one with ten.
    c controls the strength of shrinkage: higher c = stronger pull toward the mean.
    """
    return (sum(ratings) + c * global_mean) / (len(ratings) + c)


def build_taste_profile(
    rated_titles: list[RatedTitle],
    rated_actors: dict[str, list[str]] | None = None,
    rated_composers: dict[str, list[str]] | None = None,
    rated_cinematographers: dict[str, list[str]] | None = None,
) -> TasteProfile:
    """Build aggregated taste signals from the user's rated titles."""
    settings = get_settings()
    max_pairs = settings.features.max_genre_pairs

    global_mean = (
        sum(t.user_rating for t in rated_titles) / len(rated_titles) if rated_titles else 7.0
    )

    # Director averages (Bayesian-smoothed)
    director_ratings: dict[str, list[int]] = defaultdict(list)
    for t in rated_titles:
        for d in t.directors:
            director_ratings[d].append(t.user_rating)
    director_avg = {d: _bayesian_avg(r, global_mean) for d, r in director_ratings.items()}

    # Actor averages (Bayesian-smoothed)
    actor_avg: dict[str, float] = {}
    if rated_actors:
        title_rating = {t.imdb_id: t.user_rating for t in rated_titles}
        actor_ratings: dict[str, list[int]] = defaultdict(list)
        for imdb_id, actors in rated_actors.items():
            rating = title_rating.get(imdb_id)
            if rating is None:
                continue
            for a in actors:
                actor_ratings[a].append(rating)
        actor_avg = {a: _bayesian_avg(r, global_mean) for a, r in actor_ratings.items()}

    # Subtask 1: Genre averages (Bayesian-smoothed)
    genre_ratings: dict[str, list[int]] = defaultdict(list)
    for t in rated_titles:
        for g in t.genres:
            if g in ALL_GENRES:
                genre_ratings[g].append(t.user_rating)
    genre_avg = {g: _bayesian_avg(r, global_mean) for g, r in genre_ratings.items()}

    # Subtask 4: Writer averages (Bayesian-smoothed)
    writer_ratings: dict[str, list[int]] = defaultdict(list)
    for t in rated_titles:
        for w in t.writers:
            writer_ratings[w].append(t.user_rating)
    writer_avg = {w: _bayesian_avg(r, global_mean) for w, r in writer_ratings.items()}

    # Subtask 8: Composer averages (Bayesian-smoothed)
    composer_avg: dict[str, float] = {}
    if rated_composers:
        title_rating = {t.imdb_id: t.user_rating for t in rated_titles}
        composer_ratings: dict[str, list[int]] = defaultdict(list)
        for imdb_id, composers in rated_composers.items():
            rating = title_rating.get(imdb_id)
            if rating is None:
                continue
            for c in composers:
                composer_ratings[c].append(rating)
        composer_avg = {c: _bayesian_avg(r, global_mean) for c, r in composer_ratings.items()}

    # Subtask 8: Cinematographer averages (Bayesian-smoothed)
    cinematographer_avg: dict[str, float] = {}
    if rated_cinematographers:
        title_rating = {t.imdb_id: t.user_rating for t in rated_titles}
        cine_ratings: dict[str, list[int]] = defaultdict(list)
        for imdb_id, cines in rated_cinematographers.items():
            rating = title_rating.get(imdb_id)
            if rating is None:
                continue
            for c in cines:
                cine_ratings[c].append(rating)
        cinematographer_avg = {c: _bayesian_avg(r, global_mean) for c, r in cine_ratings.items()}

    # Subtask 6: Top genre interaction pairs
    genre_pairs = _top_genre_pairs(rated_titles, max_pairs)

    return TasteProfile(
        director_avg=director_avg,
        actor_avg=actor_avg,
        genre_avg=genre_avg,
        writer_avg=writer_avg,
        composer_avg=composer_avg,
        cinematographer_avg=cinematographer_avg,
        genre_pairs=genre_pairs,
    )


def _build_genre_flags(genres: list[str]) -> dict[str, int]:
    """Create a binary dict for each known genre."""
    genre_set = {g.strip() for g in genres}
    return {f"genre_{g.lower().replace('-', '_')}": int(g in genre_set) for g in ALL_GENRES}


def _build_genre_affinity(genres: list[str], taste: TasteProfile | None) -> dict[str, float]:
    """Subtask 1: User's average rating per genre (0.0 if no rated titles in that genre)."""
    if taste is None:
        return {f"genre_{g.lower().replace('-', '_')}_affinity": 0.0 for g in ALL_GENRES}
    return {
        f"genre_{g.lower().replace('-', '_')}_affinity": taste.genre_avg.get(g, 0.0)
        for g in ALL_GENRES
    }


def _build_language_flags(language: str | None, top_languages: list[str]) -> dict[str, int]:
    """Subtask 3: One-hot encode language against the configured top languages."""
    flags = {f"lang_{lang.lower().replace(' ', '_')}": 0 for lang in top_languages}
    if language and language in top_languages:
        flags[f"lang_{language.lower().replace(' ', '_')}"] = 1
    return flags


def _build_type_flags(title_type: str) -> dict[str, int]:
    """Subtask 5: One-hot encode title type."""
    tt = title_type.lower()
    return {f"type_{t}": int(tt == t) for t in ALL_TITLE_TYPES}


def _build_genre_pair_flags(genres: list[str], genre_pairs: list[str]) -> dict[str, int]:
    """Subtask 6: Binary flags for the configured genre interaction pairs."""
    genre_set = {g.lower().replace("-", "_") for g in genres if g in ALL_GENRES}
    result: dict[str, int] = {}
    for pair in genre_pairs:
        parts = pair.split("_x_")
        if len(parts) == 2:
            result[f"gpair_{pair}"] = int(parts[0] in genre_set and parts[1] in genre_set)
    return result


def _compute_derived_features(
    imdb_rating: float, num_votes: int, year: int | None, runtime: int | None
) -> dict:
    """Compute derived numerical features."""
    yr = year or 2000
    return {
        "decade": (yr // 10) * 10,
        "rating_vote_ratio": imdb_rating / np.log1p(num_votes),
        "runtime_mins": float(runtime) if runtime else 0.0,
    }


def _compute_popularity_features(num_votes: int, year: int | None) -> dict:
    """Subtask 7: Popularity tier, title age, log votes."""
    settings = get_settings()
    tiers = settings.features.popularity_tiers
    tier = 0
    for threshold in tiers:
        if num_votes >= threshold:
            tier += 1
    current_year = datetime.now().year
    title_age = current_year - (year or current_year)
    log_votes = math.log10(num_votes) if num_votes > 0 else 0.0
    return {
        "popularity_tier": tier,
        "title_age": title_age,
        "log_votes": log_votes,
    }


def _compute_taste_features(
    directors: list[str],
    actors: list[str],
    taste: TasteProfile | None,
    writers: list[str] | None = None,
    composers: list[str] | None = None,
    cinematographers: list[str] | None = None,
) -> dict:
    """Compute features derived from the user's taste profile."""
    director_taste_score = 0.0
    has_known_director = False
    director_taste_count = 0
    director_taste_mean = 0.0
    actor_taste_score = 0.0
    has_known_actor = False
    actor_taste_count = 0
    actor_taste_mean = 0.0
    writer_taste_score = 0.0
    has_known_writer = False
    writer_taste_count = 0
    writer_taste_mean = 0.0
    composer_taste_score = 0.0
    has_known_composer = False
    cinematographer_taste_score = 0.0
    has_known_cinematographer = False

    if taste:
        # Directors (subtask 2: count + mean in addition to max)
        dir_scores = [taste.director_avg[d] for d in directors if d in taste.director_avg]
        if dir_scores:
            has_known_director = True
            director_taste_score = max(dir_scores)
            director_taste_count = len(dir_scores)
            director_taste_mean = sum(dir_scores) / len(dir_scores)

        # Actors (subtask 2: count + mean in addition to max)
        act_scores = [taste.actor_avg[a] for a in actors if a in taste.actor_avg]
        if act_scores:
            has_known_actor = True
            actor_taste_score = max(act_scores)
            actor_taste_count = len(act_scores)
            actor_taste_mean = sum(act_scores) / len(act_scores)

        # Writers (subtask 4)
        if writers:
            w_scores = [taste.writer_avg[w] for w in writers if w in taste.writer_avg]
            if w_scores:
                has_known_writer = True
                writer_taste_score = max(w_scores)
                writer_taste_count = len(w_scores)
                writer_taste_mean = sum(w_scores) / len(w_scores)

        # Composers (subtask 8)
        if composers:
            c_scores = [taste.composer_avg[c] for c in composers if c in taste.composer_avg]
            if c_scores:
                has_known_composer = True
                composer_taste_score = max(c_scores)

        # Cinematographers (subtask 8)
        if cinematographers:
            ci_scores = [
                taste.cinematographer_avg[c]
                for c in cinematographers
                if c in taste.cinematographer_avg
            ]
            if ci_scores:
                has_known_cinematographer = True
                cinematographer_taste_score = max(ci_scores)

    return {
        "director_taste_score": director_taste_score,
        "has_known_director": has_known_director,
        "director_taste_count": director_taste_count,
        "director_taste_mean": director_taste_mean,
        "actor_taste_score": actor_taste_score,
        "has_known_actor": has_known_actor,
        "actor_taste_count": actor_taste_count,
        "actor_taste_mean": actor_taste_mean,
        "writer_taste_score": writer_taste_score,
        "has_known_writer": has_known_writer,
        "writer_taste_count": writer_taste_count,
        "writer_taste_mean": writer_taste_mean,
        "composer_taste_score": composer_taste_score,
        "has_known_composer": has_known_composer,
        "cinematographer_taste_score": cinematographer_taste_score,
        "has_known_cinematographer": has_known_cinematographer,
    }


def rated_title_to_features(
    title: RatedTitle,
    taste: TasteProfile | None = None,
) -> FeatureVector:
    """Convert a rated title into a feature vector."""
    settings = get_settings()
    top_languages = settings.features.top_languages

    genre_flags = _build_genre_flags(title.genres)
    genre_affinity = _build_genre_affinity(title.genres, taste)
    derived = _compute_derived_features(
        title.imdb_rating, title.num_votes, title.year, title.runtime_mins
    )
    pop_feats = _compute_popularity_features(title.num_votes, title.year)
    taste_feats = _compute_taste_features(
        title.directors, [], taste, writers=title.writers
    )
    language_flags = _build_language_flags(title.language, top_languages)
    type_flags = _build_type_flags(title.title_type)
    genre_pairs = taste.genre_pairs if taste else []
    genre_pair_flags = _build_genre_pair_flags(title.genres, genre_pairs)

    return FeatureVector(
        imdb_id=title.imdb_id,
        title=title.title,
        title_type=title.title_type,
        imdb_rating=title.imdb_rating,
        runtime_mins=derived["runtime_mins"],
        year=title.year,
        num_votes=title.num_votes,
        genre_flags=genre_flags,
        decade=derived["decade"],
        rating_vote_ratio=derived["rating_vote_ratio"],
        is_anime="Animation" in title.genres,
        director_taste_score=taste_feats["director_taste_score"],
        has_known_director=taste_feats["has_known_director"],
        actor_taste_score=taste_feats["actor_taste_score"],
        has_known_actor=taste_feats["has_known_actor"],
        genre_affinity=genre_affinity,
        director_taste_count=taste_feats["director_taste_count"],
        director_taste_mean=taste_feats["director_taste_mean"],
        actor_taste_count=taste_feats["actor_taste_count"],
        actor_taste_mean=taste_feats["actor_taste_mean"],
        language_flags=language_flags,
        writer_taste_score=taste_feats["writer_taste_score"],
        has_known_writer=taste_feats["has_known_writer"],
        writer_taste_count=taste_feats["writer_taste_count"],
        writer_taste_mean=taste_feats["writer_taste_mean"],
        type_flags=type_flags,
        genre_pair_flags=genre_pair_flags,
        popularity_tier=pop_feats["popularity_tier"],
        title_age=pop_feats["title_age"],
        log_votes=pop_feats["log_votes"],
        composer_taste_score=taste_feats["composer_taste_score"],
        has_known_composer=taste_feats["has_known_composer"],
        cinematographer_taste_score=taste_feats["cinematographer_taste_score"],
        has_known_cinematographer=taste_feats["has_known_cinematographer"],
    )


def candidate_to_features(
    candidate: CandidateTitle,
    taste: TasteProfile | None = None,
) -> FeatureVector:
    """Convert an IMDB candidate into a feature vector."""
    settings = get_settings()
    top_languages = settings.features.top_languages

    genre_flags = _build_genre_flags(candidate.genres)
    genre_affinity = _build_genre_affinity(candidate.genres, taste)
    yr = candidate.year or 2000
    rt = candidate.runtime_mins or 0
    imdb_r = candidate.imdb_rating or 0.0
    votes = candidate.num_votes or 0
    derived = _compute_derived_features(imdb_r, votes, yr, rt)
    pop_feats = _compute_popularity_features(votes, candidate.year)
    taste_feats = _compute_taste_features(
        candidate.directors,
        candidate.actors,
        taste,
        writers=candidate.writers,
        composers=candidate.composers,
        cinematographers=candidate.cinematographers,
    )
    language_flags = _build_language_flags(candidate.language, top_languages)
    type_flags = _build_type_flags(candidate.title_type)
    genre_pairs = taste.genre_pairs if taste else []
    genre_pair_flags = _build_genre_pair_flags(candidate.genres, genre_pairs)

    return FeatureVector(
        imdb_id=candidate.imdb_id,
        title=candidate.title,
        title_type=candidate.title_type,
        imdb_rating=imdb_r,
        runtime_mins=derived["runtime_mins"],
        year=yr,
        num_votes=votes,
        genre_flags=genre_flags,
        decade=derived["decade"],
        rating_vote_ratio=derived["rating_vote_ratio"],
        is_anime=candidate.is_anime,
        director_taste_score=taste_feats["director_taste_score"],
        has_known_director=taste_feats["has_known_director"],
        actor_taste_score=taste_feats["actor_taste_score"],
        has_known_actor=taste_feats["has_known_actor"],
        genre_affinity=genre_affinity,
        director_taste_count=taste_feats["director_taste_count"],
        director_taste_mean=taste_feats["director_taste_mean"],
        actor_taste_count=taste_feats["actor_taste_count"],
        actor_taste_mean=taste_feats["actor_taste_mean"],
        language_flags=language_flags,
        writer_taste_score=taste_feats["writer_taste_score"],
        has_known_writer=taste_feats["has_known_writer"],
        writer_taste_count=taste_feats["writer_taste_count"],
        writer_taste_mean=taste_feats["writer_taste_mean"],
        type_flags=type_flags,
        genre_pair_flags=genre_pair_flags,
        popularity_tier=pop_feats["popularity_tier"],
        title_age=pop_feats["title_age"],
        log_votes=pop_feats["log_votes"],
        composer_taste_score=taste_feats["composer_taste_score"],
        has_known_composer=taste_feats["has_known_composer"],
        cinematographer_taste_score=taste_feats["cinematographer_taste_score"],
        has_known_cinematographer=taste_feats["has_known_cinematographer"],
    )


def features_to_dataframe(features: list[FeatureVector]) -> pd.DataFrame:
    """Flatten a list of feature vectors into a DataFrame ready for model input."""
    rows = []
    for fv in features:
        row = {
            "imdb_rating": fv.imdb_rating,
            "runtime_mins": fv.runtime_mins,
            "year": fv.year,
            "num_votes": fv.num_votes,
            "decade": fv.decade,
            "rating_vote_ratio": fv.rating_vote_ratio,
            "is_anime": int(fv.is_anime),
            "director_taste_score": fv.director_taste_score,
            "has_known_director": int(fv.has_known_director),
            "actor_taste_score": fv.actor_taste_score,
            "has_known_actor": int(fv.has_known_actor),
            # Subtask 2
            "director_taste_count": fv.director_taste_count,
            "director_taste_mean": fv.director_taste_mean,
            "actor_taste_count": fv.actor_taste_count,
            "actor_taste_mean": fv.actor_taste_mean,
            # Subtask 4
            "writer_taste_score": fv.writer_taste_score,
            "has_known_writer": int(fv.has_known_writer),
            "writer_taste_count": fv.writer_taste_count,
            "writer_taste_mean": fv.writer_taste_mean,
            # Subtask 7
            "popularity_tier": fv.popularity_tier,
            "title_age": fv.title_age,
            "log_votes": fv.log_votes,
            # Subtask 8
            "composer_taste_score": fv.composer_taste_score,
            "has_known_composer": int(fv.has_known_composer),
            "cinematographer_taste_score": fv.cinematographer_taste_score,
            "has_known_cinematographer": int(fv.has_known_cinematographer),
            # Subtask 9
            "keyword_affinity_score": fv.keyword_affinity_score,
            "has_known_keywords": int(fv.has_known_keywords),
            "keyword_overlap_count": fv.keyword_overlap_count,
            # Subtask 10
            "rt_score": fv.rt_score,
            "metacritic_score": fv.metacritic_score,
            "imdb_rt_gap": fv.imdb_rt_gap,
            "imdb_metacritic_gap": fv.imdb_metacritic_gap,
        }
        # Subtask 1: genre affinity scores
        row.update(fv.genre_affinity)
        # genre binary flags
        row.update(fv.genre_flags)
        # Subtask 3: language flags
        row.update(fv.language_flags)
        # Subtask 5: title type flags
        row.update(fv.type_flags)
        # Subtask 6: genre pair flags
        row.update(fv.genre_pair_flags)
        rows.append(row)
    return pd.DataFrame(rows)


def feature_vector_to_array(fv: FeatureVector, feature_names: list[str]) -> np.ndarray:
    """Convert a FeatureVector to a numpy array aligned with the model's feature names."""
    row = {
        "imdb_rating": fv.imdb_rating,
        "runtime_mins": fv.runtime_mins,
        "year": fv.year or 0,
        "num_votes": fv.num_votes,
        "decade": fv.decade,
        "rating_vote_ratio": fv.rating_vote_ratio,
        "is_anime": int(fv.is_anime),
        "director_taste_score": fv.director_taste_score,
        "has_known_director": int(fv.has_known_director),
        "actor_taste_score": fv.actor_taste_score,
        "has_known_actor": int(fv.has_known_actor),
        # Subtask 2
        "director_taste_count": fv.director_taste_count,
        "director_taste_mean": fv.director_taste_mean,
        "actor_taste_count": fv.actor_taste_count,
        "actor_taste_mean": fv.actor_taste_mean,
        # Subtask 4
        "writer_taste_score": fv.writer_taste_score,
        "has_known_writer": int(fv.has_known_writer),
        "writer_taste_count": fv.writer_taste_count,
        "writer_taste_mean": fv.writer_taste_mean,
        # Subtask 7
        "popularity_tier": fv.popularity_tier,
        "title_age": fv.title_age,
        "log_votes": fv.log_votes,
        # Subtask 8
        "composer_taste_score": fv.composer_taste_score,
        "has_known_composer": int(fv.has_known_composer),
        "cinematographer_taste_score": fv.cinematographer_taste_score,
        "has_known_cinematographer": int(fv.has_known_cinematographer),
        # Subtask 9
        "keyword_affinity_score": fv.keyword_affinity_score,
        "has_known_keywords": int(fv.has_known_keywords),
        "keyword_overlap_count": fv.keyword_overlap_count,
        # Subtask 10
        "rt_score": fv.rt_score,
        "metacritic_score": fv.metacritic_score,
        "imdb_rt_gap": fv.imdb_rt_gap,
        "imdb_metacritic_gap": fv.imdb_metacritic_gap,
    }
    row.update(fv.genre_affinity)
    row.update(fv.genre_flags)
    row.update(fv.language_flags)
    row.update(fv.type_flags)
    row.update(fv.genre_pair_flags)
    return np.array([row.get(name, 0) for name in feature_names], dtype=float)
