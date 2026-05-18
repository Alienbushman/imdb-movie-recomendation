"""Offline evaluation harness for the IMDB recommendation engine.

CLI entry point: ``uv run python -m eval.run_eval``.

The metric implementations themselves live in ``app/services/eval_metrics.py``
so they can also be imported by ``app/services/model.py`` for training-time
ranking-metric logging (T1.1) and Optuna objective (T1.2).
"""

from app.services.eval_metrics import (
    average_precision_at_k,
    catalog_coverage,
    diversity,
    map_at_k,
    mrr,
    ndcg_at_k,
    ndcg_at_k_from_scores,
    novelty,
    recall_at_k,
    spearman_corr,
)

__all__ = [
    "average_precision_at_k",
    "catalog_coverage",
    "diversity",
    "map_at_k",
    "mrr",
    "ndcg_at_k",
    "ndcg_at_k_from_scores",
    "novelty",
    "recall_at_k",
    "spearman_corr",
]
