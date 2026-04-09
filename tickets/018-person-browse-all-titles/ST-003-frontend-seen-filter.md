---
id: ST-003
ticket: "018"
title: "Frontend: seen/unseen toggle + seen badge on person browse"
priority: Medium
risk: low
status: Open
dependencies: [ST-002]
subsystems: [frontend]
---

# SUBTASK 03 — Frontend: seen/unseen toggle + seen badge on person browse

---

## Objective

After ST-002, the API returns `is_rated` on every `PersonTitleResult`. Wire it up in
the frontend:
1. Add `is_rated: boolean` to the `PersonTitleResult` interface in `types/index.ts`.
2. In `toPersonCardItem`, add a "Seen" badge when `is_rated` is true.
3. In `person.vue`, add a seen/unseen/all toggle that filters `filteredResults`.

---

## Fix

### Step 1 — `frontend/app/types/index.ts`: add is_rated to PersonTitleResult

In the `PersonTitleResult` interface, add after `roles`:

```typescript
  is_rated: boolean
```

In `toPersonCardItem`, change the `extra_badges` line:

```typescript
    extra_badges: person.is_rated ? [{ label: 'Seen', color: 'success' }] : [],
```

### Step 2 — `frontend/app/pages/person.vue`: add seen filter

After the `roleFilter` ref, add:

```typescript
const seenFilter = ref<'all' | 'unseen' | 'seen'>('all')
```

In `filteredResults`, add a seen filter step before the role filter:

```typescript
const filteredResults = computed<PersonTitleResult[]>(() => {
  let results = person.personResults?.results ?? []
  if (seenFilter.value === 'unseen') {
    results = results.filter(r => !r.is_rated)
  } else if (seenFilter.value === 'seen') {
    results = results.filter(r => r.is_rated)
  }
  if (roleFilter.value !== 'any') {
    results = results.filter(r => r.roles.includes(roleFilter.value))
  }
  return [...results].sort(
    (a, b) => ((b[sortBy.value] ?? 0) as number) - ((a[sortBy.value] ?? 0) as number),
  )
})
```

In the results header `<div>` (right after the role toggle `<v-btn-toggle>`), add a
seen filter toggle:

```html
        <v-btn-toggle
          v-model="seenFilter"
          density="compact"
          color="secondary"
          mandatory
        >
          <v-btn value="all" size="small">All</v-btn>
          <v-btn value="unseen" size="small">Unseen</v-btn>
          <v-btn value="seen" size="small">Seen</v-btn>
        </v-btn-toggle>
```

---

## Tests

```bash
cd frontend && npx nuxt typecheck
```

---

## Files Changed

- `frontend/app/types/index.ts`
- `frontend/app/pages/person.vue`

---

## Commit Message

```
feat: add seen badge and seen/unseen toggle on person browse page (ST-003)
```
