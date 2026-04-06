# ST-001 — Re-enable CSRF middleware

**Priority:** High  
**File:** `platform-backend/orchestrator/orchestrator/settings.py`

## Problem

`CsrfViewMiddleware` is absent from `MIDDLEWARE` in `settings.py`. The existing comment in
that file says "CSRF is intentionally disabled — this is a JWT-only API. All authentication
uses Bearer tokens" — but this is inaccurate. Tokens are stored as **HTTP-only cookies** set
by Nuxt server routes, not Authorization headers. That means browser-context requests (e.g.,
via Swagger UI or curl with cookies) are genuinely unprotected against CSRF.

The Nuxt server-side proxy routes themselves are not a browser context and are not at risk,
but any direct browser POST to port 9020 (e.g., through Swagger UI in local dev) would be
unprotected.

## Decision

**Option B — Document the waiver** (see Q-001 in parent ticket).
Port 9020 is Docker-internal only and all browser requests go through the Nuxt proxy layer.
Re-enabling CSRF middleware is unnecessary for the current architecture.

## Fix

Read `orchestrator/settings.py` before editing to confirm the current state.

Replace the inaccurate comment above the `MIDDLEWARE` list with an accurate block:

```python
# CSRF NOTE: CsrfViewMiddleware is not enabled.
# Risk: Swagger UI or any browser-direct POST to port 9020 is unprotected.
# Accepted because port 9020 is Docker-internal only (not host-bound).
# All browser requests go through the Nuxt server-side proxy layer.
# Re-enable before adding any host-exposed browser-direct POST surface.
```

## Pre-conditions

```bash
# Confirm the inaccurate comment still exists
grep -n "CSRF is intentionally disabled" platform-backend/orchestrator/orchestrator/settings.py
# Expected: 1 match
```

## Post-conditions

```bash
# Confirm the old comment is gone
grep -n "CSRF is intentionally disabled" platform-backend/orchestrator/orchestrator/settings.py
# Expected: 0 matches

# Confirm the new waiver comment is present
grep -n "CSRF NOTE" platform-backend/orchestrator/orchestrator/settings.py
# Expected: 1 match
```

## Files Changed

```
platform-backend/orchestrator/orchestrator/settings.py
```

## Rollback

```bash
git revert HEAD
```

## Commit Message

```
docs: document CSRF waiver with accurate rationale in settings.py
```

## Tests

```bash
# Targeted
cd platform-backend/orchestrator
python manage.py test authenticator.tests_security

# Full suite (required)
python manage.py test
cd ../../platform-frontend && npx vitest run

# Integration (if available)
cd ../.. && ./run_integration_tests.sh --keep
```
