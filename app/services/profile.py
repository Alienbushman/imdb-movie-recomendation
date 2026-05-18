"""T3.14: Build the taste-profile payload for /api/v1/profile.

Aggregates user-rated titles into the visualisations the frontend needs:
top genres / directors / actors / writers / composers / cinematographers,
decade preferences, runtime distribution, language histogram, and a "model
health" footer summarising the latest training metrics.

All aggregation logic is here (not in the route handler) so it stays testable
and can be reused by future tooling (e.g. an email digest).
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict

from app.models.schemas import (
    RatedTitle,
    TasteDecadeStat,
    TasteGenreStat,
    TasteHealth,
    TasteLanguageStat,
    TastePersonStat,
    TasteProfileResponse,
    TasteRuntimeBucket,
)
from app.services.model import load_model_bundle

logger = logging.getLogger(__name__)


_RUNTIME_BUCKETS = [
    ("Under 60m", 0, 60),
    ("60-90m", 60, 90),
    ("90-120m", 90, 120),
    ("2-2.5h", 120, 150),
    ("2.5-3h", 150, 180),
    ("3h+", 180, 10_000),
]


def _person_stats(
    pairs: list[tuple[str, int]],
    top_n: int = 20,
    min_count: int = 2,
) -> list[TastePersonStat]:
    """Aggregate (name, rating) pairs into ranked person stats."""
    by_name: dict[str, list[int]] = defaultdict(list)
    for name, rating in pairs:
        if name:
            by_name[name].append(rating)
    stats = [
        TastePersonStat(
            name=name,
            mean_rating=sum(ratings) / len(ratings),
            count=len(ratings),
        )
        for name, ratings in by_name.items()
        if len(ratings) >= min_count
    ]
    stats.sort(key=lambda s: (s.mean_rating, s.count), reverse=True)
    return stats[:top_n]


def _genre_stats(titles: list[RatedTitle], top_n: int = 23) -> list[TasteGenreStat]:
    by_genre: dict[str, list[int]] = defaultdict(list)
    for t in titles:
        for g in t.genres:
            by_genre[g].append(t.user_rating)
    stats = [
        TasteGenreStat(
            name=g,
            mean_rating=sum(rs) / len(rs),
            count=len(rs),
        )
        for g, rs in by_genre.items()
    ]
    stats.sort(key=lambda s: (s.mean_rating, s.count), reverse=True)
    return stats[:top_n]


def _decade_stats(titles: list[RatedTitle]) -> list[TasteDecadeStat]:
    by_decade: dict[int, list[int]] = defaultdict(list)
    for t in titles:
        if not t.year:
            continue
        by_decade[(t.year // 10) * 10].append(t.user_rating)
    return sorted(
        [
            TasteDecadeStat(decade=d, mean_rating=sum(rs) / len(rs), count=len(rs))
            for d, rs in by_decade.items()
        ],
        key=lambda s: s.decade,
    )


def _language_stats(titles: list[RatedTitle], top_n: int = 10) -> list[TasteLanguageStat]:
    counts = Counter(t.language for t in titles if t.language)
    return [
        TasteLanguageStat(language=lang, count=count) for lang, count in counts.most_common(top_n)
    ]


def _runtime_histogram(titles: list[RatedTitle]) -> list[TasteRuntimeBucket]:
    counts = [0] * len(_RUNTIME_BUCKETS)
    for t in titles:
        if not t.runtime_mins:
            continue
        for i, (_, lo, hi) in enumerate(_RUNTIME_BUCKETS):
            if lo <= t.runtime_mins < hi:
                counts[i] += 1
                break
    return [
        TasteRuntimeBucket(label=label, count=count)
        for (label, _, _), count in zip(_RUNTIME_BUCKETS, counts)
    ]


def _rating_distribution(titles: list[RatedTitle]) -> dict[int, int]:
    counts: Counter[int] = Counter(int(t.user_rating) for t in titles)
    # Force keys 1..10 to exist for nice frontend rendering.
    return {i: counts.get(i, 0) for i in range(1, 11)}


def _health() -> TasteHealth:
    bundle = load_model_bundle()
    if bundle is None:
        return TasteHealth()
    metrics = bundle.get("metrics", {}) or {}
    # Find whichever ndcg/map key exists (key depends on configured k).
    ndcg = next((v for k, v in metrics.items() if k.startswith("ndcg_at_")), None)
    map_v = next((v for k, v in metrics.items() if k.startswith("map_at_")), None)
    return TasteHealth(
        trained_at=bundle.get("trained_at"),
        objective=bundle.get("objective", "regression"),
        ndcg_at_k=float(ndcg) if ndcg is not None else None,
        map_at_k=float(map_v) if map_v is not None else None,
        spearman=float(metrics["spearman"]) if "spearman" in metrics else None,
        feature_count=len(bundle.get("feature_names") or []) or None,
        best_params=bundle.get("best_params") or {},
    )


def build_taste_profile(
    titles: list[RatedTitle],
    rated_actors: dict[str, list[str]] | None = None,
    rated_writers: dict[str, list[str]] | None = None,
    rated_composers: dict[str, list[str]] | None = None,
    rated_cinematographers: dict[str, list[str]] | None = None,
) -> TasteProfileResponse:
    """Assemble the visualisation payload from rated titles + crew lookups."""
    if not titles:
        return TasteProfileResponse(health=_health())

    by_id = {t.imdb_id: t.user_rating for t in titles}

    # Directors are on RatedTitle directly. Other crew come in as lookups.
    director_pairs = [(d, t.user_rating) for t in titles for d in t.directors]
    writer_pairs = [(w, t.user_rating) for t in titles for w in (t.writers or [])]
    actor_pairs: list[tuple[str, int]] = []
    composer_pairs: list[tuple[str, int]] = []
    cine_pairs: list[tuple[str, int]] = []
    if rated_actors:
        for imdb_id, names in rated_actors.items():
            rating = by_id.get(imdb_id)
            if rating is None:
                continue
            actor_pairs.extend((n, rating) for n in names)
    if rated_composers:
        for imdb_id, names in rated_composers.items():
            rating = by_id.get(imdb_id)
            if rating is None:
                continue
            composer_pairs.extend((n, rating) for n in names)
    if rated_cinematographers:
        for imdb_id, names in rated_cinematographers.items():
            rating = by_id.get(imdb_id)
            if rating is None:
                continue
            cine_pairs.extend((n, rating) for n in names)
    if rated_writers:
        # Override CSV-derived writers when we have a better lookup.
        writer_pairs = []
        for imdb_id, names in rated_writers.items():
            rating = by_id.get(imdb_id)
            if rating is None:
                continue
            writer_pairs.extend((n, rating) for n in names)

    return TasteProfileResponse(
        rated_count=len(titles),
        rating_distribution=_rating_distribution(titles),
        top_genres=_genre_stats(titles),
        top_directors=_person_stats(director_pairs),
        top_actors=_person_stats(actor_pairs),
        top_writers=_person_stats(writer_pairs),
        top_composers=_person_stats(composer_pairs),
        top_cinematographers=_person_stats(cine_pairs),
        decade_distribution=_decade_stats(titles),
        language_distribution=_language_stats(titles),
        runtime_histogram=_runtime_histogram(titles),
        health=_health(),
    )
