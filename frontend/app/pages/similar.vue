<script setup lang="ts">
import { useSimilarStore } from '../stores/similar'
import { useFiltersStore } from '../stores/filters'
import type { TitleSearchResult } from '../types'

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

// Watch filters for auto-apply (debounced)
let _filterTimer: ReturnType<typeof setTimeout> | null = null
watch(
  () => [
    filters.yearRange,
    filters.selectedGenres,
    filters.excludedGenres,
    filters.selectedLanguages,
    filters.excludedLanguages,
    filters.minImdbRating,
    filters.maxRuntime,
    filters.minVoteCount,
    similar.seenFilter,
  ],
  () => {
    if (!similar.selectedSeed) return
    if (_filterTimer) clearTimeout(_filterTimer)
    _filterTimer = setTimeout(() => {
      similar.applyFilters()
    }, 400)
  },
  { deep: true },
)
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

      <!-- Seed summary -->
      <v-card v-if="similar.selectedSeed && similar.similarResults" variant="tonal" class="mb-4 pa-3">
        <div class="d-flex align-center ga-2">
          <v-icon size="20">mdi-movie-star</v-icon>
          <span class="font-weight-bold">{{ similar.similarResults.seed_title }}</span>
          <v-chip size="x-small" variant="outlined">{{ similar.similarResults.total_candidates }} candidates</v-chip>
        </div>
      </v-card>

      <!-- Seen/Unseen filter -->
      <div v-if="similar.selectedSeed" class="d-flex align-center ga-2 mb-3">
        <span class="text-caption text-medium-emphasis">Show:</span>
        <v-btn-toggle v-model="similar.seenFilter" density="compact" variant="outlined">
          <v-btn :value="null" size="small">All</v-btn>
          <v-btn :value="false" size="small">Unseen</v-btn>
          <v-btn :value="true" size="small">Seen</v-btn>
        </v-btn-toggle>
        <v-spacer />
        <span v-if="similar.similarResults" class="text-caption text-medium-emphasis">
          Showing {{ similar.similarResults.results.length }} results
        </span>
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
      <div v-else-if="similar.similarResults?.results.length" class="card-grid">
        <v-card
          v-for="item in similar.similarResults.results"
          :key="item.imdb_id ?? item.title"
          variant="outlined"
          class="pa-3"
        >
          <div class="d-flex align-center ga-2 mb-2">
            <span class="font-weight-bold text-body-1 flex-grow-1">
              <a
                v-if="item.imdb_url"
                :href="item.imdb_url"
                target="_blank"
                class="text-decoration-none text-on-surface"
              >
                {{ item.title }}
              </a>
              <template v-else>{{ item.title }}</template>
            </span>
            <v-chip size="x-small" variant="tonal">{{ formatType(item.title_type) }}</v-chip>
            <v-chip v-if="item.is_rated" size="x-small" color="success" variant="flat">Seen</v-chip>
          </div>

          <div class="d-flex align-center ga-2 mb-2 text-body-2 text-medium-emphasis">
            <span v-if="item.year">{{ item.year }}</span>
            <span v-if="item.language">{{ item.language }}</span>
            <span v-if="item.director">Dir: {{ item.director }}</span>
          </div>

          <!-- Scores row -->
          <div class="d-flex align-center ga-3 mb-2">
            <v-chip
              size="small"
              :color="item.similarity_score >= 0.5 ? 'success' : item.similarity_score >= 0.3 ? 'warning' : 'default'"
              variant="flat"
            >
              {{ (item.similarity_score * 100).toFixed(0) }}% match
            </v-chip>
            <span v-if="item.imdb_rating" class="text-body-2">
              <v-icon size="14" color="amber">mdi-star</v-icon>
              {{ item.imdb_rating.toFixed(1) }}
            </span>
            <span v-if="item.predicted_score" class="text-body-2">
              Predicted: {{ item.predicted_score.toFixed(1) }}
            </span>
          </div>

          <!-- Genres -->
          <div class="d-flex flex-wrap ga-1 mb-2">
            <v-chip v-for="genre in item.genres" :key="genre" size="x-small" variant="outlined">
              {{ genre }}
            </v-chip>
          </div>

          <!-- Similarity explanation -->
          <div v-if="item.similarity_explanation.length" class="text-caption text-medium-emphasis">
            <div v-for="reason in item.similarity_explanation" :key="reason">
              {{ reason }}
            </div>
          </div>

          <!-- Actors -->
          <div v-if="item.actors.length" class="text-caption text-medium-emphasis mt-1">
            {{ item.actors.join(', ') }}
          </div>
        </v-card>
      </div>

      <!-- No results -->
      <v-alert
        v-else-if="similar.similarResults && !similar.similarResults.results.length && !similar.loading"
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
