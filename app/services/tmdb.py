"""Subtask 9: TMDB API integration for keyword features.

Fetches keyword metadata for IMDB titles using the TMDB API and caches it locally.
Requires TMDB_API_KEY environment variable (free tier: 40 req/10s).

If TMDB_API_KEY is not set, all functions degrade gracefully (empty results).
"""

import json
import logging
import os
import time

import httpx

from app.core.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

_TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")
_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "tmdb_metadata.json"
_MEDIA_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "tmdb_media.json"
_RATE_LIMIT_DELAY = 0.25  # 4 req/s to stay within 40 req/10s

_TMDB_IMG_BASE = "https://image.tmdb.org/t/p"
_PROFILE_SIZE = "w185"
_BACKDROP_SIZE = "w780"
_POSTER_SIZE = "w500"

# Curated fallback list used when TMDB metadata is unavailable.
DEFAULT_MOOD_TAGS = [
    "dystopia", "time travel", "post-apocalyptic", "based on novel",
    "feel-good", "dark comedy", "psychological thriller", "noir",
    "coming of age", "found family", "heist", "revenge",
    "slow burn", "mind bending", "twist ending", "one-shot",
    "courtroom", "biography", "true story", "war",
    "space", "cyberpunk", "magic", "fairy tale",
    "family drama", "redemption", "satire", "mockumentary",
    "road trip", "survival", "monster", "haunted house",
    "spy", "assassin", "hacker", "vigilante",
]


def _load_tmdb_cache() -> dict[str, dict]:
    if _CACHE_PATH.exists():
        try:
            with open(_CACHE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_tmdb_cache(data: dict[str, dict]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "w") as f:
        json.dump(data, f)


def _find_tmdb_id(client: httpx.Client, imdb_id: str) -> tuple[str | None, str | None]:
    """Map an IMDB ID to a TMDB ID via the find endpoint."""
    url = f"https://api.themoviedb.org/3/find/{imdb_id}"
    try:
        resp = client.get(url, params={"api_key": _TMDB_API_KEY, "external_source": "imdb_id"})
        resp.raise_for_status()
        data = resp.json()
        for key in ("movie_results", "tv_results"):
            results = data.get(key, [])
            if results:
                return str(results[0]["id"]), key.split("_")[0]
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        pass
    return None, None


def _fetch_keywords(client: httpx.Client, tmdb_id: str, media_type: str) -> list[str]:
    """Fetch keyword names for a TMDB title."""
    url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/keywords"
    try:
        resp = client.get(url, params={"api_key": _TMDB_API_KEY})
        resp.raise_for_status()
        data = resp.json()
        # Movies use "keywords", TV shows use "results"
        keywords = data.get("keywords") or data.get("results") or []
        return [kw["name"] for kw in keywords if "name" in kw]
    except (httpx.HTTPError, KeyError, ValueError):
        return []


def fetch_tmdb_keywords(imdb_ids: list[str]) -> dict[str, list[str]]:
    """Fetch TMDB keywords for a list of IMDB IDs, using and updating the local cache.

    Returns imdb_id → list[keyword_name]. Missing/failed lookups return [].
    No-ops if TMDB_API_KEY is not configured.
    """
    if not _TMDB_API_KEY:
        logger.debug("TMDB_API_KEY not set — skipping keyword fetch")
        return {}

    cache = _load_tmdb_cache()
    result: dict[str, list[str]] = {}
    to_fetch = []

    for imdb_id in imdb_ids:
        if imdb_id in cache:
            result[imdb_id] = cache[imdb_id].get("keywords", [])
        else:
            to_fetch.append(imdb_id)

    if not to_fetch:
        return result

    logger.info("Fetching TMDB keywords for %d uncached titles", len(to_fetch))
    with httpx.Client(timeout=10.0) as client:
        for imdb_id in to_fetch:
            tmdb_id, media_type = _find_tmdb_id(client, imdb_id)
            keywords: list[str] = []
            if tmdb_id and media_type:
                time.sleep(_RATE_LIMIT_DELAY)
                keywords = _fetch_keywords(client, tmdb_id, media_type)
                time.sleep(_RATE_LIMIT_DELAY)
            cache[imdb_id] = {"keywords": keywords}
            result[imdb_id] = keywords

    _save_tmdb_cache(cache)
    logger.info("TMDB cache updated: %d total entries", len(cache))
    return result


def compute_keyword_features(
    candidate_keywords: list[str],
    keyword_affinity: dict[str, float],
) -> dict:
    """Compute keyword-based feature values for a single candidate.

    Args:
        candidate_keywords: Keywords for the candidate title.
        keyword_affinity: User's average rating per keyword (from taste profile).

    Returns dict with keyword_affinity_score, has_known_keywords, keyword_overlap_count.
    """
    if not candidate_keywords or not keyword_affinity:
        return {
            "keyword_affinity_score": 0.0,
            "has_known_keywords": False,
            "keyword_overlap_count": 0,
        }

    matched = [keyword_affinity[kw] for kw in candidate_keywords if kw in keyword_affinity]
    return {
        "keyword_affinity_score": sum(matched) / len(matched) if matched else 0.0,
        "has_known_keywords": bool(matched),
        "keyword_overlap_count": len(matched),
    }


def _load_media_cache() -> dict[str, dict]:
    if _MEDIA_CACHE_PATH.exists():
        try:
            with open(_MEDIA_CACHE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_media_cache(data: dict[str, dict]) -> None:
    _MEDIA_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_MEDIA_CACHE_PATH, "w") as f:
        json.dump(data, f)


def _empty_media(imdb_id: str) -> dict:
    return {
        "imdb_id": imdb_id,
        "trailer_url": None,
        "poster_url": None,
        "backdrop_url": None,
        "overview": None,
        "cast": [],
        "available": False,
    }


def _pick_trailer(videos: list[dict]) -> str | None:
    """Pick the best YouTube trailer from TMDB's videos response."""
    candidates = [
        v for v in videos
        if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser")
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda v: (
            v.get("type") != "Trailer",
            not v.get("official", False),
            v.get("size", 0) * -1,
        ),
    )
    key = candidates[0].get("key")
    return f"https://www.youtube.com/embed/{key}" if key else None


def fetch_title_media(imdb_id: str) -> dict:
    """Fetch trailer + poster + backdrop + cast images for an IMDB ID via TMDB.

    Cached forever in ``data/cache/tmdb_media.json``. Returns an empty payload
    (``available=False``) if no API key is configured or the lookup fails.
    """
    cache = _load_media_cache()
    if imdb_id in cache:
        return cache[imdb_id]

    if not _TMDB_API_KEY:
        result = _empty_media(imdb_id)
        # Don't cache the no-key case — caching would lock the app into an
        # empty state if the key is added later.
        return result

    try:
        with httpx.Client(timeout=10.0) as client:
            tmdb_id, media_type = _find_tmdb_id(client, imdb_id)
            if not tmdb_id or not media_type:
                cache[imdb_id] = _empty_media(imdb_id)
                _save_media_cache(cache)
                return cache[imdb_id]

            time.sleep(_RATE_LIMIT_DELAY)
            details_url = f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}"
            details_resp = client.get(
                details_url,
                params={
                    "api_key": _TMDB_API_KEY,
                    "append_to_response": "videos,credits",
                },
            )
            details_resp.raise_for_status()
            data = details_resp.json()

        videos = data.get("videos", {}).get("results", []) or []
        credits = data.get("credits", {}) or {}
        cast_raw = credits.get("cast", [])[:10]

        cast = []
        for c in cast_raw:
            profile = c.get("profile_path")
            cast.append({
                "name": c.get("name", ""),
                "character": c.get("character"),
                "profile_url": (
                    f"{_TMDB_IMG_BASE}/{_PROFILE_SIZE}{profile}" if profile else None
                ),
            })

        poster = data.get("poster_path")
        backdrop = data.get("backdrop_path")
        result = {
            "imdb_id": imdb_id,
            "trailer_url": _pick_trailer(videos),
            "poster_url": f"{_TMDB_IMG_BASE}/{_POSTER_SIZE}{poster}" if poster else None,
            "backdrop_url": (
                f"{_TMDB_IMG_BASE}/{_BACKDROP_SIZE}{backdrop}" if backdrop else None
            ),
            "overview": data.get("overview") or None,
            "cast": cast,
            "available": True,
        }
    except (httpx.HTTPError, KeyError, ValueError) as e:
        logger.warning("TMDB media fetch failed for %s: %s", imdb_id, e)
        result = _empty_media(imdb_id)

    cache[imdb_id] = result
    _save_media_cache(cache)
    return result


def top_keywords(limit: int = 60) -> list[str]:
    """Return the most-frequent TMDB keywords across the cached metadata.

    Falls back to the curated DEFAULT_MOOD_TAGS list when the cache is empty
    so the frontend filter chips always have something to render.
    """
    cache = _load_tmdb_cache()
    if not cache:
        return DEFAULT_MOOD_TAGS[:limit]
    counts: dict[str, int] = {}
    for entry in cache.values():
        for kw in entry.get("keywords", []):
            counts[kw] = counts.get(kw, 0) + 1
    if not counts:
        return DEFAULT_MOOD_TAGS[:limit]
    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    return [kw for kw, _ in ranked[:limit]]


def get_keywords_for(imdb_id: str) -> list[str]:
    """Return cached TMDB keywords for an IMDB ID, or [] if missing."""
    cache = _load_tmdb_cache()
    entry = cache.get(imdb_id)
    return entry.get("keywords", []) if entry else []


def build_keyword_affinity(
    rated_titles_keywords: dict[str, list[str]],
    title_ratings: dict[str, int],
) -> dict[str, float]:
    """Compute user's average rating per keyword from their rated titles.

    Args:
        rated_titles_keywords: imdb_id → list[keyword] for rated titles.
        title_ratings: imdb_id → user_rating.
    """
    from collections import defaultdict

    kw_ratings: dict[str, list[int]] = defaultdict(list)
    for imdb_id, keywords in rated_titles_keywords.items():
        rating = title_ratings.get(imdb_id)
        if rating is None:
            continue
        for kw in keywords:
            kw_ratings[kw].append(rating)
    return {kw: sum(r) / len(r) for kw, r in kw_ratings.items()}
