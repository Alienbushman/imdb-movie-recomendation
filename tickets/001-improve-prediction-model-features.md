---
id: "001"
title: "Improve Prediction Model with Additional Features and Data Sources"
status: done
priority: high
component: backend
files_affected:
  - app/services/features.py
  - app/services/model.py
  - app/services/candidates.py
  - app/services/recommend.py
  - app/models/schemas.py
  - config.yaml
---

# TICKET-001: Improve Prediction Model with Additional Features and Data Sources

---

## Summary

The current LightGBM recommendation model uses 32 features (23 binary genre flags + 9 derived features). Analysis of the codebase reveals multiple opportunities to improve prediction accuracy by:

1. Using data already loaded but not fed to the model (language, title type, richer taste signals)
2. Engineering new features from existing data (genre affinity, interaction pairs, counts)
3. Incorporating new external data sources (IMDB writers, TMDB keywords, RT/Metacritic scores)

## Current Feature Set (32 features)

- **23 genre flags** - binary indicators for each IMDB genre (Action, Adventure, Animation, etc.)
- `imdb_rating` - IMDB average rating
- `runtime_mins` - runtime in minutes
- `year` - release year
- `num_votes` - number of IMDB votes
- `decade` - decade derived from year (e.g., 2010)
- `rating_vote_ratio` - `imdb_rating / log1p(num_votes)`
- `is_animation` - boolean flag
- `director_taste_score` - max average user rating across titles by the same director
- `has_known_director` - boolean
- `actor_taste_score` - max average user rating across titles by the same actor
- `has_known_actor` - boolean

## Current Data Sources

Downloaded from IMDB bulk datasets (defined in `candidates.py:14-20`):
- `title.basics.tsv.gz` - title, type, year, runtime, genres
- `title.ratings.tsv.gz` - average rating, vote count
- `title.principals.tsv.gz` - actors, directors (filtered to actor/actress/director only)
- `title.akas.tsv.gz` - language/region data
- `name.basics.tsv.gz` - person name resolution

**NOT downloaded but available from IMDB:**
- `title.crew.tsv.gz` - writers and directors (writers not currently used)
- `title.episode.tsv.gz` - episode-level info for series

---

## Subtasks

### SUBTASK 1: Add Genre Affinity Scores (User Average Rating per Genre)
**Effort:** Low | **Impact:** High
**Files:** `app/services/features.py`, `app/models/schemas.py`

**Context:** Currently genre features are binary flags (0/1). The user's actual affinity for each genre — computed as their average rating of titles in that genre — is a much stronger signal. A user who averages 8.5 on Sci-Fi titles vs 5.2 on Romance titles carries information that binary flags cannot express.

**Implementation:**
1. In `build_taste_profile()` (`features.py:38-65`), compute `genre_avg: dict[str, float]` — the user's mean rating per genre from their watchlist.
2. Add `genre_avg` field to the `TasteProfile` schema in `schemas.py`.
3. In `_build_genre_flags()` (`features.py:68-71`) or a new `_compute_genre_affinity()` function, produce features like `genre_action_affinity = user's avg rating for Action titles` (0.0 if no rated titles in that genre).
4. Add these 23 affinity features to `FeatureVector`, `features_to_dataframe()`, and `feature_vector_to_array()`.
5. Ensure the model trains and predicts with the expanded feature set.

**Acceptance criteria:**
- `TasteProfile` contains `genre_avg` dict
- 23 new `genre_X_affinity` features appear in the feature matrix alongside existing binary genre flags
- Model trains successfully with the new features
- Existing tests (if any) pass; new unit tests cover `build_taste_profile` genre averaging

---

### SUBTASK 2: Enrich Director/Actor Taste Features (Count + Mean, Not Just Max)
**Effort:** Low | **Impact:** Medium-High
**Files:** `app/services/features.py`, `app/models/schemas.py`

**Context:** `_compute_taste_features()` (`features.py:86-113`) currently computes only the `max` taste score for directors and actors. This loses important information:
- **Frequency (count):** A director with 5 rated titles at avg 7.5 is a much stronger signal than one with 1 title at 7.5.
- **Mean vs max:** Max captures "best case" but mean captures consistency. A director whose titles average 8.0 vs one with one 9.0 and three 5.0s are very different signals.

**Implementation:**
1. In `_compute_taste_features()`, compute and return four additional fields:
   - `director_taste_count`: number of user-rated titles by the candidate's director(s)
   - `director_taste_mean`: mean of user ratings for the candidate's director(s)
   - `actor_taste_count`: number of user-rated titles featuring the candidate's actor(s)
   - `actor_taste_mean`: mean of user ratings for the candidate's actor(s)
2. Add these to `FeatureVector` schema.
3. Include in `features_to_dataframe()` and `feature_vector_to_array()`.

**Acceptance criteria:**
- 4 new features in the feature vector: `director_taste_count`, `director_taste_mean`, `actor_taste_count`, `actor_taste_mean`
- For directors/actors not in the taste profile, count = 0, mean = 0.0
- Model trains and predicts with expanded features

---

### SUBTASK 3: Add Language as a Model Feature
**Effort:** Low | **Impact:** Medium
**Files:** `app/services/features.py`, `app/services/candidates.py`, `app/models/schemas.py`

**Context:** Language is loaded from `title.akas.tsv.gz` in `_load_language_data()` (`candidates.py:329-386`) and stored on `CandidateTitle.language`, but it's only used for runtime filtering in `recommend.py`. It is never passed to the model as a feature. Users often have strong language preferences that go beyond explicit filtering (e.g., consistently rating Korean or French films higher).

**Implementation:**
1. In `build_taste_profile()`, compute `language_avg: dict[str, float]` — the user's mean rating per language. This requires language info on `RatedTitle`, which currently doesn't have it. Either:
   - (a) Enrich `RatedTitle` with language during ingest by cross-referencing the akas dataset, OR
   - (b) Compute language affinity from candidate-side data only (simpler: one-hot top ~15 languages as features, let the model learn from IMDB-wide patterns rather than user-specific).
2. Option (b) is simpler: add `language_X` binary features for the top 15 languages (English, French, German, Japanese, Korean, Spanish, Italian, Hindi, Chinese, Portuguese, Swedish, Danish, Turkish, Russian, Other).
3. Add to `FeatureVector`, `features_to_dataframe()`, `feature_vector_to_array()`.
4. For `RatedTitle` (training data), language is not in the CSV export — so either cross-reference with akas at training time, or only use language features during candidate scoring (set to 0 during training). Option (a) with cross-reference is preferred for model quality.

**Acceptance criteria:**
- Language features appear in the feature matrix
- Model handles missing language gracefully (defaults to 0 / "Unknown")
- No regression in existing recommendation quality

---

### SUBTASK 4: Add Writer Taste Features via title.crew.tsv.gz
**Effort:** Medium | **Impact:** Medium-High
**Files:** `app/services/candidates.py`, `app/services/features.py`, `app/models/schemas.py`, `config.yaml`

**Context:** IMDB publishes `title.crew.tsv.gz` which contains writers for every title. Writers are a strong taste signal (e.g., Aaron Sorkin, Charlie Kaufman, Quentin Tarantino as writer). This file is not currently downloaded or used.

**Implementation:**
1. Add `"title.crew.tsv.gz": "https://datasets.imdbws.com/title.crew.tsv.gz"` to `DATASET_URLS` in `candidates.py:14`.
2. Add `title_crew: "data/datasets/title.crew.tsv.gz"` to `imdb_datasets` in `config.yaml` and the corresponding `ImdbDatasetSettings` in `config.py`.
3. Create `_load_writer_data(title_ids: set[str]) -> dict[str, list[str]]` in `candidates.py`, similar to `_load_person_data()`. The crew file has `tconst`, `directors`, `writers` columns where writers is a comma-separated list of `nconst` IDs. Resolve names using the existing `name.basics` dataset.
4. Add `writers: list[str]` field to `CandidateTitle` and `RatedTitle` schemas.
5. In `build_taste_profile()`, compute `writer_avg: dict[str, float]` analogous to `director_avg`.
6. In `_compute_taste_features()`, compute `writer_taste_score`, `has_known_writer`, `writer_taste_count`, `writer_taste_mean`.
7. Add these 4 features to `FeatureVector` and the dataframe builders.
8. Include writer data in the candidate cache JSON schema. Invalidate stale caches missing the `writers` field.

**Acceptance criteria:**
- `title.crew.tsv.gz` is downloaded with other datasets
- Writer names resolved and stored on candidate/rated title objects
- 4 writer taste features in the model
- Cache invalidation handles the schema change
- Existing functionality unaffected when writer data is unavailable (graceful fallback)

---

### SUBTASK 5: Add Title Type as a Model Feature
**Effort:** Low | **Impact:** Low-Medium
**Files:** `app/services/features.py`, `app/models/schemas.py`

**Context:** `title_type` (movie, tvSeries, tvMiniSeries, tvMovie) exists on every title but is only used for post-scoring categorization in `recommend.py`. It is never fed to the model. Users may systematically rate certain types higher.

**Implementation:**
1. In `rated_title_to_features()` and `candidate_to_features()`, add one-hot features for each title type: `type_movie`, `type_tvseries`, `type_tvminiseries`, `type_tvmovie`.
2. Add these to `FeatureVector` (as a `type_flags: dict[str, int]` similar to `genre_flags`), and include in `features_to_dataframe()` / `feature_vector_to_array()`.

**Acceptance criteria:**
- 4 new binary features for title type in the feature matrix
- Model trains and predicts with expanded features

---

### SUBTASK 6: Add Genre Interaction Pair Features
**Effort:** Low | **Impact:** Medium
**Files:** `app/services/features.py`, `app/models/schemas.py`

**Context:** The model only has additive genre flags. But "Sci-Fi + Drama" vs "Sci-Fi + Action" may appeal very differently to a user. LightGBM can learn some interactions via tree splits, but explicit interaction features help, especially with limited tree depth (max_depth=6).

**Implementation:**
1. Identify the top ~15 most common genre pairs in the user's watchlist (e.g., Action+Thriller, Sci-Fi+Action, Drama+Romance).
2. Add binary interaction features for these pairs: `genre_pair_action_thriller`, etc.
3. Compute them in a new `_build_genre_interactions()` function in `features.py`.
4. Add to `FeatureVector`, dataframe builders.
5. Make the list of interaction pairs configurable or auto-derived from the user's watchlist.

**Acceptance criteria:**
- Top genre pairs identified from user's rated titles
- Binary interaction features added to feature matrix
- Auto-derived (not hardcoded) pair selection

---

### SUBTASK 7: Add Popularity Tier and Title Age Features
**Effort:** Low | **Impact:** Low-Medium
**Files:** `app/services/features.py`

**Context:** `num_votes` has a huge range (10k to 2M+) making it hard for the model to use effectively. `decade` loses granularity within a 10-year window. Two simple derived features would help.

**Implementation:**
1. Add `popularity_tier` feature: bucket `num_votes` into tiers (e.g., 0=indie <25k, 1=niche 25k-100k, 2=mainstream 100k-500k, 3=blockbuster 500k+). Thresholds configurable in `config.yaml`.
2. Add `title_age` feature: `current_year - year`. More granular than decade and captures recency preference.
3. Add `log_votes` feature: `log10(num_votes)` for a smoother numerical representation than raw votes.
4. Add to `_compute_derived_features()`, `FeatureVector`, and dataframe builders.

**Acceptance criteria:**
- 3 new features: `popularity_tier`, `title_age`, `log_votes`
- Popularity tier thresholds configurable in config.yaml
- Existing `decade`, `num_votes`, `rating_vote_ratio` features retained (let the model decide importance)

---

### SUBTASK 8: Expand Principals to Include Composers and Cinematographers
**Effort:** Low | **Impact:** Low-Medium
**Files:** `app/services/candidates.py`, `app/services/features.py`, `app/models/schemas.py`

**Context:** `_load_person_data()` (`candidates.py:301`) filters principals to only `["actor", "actress", "director"]`. Composers (Hans Zimmer, Ennio Morricone) and cinematographers (Roger Deakins) are real taste signals for film enthusiasts. The data is already downloaded — it just needs to be extracted.

**Implementation:**
1. In `_load_person_data()`, expand the category filter to include `"composer"` and `"cinematographer"`.
2. Build `composers_by_title` and `cinematographers_by_title` dicts, analogous to `actors_by_title`.
3. Add `composers: list[str]` and `cinematographers: list[str]` to `CandidateTitle` schema.
4. In `build_taste_profile()`, compute `composer_avg` and `cinematographer_avg`.
5. In `_compute_taste_features()`, compute `composer_taste_score`, `has_known_composer`, `cinematographer_taste_score`, `has_known_cinematographer`.
6. Add these 4 features to `FeatureVector` and dataframe builders.
7. Update cache invalidation for new fields.

**Acceptance criteria:**
- Composer and cinematographer data extracted from principals
- 4 new taste features in the model
- Cache invalidation handles schema change
- Graceful fallback when data is missing

---

### SUBTASK 9: Integrate TMDB API for Keywords, Budget, and Revenue
**Effort:** Medium-High | **Impact:** High
**Files:** `app/services/candidates.py` (new TMDB module), `app/services/features.py`, `app/models/schemas.py`, `config.yaml`

**Context:** TMDB (The Movie Database) provides a free API with rich metadata not available from IMDB bulk files: **keywords/tags** (e.g., "time travel", "heist", "based on true story"), **budget**, **revenue**, and **production companies**. Keywords are particularly valuable — they capture thematic elements that genres miss entirely.

**Implementation:**
1. Create `app/services/tmdb.py` for TMDB API integration.
2. Add TMDB API key to config (via environment variable `TMDB_API_KEY`).
3. Map IMDB IDs to TMDB IDs using TMDB's `/find/{imdb_id}?external_source=imdb_id` endpoint.
4. Fetch keywords for each title via `/movie/{id}/keywords` or `/tv/{id}/keywords`.
5. Cache TMDB data locally (JSON file in `data/cache/tmdb_metadata.json`) to avoid repeated API calls.
6. Compute keyword features:
   - Build user keyword affinity from rated titles (avg rating per keyword)
   - For candidates: `keyword_affinity_score` = mean of user affinities for the candidate's keywords
   - `has_known_keywords` boolean
   - `keyword_overlap_count` = number of keywords shared with user's top-rated titles
7. Optional: add `budget_tier` and `revenue_tier` as ordinal features.
8. Add to `FeatureVector` and dataframe builders.
9. Respect TMDB API rate limits (40 requests/10 seconds on free tier). Use batch processing with delays.

**Acceptance criteria:**
- TMDB API integration with caching
- Keyword affinity features in the model
- Rate limiting respected
- Graceful degradation when API key is not configured or API is unavailable
- Documentation for obtaining and configuring TMDB API key

---

### SUBTASK 10: Integrate OMDb API for Rotten Tomatoes and Metacritic Scores
**Effort:** Medium | **Impact:** Medium
**Files:** new `app/services/omdb.py`, `app/services/features.py`, `app/models/schemas.py`, `config.yaml`

**Context:** The OMDb API provides Rotten Tomatoes and Metacritic scores alongside IMDB data. Adding critic consensus scores gives the model a second perspective. The *gap* between IMDB user rating and critic scores is also informative — it captures "audience vs critic disagreement" which correlates with certain user taste profiles.

**Implementation:**
1. Create `app/services/omdb.py` for OMDb API integration.
2. Add OMDb API key to config (via environment variable `OMDB_API_KEY`). Free tier: 1000 requests/day.
3. Fetch RT and Metacritic scores via `http://www.omdbapi.com/?i={imdb_id}&apikey={key}`.
4. Cache locally in `data/cache/omdb_scores.json`.
5. Add features:
   - `rt_score` (Rotten Tomatoes %, normalized to 0-10)
   - `metacritic_score` (normalized to 0-10)
   - `imdb_rt_gap` = `imdb_rating - rt_score` (audience vs critic divergence)
   - `imdb_metacritic_gap` = `imdb_rating - metacritic_score`
6. Handle missing scores (many titles lack RT/Metacritic data) — default to 0 or median.
7. Add to `FeatureVector` and dataframe builders.

**Acceptance criteria:**
- OMDb API integration with caching
- 4 new score features in the model
- Missing scores handled gracefully
- Rate limiting respected (1000/day free tier)
- Documentation for obtaining and configuring OMDb API key

---

## Implementation Order

The subtasks are ordered by priority (effort vs impact ratio):

| Order | Subtask | Effort | Impact | Dependencies |
|-------|---------|--------|--------|--------------|
| 1 | SUBTASK 1: Genre affinity scores | Low | High | None |
| 2 | SUBTASK 2: Director/actor count + mean | Low | Med-High | None |
| 3 | SUBTASK 3: Language as feature | Low | Medium | None |
| 4 | SUBTASK 5: Title type as feature | Low | Low-Med | None |
| 5 | SUBTASK 7: Popularity tier + title age | Low | Low-Med | None |
| 6 | SUBTASK 6: Genre interaction pairs | Low | Medium | SUBTASK 1 (uses genre affinity data) |
| 7 | SUBTASK 4: Writer taste features | Medium | Med-High | None |
| 8 | SUBTASK 8: Composer/cinematographer | Low | Low-Med | None |
| 9 | SUBTASK 9: TMDB keywords/budget | Med-High | High | None |
| 10 | SUBTASK 10: OMDb RT/Metacritic | Medium | Medium | None |

Subtasks 1-5 can all be executed in parallel (no dependencies between them).
Subtask 6 depends on subtask 1 (needs genre affinity data for pair selection).
Subtasks 7-10 are independent of each other and of 1-5.

---

## Notes

- Each subtask should include unit tests for the new features.
- After implementing a batch of subtasks, retrain the model and compare MAE against the baseline to validate improvement.
- The candidate cache (`data/cache/imdb_candidates.json`) schema changes with subtasks 4 and 8 — cache invalidation must handle the new fields.
- Feature count will grow from 32 to approximately 80-100. Monitor for overfitting given the typical watchlist size (200-1000 rated titles). LightGBM handles this well with proper regularization but `min_child_samples` in `config.yaml` may need adjustment.
