# Decisions — Ticket 022

## Decisions

Used `_lang.notna()` check (not `_resolved.notna()`) in steps 1 and 3 because `_resolved`
fuses both explicit and region-inferred language — checking `_lang` directly isolates only
the BCP-47 column. Similarly step 2 checks `_region_lang.notna()` rather than `_resolved`
to avoid mixing in explicit codes.

`_ENGLISH_REGIONS` does not include `CA` even though it appears in `_AMBIGUOUS_REGIONS`,
because the ambiguous-region mask already nulls out `_region_lang` for `CA` — adding it to
`_ENGLISH_REGIONS` would be redundant but harmless.

## Future Improvements

The `country_code` field (first `isOriginalTitle=1` region) could be used as a tie-breaker
in step 2 to prefer the film's production country over other non-English region entries.
Not implemented here as the 4-step chain already handles the reported cases.

Cache note: `data/cache/imdb_candidates.json` must be deleted and the pipeline re-run for
the improved language data to take effect in recommendations.
