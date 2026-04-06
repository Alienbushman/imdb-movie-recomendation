# TICKET-002 Decisions Log

Record non-obvious implementation choices here as subtasks are completed. Future agents need to understand *why* the code is shaped a certain way — not just what changed.

## Format

```
### [Subtask N — Title] Short description of the decision
**Context:** What was unclear or had multiple valid options.
**Decision:** What was chosen.
**Reason:** Why this option over the alternatives.
```

## Decisions

### [Subtask 1 — Backend Scrape Service] Playwright instead of httpx for IMDB fetch
**Context:** The original plan used `httpx` with browser-like headers to call `https://www.imdb.com/user/{id}/ratings/export`. Investigation showed IMDB's export endpoint is now behind AWS WAF bot detection that returns `202` with a JS challenge page regardless of headers or TLS fingerprint spoofing (tested: plain httpx, curl, curl_cffi with `impersonate='chrome'`).
**Decision:** Use Playwright with headed Chrome (`headless=False`, `channel="chrome"`, `--disable-blink-features=AutomationControlled`) instead of any HTTP client. Rather than downloading the export file, the scraper extracts ratings from two sources the page already loads: `__NEXT_DATA__` (embedded SSR JSON with title metadata) and `PersonalizedUserData` GraphQL responses (user's per-title ratings). Pages through all results 250 at a time.
**Reason:** Headed Chrome passes IMDB's WAF fingerprinting where headless and all HTTP clients fail. The `PersonalizedUserData` GraphQL endpoint is called automatically by the page JS on load — no need to reverse-engineer the auth flow. The resulting CSV is field-for-field compatible with the legacy export format (validated against an existing watchlist: zero rating mismatches across 2000+ titles).

### [Subtask 1 — Backend Scrape Service] WAF challenge handling with polling wait
**Context:** The WAF challenge page runs JS that acquires a token and calls `window.location.reload()`. During this reload, calling `page.content()` throws "Unable to retrieve content because the page is navigating". Simple `wait_for_load_state("networkidle")` is not reliable because the WAF challenge page itself reaches networkidle before the reload happens.
**Decision:** Poll `page.content()` in a loop with `try/except` to ignore navigation exceptions. Detect the real page by checking for `__NEXT_DATA__` in the content. Distinct return values (`"ok"`, `"blocked"`, `"error"`, `"timeout"`) allow the caller to give specific error messages to the user.
**Reason:** `wait_for_function` with a JS predicate timed out inconsistently. The polling approach handles both the navigation race and the case where IMDB returns 503 (rate-limited) on a later page.

### [Subtask 1 — Backend Scrape Service] Rate limiting and graceful partial collection
**Context:** IMDB returned 503 after ~45 pages of rapid sequential requests during testing. The scraper is used interactively (user clicks a button), so it can't run infinitely slowly.
**Decision:** Add a 1.5s delay between page navigations. On 503/timeout on a subsequent page, stop and return whatever rows have been collected so far rather than failing the whole request. Log the partial count. Retry each page up to 2 times before giving up.
**Reason:** 1.5s × ~9 pages for 2150 ratings ≈ 14s of pure delay — acceptable. Returning partial data is better than a total failure if IMDB rate-limits mid-scrape. The user can re-run to get a fresh full scrape.

### [Subtask 7 — CSV Upload Fallback] Upload saves to disk, no pipeline trigger
**Context:** Options were: (a) save file then auto-trigger pipeline, (b) save file and let user click Generate, (c) accept file in-memory and pass directly to pipeline.
**Decision:** Save to `data/watchlist.csv` and return success — no pipeline trigger. The user clicks Generate afterward.
**Reason:** Decouples upload from the pipeline run (which takes 30–120s). Allows the user to set filters before running. Keeps the endpoint simple and synchronous. Also means the uploaded file persists for subsequent runs without re-uploading.
