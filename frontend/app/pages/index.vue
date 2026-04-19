<script setup lang="ts">
import type { PipelineStatus } from '../types'
import { useRecommendationsStore } from '../stores/recommendations'
import { useFiltersStore } from '../stores/filters'

const recommendations = useRecommendationsStore()
const filters = useFiltersStore()
const api = useApi()

const gridDense = ref(false)
onMounted(() => {
  gridDense.value = localStorage.getItem('grid-dense') === 'true'
})
watch(gridDense, (v) => localStorage.setItem('grid-dense', String(v)))

const sortOptions = [
  { label: 'Best Match', value: 'score' },
  { label: 'IMDB Rating', value: 'imdb_rating' },
  { label: 'Newest', value: 'year_desc' },
  { label: 'Oldest', value: 'year_asc' },
  { label: 'Most Voted', value: 'votes' },
  { label: 'A–Z', value: 'title' },
]

function handleExcludeGenre(genre: string) {
  filters.addExcludedGenre(genre)
  recommendations.applyFilters()
}

function handleIncludeLanguage(language: string) {
  filters.addSelectedLanguage(language)
  recommendations.applyFilters()
}

function removeExcludedGenreAndApply(genre: string) {
  filters.removeExcludedGenre(genre)
  recommendations.applyFilters()
}

function removeExcludedLanguageAndApply(language: string) {
  filters.removeExcludedLanguage(language)
  recommendations.applyFilters()
}

async function handleCsvUpload(file: File) {
  try {
    await api.uploadWatchlist(file)
    await recommendations.generate()
  } catch (e: unknown) {
    const err = e as { data?: { detail?: string }; message?: string }
    recommendations.error = err.data?.detail || err.message || 'Failed to upload watchlist'
  }
}

const contentEl = useTemplateRef<HTMLElement>('contentArea')
const showScrollTop = ref(false)

function onScroll() {
  showScrollTop.value = (contentEl.value?.scrollTop ?? 0) > 300
}

function scrollToTop() {
  contentEl.value?.scrollTo({ top: 0, behavior: 'smooth' })
}

const showSetupWizard = ref(false)
const setupStatus = ref<PipelineStatus | null>(null)
let statusPollInterval: ReturnType<typeof setInterval> | null = null

async function initializeApp() {
  try {
    const status = await api.getStatus()
    setupStatus.value = status

    if (status.pipeline_running) {
      // A pipeline run is already in progress (different tab, prior session, or
      // a page refresh mid-run). Attach to it so the user sees progress and gets
      // the results when it finishes — don't start a new run.
      if (!status.watchlist_ready || !status.scored_db_ready) {
        showSetupWizard.value = true
        startStatusPolling()
      } else {
        showSetupWizard.value = false
      }
      recommendations.attachToRunningPipeline()
      return
    }

    if (status.watchlist_ready) {
      // Returning user — proceed with normal load flow
      showSetupWizard.value = false
      recommendations.loadOrGenerate()
    } else {
      // Fresh install — show wizard
      showSetupWizard.value = true
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
</script>

<template>
  <div data-e2e="index-page" class="index-root">
    <SetupWizard
      v-if="showSetupWizard"
      :status="setupStatus"
      :generate-running="recommendations.loading"
      :generate-progress="recommendations.generateProgress"
      :generate-error="recommendations.error"
      @started="handleSetupStart"
    />
    <div class="d-flex" style="min-height: calc(100vh - 64px)">
    <!-- Persistent filter sidebar -->
    <FilterDrawer />

    <!-- Main content area -->
    <div ref="contentArea" data-e2e="index-content" class="flex-grow-1 pa-4 overflow-auto content-area">
      <ActionsBar
        :loading="recommendations.loading"
        :last-operation="recommendations.lastOperation"
        :model-accuracy="recommendations.data?.model_accuracy ?? null"
        @generate="(retrain, url) => recommendations.generate(retrain, url)"
        @csv-uploaded="handleCsvUpload"
      />

      <!-- Inline progress banner while the pipeline is running from the main page -->
      <v-alert
        v-if="recommendations.loading && recommendations.generateProgress"
        data-e2e="generate-progress-banner"
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
      >
        <div class="d-flex align-center ga-2">
          <v-progress-circular indeterminate size="18" width="2" />
          <span>
            <strong v-if="recommendations.generateProgress.step">
              Step {{ recommendations.generateProgress.step }}/4:
            </strong>
            {{ recommendations.generateProgress.label || 'Starting…' }}
          </span>
        </div>
      </v-alert>

      <ActiveFilterSummary
        @remove-excluded-genre="removeExcludedGenreAndApply"
        @remove-excluded-language="removeExcludedLanguageAndApply"
      />

      <!-- Sort bar -->
      <div data-e2e="sort-bar" class="d-flex align-center ga-2 mb-2">
        <span data-e2e="recommendations-result-count" class="text-caption text-medium-emphasis">Showing {{ recommendations.currentList.length }}</span>
        <v-spacer />
        <v-select
          v-model="recommendations.sortBy[recommendations.tab]"
          :items="sortOptions"
          data-e2e="recommendations-sort-select"
          item-title="label"
          item-value="value"
          density="compact"
          hide-details
          variant="outlined"
          style="max-width: 180px"
          prepend-inner-icon="mdi-sort"
        />
        <v-btn-toggle v-model="gridDense" data-e2e="grid-density-toggle" density="compact" variant="outlined" mandatory>
          <v-btn data-e2e="grid-density-comfortable" :value="false" icon="mdi-view-grid-outline" size="small" />
          <v-btn data-e2e="grid-density-dense" :value="true" icon="mdi-view-grid" size="small" />
        </v-btn-toggle>
      </div>

      <!-- Error -->
      <v-alert v-if="recommendations.error" data-e2e="alert-error" type="error" closable class="mb-4" @click:close="recommendations.clearError()">
        {{ recommendations.error }}
      </v-alert>

      <CategoryTabs
        v-model="recommendations.tab"
        :movie-count="recommendations.data?.movies.length ?? 0"
        :series-count="recommendations.data?.series.length ?? 0"
        :anime-count="recommendations.data?.anime.length ?? 0"
      />

      <RecommendationGrid
        :items="recommendations.currentList"
        :loading="recommendations.loading"
        :has-data="!!recommendations.data"
        :grid-dense="gridDense"
        @generate="recommendations.generate(false)"
        @dismissed="recommendations.handleDismissed"
        @exclude-genre="handleExcludeGenre"
        @include-language="handleIncludeLanguage"
      />

      <!-- Scroll-to-top FAB -->
      <v-btn
        v-if="showScrollTop"
        data-e2e="btn-scroll-top"
        icon="mdi-chevron-double-up"
        color="primary"
        variant="tonal"
        size="small"
        style="position: fixed; bottom: 24px; right: 24px; z-index: 10"
        @click="scrollToTop"
      />
    </div>
    </div>
  </div>
</template>

<style scoped>
.index-root {
  position: relative;
}

.content-area {
  background:
    radial-gradient(ellipse at top left, rgba(var(--v-theme-primary), 0.06) 0%, transparent 55%),
    radial-gradient(ellipse at bottom right, rgba(var(--v-theme-secondary), 0.05) 0%, transparent 55%);
}
</style>
