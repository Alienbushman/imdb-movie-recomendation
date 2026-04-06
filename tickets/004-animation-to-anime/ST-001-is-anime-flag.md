---
ticket: "004"
subtask: 1
title: "Download Anime Whitelist + Add is_anime to CandidateTitle"
status: done
effort: low-medium
component: backend
depends_on: []
files_modified:
  - app/models/schemas.py
  - app/services/candidates.py
  - app/services/features.py
  - config.yaml
files_created: []
---

# SUBTASK 004-01: Download Anime Whitelist + Add `is_anime` to CandidateTitle

---

## Context

IMDB's `country_code` and `language` fields (derived from `title.akas`) are too unreliable to identify anime — many titles have null or incorrect values due to how IMDB records dubbed/simulcast releases. The correct approach is to use the [`Fribb/anime-lists`](https://github.com/Fribb/anime-lists) cross-reference, which maps anime AniDB/MAL/AniList IDs directly to IMDB tconst values.

The whitelist download belongs alongside the other IMDB dataset downloads in `candidates.py`.

---

## Implementation

### 1. `config.yaml` — add whitelist URL to `imdb_datasets`

```yaml
imdb_datasets:
  ...
  anime_list: "data/datasets/anime-list-mini.json"
  anime_list_url: "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-mini.json"
```

### 2. `app/services/candidates.py` — download and load whitelist

**Add to `DATASET_URLS`** (or handle separately since it's JSON not gzip):

```python
ANIME_LIST_URL = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-mini.json"
```

**Add a `download_anime_list()` helper** (called from `download_datasets()`):

```python
def _download_anime_list() -> None:
    dest = _dataset_dir() / "anime-list-mini.json"
    if dest.exists():
        logger.info("Anime list already exists: %s", dest)
        return
    logger.info("Downloading anime list from Fribb/anime-lists ...")
    subprocess.run(["curl", "-L", "-o", str(dest), ANIME_LIST_URL], check=True)
    logger.info("Downloaded anime list (%d bytes)", dest.stat().st_size)
```

Call `_download_anime_list()` from `download_datasets()`.

**Add a `_load_anime_ids()` helper** that returns a `set[str]` of IMDB tconst values:

```python
def _load_anime_ids() -> set[str]:
    path = _dataset_dir() / "anime-list-mini.json"
    if not path.exists():
        logger.warning("Anime list not found — is_anime will fall back to country/language heuristic")
        return set()
    with open(path) as f:
        entries = json.load(f)
    ids = {entry["imdb_id"] for entry in entries if entry.get("imdb_id")}
    logger.info("Loaded %d anime IMDB IDs from whitelist", len(ids))
    return ids
```

**In `load_candidates_from_datasets()`**, load the anime ID set before building candidates:

```python
anime_ids = _load_anime_ids()
```

Then in the candidate construction loop, compute `is_anime`:

```python
tconst = row["tconst"]

# Primary: whitelist lookup
is_anime = tconst in anime_ids
# Fallback: JP country/Japanese language + Animation genre (for titles not yet in whitelist)
if not is_anime and "Animation" in genres:
    is_anime = (
        country_by_title.get(tconst) == "JP"
        or lang_by_title.get(tconst) == "Japanese"
    )

candidates.append(CandidateTitle(..., is_anime=is_anime))
```

### 3. `app/models/schemas.py` — add field to `CandidateTitle`

```python
class CandidateTitle(BaseModel):
    ...
    cinematographers: list[str] = []
    is_anime: bool = False
```

### 4. `app/services/features.py` — rename `is_animation` to `is_anime`

- In `FeatureVector`: rename `is_animation: bool = False` → `is_anime: bool = False`
- In `candidate_to_features()`: set `is_anime=candidate.is_anime` (instead of deriving from genres)
- In `features_to_dataframe()`: column name `"is_animation"` → `"is_anime"`
- In `feature_vector_to_array()`: same rename in the ordered list
- In `recommend.py:196`: update explanation string from `"Matches your animation interest"` → `"Matches your anime interest"`

> **Gotcha:** Renaming `is_animation` in `FeatureVector` changes the feature array column order used during training and inference. Delete `data/taste_model.pkl` and retrain.

---

## Cache Invalidation

After implementing this subtask, delete:
- `data/cache/imdb_candidates.json` — new `is_anime` field not present in cached entries
- `data/taste_model.pkl` — feature column renamed

---

## Acceptance Criteria

- [x] `data/datasets/anime-list-mini.json` is downloaded by `download_datasets()` if not present
- [x] `_load_anime_ids()` returns a set of IMDB tconst strings
- [x] `CandidateTitle.is_anime` is `True` for titles in the whitelist (e.g. `tt0988982` — Gurren Lagann)
- [x] `CandidateTitle.is_anime` is `False` for non-anime animated titles (e.g. `tt0910970` — WALL-E)
- [x] `FeatureVector.is_animation` is renamed to `is_anime` throughout `features.py` and `recommend.py`
- [x] `uv run ruff check app/` passes
- [x] `uv run pytest tests/ -q` passes
