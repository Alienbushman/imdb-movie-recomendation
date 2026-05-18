"""T3.15: Ranking-aware evaluation metrics.

These functions are used in three places:

1. Model training (``app/services/model.py``) — to log NDCG@k / MAP@k / MRR on
   the temporal holdout and to drive the Optuna objective (T1.2).
2. Cross-validation (``cross_validate`` in model.py) — to aggregate per-fold
   ranking scores.
3. The offline eval harness CLI (``eval/run_eval.py``) — to produce a baseline
   report and track quality across model iterations.

The implementations stay dependency-light: numpy only. We intentionally do NOT
re-use sklearn.metrics.ndcg_score everywhere because we also want NDCG@k for
arbitrary relevance lists (not just a single query) and a NaN-tolerant variant
for tiny holdouts.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

import numpy as np

# ---------------------------------------------------------------------------
# DCG / NDCG
# ---------------------------------------------------------------------------


def _dcg_at_k(rel_scores: list[float], k: int) -> float:
    """Discounted cumulative gain on the first k positions.

    rel_scores[i] is the graded relevance of the item ranked at position i+1
    (i.e. the list is already ordered by predicted relevance, descending).
    Standard formulation: sum_i (2**rel - 1) / log2(i + 2).
    """
    out = 0.0
    for i, rel in enumerate(rel_scores[:k]):
        out += (2.0**rel - 1.0) / math.log2(i + 2.0)
    return out


def ndcg_at_k(rel_scores: list[float], k: int) -> float:
    """Normalized DCG@k for a single ranking.

    Args:
        rel_scores: relevance scores ordered by predicted rank (descending
            predicted score). For our use case, these are the user's ground-
            truth ratings (1-10) of the recommended items.
        k: cutoff.

    Returns:
        NDCG@k in [0, 1]. 0.0 if the ideal ranking has zero gain (all rel=0)
        or the list is empty.
    """
    if not rel_scores:
        return 0.0
    actual = _dcg_at_k(rel_scores, k)
    ideal = _dcg_at_k(sorted(rel_scores, reverse=True), k)
    return actual / ideal if ideal > 0 else 0.0


def ndcg_at_k_from_scores(y_true: Iterable[float], y_pred: Iterable[float], k: int) -> float:
    """NDCG@k from parallel arrays of true relevance and predicted scores.

    Sorts items by y_pred descending, then reads y_true in that order.
    """
    pairs = list(zip(y_true, y_pred))
    pairs.sort(key=lambda p: p[1], reverse=True)
    return ndcg_at_k([float(t) for t, _ in pairs], k)


# ---------------------------------------------------------------------------
# Precision / Recall / MAP / MRR
# ---------------------------------------------------------------------------


def average_precision_at_k(predicted_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Average Precision @ k for a single query.

    AP@k = (1 / min(|R|, k)) * sum_{i in 1..k} P(i) * rel(i)
    where rel(i) is 1 if predicted_ids[i] is relevant, else 0.
    """
    if not relevant_ids or not predicted_ids:
        return 0.0
    score = 0.0
    hits = 0
    for i, pid in enumerate(predicted_ids[:k]):
        if pid in relevant_ids:
            hits += 1
            score += hits / (i + 1)
    denom = min(len(relevant_ids), k)
    return score / denom if denom else 0.0


def map_at_k(queries: list[tuple[list[str], set[str]]], k: int) -> float:
    """Mean Average Precision over a list of (predicted, relevant) pairs.

    With a single-user system there's exactly one query per evaluation, so this
    collapses to AP@k — but we keep the standard interface for forward
    compatibility (multi-user, multi-context recommendations).
    """
    if not queries:
        return 0.0
    return float(np.mean([average_precision_at_k(p, r, k) for p, r in queries]))


def recall_at_k(predicted_ids: list[str], relevant_ids: set[str], k: int) -> float:
    """Fraction of relevant items that appear in the top-k predictions."""
    if not relevant_ids:
        return 0.0
    hits = sum(1 for pid in predicted_ids[:k] if pid in relevant_ids)
    return hits / len(relevant_ids)


def mrr(predicted_ids: list[str], relevant_ids: set[str]) -> float:
    """Reciprocal rank of the first relevant item; 0 if none in the list."""
    for i, pid in enumerate(predicted_ids):
        if pid in relevant_ids:
            return 1.0 / (i + 1)
    return 0.0


# ---------------------------------------------------------------------------
# Spearman rank correlation (non-ranking-aware sanity check)
# ---------------------------------------------------------------------------


def spearman_corr(y_true: Iterable[float], y_pred: Iterable[float]) -> float:
    """Spearman rank correlation between true and predicted, NaN-safe.

    Returns 0.0 if either list is empty or one of them has no variance (e.g.
    a constant predictor — no discriminative power, so correlation isn't a
    meaningful number).
    """
    t = np.asarray(list(y_true), dtype=float)
    p = np.asarray(list(y_pred), dtype=float)
    if len(t) < 2 or len(p) < 2:
        return 0.0
    # If one side has only one unique value the rank correlation is
    # undefined. Returning 0.0 matches scipy's "constant input ⇒ NaN" case
    # rephrased as "the model has zero discriminative power, so spearman=0".
    if np.unique(t).size < 2 or np.unique(p).size < 2:
        return 0.0

    def _rank(a: np.ndarray) -> np.ndarray:
        # Average-rank for ties so a constant column produces equal ranks
        # (and therefore zero variance — caught by the unique-check above).
        order = a.argsort()
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.arange(len(a))
        return ranks

    rt = _rank(t)
    rp = _rank(p)
    rt -= rt.mean()
    rp -= rp.mean()
    denom = float(np.sqrt((rt**2).sum() * (rp**2).sum()))
    if denom == 0.0:
        return 0.0
    return float((rt * rp).sum() / denom)


# ---------------------------------------------------------------------------
# Beyond accuracy: coverage / diversity / novelty
# ---------------------------------------------------------------------------


def catalog_coverage(recommended_ids_per_query: list[list[str]], total_catalog_size: int) -> float:
    """Fraction of the catalog that appears in at least one recommendation list.

    Single-user systems will have exactly one query in the outer list.
    """
    if total_catalog_size <= 0:
        return 0.0
    seen: set[str] = set()
    for lst in recommended_ids_per_query:
        seen.update(lst)
    return len(seen) / total_catalog_size


def diversity(
    items: list[str],
    similarity_fn,
) -> float:
    """Mean pairwise dissimilarity (1 - sim) across items in a result list.

    similarity_fn(id_a, id_b) -> float in [0, 1].
    Returns 0.0 for lists of length < 2.
    """
    n = len(items)
    if n < 2:
        return 0.0
    pairs = 0
    total = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            total += 1.0 - float(similarity_fn(items[i], items[j]))
            pairs += 1
    return total / pairs if pairs else 0.0


def novelty(predicted_ids: list[str], popularity_map: dict[str, float]) -> float:
    """Self-information novelty: mean -log2(popularity) over the list.

    popularity_map[id] should be in (0, 1] (fraction of users / log-vote ratio).
    Items missing from the map are skipped (no penalty, no boost).
    """
    if not predicted_ids:
        return 0.0
    scores = []
    for pid in predicted_ids:
        pop = popularity_map.get(pid)
        if pop is None or pop <= 0.0:
            continue
        scores.append(-math.log2(min(pop, 1.0)))
    return float(np.mean(scores)) if scores else 0.0
