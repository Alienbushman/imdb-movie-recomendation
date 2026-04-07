# Agent Instructions — Ticket 015

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Open** — Ready for execution.

---

## Goal

Fix five correctness and quality issues identified in a codebase audit. No new features.
All changes are surgical — minimal diff, maximum correctness.

---

## Subtask Order

```
ST-001  ← fix writer taste features (no deps)
ST-002  ← align min_vote_count default (no deps, parallel with ST-001)
ST-004  ← CORS env var (no deps, parallel with ST-001/ST-002)
ST-005  ← feature array assertion (no deps, parallel with ST-001/ST-002)
ST-003  ← candidates tests (depends on ST-001 — tests writer lookup path)
```

ST-001, ST-002, ST-004, and ST-005 have no dependencies and can run in any order.
ST-003 depends on ST-001 so that writer-related tests can assert correct behaviour.

---

## Ticket-Specific Context

### The writer bug in detail

`build_taste_profile()` in `features.py` uses two different patterns for crew members:

**Broken pattern (writers)** — reads directly from `RatedTitle.writers`, which is
always `[]` because the IMDB CSV does not include a writers column:

```python
writer_ratings: dict[str, list[int]] = defaultdict(list)
for t in rated_titles:
    for w in t.writers:          # always empty
        writer_ratings[w].append(t.user_rating)
writer_avg = {...}
```

**Correct pattern (actors, composers, cinematographers)** — receives a pre-built
lookup dict `rated_actors: dict[str, list[str]]` (tconst → name list) that was
built from `title.principals.tsv.gz` by `load_candidates_from_datasets()`:

```python
if rated_actors:
    title_rating = {t.imdb_id: t.user_rating for t in rated_titles}
    for imdb_id, actors in rated_actors.items():
        rating = title_rating.get(imdb_id)
        for a in actors:
            actor_ratings[a].append(rating)
```

Writers need to be migrated to the correct pattern: build `rated_writers` in
`candidates.py` (writers data is already loaded there from `title.crew.tsv.gz`),
return it alongside `rated_actors`, and pass it through the pipeline.

### Cache and model behaviour after ST-001

After fixing the writer features, `taste_model.pkl` must be retrained before
writer scores are meaningful. The existing model was trained with all-zero writer
features. **Do not delete `taste_model.pkl` or the scored DB** — the protocol
requires asking the user first. The subtask will instruct the agent to note this
in post-conditions and let the user decide when to retrain.

### ST-003 test scope

`tests/test_candidates.py` should use small synthetic TSV fixtures (in-memory
StringIO or tmp_path), not the real ~1 GB IMDB dataset files. The goal is to cover:
- The join logic (basics + ratings merge)
- Writer lookup (the key fix from ST-001)
- Anime detection (whitelist-based)

Full integration tests that require real files are out of scope.

### CORS change (ST-004)

The env var should be `CORS_ORIGINS`, a comma-separated list of origins. Parse it
in `app/main.py` at startup. The Docker default (no env set) should behave
identically to today — `localhost:3000` and `localhost:9137`.

### Feature array assertion (ST-005)

The assertion goes in `feature_vector_to_array()` immediately after the `row` dict
is fully built and before the `np.array` return. It should fire if any name in
`feature_names` is missing from `row`.
