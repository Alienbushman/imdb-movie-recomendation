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
_RATE_LIMIT_DELAY = 0.25  # 4 req/s to stay within 40 req/10s


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
