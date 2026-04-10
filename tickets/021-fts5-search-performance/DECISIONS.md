# Decisions and Issues — Ticket 021

## Decisions

- Created all three FTS5 virtual tables (`people_fts`, `scored_candidates_fts`, `rated_titles_fts`) in `_ensure_schema()` during ST-002 rather than incrementally, since they're all needed and adding them together avoids multiple schema migration steps.
- Used external content FTS5 (`content='table_name'`) with `'rebuild'` after bulk inserts rather than triggers, since writes are batch-only (pipeline runs).
- Added additive migration for `title_count`/`rated_count` columns on `people` table (same pattern as `rated_titles` migrations) so existing databases upgrade without needing to delete the DB file.

## Future Improvements

- FTS5 query sanitization: special characters like `"`, `*`, `(`, `)` in user input could cause FTS5 syntax errors. Currently mitigated by the LIKE fallback (OperationalError is caught), but explicit sanitization would be cleaner.
- The `people` count denormalization UPDATE scans all people rows; for very large datasets a targeted update (only dirty rows) would be faster, but is unnecessary at current scale.
