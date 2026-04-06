# TICKET-003 Decisions Log

Record non-obvious implementation choices here as subtasks are completed. Future agents need to understand *why* the code is shaped a certain way — not just what changed.

## Format

```
### [Subtask N — Title] Short description of the decision
**Context:** What was unclear or had multiple valid options.
**Decision:** What was chosen.
**Reason:** Why this option over the alternatives.
```

## Decisions

### [Subtask 01 — Filter Panel Layout] Inline sidebar vs drawer offset
**Context:** `v-navigation-drawer permanent` normally pairs with `v-main` to shift the content area. The app only needs the sidebar on the index page, not on the dismissed page.
**Decision:** Wrapped the sidebar and content in a `d-flex` div inside `index.vue` rather than registering it in the layout.
**Reason:** Keeps the sidebar self-contained to the one page that needs it. Restructuring `default.vue` to conditionally offset `v-main` would be more complex and fragile.

### [Subtask 01 — Genre Chips] Three-state vs two-row chip groups
**Context:** The original drawer had two separate 23-chip groups for include and exclude. The ticket recommended a single three-state toggle.
**Decision:** Implemented three-state chips (neutral → include → exclude → neutral cycle) via `toggleGenre()`.
**Reason:** Halves visual clutter while preserving full include/exclude capability. State is derived from the two existing `selectedGenres`/`excludedGenres` refs — no store changes needed.

### [Subtask 02 — Count Controls] `v-text-field` instead of `v-number-input`
**Context:** The ticket suggested `v-number-input`, which is a Vuetify 4 lab component.
**Decision:** Used `v-text-field type="number"` with `clearable`.
**Reason:** Lab components are less stable. Clearing sets the value to `undefined`, which the store naturally treats as "use config default" in `buildFilters()`.

### [Subtask 03 — Year Range] Separate refs with computed `yearRange`
**Context:** Could have replaced `minYear`/`maxYear` refs with a single tuple ref.
**Decision:** Kept both refs and added a computed `yearRange` getter/setter binding.
**Reason:** `buildFilters()`, `activeFilterSummary`, and `hasActiveFilters` all use `minYear`/`maxYear` individually. The computed adds the slider binding without rewriting those consumers.

### [Subtask 04 — Dismissed Metadata] Cache-only resolution, no TSV fallback
**Context:** The ticket proposed three strategies: cache lookup, TSV parse, or graceful degradation.
**Decision:** Cache lookup (Strategy A) with graceful degradation (Strategy C). TSV parse (Strategy B) was skipped.
**Reason:** TSV parsing is slow and requires datasets to be downloaded. The cache is always present after the first pipeline run. The graceful fallback (ID-only) handles the case where neither is available.

### [Subtask 05 — Country Display] Code ("US") not full name ("United States")
**Context:** Could show full country name resolved from `ALL_COUNTRY_CODES`, or just the ISO code.
**Decision:** Show the ISO code (e.g., "US", "KR") in the chip.
**Reason:** Space is limited in the card subtitle row. Common codes are instantly recognizable. The `mdi-map-marker` icon provides enough visual context that it's a location.

### [Subtask 07 — Debounce] Single 400ms delay for all filter types
**Context:** Ticket suggested different delays for chips (300ms) vs sliders (500ms) vs text inputs (400ms).
**Decision:** Single 400ms debounce for all filter types.
**Reason:** The per-type approach adds complexity for marginal benefit. 400ms is the recommended middle ground and works fine for all input types.

### [Subtask 06 — Loading Skeletons] Initial load only, not during re-filter
**Context:** Could show skeletons on every API call including re-filters.
**Decision:** Skeletons appear only when `loading && !data` (initial load). Re-filters show only the slim progress bar.
**Reason:** Replacing existing cards with skeletons on re-filter causes jarring flicker. The ticket specifies keeping existing cards visible during re-filter.

### [Pre-existing test failure] `test_column_count` not fixed
**Context:** `tests/test_features.py::TestFeaturesToDataframe::test_column_count` asserts 34 columns but the dataframe now has 97.
**Decision:** Left as-is.
**Reason:** This was already failing before TICKET-003 work started. It's a TICKET-002 scope issue where feature engineering was expanded but the test assertion was not updated.
