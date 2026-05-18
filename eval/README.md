# Offline eval harness

Foundational measurement layer for the recommendation engine. Run this before
and after every model change to confirm the change actually helps.

## Run

```bash
uv run python -m eval.run_eval                # NDCG@10 baseline
uv run python -m eval.run_eval --k 20         # NDCG@20
uv run python -m eval.run_eval --top-n 200    # bigger top-N for coverage/diversity
uv run python -m eval.run_eval --json out.json  # explicit output file
```

Output JSON is written to `data/eval_results/{timestamp}.json` by default so
runs accumulate naturally over time.

## Metrics

| Metric            | What it measures                                                |
|-------------------|-----------------------------------------------------------------|
| `ndcg_at_k`       | Ranking quality: are high-rated titles ranked above low-rated?  |
| `map_at_k`        | Mean Average Precision over the held-out positives.             |
| `mrr`             | Reciprocal rank of the first "relevant" holdout title.          |
| `recall_at_k`     | Fraction of holdout positives that landed in top-k.             |
| `spearman`        | Rank correlation between predicted and true holdout ratings.    |
| `novelty`         | Mean -log2(popularity) of top-N — high = obscure titles surface.|
| `catalog_coverage`| Fraction of catalogue items in the top-N recommendations.       |
| `diversity`       | Mean pairwise dissimilarity inside the top-50.                  |

"Relevant" = the user rated the holdout title >= 7/10.

## How the holdout is built

The harness sorts the user's rated titles by `date_rated` and takes the most
recent `test_size` fraction (config `model.test_size`, default 0.2) as the
holdout. Everything before that is "train" (and is the same data the saved
model already saw).

This is the same split logic used in `model.py:train_taste_model` when
`model.split.mode = "temporal"`. Keep them in sync.

## Tests

`tests/test_eval_metrics.py` contains property-style sanity checks (perfect
ranking ⇒ NDCG@k = 1.0, etc.). Run with `uv run pytest tests/test_eval_metrics.py`.
