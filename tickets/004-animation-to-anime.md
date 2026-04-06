---
id: "004"
title: "Replace Animation Category with Anime"
status: done
priority: medium
component: full_stack
files_affected:
  - app/services/recommend.py
  - app/services/candidates.py
  - app/models/schemas.py
  - app/api/routes.py
  - config.yaml
  - frontend/app/pages/index.vue
  - frontend/app/stores/recommendations.ts
  - frontend/app/types/index.ts
---

# TICKET-004: Replace Animation Category with Anime

---

## Summary

The current "animation" category captures all animated titles (Disney, Pixar, Looney Tunes, Studio Ghibli, Demon Slayer) under one label using a single rule: `"Animation" in genres`. The intent of this category is specifically **anime** — Japanese animation. Renaming it and tightening the detection rule makes the category more useful and honest.

This ticket covers:
1. Identifying the right data source to reliably distinguish anime from Western animation
2. Adding an `is_anime` flag to `CandidateTitle` using that source
3. Renaming the "animation" category to "anime" throughout the stack

---

## Why IMDB Data Alone Is Not Reliable

The obvious first instinct is to use `country_code == "JP"` or `language == "Japanese"` (already on `CandidateTitle` from `title.akas`). These signals are **not accurate enough**:

- `country_code` is derived from `isOriginalTitle == "1"` rows in `title.akas`. Many anime titles have no such row, or have a US/XWW region code from a Netflix/Crunchyroll global release being treated as the "original" by IMDB's data.
- `language` suffers the same problem — dubbed or simulcast releases can overwrite the original language row, and many anime have null language fields entirely.
- IMDB genres include `"Animation"` for both anime and Western animation with no further distinction. There is no "Anime" genre tag in the IMDB bulk dataset.

In practice, filtering to JP country or Japanese language would miss a significant fraction of well-known anime and also catch some non-anime Japanese animated films that are not considered anime by fans.

---

## Recommended Data Source: `Fribb/anime-lists`

The [`Fribb/anime-lists`](https://github.com/Fribb/anime-lists) repository maintains a community-curated cross-reference JSON that maps AniDB, AniList, MyAnimeList, TheTVDB, TheMovieDB, and **IMDB IDs** for anime titles. It is updated regularly and available as a raw GitHub download.

**Key file:** `https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-mini.json`

Each entry looks like:
```json
{ "anidb_id": 1, "anilist_id": 1, "mal_id": 1, "imdb_id": "tt0157608", ... }
```

The `imdb_id` field is an IMDB tconst directly usable as `CandidateTitle.imdb_id`. Building a set of these IDs gives a **definitive whitelist** of known anime titles. Any `CandidateTitle` whose `imdb_id` appears in the set is anime — no genre or country guessing required.

**Practical properties:**
- File size: ~1–2 MB JSON — trivial to download and cache alongside IMDB datasets
- No authentication required
- Covers movies and TV series (both `imdb_id` and series-level IDs)
- Updated by the community as new anime are released
- Not every entry has an `imdb_id` (some obscure titles are AniDB-only) — these are anime that likely don't appear in our IMDB candidate pool anyway

**Fallback for titles not in the whitelist:**
A secondary heuristic (`country_code == "JP"` OR `language == "Japanese"`) AND `"Animation" in genres` can catch anime released after the list was last cached, but this is a best-effort fallback, not the primary signal.

---

## Subtasks

All subtasks are in the [004-animation-to-anime/](004-animation-to-anime/) directory:

| # | Subtask | Effort | Component | Dependencies |
|---|---------|--------|-----------|--------------|
| 1 | [Download anime whitelist + add `is_anime` to candidates](004-animation-to-anime/ST-001-is-anime-flag.md) | Low-Medium | Backend | None |
| 2 | [Rename animation → anime in config + backend](004-animation-to-anime/ST-002-rename-backend.md) | Low | Backend | Subtask 1 |
| 3 | [Rename animation → anime in frontend](004-animation-to-anime/ST-003-rename-frontend.md) | Low | Frontend | Subtask 2 |

### Execution Order

```
Subtask 1 (download whitelist, add is_anime to CandidateTitle)
  → Subtask 2 (backend rename — uses candidate.is_anime)
    → Subtask 3 (frontend rename — depends on API field names)
```

---

## Acceptance Criteria

- [ ] The `Fribb/anime-lists` JSON is downloaded to `data/datasets/` alongside IMDB files and cached as a set of IMDB IDs in memory
- [ ] `CandidateTitle.is_anime` is `True` for titles in the whitelist, with a JP/Japanese fallback for titles not in the list
- [ ] The "animation" category is renamed to "anime" in `config.yaml`, `schemas.py`, API routes, and frontend
- [ ] `GET /api/v1/recommendations/anime` replaces `/recommendations/animation`
- [ ] `RecommendationResponse.anime` replaces `.animation`
- [ ] `top_n_anime` replaces `top_n_animation` in config and `RecommendationFilters`
- [ ] Non-Japanese animation (Pixar, Disney, etc.) no longer appears in the anime category
- [ ] The candidate cache is invalidated (new `is_anime` field on `CandidateTitle`)
- [ ] Lint passes and smoke tests pass
