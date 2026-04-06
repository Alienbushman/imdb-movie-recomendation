---
id: ST-006
ticket: "010"
title: "Define CardDisplayItem Union Type for RecommendationCard"
priority: Low
risk: low
status: Open
dependencies: []
subsystems: [frontend]
---

# ST-006 — Define CardDisplayItem Union Type for RecommendationCard

**Priority:** Low
**Risk:** Low
**Files modified:** `frontend/app/types/index.ts`, `frontend/app/components/RecommendationCard.vue`

## Problem

T009-ST4 needs `RecommendationCard` to display both `Recommendation` and `SimilarTitle`
objects. Currently the card's prop type is `Recommendation`. Without preparation, T009
would need to modify the card's prop type, add conditional rendering logic, and
potentially break the existing usage on the recommendations page.

By defining a shared base interface now, T009-ST3 can define `SimilarTitle` as extending
it, and T009-ST4 can use the card without modifying its internals.

## Fix

Read `frontend/app/types/index.ts` and `frontend/app/components/RecommendationCard.vue`
before editing.

### Step 1 — Add `CardDisplayItem` interface to `types/index.ts`

Define a base interface with the fields that `RecommendationCard` actually reads:

```typescript
/** Shared interface for items displayed in RecommendationCard */
export interface CardDisplayItem {
  title: string
  title_type: string
  year: number | null
  genres: string[]
  imdb_rating: number | null
  actors: string[]
  director: string | null
  language: string | null
  imdb_id: string | null
  imdb_url: string | null
  num_votes: number
  // Display fields — different per source
  display_score: number        // predicted_score or similarity_score
  display_explanations: string[] // explanation or similarity_explanation
  similar_to?: string[]        // only for Recommendation
  score_label?: string         // e.g. "★ 8.2" or "87% match"
  score_color?: string         // e.g. "success" or "info"
  extra_badges?: Array<{ label: string; color: string }>  // e.g. "Seen" chip
}
```

Add a helper function to convert `Recommendation` to `CardDisplayItem`:

```typescript
export function toCardItem(rec: Recommendation): CardDisplayItem {
  return {
    ...rec,
    display_score: rec.predicted_score,
    display_explanations: rec.explanation,
    similar_to: rec.similar_to,
    score_label: `★ ${rec.predicted_score.toFixed(1)}`,
    score_color: rec.predicted_score >= 8 ? 'success' : rec.predicted_score >= 7 ? 'warning' : 'error',
    extra_badges: [],
  }
}
```

T009-ST3 will later add a `toSimilarCardItem(similar: SimilarTitle): CardDisplayItem`
converter.

### Step 2 — Update `RecommendationCard.vue` to accept `CardDisplayItem`

Change the prop type:

```typescript
import type { CardDisplayItem } from '../types'

const props = defineProps<{
  item: CardDisplayItem
}>()
```

Update the template to use the new field names:
- `recommendation.predicted_score` → `item.display_score`
- `recommendation.explanation` → `item.display_explanations`
- `scoreColor(recommendation.predicted_score)` → `item.score_color`
- Score chip text → `item.score_label`
- Add rendering for `item.extra_badges` (if any)
- Remove the local `scoreColor()` function (now computed by the converter)

### Step 3 — Update `index.vue` and any other consumers

In `index.vue` (or `RecommendationGrid.vue` if ST-004 is done), update the card usage:

```html
<RecommendationCard
  v-for="rec in displayItems"
  :key="rec.imdb_id ?? rec.title"
  :item="rec"
  @dismissed="..."
  @exclude-genre="..."
  @exclude-language="..."
/>
```

Add a computed that converts recommendations to card items:

```typescript
import { toCardItem } from '../types'

const displayItems = computed(() =>
  recommendations.currentList.map(toCardItem)
)
```

## Anti-patterns

- Do NOT use `as any` or type assertions — the converter functions handle the mapping
- Do NOT change the card's emit signatures — they stay the same
- Do NOT add SimilarTitle support yet — that's T009's job
- Preserve all `data-e2e` attributes

## Post-conditions

```bash
grep -n "CardDisplayItem" frontend/app/types/index.ts
# Expected: at least 1 match

grep -n "CardDisplayItem" frontend/app/components/RecommendationCard.vue
# Expected: at least 1 match

grep -n "toCardItem" frontend/app/types/index.ts
# Expected: at least 1 match
```

## Tests

```bash
cd frontend && npx nuxt typecheck
```

## Files Changed

```
frontend/app/types/index.ts
frontend/app/components/RecommendationCard.vue
frontend/app/pages/index.vue (or frontend/app/components/RecommendationGrid.vue)
```

## Commit Message

```
refactor: define CardDisplayItem interface and adapt RecommendationCard
```
