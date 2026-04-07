---
id: ST-001
ticket: "015"
title: "Fix writer taste features (always zero)"
priority: High
risk: medium
status: Open
dependencies: []
subsystems: [backend]
---

# SUBTASK 01 — Fix writer taste features (always zero)

---

## Objective

The four writer taste features (`writer_taste_score`, `has_known_writer`,
`writer_taste_count`, `writer_taste_mean`) are always `0.0` because
`build_taste_profile()` reads writers from `RatedTitle.writers`, which is
always `[]` — the IMDB CSV export does not include a writers column.

Writers are already loaded from `title.crew.tsv.gz` in `candidates.py` into
`writers_by_title`. This fix routes that data through the same pipeline path
already used for actors, composers, and cinematographers.

---

## Pre-conditions

Confirm the bug: `build_taste_profile()` should produce an empty `writer_avg`
with the current code.

```bash
grep -n "for w in t.writers" app/services/features.py
```

Expected: one match at the writer averages block — confirm the loop reads from
`t.writers` (not from a passed-in dict).

```bash
grep -n "rated_writers" app/services/candidates.py app/services/pipeline.py app/services/model.py app/services/features.py
```

Expected: zero matches — `rated_writers` does not exist yet.

---

## Fix

### Step 1 — `app/services/candidates.py`: build and return `rated_writers`

Find the block at lines ~867–886 where `rated_actors`, `rated_composers`, and
`rated_cinematographers` are built and returned:

```python
    # Extract per-person data for rated (seen) titles — used to build taste profile
    rated_actors = {tid: actors_by_title[tid] for tid in seen_ids if tid in actors_by_title}
    rated_composers = {
        tid: composers_by_title[tid] for tid in seen_ids if tid in composers_by_title
    }
    rated_cinematographers = {
        tid: cinematographers_by_title[tid]
        for tid in seen_ids
        if tid in cinematographers_by_title
    }
    logger.info(
        "Loaded %d candidate titles from IMDB datasets in %.2fs "
        "(rated: %d actors, %d composers, %d cinematographers)",
        len(candidates),
        time.perf_counter() - t_total,
        len(rated_actors),
        len(rated_composers),
        len(rated_cinematographers),
    )
    return candidates, rated_actors, rated_composers, rated_cinematographers
```

Replace with:

```python
    # Extract per-person data for rated (seen) titles — used to build taste profile
    rated_actors = {tid: actors_by_title[tid] for tid in seen_ids if tid in actors_by_title}
    rated_writers = {tid: writers_by_title[tid] for tid in seen_ids if tid in writers_by_title}
    rated_composers = {
        tid: composers_by_title[tid] for tid in seen_ids if tid in composers_by_title
    }
    rated_cinematographers = {
        tid: cinematographers_by_title[tid]
        for tid in seen_ids
        if tid in cinematographers_by_title
    }
    logger.info(
        "Loaded %d candidate titles from IMDB datasets in %.2fs "
        "(rated: %d actors, %d writers, %d composers, %d cinematographers)",
        len(candidates),
        time.perf_counter() - t_total,
        len(rated_actors),
        len(rated_writers),
        len(rated_composers),
        len(rated_cinematographers),
    )
    return candidates, rated_actors, rated_writers, rated_composers, rated_cinematographers
```

Also update the cache-hit early return at line ~677:

```python
        return candidates, None, None, None
```

Replace with:

```python
        return candidates, None, None, None, None
```

Also update the docstring at line ~656:

```
    Returns (candidates, rated_actors, rated_composers, rated_cinematographers).
    All three dicts are None on a cache hit — taste profile comes from the saved model.
```

Replace with:

```
    Returns (candidates, rated_actors, rated_writers, rated_composers, rated_cinematographers).
    All four dicts are None on a cache hit — taste profile comes from the saved model.
```

### Step 2 — `app/services/pipeline.py`: unpack the new return value

Find the unpack line at ~line 95:

```python
        candidates, rated_actors, rated_composers, rated_cinematographers = (
            load_candidates_from_datasets(all_excluded)
        )
```

Replace with:

```python
        candidates, rated_actors, rated_writers, rated_composers, rated_cinematographers = (
            load_candidates_from_datasets(all_excluded)
        )
```

Find the `train_taste_model` call at ~line 117:

```python
            model, mae, feature_names, taste = train_taste_model(
                titles, rated_actors, rated_composers, rated_cinematographers
            )
```

Replace with:

```python
            model, mae, feature_names, taste = train_taste_model(
                titles, rated_actors, rated_writers, rated_composers, rated_cinematographers
            )
```

### Step 3 — `app/services/model.py`: add `rated_writers` parameter

Find `train_taste_model()`:

```python
def train_taste_model(
    titles: list[RatedTitle],
    rated_actors: dict[str, list[str]] | None = None,
    rated_composers: dict[str, list[str]] | None = None,
    rated_cinematographers: dict[str, list[str]] | None = None,
```

Replace with:

```python
def train_taste_model(
    titles: list[RatedTitle],
    rated_actors: dict[str, list[str]] | None = None,
    rated_writers: dict[str, list[str]] | None = None,
    rated_composers: dict[str, list[str]] | None = None,
    rated_cinematographers: dict[str, list[str]] | None = None,
```

Find the `build_taste_profile` call inside the function:

```python
    taste = build_taste_profile(titles, rated_actors, rated_composers, rated_cinematographers)
```

Replace with:

```python
    taste = build_taste_profile(
        titles, rated_actors, rated_writers, rated_composers, rated_cinematographers
    )
```

### Step 4 — `app/services/features.py`: fix `build_taste_profile()`

Find the function signature:

```python
def build_taste_profile(
    rated_titles: list[RatedTitle],
    rated_actors: dict[str, list[str]] | None = None,
    rated_composers: dict[str, list[str]] | None = None,
    rated_cinematographers: dict[str, list[str]] | None = None,
) -> TasteProfile:
```

Replace with:

```python
def build_taste_profile(
    rated_titles: list[RatedTitle],
    rated_actors: dict[str, list[str]] | None = None,
    rated_writers: dict[str, list[str]] | None = None,
    rated_composers: dict[str, list[str]] | None = None,
    rated_cinematographers: dict[str, list[str]] | None = None,
) -> TasteProfile:
```

Find the broken writer loop (reads from `t.writers`):

```python
    # Subtask 4: Writer averages (Bayesian-smoothed)
    writer_ratings: dict[str, list[int]] = defaultdict(list)
    for t in rated_titles:
        for w in t.writers:
            writer_ratings[w].append(t.user_rating)
    writer_avg = {w: _bayesian_avg(r, global_mean) for w, r in writer_ratings.items()}
```

Replace with the correct lookup pattern (matching actors/composers):

```python
    # Subtask 4: Writer averages (Bayesian-smoothed)
    writer_avg: dict[str, float] = {}
    if rated_writers:
        title_rating = {t.imdb_id: t.user_rating for t in rated_titles}
        writer_ratings: dict[str, list[int]] = defaultdict(list)
        for imdb_id, writers in rated_writers.items():
            rating = title_rating.get(imdb_id)
            if rating is None:
                continue
            for w in writers:
                writer_ratings[w].append(rating)
        writer_avg = {w: _bayesian_avg(r, global_mean) for w, r in writer_ratings.items()}
```

---

## Post-conditions

After the fix, confirm the call graph is consistent:

```bash
grep -n "rated_writers" app/services/candidates.py app/services/pipeline.py app/services/model.py app/services/features.py
```

Expected: each file has matching references — `candidates.py` builds and returns it,
`pipeline.py` unpacks and passes it, `model.py` accepts and forwards it, `features.py`
accepts and uses it.

Note: `taste_model.pkl` was trained without writer features. It must be retrained
before `writer_taste_score` is non-zero in predictions. **Do not delete the model
file** — flag this to the user so they can retrain at their convenience.

---

## Tests

```bash
uv run ruff check app/
uv run pytest tests/ -q
```

All existing tests must pass. New writer-specific tests are covered in ST-003.

---

## Files Changed

- `app/services/candidates.py`
- `app/services/pipeline.py`
- `app/services/model.py`
- `app/services/features.py`

---

## Commit Message

```
fix: route writer data through pipeline so writer_taste_score is non-zero (ST-001)
```
