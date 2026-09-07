# 023 — `rating_vote_ratio` / `num_votes` block widening the candidate pool

**Status:** open
**Raised:** 2026-09-07

## Problem

Two config values make part of this user's taste structurally unreachable:

- `imdb_datasets.min_rating: 5.0` — 14% of everything they have rated that IMDB
  scores under 5.5 got 8+/10 from them. Their highest-delta ratings include
  Epic Movie (IMDB 2.5 → 10) and S. Darko (3.6 → 9).
- `imdb_datasets.min_year: 1970` — excludes their two best decades (1950s 8.11,
  1940s 7.29, against 6.98 for 1970+).

A candidate the pool filters out can never be recommended, whatever the model
learns.

## Why it is not just a config change

Tried on 2026-09-07 (`min_rating: 3.0`, `min_year: 0`) and **reverted**:

| | before | after |
|---|---|---|
| candidate pool | 143,241 | 195,347 |
| top-100 with <1000 votes | — | 26 |
| top movie recommendations | Altman back catalogue | *Malibu Rescue*, *Stuck in the Suburbs*, *Even Pigs Go to Heaven* |

Those titles are kids/family/TV-movie — empirically this user's **worst**
cluster (residual −0.61 against their own baseline).

Root cause is the model, not the pool. `rating_vote_ratio` is
`imdb_rating / log1p(num_votes)` and is the second-heaviest feature (0.148);
`num_votes` is the heaviest (0.186). The ratio is *maximised* by obscure titles,
so widening the pool feeds it directly.

## Subtasks

1. Replace `rating_vote_ratio` with something that does not reward low vote
   counts, or drop it. Confirm the top-100 vote distribution does not collapse.
2. Re-apply `min_rating: 3.0` and `min_year: 0`; verify the top-20 movies are
   not dominated by sub-1000-vote titles.
3. Re-check that pre-1970 and sub-5.0 titles actually surface.

## Blocked on

Ticket 024 — the eval harness cannot currently resolve a change of this size,
so "did this help?" is unanswerable today.
