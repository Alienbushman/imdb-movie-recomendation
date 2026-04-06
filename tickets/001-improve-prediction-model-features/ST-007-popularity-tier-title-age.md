---
ticket: "001"
subtask: 7
title: "Add Popularity Tier, Title Age, and Log Votes Features"
status: done
effort: low
component: backend
depends_on: []
files_modified:
  - app/services/features.py
  - config.yaml
files_created: []
---

# SUBTASK 07: Add Popularity Tier, Title Age, and Log Votes Features

---

## Objective

Add three derived numerical features that make existing raw features more model-friendly: a bucketed popularity tier, a granular title age, and a log-transformed vote count.

## Context

- `num_votes` has a huge range (10k to 2M+) making it hard for the model to use linearly. Bucketing into tiers creates a cleaner ordinal signal.
- `decade` loses granularity within a 10-year window. `title_age = current_year - year` is more precise and captures recency preference directly.
- `log_votes = log10(num_votes)` provides a smoother numerical representation than raw votes and is more stable for regression.

The existing `decade`, `num_votes`, and `rating_vote_ratio` features are **retained** — let the model decide feature importance.

New features are computed in `_compute_derived_features()` in `features.py`.

## Implementation

### 1. Add popularity tier thresholds to `config.yaml`

```yaml
model:
  popularity_tiers:
    indie: 25000       # < 25k votes → tier 0
    niche: 100000      # 25k–100k → tier 1
    mainstream: 500000 # 100k–500k → tier 2
                       # 500k+ → tier 3 (blockbuster)
```

### 2. Compute the three features in `_compute_derived_features()`

```python
import math
from datetime import date

CURRENT_YEAR = date.today().year

def _compute_popularity_tier(num_votes: int, tiers: dict) -> int:
    if num_votes < tiers["indie"]:
        return 0
    elif num_votes < tiers["niche"]:
        return 1
    elif num_votes < tiers["mainstream"]:
        return 2
    return 3

# In _compute_derived_features():
popularity_tier = _compute_popularity_tier(num_votes, settings.model.popularity_tiers)
title_age = CURRENT_YEAR - year if year else 0
log_votes = math.log10(max(num_votes, 1))
```

### 3. Add to `FeatureVector`

Add `popularity_tier: int`, `title_age: int`, and `log_votes: float` to `FeatureVector` in `schemas.py`.

### 4. Include in dataframe builders

Add the three fields to `features_to_dataframe()` and `feature_vector_to_array()`.

## Acceptance Criteria

- [x] 3 new features: `popularity_tier` (int 0–3), `title_age` (int), `log_votes` (float)
- [x] Popularity tier thresholds are configurable in `config.yaml`
- [x] `title_age` and `log_votes` handle missing/zero values gracefully (no division by zero, no log(0))
- [x] Existing `decade`, `num_votes`, `rating_vote_ratio` features retained
- [x] Model trains and predicts with the expanded feature set

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
