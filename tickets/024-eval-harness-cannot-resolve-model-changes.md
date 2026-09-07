# 024 — The eval harness cannot resolve a model change

**Status:** open
**Raised:** 2026-09-07

## Problem

Every model change measured on 2026-09-07 landed inside the noise.

5-fold vs 10-fold temporal CV, NDCG@10, on 2250 ratings:

| variant | 5 folds | 10 folds |
|---|---|---|
| baseline | 0.7293 ± 0.1849 | 0.5692 ± 0.1631 |
| + genre-affinity fix & aggregates | 0.6883 ± 0.1952 | 0.6224 ± 0.1683 |

The change looks harmful at 5 folds and helpful at 10. Fold-to-fold std is
0.16–0.20 while the differences under test are ~0.05, so the sign of the result
is decided by the fold count, not the change.

A single temporal holdout is worse still, and actively misleading. On one
450-item split, removing the person-taste features looked like a large win
(NDCG 0.2419 → 0.5925, spearman 0.2026 → 0.3451). Under 5-fold temporal CV the
same change is a large **loss** (0.6883 → 0.3759). A change was nearly shipped
on the strength of the single split.

## Why

The most recent 20% of this library is dominated by anime and TV series, where
person-taste features are mostly noise. A single most-recent-slice holdout
therefore measures a different question from the one being asked.

## Subtasks

1. Report `cv_ndcg_at_k_sem` and `cv_spearman_mean` — **done 2026-09-07**, so
   the spread is visible rather than inferred.
2. Make `run_eval` refuse to declare an improvement smaller than 1 SEM.
3. Consider bootstrap CIs over folds rather than mean ± std.
4. Until 1–3 land, treat any single-holdout result as a hypothesis, not evidence.

## Rejected on 2026-09-07: aggregate genre-affinity features

Fixing the gating bug leaves the 23 per-genre affinity columns still useless:
for a single user each one is `genre_x_flag * constant_x`, a monotone rescale of
a flag the model already has. Three aggregates over the title's own genres
(`genre_affinity_mean` / `_max` / `_min`) were added to give the splitter
something that actually varies. They were **used** — `genre_affinity_mean`
became the 8th-heaviest feature at 0.084 — and then **reverted**:

| | with aggregates | gating fix only |
|---|---|---|
| CV spearman | 0.371 ± 0.090 | **0.4246 ± 0.029** |
| CV NDCG@10 | 0.9017 ± 0.058 | 0.8321 ± 0.154 |
| top movie recs | *Malibu Rescue*, *Stuck in the Suburbs* | Altman back catalogue |

Likely mechanism: this user's Animation average is 7.77, inflated by highly
rated anime **series**, and the aggregate transfers that to Western kids'
animation — empirically their worst cluster. A per-genre average that is not
title-type aware leaks across a boundary that matters.

Worth retrying once ticket 023 lands, split by title type.
