---
ticket: "003"
subtask: 4
title: "Show Title Metadata on Dismissed Page"
status: done
effort: low-medium
component: full_stack
depends_on: []
files_modified:
  - app/api/routes.py
  - app/models/schemas.py
  - app/services/dismissed.py
  - app/services/pipeline.py
  - frontend/app/pages/dismissed.vue
  - frontend/app/types/index.ts
  - frontend/app/composables/useApi.ts
files_created: []
---

# SUBTASK 04: Show Title Metadata on Dismissed Page

---

## Objective

Show human-readable title information (name, year, type, genres) on the dismissed page instead of raw IMDB IDs like `tt1375666`.

## Context

The dismissed page (`pages/dismissed.vue`) currently:
- Calls `GET /dismissed` which returns `{ dismissed_ids: ["tt1375666", ...], count: 5 }`
- Renders each ID as a `v-list-item` with the raw ID string as a clickable IMDB link
- Users have no way to remember what `tt1375666` was without clicking through to IMDB

The backend stores dismissed IDs in `data/dismissed.json` as a flat list of strings. Title metadata is available from the candidate cache (`data/cache/imdb_candidates.json`) or from the IMDB datasets in memory (if the pipeline has been run).

## Implementation

### 1. Backend: Create a dismissed title info model

In `schemas.py`, add:

```python
class DismissedTitle(BaseModel):
    """Metadata for a dismissed title."""
    imdb_id: str
    title: str | None = None
    year: int | None = None
    title_type: str | None = None
    genres: list[str] = []
    imdb_url: str | None = None
```

Update `DismissedListResponse`:
```python
class DismissedListResponse(BaseModel):
    dismissed_ids: list[str] = []
    dismissed_titles: list[DismissedTitle] = []
    count: int
```

### 2. Backend: Resolve title metadata for dismissed IDs

In `routes.py`, update the `list_dismissed()` endpoint to look up title metadata. Two strategies (in order of preference):

**Strategy A — Read from candidate cache:** If `data/cache/imdb_candidates.json` exists, load it (or use the in-memory candidates if the pipeline has run) and look up each dismissed ID. This is the fast path.

**Strategy B — Read from IMDB datasets:** If the cache doesn't exist, read `title.basics.tsv.gz` filtered to the dismissed IDs. This is slower but always works after datasets are downloaded.

**Strategy C — Graceful degradation:** If neither source is available, return `DismissedTitle(imdb_id=id)` with all other fields as `None`. The frontend handles this by showing the ID as fallback.

Implementation should be a helper function (e.g., in `dismissed.py` or a new utility):

```python
def get_dismissed_with_metadata() -> list[DismissedTitle]:
    """Return dismissed IDs enriched with title metadata where available."""
    ids = get_dismissed_ids()
    # Try to resolve from pipeline cache first, then fallback to ID-only
    ...
```

### 3. Frontend: Update types

In `types/index.ts`, add:
```typescript
export interface DismissedTitle {
  imdb_id: string
  title: string | null
  year: number | null
  title_type: string | null
  genres: string[]
  imdb_url: string | null
}
```

Update `DismissedListResponse`:
```typescript
export interface DismissedListResponse {
  dismissed_ids: string[]
  dismissed_titles: DismissedTitle[]
  count: number
}
```

### 4. Frontend: Redesign dismissed page

Replace the current minimal `v-list` with richer cards or list items:

```vue
<v-list-item
  v-for="title in dismissedTitles"
  :key="title.imdb_id"
>
  <template #prepend>
    <v-icon>mdi-eye-off</v-icon>
  </template>

  <v-list-item-title>
    <a v-if="title.imdb_url" :href="title.imdb_url" target="_blank" rel="noopener">
      {{ title.title || title.imdb_id }}
    </a>
  </v-list-item-title>
  <v-list-item-subtitle v-if="title.year || title.title_type">
    {{ title.year }} · {{ title.title_type }}
    <v-chip v-for="genre in title.genres.slice(0, 3)" :key="genre" size="x-small" class="ml-1">
      {{ genre }}
    </v-chip>
  </v-list-item-subtitle>

  <template #append>
    <v-btn size="small" variant="text" color="success" prepend-icon="mdi-restore" @click="restore(title.imdb_id)">
      Restore
    </v-btn>
  </template>
</v-list-item>
```

### 5. Frontend: Use dismissed_titles from response

Update the composable and component to use `dismissed_titles` instead of (or alongside) `dismissed_ids`:

```typescript
const dismissedTitles = ref<DismissedTitle[]>([])

async function fetchDismissed() {
  loading.value = true
  const res = await api.getDismissedList()
  dismissedTitles.value = res.dismissed_titles
  loading.value = false
}
```

## Acceptance Criteria

- [x] `GET /dismissed` returns `dismissed_titles` array with title, year, type, genres, and IMDB URL
- [x] Dismissed page shows title name, year, type, and up to 3 genre chips for each entry
- [x] Falls back gracefully to showing IMDB ID when metadata is unavailable
- [x] Restore functionality still works
- [x] Backward compatible — `dismissed_ids` still present in response
- [x] No performance regression — metadata resolution is fast (cache lookup, not dataset parsing)

---

> **On completion:** update your row in [progress.md](progress.md) to `Done`, add any non-obvious decisions to [decisions.md](decisions.md), and verify the Definition of Done checklist in `CLAUDE.md`.
