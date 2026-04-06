# Ticket 010 — Decisions

## ST-004: index.vue line count exceeds 80-line target

The subtask expected index.vue to be under 80 lines after all extractions. The actual
result is ~148 lines because T008 (sort controls, grid density toggle, scroll-to-top FAB)
was completed before this ticket ran, adding ~40 lines of sort bar, scroll logic, and
density toggle that the subtask didn't account for. The template section is 77 lines,
which meets the "under 80 lines of template" acceptance criterion. The sort bar and
scroll-to-top remain in index.vue because they reference the parent's scroll container.

## ST-004: Added gridDense prop not in original spec

The subtask's Props only specified `items`, `loading`, `hasData`. Since T008 added
`.card-grid--dense` CSS (controlled by `gridDense` ref in index.vue) and the CSS moved
into RecommendationGrid, a `gridDense: boolean` prop was added to make the class binding
work.

## ST-006: Added toSimilarCardItem for T009 compatibility

The subtask said "Do NOT add SimilarTitle support yet — that's T009's job." However,
T009 was already completed, so `similar.vue` was already using `RecommendationCard` with
`SimilarTitle`. Added `toSimilarCardItem()` converter and updated `similar.vue` to
maintain existing functionality.
