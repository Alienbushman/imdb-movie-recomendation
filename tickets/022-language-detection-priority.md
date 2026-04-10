---
id: "022"
title: "Fix English language misclassification via priority chain"
status: open
priority: medium
component: backend
files_affected:
  - app/services/candidates.py
---

# TICKET-022: Fix English language misclassification via priority chain

---

## Summary

Non-English films (Korean, Japanese, Chinese) are being classified as English because
`_load_language_data` uses a mode-based vote over `isOriginalTitle=1` rows. Two patterns
corrupt the result: (1) `XWW` (worldwide) entries in `isOriginalTitle=1` rows map to
English and outvote the true original language; (2) the fallback mode across all rows
heavily favours English for internationally distributed films. The fix replaces the
two-pass approach with a 4-step priority chain that prefers explicit BCP-47 language
codes and non-English regions before falling back to anything English-biased.

## Priority Breakdown

| Priority | Count |
|---|---|
| High | 0 |
| Medium | 1 |
| Low | 0 |

## Subtasks

| ID | Title | Priority | Status |
|---|---|---|---|
| [ST-001](022-language-detection-priority/ST-001-four-step-language-priority.md) | 4-step language detection priority chain | Medium | Open |

## Context

Observed misclassified titles: "j-hope IN THE BOX" (Korean), "Ley Lines" (Japanese),
"Visitor Q" (Japanese), "A Woman, a Gun and a Noodle Shop" (Chinese) all resolved to
English. Root cause analysis is in the conversation that produced this ticket.

Ticket 007 introduced the current mode-aggregation approach. This ticket improves on it
without changing the `CandidateTitle` schema.

## Files in Scope

- `app/services/candidates.py`

## Acceptance Criteria

- [ ] `_load_language_data` resolves language using a 4-step priority chain
- [ ] Step 1: explicit BCP-47 language code from `isOriginalTitle=1` rows
- [ ] Step 2: non-English, non-ambiguous region from `isOriginalTitle=1` rows
- [ ] Step 3: explicit BCP-47 language code from ALL rows (mode)
- [ ] Step 4: full mode fallback (last resort, current behaviour)
- [ ] `_ENGLISH_REGIONS` constant defined at module level
- [ ] Lint and tests pass

## Scope Fence

- Only modify `app/services/candidates.py`
- Do not change `CandidateTitle` schema
- Do not change `_REGION_TO_LANG`, `_LANG_CODE_TO_NAME`, or `_AMBIGUOUS_REGIONS`
