<script setup lang="ts">
import type { Recommendation } from '../types'

defineProps<{
  items: Recommendation[]
  loading: boolean
  hasData: boolean
  gridDense: boolean
}>()

const emit = defineEmits<{
  generate: []
  dismissed: [imdbId: string]
  excludeGenre: [genre: string]
  excludeLanguage: [language: string]
}>()
</script>

<template>
  <!-- Loading indicator during re-filter -->
  <v-progress-linear
    v-if="loading"
    indeterminate
    color="primary"
    class="mb-3"
    height="2"
  />

  <!-- Empty state -->
  <div v-if="!hasData && !loading" data-e2e="empty-state" class="text-center py-16">
    <v-icon size="80" color="primary" class="mb-6 opacity-50">mdi-movie-search</v-icon>
    <h2 class="text-h5 font-weight-bold mb-2">Discover Your Next Favorite</h2>
    <p class="text-body-1 text-medium-emphasis mb-6">
      Generate personalized recommendations based on your IMDB ratings
    </p>
    <v-btn color="primary" size="large" prepend-icon="mdi-play" @click="emit('generate')">
      Get Started
    </v-btn>
  </div>

  <!-- Loading skeletons -->
  <div v-else-if="loading && !hasData" data-e2e="loading-skeletons" class="card-grid">
    <v-skeleton-loader v-for="i in 8" :key="i" type="card" />
  </div>

  <!-- Recommendation grid -->
  <div v-else data-e2e="recommendations-grid" class="card-grid" :class="{ 'card-grid--dense': gridDense }">
    <RecommendationCard
      v-for="rec in items"
      :key="rec.imdb_id ?? rec.title"
      :recommendation="rec"
      @dismissed="emit('dismissed', $event)"
      @exclude-genre="emit('excludeGenre', $event)"
      @exclude-language="emit('excludeLanguage', $event)"
    />
    <v-alert
      v-if="hasData && !items.length && !loading"
      data-e2e="alert-no-results"
      type="info"
      variant="tonal"
      style="grid-column: 1 / -1"
    >
      No recommendations in this category. Try adjusting your filters.
    </v-alert>
  </div>
</template>

<style scoped>
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 16px;
}

.card-grid--dense {
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
}
</style>
