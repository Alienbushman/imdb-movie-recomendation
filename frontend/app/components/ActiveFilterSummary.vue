<script setup lang="ts">
import { useFiltersStore } from '../stores/filters'

const filters = useFiltersStore()

const emit = defineEmits<{
  removeExcludedGenre: [genre: string]
  removeExcludedLanguage: [language: string]
}>()
</script>

<template>
  <div v-if="filters.activeFilterSummary.length || filters.hasActiveExclusions" data-e2e="active-filter-summary" class="d-flex align-center ga-2 mb-3 flex-wrap">
    <span class="text-caption text-medium-emphasis">Filters:</span>
    <v-chip
      v-for="label in filters.activeFilterSummary"
      :key="label"
      :data-e2e="`active-filter-chip-${label}`"
      size="small"
      color="primary"
      variant="tonal"
    >
      {{ label }}
    </v-chip>
    <template v-if="filters.hasActiveExclusions">
      <span class="text-caption text-medium-emphasis">Excluding:</span>
      <v-chip
        v-for="genre in filters.excludedGenres"
        :key="'eg-' + genre"
        :data-e2e="`excluded-genre-chip-${genre.toLowerCase()}`"
        size="small"
        color="error"
        variant="outlined"
        closable
        @click:close="emit('removeExcludedGenre', genre)"
      >
        {{ genre }}
      </v-chip>
      <v-chip
        v-for="lang in filters.excludedLanguages"
        :key="'el-' + lang"
        :data-e2e="`excluded-language-chip-${lang.toLowerCase()}`"
        size="small"
        color="warning"
        variant="outlined"
        closable
        @click:close="emit('removeExcludedLanguage', lang)"
      >
        {{ lang }}
      </v-chip>
    </template>
  </div>
</template>
