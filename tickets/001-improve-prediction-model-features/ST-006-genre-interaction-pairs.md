---
ticket: "001"
subtask: 6
title: "Add Genre Interaction Pair Features"
status: done
effort: low
component: backend
depends_on: [1]
files_modified:
  - app/services/features.py
  - app/models/schemas.py
files_created: []
---

# SUBTASK 06: Add Genre Interaction Pair Features

---

## Objective

Add binary interaction features for the most common genre combinations in the user's watchlist, helping the model distinguish "Sci-Fi + Drama" from "Sci-Fi + Action" without relying solely on tree splits.

## Context

The model currently only has additive genre flags. But "Sci-Fi + Drama" vs "Sci-Fi + Action" may appeal very differently to a user. LightGBM can learn some interactions via tree splits, but explicit interaction features help, especially with limited tree depth (`max_depth=6`).

The list of interaction pairs must be **auto-derived** from the user's rated titles — not hardcoded — so it adapts to each user's watchlist.

## Implementation

### 1. Compute top genre pairs in `build_taste_profile()`

After computing `genre_avg` (SUBTASK 01), compute the most frequent genre pairs from the user's rated titles:

```python
from itertools import combinations
from collections import Counter

pair_counts = Counter()
for title in rated_titles:
    genres = sorted(title.genres)  # sort for canonical order
    for a, b in combinations(genres, 2):
        pair_counts[(a, b)] += 1

top_pairs = [pair for pair, _ in pair_counts.most_common(15)]
```

Store `top_genre_pairs: list[tuple[str, str]]` on `TasteProfile`.

### 2. Add `top_genre_pairs` to `TasteProfile` schema

Add `top_genre_pairs: list[tuple[str, str]]` to `TasteProfile` in `schemas.py`.

### 3. Add a `_build_genre_interactions()` function

```python
def _build_genre_interactions(
    genre_flags: dict[str, int],
    top_pairs: list[tuple[str, str]],
) -> dict[str, int]:
    result = {}
    for a, b in top_pairs:
        key = f"genre_pair_{a.lower()}_{b.lower()}"
        result[key] = genre_flags.get(a, 0) & genre_flags.get(b, 0)
    return result
```

### 4. Add `genre_pair_flags` to `FeatureVector`

Add `genre_pair_flags: dict[str, int]` to `FeatureVector`. Include in `features_to_dataframe()` and `feature_vector_to_array()`.

**Important:** The column names are dynamic (depend on the user's top pairs). The feature matrix must be built consistently between training and inference — use the pairs stored on the trained model or pass them via `TasteProfile`.

## Acceptance Criteria

- [x] Top 15 genre pairs auto-derived from the user's rated titles (not hardcoded)
- [x] `TasteProfile.top_genre_pairs` stores the derived pairs
- [x] Binary interaction features added to feature matrix with keys like `genre_pair_action_thriller`
- [x] Feature columns are consistent between training and inference (same pairs used for both)
- [x] Model trains and predicts with the expanded features

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
