---
ticket: "012"
subtask: 2
title: "Frontend: Onboarding Wizard for First-Time Users"
status: Done
effort: medium
component: frontend
depends_on: [ST-001]
files_modified:
  - frontend/app/types/index.ts
  - frontend/app/pages/index.vue
files_created:
  - frontend/app/components/SetupWizard.vue
---

# SUBTASK 02: Frontend — Onboarding Wizard for First-Time Users

---

## Objective

Show a clear setup wizard on first run instead of auto-triggering the pipeline (which
fails without a watchlist). The wizard guides the user through dataset preparation and
connecting their IMDB ratings in one place.

---

## Pre-conditions

Read these files in full before writing any code:
- `frontend/app/types/index.ts` — find `PipelineStatus`
- `frontend/app/pages/index.vue` — understand the existing `onMounted` flow
- `frontend/app/stores/recommendations.ts` — understand `loadOrGenerate()` and `generate()`
- `frontend/app/composables/useApi.ts` — find `getStatus()`
- `frontend/app/components/ActionsBar.vue` — understand the existing URL/CSV inputs

Verify ST-001 is done: `GET /api/v1/status` must return `watchlist_ready`, `datasets_ready`,
`datasets_downloading`, and `scored_db_ready`.

```bash
cd frontend && npx nuxt typecheck
```

Must pass before starting.

---

## Context

Currently `index.vue` calls `recommendations.loadOrGenerate()` unconditionally on mount.
On a fresh install (no `data/watchlist.csv`), `loadOrGenerate()` eventually calls
`generate()`, which runs the pipeline, which fails with an error about the missing file.

The fix is to check `GET /status` first. If `watchlist_ready` is false, skip
`loadOrGenerate()` entirely and show the setup wizard instead. Once the wizard completes
a successful `generate()`, the wizard disappears and the recommendations page is shown.

Returning users (who already have a watchlist and/or scored results) are completely
unaffected — they never see the wizard.

---

## Implementation

### 1. Add four fields to `PipelineStatus` in `types/index.ts`

```typescript
// BEFORE
export interface PipelineStatus {
  rated_titles_count: number
  candidates_count: number
  model_trained: boolean
  last_run: string | null
}
```

```typescript
// AFTER
export interface PipelineStatus {
  rated_titles_count: number
  candidates_count: number
  model_trained: boolean
  last_run: string | null
  datasets_ready: boolean
  datasets_downloading: boolean
  watchlist_ready: boolean
  scored_db_ready: boolean
}
```

### 2. Create `frontend/app/components/SetupWizard.vue`

The wizard is a full-screen overlay rendered on top of the main layout. It has two visual
steps and a "Get Started" action.

```vue
<script setup lang="ts">
import type { PipelineStatus } from '../types'

const props = defineProps<{
  status: PipelineStatus | null
}>()

const emit = defineEmits<{
  started: [imdbUrl: string | undefined, file: File | undefined]
}>()

const imdbUrl = ref('')
const csvFile = ref<File | null>(null)

const datasetsReady = computed(() => props.status?.datasets_ready ?? false)
const datasetsDownloading = computed(() => props.status?.datasets_downloading ?? false)

// Step 1 state
const step1Icon = computed(() => {
  if (datasetsDownloading.value) return null           // show spinner
  if (datasetsReady.value) return 'mdi-check-circle'  // green check
  return 'mdi-clock-outline'                           // waiting
})
const step1Color = computed(() => datasetsReady.value ? 'success' : 'medium-emphasis')
const step1Label = computed(() => {
  if (datasetsDownloading.value) return 'Downloading dataset files… (this takes a few minutes)'
  if (datasetsReady.value) return 'Dataset files ready'
  return 'Waiting for dataset files…'
})

function handleCsvChange(files: File | File[] | null) {
  const file = Array.isArray(files) ? files[0] : files
  csvFile.value = file ?? null
}

function handleStart() {
  emit('started', imdbUrl.value || undefined, csvFile.value ?? undefined)
}
</script>

<template>
  <div
    class="setup-wizard-overlay d-flex align-center justify-center"
    style="position: fixed; inset: 0; z-index: 100; background: rgba(var(--v-theme-background), 0.97)"
  >
    <v-card
      class="setup-wizard-card pa-8"
      max-width="540"
      width="100%"
      variant="flat"
    >
      <!-- Header -->
      <div class="d-flex align-center mb-8">
        <v-icon color="primary" size="36" class="mr-3">mdi-movie-open-star</v-icon>
        <div>
          <div class="text-h5 font-weight-bold">IMDB Recommendations</div>
          <div class="text-body-2 text-medium-emphasis">First-time setup</div>
        </div>
      </div>

      <!-- Step 1: Datasets -->
      <div class="d-flex align-start mb-6">
        <div class="step-icon-col mr-4 mt-1">
          <v-progress-circular
            v-if="datasetsDownloading"
            indeterminate
            color="primary"
            size="24"
            width="3"
          />
          <v-icon v-else :color="step1Color" size="24">{{ step1Icon }}</v-icon>
        </div>
        <div class="flex-grow-1">
          <div class="text-subtitle-1 font-weight-medium mb-1">Dataset files</div>
          <div class="text-body-2 text-medium-emphasis">{{ step1Label }}</div>
        </div>
      </div>

      <!-- Step 2: Ratings input -->
      <div class="d-flex align-start mb-8">
        <div class="step-icon-col mr-4 mt-1">
          <v-icon
            :color="datasetsReady ? 'primary' : 'medium-emphasis'"
            size="24"
          >
            mdi-account-star
          </v-icon>
        </div>
        <div class="flex-grow-1">
          <div class="text-subtitle-1 font-weight-medium mb-3">Your IMDB ratings</div>
          <v-text-field
            v-model="imdbUrl"
            label="IMDB Ratings URL"
            placeholder="https://www.imdb.com/user/ur.../ratings/"
            hint="Your IMDB ratings page must be set to public"
            persistent-hint
            persistent-placeholder
            clearable
            variant="outlined"
            prepend-inner-icon="mdi-link"
            density="compact"
            :disabled="!datasetsReady"
            class="mb-3"
          />
          <div class="text-caption text-medium-emphasis mb-2">Or upload a CSV instead</div>
          <v-file-input
            label="Upload ratings CSV"
            accept=".csv"
            hint="Export from IMDB → Your ratings → Export"
            persistent-hint
            variant="outlined"
            prepend-icon="mdi-upload"
            density="compact"
            :disabled="!datasetsReady"
            @update:model-value="handleCsvChange"
          />
        </div>
      </div>

      <!-- Action -->
      <v-btn
        color="primary"
        size="large"
        block
        prepend-icon="mdi-play"
        :disabled="!datasetsReady || (!imdbUrl && !csvFile)"
        @click="handleStart"
      >
        Get Started
      </v-btn>

      <div class="text-caption text-center text-medium-emphasis mt-3">
        Need help? See the
        <a
          href="https://github.com/Alienbushman/imdb-movie-recomendation"
          target="_blank"
          class="text-primary"
        >README</a>
        for instructions.
      </div>
    </v-card>
  </div>
</template>

<style scoped>
.step-icon-col {
  flex-shrink: 0;
  width: 28px;
  display: flex;
  justify-content: center;
}
</style>
```

### 3. Modify `index.vue` — replace `onMounted` with status-aware init

Replace the current `onMounted` block:

```typescript
// BEFORE (in index.vue)
onMounted(() => {
  recommendations.loadOrGenerate()
  contentEl.value?.addEventListener('scroll', onScroll)
})
onUnmounted(() => contentEl.value?.removeEventListener('scroll', onScroll))
```

```typescript
// AFTER (in index.vue)
const api = useApi()

const showSetupWizard = ref(false)
const setupStatus = ref<PipelineStatus | null>(null)
let statusPollInterval: ReturnType<typeof setInterval> | null = null

async function initializeApp() {
  try {
    const status = await api.getStatus()
    if (status.watchlist_ready) {
      // Returning user — proceed with normal load flow
      showSetupWizard.value = false
      recommendations.loadOrGenerate()
    } else {
      // Fresh install — show wizard
      showSetupWizard.value = true
      setupStatus.value = status
      startStatusPolling()
    }
  } catch {
    // Backend still starting up; show wizard and retry
    showSetupWizard.value = true
    setTimeout(initializeApp, 2000)
  }
}

function startStatusPolling() {
  if (statusPollInterval) return
  statusPollInterval = setInterval(async () => {
    try {
      setupStatus.value = await api.getStatus()
      if (setupStatus.value.datasets_ready && !setupStatus.value.datasets_downloading) {
        clearInterval(statusPollInterval!)
        statusPollInterval = null
      }
    } catch { /* ignore transient poll errors */ }
  }, 3000)
}

async function handleSetupStart(imdbUrl: string | undefined, file: File | undefined) {
  if (file) {
    try {
      await api.uploadWatchlist(file)
      await recommendations.generate()
    } catch (e: unknown) {
      const err = e as { data?: { detail?: string }; message?: string }
      recommendations.error = err.data?.detail || err.message || 'Failed to upload watchlist'
    }
  } else {
    await recommendations.generate(false, imdbUrl)
  }
  if (!recommendations.error) {
    showSetupWizard.value = false
  }
}

onMounted(() => {
  initializeApp()
  contentEl.value?.addEventListener('scroll', onScroll)
})

onUnmounted(() => {
  contentEl.value?.removeEventListener('scroll', onScroll)
  if (statusPollInterval) {
    clearInterval(statusPollInterval)
    statusPollInterval = null
  }
})
```

Also add the import for `PipelineStatus` at the top of the `<script setup>` block:

```typescript
import type { PipelineStatus } from '../types'
```

### 4. Add the wizard to the `index.vue` template

Add `<SetupWizard>` at the outermost level of the template, above the main content div:

```vue
<!-- BEFORE: top of template -->
<template>
  <div class="d-flex" style="min-height: calc(100vh - 64px)">
    ...
  </div>
</template>
```

```vue
<!-- AFTER: wizard overlays the main content -->
<template>
  <div>
    <SetupWizard
      v-if="showSetupWizard"
      :status="setupStatus"
      @started="handleSetupStart"
    />
    <div class="d-flex" style="min-height: calc(100vh - 64px)">
      ...existing content unchanged...
    </div>
  </div>
</template>
```

Note: the main content div remains in the DOM when the wizard is shown — the wizard
overlays it with `position: fixed`. This means the layout is not disrupted when the wizard
dismisses.

### 5. Remove the duplicate `const api = useApi()` declaration

`index.vue` already declares `const api = useApi()` inside `handleCsvUpload`. Move the
declaration to the top of `<script setup>` (outside any function) if it is not already
there. There must be exactly one `const api = useApi()` at the module scope.

---

## Acceptance Criteria

- [ ] `PipelineStatus` interface in `types/index.ts` has all four new fields
- [ ] `SetupWizard.vue` exists and renders a full-screen overlay when `showSetupWizard` is true
- [ ] The wizard shows a spinner next to "Dataset files" while `datasets_downloading` is true
- [ ] The wizard shows a green check next to "Dataset files" once `datasets_ready` is true
- [ ] The URL input and CSV upload are disabled while `datasets_ready` is false
- [ ] "Get Started" is disabled until `datasets_ready` and at least one of (URL, file) is provided
- [ ] Clicking "Get Started" with a URL calls `generate(false, url)` and hides the wizard on success
- [ ] Clicking "Get Started" with a CSV file uploads it, calls `generate()`, and hides the wizard on success
- [ ] If `generate()` fails (e.g., bad URL), the wizard stays visible and the error is shown via `recommendations.error`
- [ ] A returning user (`watchlist_ready == true`) never sees the wizard
- [ ] The `statusPollInterval` is cleared on component unmount
- [ ] `cd frontend && npx nuxt typecheck` passes with zero new errors

---

## Tests

```bash
cd frontend && npx nuxt typecheck
```

Manual verification steps:

1. **Fresh install simulation** — delete `data/watchlist.csv` and `data/cache/scored_candidates.db`
   (ask the user first per Hard Stop List), restart the backend, open the frontend.
   - Wizard should appear
   - If datasets are still downloading: spinner visible next to "Dataset files"
   - Once datasets are ready: URL input enabled, "Get Started" not yet active
   - Enter a valid IMDB URL and click "Get Started" → wizard disappears, recommendations load

2. **Returning user** — with `watchlist.csv` and `scored_candidates.db` in place, reload the
   frontend. Wizard must not appear; recommendations load immediately via the fast path.

3. **Error handling** — Enter an invalid IMDB URL, click "Get Started". Wizard should stay
   visible and show the error message from `recommendations.error`.

---

## Commit Message

```
feat: add SetupWizard onboarding for first-time users
```
