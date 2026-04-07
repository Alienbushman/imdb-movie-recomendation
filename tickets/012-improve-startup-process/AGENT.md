# Agent Instructions — Ticket 012

See [`../PROTOCOL.md`](../PROTOCOL.md) for global execution rules, commit protocol, and
failure handling. This file contains only ticket-specific context.

**Status: Open** — Ready for implementation.

---

## Subtask Order

```
ST-001  ← backend: enrich /status (no deps)
ST-002  ← frontend: onboarding wizard (depends on ST-001)
```

ST-001 must be done first so the frontend has the new status fields to consume.

---

## Ticket-Specific Context

- **Read `app/services/candidates.py` in full before touching it** — `download_datasets()`
  is called from a daemon thread in `main.py`; the new module-level `_datasets_downloading`
  flag must be set/cleared inside `download_datasets()` itself (not in `main.py`) so it
  stays in scope for `is_datasets_downloading()`
- **Thread safety** — Python's GIL makes simple bool assignment effectively atomic for a
  single-writer/single-reader pattern; no `threading.Lock` is needed for this flag
- **`has_scored_results()` already exists** in `scored_store.py` — reuse it for the
  `scored_db_ready` field rather than adding a new query
- **`PipelineStatus` backwards compatibility** — the four new bool fields must have
  `default=False` so existing clients that don't read them are unaffected
- **Frontend wizard is overlay, not page** — `SetupWizard.vue` renders as a full-screen
  overlay (absolute-positioned, z-index above the app shell) while `showSetupWizard` is
  true; the normal index page content mounts behind it but is not interactive
- **Polling cleanup** — the `setInterval` for status polling must be cleared in
  `onUnmounted` to prevent memory leaks if the user navigates away mid-wizard
- **Wizard dismissal** — the wizard should only be dismissed after a successful
  `generate()` call, not on any click-away or escape; this prevents accidentally
  bypassing setup
- **`loadOrGenerate()` is unchanged** — the store function is not modified; `index.vue`
  simply calls it only when `watchlist_ready` is true (skipping the fallback-to-generate
  path that would fail on a fresh install)
- Lint: `uv run ruff check app/` (backend), `cd frontend && npx nuxt typecheck` (frontend)
- Tests: `uv run pytest tests/ -q`
