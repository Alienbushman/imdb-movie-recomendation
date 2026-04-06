# TICKET-001 Decisions Log

Record non-obvious implementation choices here as subtasks are completed. Future agents need to understand *why* the code is shaped a certain way — not just what changed.

## Format

```
### [Subtask N — Title] Short description of the decision
**Context:** What was unclear or had multiple valid options.
**Decision:** What was chosen.
**Reason:** Why this option over the alternatives.
```

## Decisions

### [Subtask 09 + 10] TMDB and OMDb are opt-in, not required
**Context:** Both APIs require free-tier API keys. Making them mandatory would break first-run setup for most users.
**Decision:** All TMDB/OMDb fetching is gated on the presence of `TMDB_API_KEY` / `OMDB_API_KEY` env vars. Features default to `0.0` / `0` when the key is absent.
**Reason:** Graceful degradation — the model still trains and predicts without these keys, just with less signal. One info log emitted per missing key per run.

### [Subtask 09] TMDB metadata cached separately from candidate JSON
**Context:** TMDB fetches are slow (rate-limited to 40 req/10s). Re-fetching on every candidate rebuild would be prohibitive.
**Decision:** Metadata written to `data/cache/tmdb_metadata.json`, keyed by IMDB ID. Already-cached IDs are skipped on subsequent runs.
**Reason:** TMDB data is stable — it rarely changes. A separate cache lets us rebuild `imdb_candidates.json` without re-hitting the TMDB API.

### [Subtask 10] RT and Metacritic scores normalised to 0–10 scale
**Context:** RT returns `"94%"`, Metacritic returns `"88/100"`. The model expects numeric features on a common scale.
**Decision:** RT divided by 10, Metacritic divided by 10. Both stored as floats.
**Reason:** Aligns with the IMDB rating scale (0–10), making `imdb_rt_gap` and `imdb_metacritic_gap` directly interpretable as rating deltas.

### [Subtask 10] RT/Metacritic gap features default to 0.0 when either score is missing
**Context:** During training, rated titles come from the IMDB CSV which contains no RT/Metacritic data — so these features are always 0.0 in the training set.
**Decision:** Gap features default to 0.0 when either score is absent. The model learns to treat 0 gap as "no critic data available" rather than "perfect agreement".
**Reason:** Avoids imputation complexity. LightGBM handles uninformative zero features gracefully. The `has_known_keywords` flag (TMDB) serves a similar disambiguation role.

### [Subtask 06] Genre pairs auto-derived from watchlist, not hardcoded
**Context:** Hardcoded pairs would be wrong for most users and require maintenance.
**Decision:** Top-N pairs computed from the user's own rated titles via `Counter` over `combinations(genres, 2)`. N configurable via `features.max_genre_pairs` in `config.yaml`.
**Reason:** Self-adapting — a user who watches a lot of "Sci-Fi + Drama" gets that pair as a feature; "Sci-Fi + Action" gets it for action fans. Consistent between training and inference via `TasteProfile.top_genre_pairs`.

### [Subtask 04] Writers require a separate dataset download
**Context:** `title.principals.tsv.gz` doesn't include writers. Writer credits are only in `title.crew.tsv.gz`.
**Decision:** Added `title.crew.tsv.gz` to the download list. Writer features default to `[]` / score 0 if the file hasn't been downloaded.
**Reason:** Maintains backwards compatibility — existing installs without the crew file keep working, just without writer features.

### [Subtask 08] Composers and cinematographers added via principals category filter
**Context:** IMDB principals uses a `category` field (`"composer"`, `"cinematographer"`). The existing principals loading already filters by category.
**Decision:** Extended the category filter list rather than adding a separate join. `composers` and `cinematographers` lists added to `CandidateTitle` alongside `directors` and `actors`.
**Reason:** Minimal data pipeline change; reuses the existing name-lookup infrastructure built for directors/actors.
