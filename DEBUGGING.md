# Debugging Guide

## Filter issues

### Quickest check: browser console

In dev mode (`npm run dev`), every API call logs its inputs:

```
[api] filterRecommendations { filters: { min_year: 2020 }, query: { min_year: 2020 } }
[api] getRecommendations    { filters: undefined, query: { retrain: false } }
```

If `filters` is `undefined` when you expect it not to be, the problem is in `buildFilters()` — the filter
condition for that field evaluated to falsy. See the rules below.

If `filters` is correct but results don't change, the problem is in the backend or the fallback path.

---

### `buildFilters()` rules — when each filter is sent

| Field | Sent when |
|---|---|
| `min_year` | truthy (`> 0`, not `undefined`/`null`/`NaN`) |
| `max_year` | truthy |
| `genres` | array is non-empty |
| `exclude_genres` | array is non-empty |
| `language` | truthy string |
| `exclude_languages` | array is non-empty |
| `min_imdb_rating` | `> 0` (default is `0`) |
| `max_runtime` | `< 300` (default is `300`) |
| `min_predicted_score` | `!== 6.5` (default is `6.5`) |

**Common gotcha:** If you set a slider to its default value after changing it, the filter is dropped
and the backend uses its own config default (`min_predicted_score: 6.5` in `config.yaml`). This is
intentional — but means "reset to 6.5" and "never touched" are indistinguishable.

---

### The fallback path: filter → generate

`applyFilters()` first tries `POST /recommendations/filter` (fast, uses cached scores).
If the backend has no cached scores (fresh server start, or server restart), it returns `409` and
the frontend falls back to a full `POST /recommendations` pipeline run.

**How to spot it:** The operation badge in the UI shows `⚡ from cache` (filter path) or `🔄 full run`
(pipeline path). If you always see `🔄 full run` after clicking Apply Filters, the backend cache is
being cleared — check if the server is restarting between requests.

**Backend log to look for:**
```
INFO  app.services.pipeline — Filter-only path: re-filtering 11234 cached scores
# vs
INFO  app.services.pipeline — Pipeline started (retrain=False, filters=True)
```

---

### Reproducing a filter bug

Provide these details in your ticket:

1. **Filter values set** — e.g. "min year = 2020, genres = Action"
2. **Expected** — e.g. "results should all be from 2020 or later"
3. **Actual** — e.g. "results unchanged, includes titles from 2005"
4. **Operation badge** — `⚡ from cache` or `🔄 full run`
5. **Console output** — paste the `[api] filterRecommendations` line

---

## Backend pipeline issues

### Check server logs

```bash
# Docker
docker compose logs api --tail=50

# Local
uv run uvicorn app.main:app --reload --port 8562
```

Key log lines to look for:

```
Step 4/4: Scoring and ranking N candidates           ← scoring happened
Filter min_year>=2020: 11234 → 4210 candidates       ← filter was applied
Min predicted score threshold: 6.50                  ← what threshold was used
Recommendations built in 0.12s — 20 movies, 10 series, 10 animation
```

If the filter log line is missing, the filters object was `None` — meaning the frontend sent no
query params or the backend received them incorrectly.

### Cache invalidation

The candidate cache at `data/cache/imdb_candidates.json` is only rebuilt when deleted. The scored
results cache is in-memory only and clears on every server restart.

```bash
# Force candidate rebuild
rm data/cache/imdb_candidates.json
```

---

## Running frontend tests

```bash
cd frontend
npm test           # single run
npm run test:watch # watch mode
```

Tests cover `buildFilters()` and `activeFilterSummary` — run these first when suspecting a filter
logic regression.
