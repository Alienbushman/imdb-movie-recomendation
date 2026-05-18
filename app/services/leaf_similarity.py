"""T2.7: Tree-leaf-index similarity (the GBDT+LR trick).

After LightGBM is fit, every row gets assigned to a single leaf in every tree.
Two rows that share many leaves are similar in a learned, model-aware sense —
much richer than Jaccard over the raw genre list. We use the fraction of trees
in which the two rows land in the same leaf as a similarity in [0, 1].

The full leaf-index matrix for the scored-candidate catalogue is cached on
disk under ``data/cache/leaf_indices.npz`` after the first /similar query so
subsequent calls don't re-run inference. The cache is invalidated by
``invalidate_leaf_cache()`` and is automatically rebuilt when missing.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time

import numpy as np

from app.core.config import PROJECT_ROOT
from app.models.schemas import CandidateTitle
from app.services.features import candidate_to_features
from app.services.model import load_model_bundle, predict_leaf_indices

logger = logging.getLogger(__name__)

_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "leaf_indices.npz"
_SCORED_DB = PROJECT_ROOT / "data" / "cache" / "scored_candidates.db"

# Module-level memoisation. Built once per process to avoid the disk read cost
# on every /similar request. invalidate_leaf_cache() clears both layers.
_lock = threading.Lock()
_cache: dict | None = None  # {"ids": np.array of str, "leaves": np.int32[n, t]}


def invalidate_leaf_cache() -> None:
    """Drop both in-memory and on-disk caches. Called when the model retrains."""
    global _cache
    with _lock:
        _cache = None
        try:
            _CACHE_PATH.unlink(missing_ok=True)
        except OSError as e:
            logger.warning("Could not delete %s: %s", _CACHE_PATH, e)


def _load_candidates_from_db() -> list[CandidateTitle]:
    """Re-hydrate every scored candidate as a CandidateTitle.

    Cheap (~1s for 50k titles) — only run when the cache needs rebuilding.
    """
    if not _SCORED_DB.exists():
        return []
    conn = sqlite3.connect(str(_SCORED_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM scored_candidates").fetchall()
    conn.close()

    out: list[CandidateTitle] = []
    for row in rows:
        keys = row.keys()
        try:
            out.append(
                CandidateTitle(
                    imdb_id=row["imdb_id"],
                    title=row["title"],
                    original_title=row["title"],
                    title_type=row["title_type"],
                    imdb_rating=row["imdb_rating"] or 0.0,
                    runtime_mins=row["runtime_mins"],
                    year=row["year"],
                    genres=json.loads(row["genres"] or "[]"),
                    num_votes=row["num_votes"] or 0,
                    directors=json.loads(row["directors"] or "[]"),
                    actors=json.loads(row["actors"] or "[]"),
                    language=row["language"],
                    languages=json.loads(row["languages"] or "[]") if "languages" in keys else [],
                    country_code=row["country_code"],
                    writers=json.loads(row["writers"] or "[]") if "writers" in keys else [],
                    composers=json.loads(row["composers"] or "[]") if "composers" in keys else [],
                    cinematographers=(
                        json.loads(row["cinematographers"] or "[]")
                        if "cinematographers" in keys
                        else []
                    ),
                    is_anime=bool(row["is_anime"]) if "is_anime" in keys else False,
                )
            )
        except (KeyError, json.JSONDecodeError, ValueError):
            continue
    return out


def _build_cache() -> dict | None:
    """Recompute the leaf-index matrix for the full scored catalogue."""
    bundle = load_model_bundle()
    if bundle is None:
        logger.info("No model bundle available — leaf-similarity falls back to jaccard.")
        return None

    candidates = _load_candidates_from_db()
    if not candidates:
        logger.info("Scored DB empty — leaf-similarity unavailable.")
        return None

    t0 = time.perf_counter()
    # Resolve taste so candidate_to_features produces complete vectors.
    from app.models.schemas import TasteProfile

    taste_dict = bundle.get("taste_profile") or {}
    taste = TasteProfile(**taste_dict) if taste_dict else TasteProfile()

    feats = [candidate_to_features(c, taste) for c in candidates]
    leaves = predict_leaf_indices(bundle["model"], bundle["feature_names"], feats)
    ids = np.array([c.imdb_id for c in candidates], dtype=object)

    cache = {"ids": ids, "leaves": leaves}
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(_CACHE_PATH, ids=ids, leaves=leaves)
    except OSError as e:
        logger.warning("Could not write %s: %s", _CACHE_PATH, e)
    logger.info(
        "Built leaf-similarity cache: %d titles × %d trees in %.2fs",
        len(ids),
        leaves.shape[1],
        time.perf_counter() - t0,
    )
    return cache


def _load_cache_from_disk() -> dict | None:
    if not _CACHE_PATH.exists():
        return None
    try:
        npz = np.load(_CACHE_PATH, allow_pickle=True)
        return {"ids": npz["ids"], "leaves": npz["leaves"]}
    except (OSError, ValueError, KeyError) as e:
        logger.warning("Could not read %s: %s", _CACHE_PATH, e)
        return None


def _get_cache() -> dict | None:
    """Return the cache, rebuilding it lazily if missing."""
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
        disk = _load_cache_from_disk()
        if disk is not None:
            _cache = disk
            return _cache
        _cache = _build_cache()
        return _cache


def _id_to_row(cache: dict) -> dict[str, int]:
    """Map imdb_id → row index in the leaf matrix."""
    return {str(imdb_id): i for i, imdb_id in enumerate(cache["ids"])}


# ---------------------------------------------------------------------------
# Public similarity helpers
# ---------------------------------------------------------------------------


def similarity_by_leaves(seed_leaves: np.ndarray, candidate_leaves: np.ndarray) -> np.ndarray:
    """Hamming match rate between one seed and many candidates.

    Args:
        seed_leaves: shape (n_trees,).
        candidate_leaves: shape (n_candidates, n_trees).

    Returns: shape (n_candidates,), values in [0, 1].
    """
    if candidate_leaves.size == 0:
        return np.array([], dtype=float)
    return np.mean(candidate_leaves == seed_leaves, axis=1).astype(float)


def find_similar_by_leaves(seed_imdb_id: str, top_n: int = 50) -> list[tuple[str, float]] | None:
    """Return (imdb_id, similarity) pairs ranked by leaf overlap.

    Returns None when leaf similarity is unavailable (no model / no scored DB).
    The caller should then fall back to the legacy Jaccard path.
    """
    cache = _get_cache()
    if cache is None:
        return None
    id_to_row = _id_to_row(cache)
    if seed_imdb_id not in id_to_row:
        # Seed isn't in the candidate matrix — caller should fall back.
        return None
    seed_idx = id_to_row[seed_imdb_id]
    sims = similarity_by_leaves(cache["leaves"][seed_idx], cache["leaves"])
    sims[seed_idx] = -1.0  # exclude self
    top_idx = np.argsort(-sims)[:top_n]
    return [(str(cache["ids"][i]), float(sims[i])) for i in top_idx if sims[i] >= 0.0]


def pairwise_similarity_by_id(a_id: str, b_id: str) -> float:
    """Single-pair similarity wrapper (used by diversity / MMR fallbacks)."""
    cache = _get_cache()
    if cache is None:
        return 0.0
    id_to_row = _id_to_row(cache)
    if a_id not in id_to_row or b_id not in id_to_row:
        return 0.0
    a = cache["leaves"][id_to_row[a_id]]
    b = cache["leaves"][id_to_row[b_id]]
    return float(np.mean(a == b))
