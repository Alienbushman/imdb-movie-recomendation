# Decisions & Future Improvements — Ticket 018

## Decisions

- **UNION ALL vs UNION**: Used `UNION ALL` (not `UNION`) in `query_titles_by_person` because a title can't appear in both `scored_candidates` and `rated_titles` by design — `scored_candidates` only contains unseen titles. `UNION ALL` avoids the deduplication overhead.
- **rated_titles filter for dismissed IDs**: Dismissed IDs are not applied to the rated branch of the UNION. Rated titles are in the user's watchlist; dismissing is only relevant for unscored candidates.
- **user_rating as predicted_score**: The scope fence says not to rescore rated titles. Using `user_rating` from the IMDB CSV as the predicted score stand-in means rated titles sort by the user's own rating, which is the most meaningful ordering.
- **actors/composers on cache hits**: When the candidate cache is hit, `rated_actors` etc. are `None`. Writers and directors are still indexed (always present in RatedTitle), so actors/composers are only indexed on full builds.

## Future Improvements

- Actors from rated titles are missing on cache hits (rated_actors is None). A future improvement could cache rated actor data separately so it survives beyond the first full build.
- The `languages` field for rated_titles is populated from `RatedTitle.language` as a single-element list. A future improvement could cross-reference title.akas for the full language list.
