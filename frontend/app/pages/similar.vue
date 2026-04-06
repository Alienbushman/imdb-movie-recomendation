<script setup lang="ts">
import { useSimilarStore } from '../stores/similar'
import { useFiltersStore } from '../stores/filters'
import type { TitleSearchResult, SimilarTitle } from '../types'

const similar = useSimilarStore()
const filters = useFiltersStore()

// Debounced search
let _searchTimer: ReturnType<typeof setTimeout> | null = null
function onSearchUpdate(query: string) {
  if (_searchTimer) clearTimeout(_searchTimer)
  _searchTimer = setTimeout(() => {
    similar.search(query)
  }, 300)
}

function onSeedSelected(seed: TitleSearchResult | null) {
  similar.selectedSeed = seed
  if (seed) {
    similar.fetchSimilar()
  }
}

function formatType(type: string): string {
  const map: Record<string, string> = {
    movie: 'Movie',
    tvSeries: 'Series',
    tvMiniSeries: 'Mini',
    tvMovie: 'TV Movie',
  }
  return map[type] || type
}

// Sort
type SimilarSortOption = 'similarity' | 'predicted' | 'imdb_rating' | 'year_desc'
const sortBy = ref<SimilarSortOption>('similarity')
const sortOptions = [
  { label: 'Most Similar', value: 'similarity' },
  { label: 'Best Match', value: 'predicted' },
  { label: 'IMDB Rating', value: 'imdb_rating' },
  { label: 'Newest', value: 'year_desc' },
]

const sortedResults = computed<SimilarTitle[]>(() => {
  if (!similar.similarResults) return []
  const items = [...similar.similarResults.results]
  switch (sortBy.value) {
    case 'similarity':
      items.sort((a, b) => b.similarity_score - a.similarity_score)
      break
    case 'predicted':
      items.sort((a, b) => (b.predicted_score ?? 0) - (a.predicted_score ?? 0))
      break
    case 'imdb_rating':
      items.sort((a, b) => (b.imdb_rating ?? 0) - (a.imdb_rating ?? 0))
      break
    case 'year_desc':
      items.sort((a, b) => (b.year ?? 0) - (a.year ?? 0))
      break
  }
  return items
})

function handleExcludeGenre(genre: string) {
  filters.addExcludedGenre(genre)
  similar.applyFilters()
}

function handleExcludeLanguage(language: string) {
  filters.addExcludedLanguage(language)
  similar.applyFilters()
}

function handleDismissed(imdbId: string) {
  if (similar.similarResults) {
    similar.similarResults.results = similar.similarResults.results.filter(
      r => r.imdb_id !== imdbId,
    )
  }
}
</script>

<template>
  <div class="d-flex" style="min-height: calc(100vh - 64px)">
    <!-- Persistent filter sidebar -->
    <FilterDrawer />

    <!-- Main content area -->
    <div class="flex-grow-1 pa-4 overflow-auto">
      <!-- Search bar -->
      <v-autocomplete
        :model-value="similar.selectedSeed"
        :items="similar.searchResults"
        :loading="similar.searchLoading"
        item-value="imdb_id"
        return-object
        no-filter
        clearable
        placeholder="Search for a movie or series..."
        prepend-inner-icon="mdi-magnify"
        variant="outlined"
        density="comfortable"
        hide-details
        class="mb-4"
        style="max-width: 600px"
        @update:search="onSearchUpdate"
        @update:model-value="onSeedSelected"
      >
        <template #item="{ item, props: itemProps }">
          <v-list-item v-bind="itemProps" :title="undefined">
            <v-list-item-title>
              {{ item.title }}
              <span v-if="item.year" class="text-medium-emphasis ml-1">({{ item.year }})</span>
            </v-list-item-title>
            <template #append>
              <v-chip size="x-small" variant="tonal" class="mr-1">{{ formatType(item.title_type) }}</v-chip>
              <v-chip v-if="item.is_rated" size="x-small" color="success" variant="flat">Rated</v-chip>
            </template>
          </v-list-item>
        </template>
        <template #selection="{ item }">
          {{ item.title }}
          <span v-if="item.year" class="text-medium-emphasis ml-1">({{ item.year }})</span>
        </template>
      </v-autocomplete>

      <!-- Seed summary + sort bar -->
      <div v-if="similar.selectedSeed && similar.similarResults" class="d-flex align-center ga-2 mb-3">
        <v-icon size="20">mdi-movie-star</v-icon>
        <span class="font-weight-bold">{{ similar.similarResults.seed_title }}</span>
        <span class="text-caption text-medium-emphasis">
          Showing {{ sortedResults.length }} of {{ similar.similarResults.total_candidates }}
        </span>
        <v-spacer />
        <v-select
          v-model="sortBy"
          :items="sortOptions"
          item-title="label"
          item-value="value"
          density="compact"
          hide-details
          variant="outlined"
          style="max-width: 180px"
          prepend-inner-icon="mdi-sort"
        />
      </div>

      <!-- Loading -->
      <v-progress-linear
        v-if="similar.loading"
        indeterminate
        color="primary"
        class="mb-3"
        height="2"
      />

      <!-- Error -->
      <v-alert v-if="similar.error" type="error" closable class="mb-4" @click:close="similar.clearError()">
        {{ similar.error }}
      </v-alert>

      <!-- Empty state: no seed selected -->
      <div v-if="!similar.selectedSeed && !similar.loading" class="text-center py-16">
        <v-icon size="80" color="primary" class="mb-6 opacity-50">mdi-movie-search</v-icon>
        <h2 class="text-h5 font-weight-bold mb-2">Find Similar Titles</h2>
        <p class="text-body-1 text-medium-emphasis">
          Search for a movie or series above to discover similar titles
        </p>
      </div>

      <!-- Loading skeletons -->
      <div v-else-if="similar.loading && !similar.similarResults" class="card-grid">
        <v-skeleton-loader v-for="i in 8" :key="i" type="card" />
      </div>

      <!-- Results grid -->
      <div v-else-if="sortedResults.length" class="card-grid">
        <RecommendationCard
          v-for="item in sortedResults"
          :key="item.imdb_id ?? item.title"
          :recommendation="item"
          @dismissed="handleDismissed"
          @exclude-genre="handleExcludeGenre"
          @exclude-language="handleExcludeLanguage"
        />
      </div>

      <!-- No results -->
      <v-alert
        v-else-if="similar.similarResults && !sortedResults.length && !similar.loading"
        type="info"
        variant="tonal"
      >
        No similar titles found. Try adjusting your filters.
      </v-alert>
    </div>
  </div>
</template>

<style scoped>
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}
</style>
