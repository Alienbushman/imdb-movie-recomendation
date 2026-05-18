"""T2.6: Maximal Marginal Relevance re-ranking.

Greedy MMR selects items that balance high predicted score (relevance) against
low similarity to items already picked. With ``lambda_=1.0`` we get the legacy
relevance-only ordering; with ``lambda_=0.0`` we get pure diversity (a
trash-fire for recommendations); ``lambda_=0.7`` is the standard "high
relevance, some breathing room" sweet spot used in IR.

Implementation notes:

- Operates on (item, score) pairs in an opaque way so it can be applied to
  ``(CandidateTitle, FeatureVector, score)`` tuples (the recommend.py shape)
  or to lighter ``(CandidateTitle, score)`` pairs from the GET fast-path.
- The similarity function receives the raw items, not indices — that's the
  same shape ``app/services/similar.py:compute_similarity`` already accepts.
- O(k * pool) overall, well-behaved for pool sizes up to a few thousand.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


def mmr_rerank[T](
    items: list[T],
    scores: list[float],
    similarity_fn: Callable[[T, T], float],
    lambda_: float = 0.7,
    pool_size: int | None = None,
) -> list[int]:
    """Return indices (into the input ``items`` list) in MMR order.

    Args:
        items: candidate items, ordered by predicted score descending.
        scores: parallel list of normalised relevance scores (we normalise
            inside the function so absolute magnitudes don't matter, only
            relative ordering).
        similarity_fn: pairwise similarity in [0, 1].
        lambda_: relevance vs diversity trade-off. 1.0 = ignore diversity.
        pool_size: cap the input to the top-N candidates; the remainder are
            appended in original order after MMR finishes.

    Returns: list of indices into ``items``, length == len(items).
    """
    n = len(items)
    if n <= 1 or lambda_ >= 1.0:
        return list(range(n))

    pool_size = min(pool_size or n, n)
    if pool_size <= 1:
        return list(range(n))

    # Normalise scores in the pool to [0, 1] so lambda is dimensionless.
    pool_scores = scores[:pool_size]
    s_min = min(pool_scores)
    s_max = max(pool_scores)
    rng = s_max - s_min
    if rng > 0:
        norm = [(s - s_min) / rng for s in pool_scores]
    else:
        norm = [1.0 for _ in pool_scores]

    selected: list[int] = []
    remaining: set[int] = set(range(pool_size))

    # Seed with the top-relevance item (cheap, avoids a degenerate first pick).
    first = max(remaining, key=lambda i: norm[i])
    selected.append(first)
    remaining.discard(first)

    while remaining:
        best_idx = -1
        best_score = -float("inf")
        for i in remaining:
            max_sim_to_selected = 0.0
            for j in selected:
                sim = float(similarity_fn(items[i], items[j]))
                if sim > max_sim_to_selected:
                    max_sim_to_selected = sim
            mmr = lambda_ * norm[i] - (1.0 - lambda_) * max_sim_to_selected
            if mmr > best_score:
                best_score = mmr
                best_idx = i
        if best_idx == -1:
            break
        selected.append(best_idx)
        remaining.discard(best_idx)

    # Append the tail (items beyond pool_size) in original order.
    selected.extend(range(pool_size, n))
    return selected
