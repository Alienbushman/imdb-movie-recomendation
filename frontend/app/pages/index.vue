<script setup lang="ts">
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

function handleExcludeLanguage(language: string) {
  filters.addExcludedLanguage(language)
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

onMounted(() => {
  recommendations.loadOrGenerate()
  contentEl.value?.addEventListener('scroll', onScroll)
})
onUnmounted(() => contentEl.value?.removeEventListener('scroll', onScroll))
</script>

<template>
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
        @exclude-language="handleExcludeLanguage"
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
</template>
