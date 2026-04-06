"""Subtask 10: OMDb API integration for Rotten Tomatoes and Metacritic scores.

Fetches critic scores for IMDB titles via the OMDb API and caches locally.
Requires OMDB_API_KEY environment variable (free tier: 1000 req/day).

If OMDB_API_KEY is not set, all functions degrade gracefully (zero scores).
"""

import json
import logging
import os
import time

import httpx

from app.core.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

_OMDB_API_KEY = os.environ.get("OMDB_API_KEY", "")
_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "omdb_scores.json"
_RATE_LIMIT_DELAY = 0.1  # 10 req/s — well within free tier


def _load_omdb_cache() -> dict[str, dict]:
    if _CACHE_PATH.exists():
        try:
            with open(_CACHE_PATH) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_omdb_cache(data: dict[str, dict]) -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CACHE_PATH, "w") as f:
        json.dump(data, f)


def _parse_rt_score(ratings: list[dict]) -> float | None:
    """Extract Rotten Tomatoes % from OMDb ratings list, normalized to 0-10."""
    for r in ratings:
        if r.get("Source") == "Rotten Tomatoes":
            val = r.get("Value", "")
            if val.endswith("%"):
                try:
                    return float(val[:-1]) / 10.0
                except ValueError:
                    pass
    return None


def _parse_metacritic_score(score_str: str | None) -> float | None:
    """Parse Metacritic score string (0-100) to 0-10 scale."""
    if not score_str or score_str in ("N/A", ""):
        return None
    try:
        return float(score_str) / 10.0
    except ValueError:
        return None


def fetch_omdb_scores(imdb_ids: list[str]) -> dict[str, dict]:
    """Fetch RT and Metacritic scores for a list of IMDB IDs, using local cache.

    Returns imdb_id → {"rt": float|None, "metacritic": float|None}.
    No-ops if OMDB_API_KEY is not configured.
    """
    if not _OMDB_API_KEY:
        logger.debug("OMDB_API_KEY not set — skipping critic score fetch")
        return {}

    cache = _load_omdb_cache()
    result: dict[str, dict] = {}
    to_fetch = []

    for imdb_id in imdb_ids:
        if imdb_id in cache:
            result[imdb_id] = cache[imdb_id]
        else:
            to_fetch.append(imdb_id)

    if not to_fetch:
        return result

    logger.info("Fetching OMDb scores for %d uncached titles", len(to_fetch))
    with httpx.Client(timeout=10.0) as client:
        for imdb_id in to_fetch:
            scores: dict = {"rt": None, "metacritic": None}
            try:
                resp = client.get(
                    "http://www.omdbapi.com/",
                    params={"i": imdb_id, "apikey": _OMDB_API_KEY},
                )
                resp.raise_for_status()
                data = resp.json()
                if data.get("Response") == "True":
                    scores["rt"] = _parse_rt_score(data.get("Ratings", []))
                    scores["metacritic"] = _parse_metacritic_score(
                        data.get("Metascore")
                    )
            except (httpx.HTTPError, ValueError, KeyError):
                pass
            cache[imdb_id] = scores
            result[imdb_id] = scores
            time.sleep(_RATE_LIMIT_DELAY)

    _save_omdb_cache(cache)
    logger.info("OMDb cache updated: %d total entries", len(cache))
    return result


def compute_critic_features(
    imdb_id: str,
    imdb_rating: float,
    omdb_scores: dict[str, dict],
) -> dict:
    """Compute critic score features for a single candidate.

    Returns rt_score, metacritic_score, imdb_rt_gap, imdb_metacritic_gap.
    Missing scores default to 0.0.
    """
    entry = omdb_scores.get(imdb_id, {})
    rt = entry.get("rt") or 0.0
    mc = entry.get("metacritic") or 0.0
    return {
        "rt_score": rt,
        "metacritic_score": mc,
        "imdb_rt_gap": imdb_rating - rt,
        "imdb_metacritic_gap": imdb_rating - mc,
    }
