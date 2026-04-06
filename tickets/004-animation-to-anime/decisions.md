# TICKET-004 Decisions

## Why `Fribb/anime-lists` over IMDB country/language signals

IMDB's `country_code` and `language` fields (derived from `title.akas`) are not reliable for anime identification. Many titles have null country codes, or have US/XWW as the primary region because a global streaming release (Netflix, Crunchyroll) is treated as the "original" by IMDB's akas data. The `Fribb/anime-lists` cross-reference is a community-maintained JSON that maps AniDB/MAL/AniList IDs to IMDB tconst values, giving a definitive whitelist with no guesswork.

The JP/Japanese heuristic is kept only as a fallback for titles not yet in the whitelist (e.g. very recently released anime).
