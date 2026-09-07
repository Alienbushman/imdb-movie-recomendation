"""T3.15: CLI eval harness.

Usage:
    uv run python -m eval.run_eval                  # latest model + scored DB
    uv run python -m eval.run_eval --k 20           # NDCG@20
    uv run python -m eval.run_eval --json out.json  # write metrics to JSON

What it does:

1. Loads the saved taste model + feature names + taste profile.
2. Loads the user's rated titles (the ground truth).
3. Splits temporally — last `test_size` fraction is the holdout.
4. Asks the model to score the holdout titles AND the candidate catalogue.
5. Computes ranking metrics:
   - NDCG@k / MAP@k / MRR@k / Recall@k against the holdout (treating user
     ratings >= 7 as "relevant").
   - Spearman correlation between predicted and actual ratings on the holdout.
6. Computes beyond-accuracy metrics on the top-100 candidate recommendations:
   - Catalog coverage
   - Diversity (mean pairwise dissimilarity via similarity_engine)
   - Novelty (self-information from log-vote popularity)
7. Prints a table and (optionally) writes JSON to ``data/eval_results/{ts}.json``.

The numbers this produces are the baseline to beat for every subsequent change.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import UTC, datetime
from pathlib import Path

# Allow running as `python eval/run_eval.py` from project root, too.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import PROJECT_ROOT, get_settings  # noqa: E402
from app.services.eval_metrics import (  # noqa: E402
    average_precision_at_k,
    catalog_coverage,
    diversity,
    mrr,
    ndcg_at_k_from_scores,
    novelty,
    recall_at_k,
    spearman_corr,
)
from app.services.features import (  # noqa: E402
    features_to_dataframe,
    rated_title_to_features,
)
from app.services.ingest import load_watchlist  # noqa: E402
from app.services.model import load_taste_model  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("eval")


def _temporal_split(titles, test_size: float):
    """Sort by date_rated then take the latest `test_size` fraction as holdout.

    Falls back to a random tail if the date column is missing.
    """
    try:
        sortable = sorted(
            titles,
            key=lambda t: (t.date_rated or "", t.imdb_id),
        )
    except Exception:
        sortable = list(titles)

    n = len(sortable)
    n_test = max(1, int(round(n * test_size)))
    train = sortable[: n - n_test]
    test = sortable[n - n_test :]
    return train, test


def _score(model, feature_names, titles, taste) -> list[float]:
    """Predict scores for a list of rated titles using the saved model."""
    if not titles:
        return []
    feats = [rated_title_to_features(t, taste) for t in titles]
    df = features_to_dataframe(feats)
    missing = [c for c in feature_names if c not in df.columns]
    if missing:
        df = df.assign(**{c: float("nan") for c in missing})
    df = df[feature_names]
    return [float(s) for s in model.predict(df)]


def _load_candidate_popularity(top_n: int = 200) -> dict[str, float]:
    """Lightweight popularity map built from the scored-candidates SQLite DB.

    Maps imdb_id → normalised log-vote count in (0, 1]. Used for novelty.
    """
    import sqlite3

    db_path = PROJECT_ROOT / "data" / "cache" / "scored_candidates.db"
    if not db_path.exists():
        return {}
    try:
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute(
            "SELECT imdb_id, num_votes FROM scored_candidates WHERE num_votes > 0"
        ).fetchall()
        conn.close()
    except sqlite3.OperationalError:
        return {}
    if not rows:
        return {}
    max_log = max(math.log10(v) for _, v in rows)
    return {imdb_id: math.log10(v) / max_log for imdb_id, v in rows}


def _top_n_from_scored_db(top_n: int) -> list[str]:
    """Pull the top-N predicted IDs from the scored-candidates DB."""
    import sqlite3

    db_path = PROJECT_ROOT / "data" / "cache" / "scored_candidates.db"
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    rows = conn.execute(
        "SELECT imdb_id FROM scored_candidates ORDER BY predicted_score DESC LIMIT ?",
        (top_n,),
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def run(k: int = 10, top_n: int = 100, out_path: Path | None = None) -> dict:
    settings = get_settings()
    loaded = load_taste_model()
    if loaded is None:
        raise SystemExit("No saved taste_model.pkl found — run the pipeline first.")
    model, feature_names, taste = loaded

    titles = load_watchlist()
    if not titles:
        raise SystemExit("No rated titles loaded — populate data/watchlist.csv first.")

    train, test = _temporal_split(titles, settings.model.test_size)
    logger.info("Loaded %d rated titles. Train=%d, Test=%d.", len(titles), len(train), len(test))

    # --- Holdout-based metrics ---------------------------------------------
    y_true = [float(t.user_rating) for t in test]
    y_pred = _score(model, feature_names, test, taste)

    ndcg = ndcg_at_k_from_scores(y_true, y_pred, k)
    sp = spearman_corr(y_true, y_pred)

    # Relevance bar for map/mrr/recall. Configurable because 7.0 made map and
    # mrr pin to exactly 1.0000 on a library where ~47% of ratings are 7+.
    threshold = settings.model.relevance_threshold
    relevant_ids = {t.imdb_id for t, r in zip(test, y_true) if r >= threshold}
    test_ids = [t.imdb_id for t in test]
    # Rank the holdout titles by predicted score and check where the truly
    # relevant ones land.
    by_pred = [tid for _, tid in sorted(zip(y_pred, test_ids), reverse=True)]
    ap = average_precision_at_k(by_pred, relevant_ids, k)
    rec = recall_at_k(by_pred, relevant_ids, k)
    rr = mrr(by_pred, relevant_ids)

    # --- Beyond-accuracy metrics on top-N catalogue recommendations --------
    top_ids = _top_n_from_scored_db(top_n)
    pop = _load_candidate_popularity()
    nov = novelty(top_ids, pop)
    cov = catalog_coverage([top_ids], total_catalog_size=len(pop) or 1)

    # Diversity uses similarity_engine when available; fall back to a trivial
    # "all items equally diverse" 0.5 placeholder if it can't be computed
    # (e.g. fresh checkout without a scored DB).
    try:
        from app.services.similar import compute_similarity_by_id

        div = diversity(top_ids[: min(50, len(top_ids))], compute_similarity_by_id)
    except Exception:
        div = float("nan")

    metrics = {
        "k": k,
        "n_train": len(train),
        "n_test": len(test),
        "n_relevant_in_test": len(relevant_ids),
        "n_top_n_evaluated": len(top_ids),
        "ndcg_at_k": ndcg,
        "map_at_k": ap,
        "mrr": rr,
        "recall_at_k": rec,
        "spearman": sp,
        "novelty": nov,
        "catalog_coverage": cov,
        "diversity": div,
        "generated_at": datetime.now(UTC).isoformat(),
    }

    _print_table(metrics)

    if out_path is None:
        out_dir = PROJECT_ROOT / "data" / "eval_results"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(metrics, indent=2))
    logger.info("Wrote metrics to %s", out_path)
    return metrics


def _print_table(metrics: dict) -> None:
    width = 32
    print()
    print("=" * width)
    print(" Offline eval results")
    print("=" * width)
    for key in [
        "k",
        "n_train",
        "n_test",
        "n_relevant_in_test",
        "n_top_n_evaluated",
        "ndcg_at_k",
        "map_at_k",
        "mrr",
        "recall_at_k",
        "spearman",
        "novelty",
        "catalog_coverage",
        "diversity",
    ]:
        val = metrics[key]
        if isinstance(val, float):
            print(f" {key:<22} {val:>8.4f}")
        else:
            print(f" {key:<22} {val:>8}")
    print("=" * width)
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline eval for the IMDB recommender.")
    parser.add_argument("--k", type=int, default=10, help="NDCG@k / MAP@k / Recall@k cutoff.")
    parser.add_argument("--top-n", type=int, default=100, help="Top-N for beyond-accuracy metrics.")
    parser.add_argument("--json", type=Path, default=None, help="Optional output JSON path.")
    args = parser.parse_args()
    run(k=args.k, top_n=args.top_n, out_path=args.json)
