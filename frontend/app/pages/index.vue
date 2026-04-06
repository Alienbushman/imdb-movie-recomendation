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
</script>

<template>
  <div>
    <SetupWizard
      v-if="showSetupWizard"
      :status="setupStatus"
      @started="handleSetupStart"
    />
    <div class="d-flex" style="min-height: calc(100vh - 64px)">
    <!-- Persistent filter sidebar -->
    <FilterDrawer />

    <!-- Main content area -->
    <div ref="contentArea" class="flex-grow-1 pa-4 overflow-auto">
      <ActionsBar
        :loading="recommendations.loading"
        :last-operation="recommendations.lastOperation"
        :model-accuracy="recommendations.data?.model_accuracy ?? null"
        @generate="(retrain, url) => recommendations.generate(retrain, url)"
        @csv-uploaded="handleCsvUpload"
      />

      <ActiveFilterSummary
        @remove-excluded-genre="removeExcludedGenreAndApply"
        @remove-excluded-language="removeExcludedLanguageAndApply"
      />

      <!-- Sort bar -->
      <div class="d-flex align-center ga-2 mb-2">
        <span class="text-caption text-medium-emphasis">Showing {{ recommendations.currentList.length }}</span>
        <v-spacer />
        <v-select
          v-model="recommendations.sortBy[recommendations.tab]"
          :items="sortOptions"
          item-title="label"
          item-value="value"
          density="compact"
          hide-details
          variant="outlined"
          style="max-width: 180px"
          prepend-inner-icon="mdi-sort"
        />
        <v-btn-toggle v-model="gridDense" density="compact" variant="outlined" mandatory>
          <v-btn :value="false" icon="mdi-view-grid-outline" size="small" />
          <v-btn :value="true" icon="mdi-view-grid" size="small" />
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
