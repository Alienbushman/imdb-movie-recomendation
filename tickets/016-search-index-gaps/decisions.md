# Decisions — Ticket 016

## Decisions

_None recorded yet._

## Future Improvements

- ST-003 (not scoped here): `query_titles_by_person` currently JOINs only `scored_candidates`,
  so rated films for a director don't appear in browse results. A UNION with `rated_titles`
  (added in ST-002) would surface them. Medium effort, medium value.

- `include_rated=True` in `find_similar` is currently broken — the `scored` list comes from
  `query_all_candidates_lightweight` which returns only unrated candidates, so `include_rated=True`
  always yields empty results. After ST-002, this could be fixed by also querying `rated_titles`
  and scoring those against the seed.
