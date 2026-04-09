<script setup lang="ts">
import { useRecommendationsStore } from '../stores/recommendations'
import { useSimilarStore } from '../stores/similar'
import { usePersonStore } from '../stores/person'
import {
  useFiltersStore,
  ALL_GENRES,
  ALL_LANGUAGES,
  FILTER_DEFAULTS,
  YEAR_PRESETS,
  CURRENT_YEAR,
  MIN_YEAR_BOUND,
} from '../stores/filters'

const route = useRoute()
const recommendations = useRecommendationsStore()
const similar = useSimilarStore()
const person = usePersonStore()
const filters = useFiltersStore()

const isSimilarPage = computed(() => route.path === '/similar')
const isPersonPage = computed(() => route.path === '/person')

// Search state for genre/language lists
const genreSearch = ref('')
const languageSearch = ref('')

const filteredGenres = computed(() =>
  ALL_GENRES.filter(g => g.toLowerCase().includes(genreSearch.value.toLowerCase())),
)

const filteredLanguages = computed(() =>
  ALL_LANGUAGES.filter(l => l.toLowerCase().includes(languageSearch.value.toLowerCase())),
)

// Genre chip: 3-state — neutral / include / exclude
function getGenreState(genre: string): 'include' | 'exclude' | 'neutral' {
  if (filters.selectedGenres.includes(genre)) return 'include'
  if (filters.excludedGenres.includes(genre)) return 'exclude'
  return 'neutral'
}

function toggleGenre(genre: string) {
  const state = getGenreState(genre)
  if (state === 'neutral') {
    filters.selectedGenres = [...filters.selectedGenres, genre]
  }
  else if (state === 'include') {
    filters.selectedGenres = filters.selectedGenres.filter(g => g !== genre)
    filters.addExcludedGenre(genre)
  }
  else {
    filters.removeExcludedGenre(genre)
  }
  scheduleApply()
}

function genreChipColor(genre: string) {
  const state = getGenreState(genre)
  if (state === 'include') return 'primary'
  if (state === 'exclude') return 'error'
  return undefined
}

function genreChipVariant(genre: string) {
  return getGenreState(genre) === 'neutral' ? 'outlined' : 'flat'
}

// Language chip: 3-state — neutral / include / exclude (same as genre)
function getLanguageState(lang: string): 'include' | 'exclude' | 'neutral' {
  if (filters.selectedLanguages.includes(lang)) return 'include'
  if (filters.excludedLanguages.includes(lang)) return 'exclude'
  return 'neutral'
}

function toggleLanguage(lang: string) {
  const state = getLanguageState(lang)
  if (state === 'neutral') {
    filters.selectedLanguages = [...filters.selectedLanguages, lang]
  }
  else if (state === 'include') {
    filters.selectedLanguages = filters.selectedLanguages.filter(l => l !== lang)
    filters.addExcludedLanguage(lang)
  }
  else {
    filters.removeExcludedLanguage(lang)
  }
  scheduleApply()
}

function languageChipColor(lang: string) {
  const state = getLanguageState(lang)
  if (state === 'include') return 'primary'
  if (state === 'exclude') return 'error'
  return undefined
}

function languageChipVariant(lang: string) {
  return getLanguageState(lang) === 'neutral' ? 'outlined' : 'flat'
}

// Year preset
function applyYearPreset(preset: { min: number, max: number }) {
  if (preset.min === MIN_YEAR_BOUND && preset.max === CURRENT_YEAR) {
    filters.minYear = undefined
    filters.maxYear = undefined
  }
  else {
    filters.minYear = preset.min
    filters.maxYear = Math.min(preset.max, CURRENT_YEAR)
  }
  scheduleApply()
}

// Debounced auto-apply (400ms)
let _debounceTimer: ReturnType<typeof setTimeout> | null = null
function scheduleApply() {
  if (_debounceTimer) clearTimeout(_debounceTimer)
  _debounceTimer = setTimeout(() => {
    if (isSimilarPage.value) {
      similar.applyFilters()
    } else if (isPersonPage.value) {
      person.applyFilters()
    } else if (recommendations.pipelineReady) {
      recommendations.applyFilters()
    }
  }, 400)
}

// Watch all reactive filter values
watch(
  () => [
    filters.yearRange,
    filters.selectedGenres,
    filters.excludedGenres,
    filters.selectedLanguages,
    filters.excludedLanguages,
    filters.minImdbRating,
    filters.maxRuntime,
    filters.minPredictedScore,
    filters.topNMovies,
    filters.topNSeries,
    filters.topNAnime,
    filters.minVoteCount,
  ],
  () => scheduleApply(),
  { deep: true },
)

watch(
  () => similar.seenFilter,
  () => {
    if (isSimilarPage.value) scheduleApply()
  },
)

function resetAndApply() {
  filters.resetFilters()
  genreSearch.value = ''
  languageSearch.value = ''
  if (isSimilarPage.value) {
    similar.seenFilter = null
    similar.applyFilters()
  } else if (isPersonPage.value) {
    person.applyFilters()
  } else if (recommendations.pipelineReady) {
    recommendations.applyFilters()
  }
}

// Expansion panel open state — genres + quality open by default
const openPanels = ref(['genres', 'quality'])
</script>

<template>
  <v-navigation-drawer
    data-e2e="filter-drawer"
    permanent
    location="left"
    width="300"
    class="filter-sidebar"
  >
    <div class="d-flex align-center pa-3 pb-1">
      <span class="text-subtitle-1 font-weight-bold">Filters</span>
      <v-chip v-if="filters.hasActiveFilters" size="x-small" color="primary" class="ml-2">active</v-chip>
      <v-spacer />
      <v-btn
        data-e2e="btn-filter-reset"
        size="small"
        variant="text"
        :disabled="!filters.hasActiveFilters"
        @click="resetAndApply"
      >
        Reset
      </v-btn>
    </div>

    <v-divider class="mb-1" />

    <v-expansion-panels v-model="openPanels" multiple variant="accordion" flat>

      <!-- Seen/Unseen filter (similar page only) -->
      <v-expansion-panel v-if="isSimilarPage" value="seen">
        <v-expansion-panel-title class="filter-section-title">Seen Status</v-expansion-panel-title>
        <v-expansion-panel-text>
          <v-btn-toggle v-model="similar.seenFilter" density="compact" color="primary" class="mb-2">
            <v-btn :value="null" size="small">All</v-btn>
            <v-btn :value="false" size="small">Unseen Only</v-btn>
            <v-btn :value="true" size="small">Seen Only</v-btn>
          </v-btn-toggle>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Results per category -->
      <v-expansion-panel value="results">
        <v-expansion-panel-title class="filter-section-title">Results per Category</v-expansion-panel-title>
        <v-expansion-panel-text>
          <div class="d-flex flex-column ga-2 mt-1">
            <div class="d-flex align-center ga-3">
              <span class="text-body-2 flex-shrink-0" style="width: 76px">Movies</span>
              <v-text-field
                v-model.number="filters.topNMovies"
                data-e2e="input-top-n-movies"
                type="number"
                :min="0"
                :max="100"
                :placeholder="'20'"
                density="compact"
                hide-details
                clearable
                style="max-width: 100px"
              />
            </div>
            <div class="d-flex align-center ga-3">
              <span class="text-body-2 flex-shrink-0" style="width: 76px">Series</span>
              <v-text-field
                v-model.number="filters.topNSeries"
                data-e2e="input-top-n-series"
                type="number"
                :min="0"
                :max="100"
                :placeholder="'10'"
                density="compact"
                hide-details
                clearable
                style="max-width: 100px"
              />
            </div>
            <div class="d-flex align-center ga-3">
              <span class="text-body-2 flex-shrink-0" style="width: 76px">Anime</span>
              <v-text-field
                v-model.number="filters.topNAnime"
                data-e2e="input-top-n-anime"
                type="number"
                :min="0"
                :max="100"
                :placeholder="'10'"
                density="compact"
                hide-details
                clearable
                style="max-width: 100px"
              />
            </div>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Date & Runtime -->
      <v-expansion-panel value="date">
        <v-expansion-panel-title class="filter-section-title">Date &amp; Runtime</v-expansion-panel-title>
        <v-expansion-panel-text>
          <p class="text-caption text-medium-emphasis mb-1">
            Year: {{ filters.yearRange[0] }} – {{ filters.yearRange[1] }}
          </p>
          <v-range-slider
            v-model="filters.yearRange"
            data-e2e="slider-year-range"
            :min="MIN_YEAR_BOUND"
            :max="CURRENT_YEAR"
            :step="1"
            thumb-label="always"
            hide-details
            class="mt-4 mb-1"
          />
          <div class="d-flex ga-1 flex-wrap mt-2">
            <v-chip
              v-for="preset in YEAR_PRESETS"
              :key="preset.label"
              size="x-small"
              variant="outlined"
              @click="applyYearPreset(preset)"
            >
              {{ preset.label }}
            </v-chip>
          </div>

          <p class="text-caption text-medium-emphasis mt-3 mb-1">
            Max Runtime: {{ filters.maxRuntime }}min
          </p>
          <v-slider
            v-model="filters.maxRuntime"
            data-e2e="slider-max-runtime"
            :min="30"
            :max="FILTER_DEFAULTS.maxRuntime"
            :step="10"
            hide-details
            thumb-label
          />
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Genres -->
      <v-expansion-panel value="genres">
        <v-expansion-panel-title class="filter-section-title">
          Genres
          <v-chip
            v-if="filters.selectedGenres.length || filters.excludedGenres.length"
            size="x-small"
            color="primary"
            class="ml-2"
          >
            {{ filters.selectedGenres.length + filters.excludedGenres.length }}
          </v-chip>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <p class="text-caption text-medium-emphasis mb-2">
            Click once to include, again to exclude, again to clear.
          </p>
          <v-text-field
            v-model="genreSearch"
            placeholder="Search genres..."
            density="compact"
            hide-details
            prepend-inner-icon="mdi-magnify"
            clearable
            class="mb-2"
          />
          <div class="d-flex flex-wrap ga-1">
            <v-chip
              v-for="genre in filteredGenres"
              :key="genre"
              :data-e2e="`genre-chip-${genre.toLowerCase()}`"
              size="small"
              :color="genreChipColor(genre)"
              :variant="genreChipVariant(genre)"
              class="genre-chip"
              @click="toggleGenre(genre)"
            >
              {{ genre }}
            </v-chip>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Language -->
      <v-expansion-panel value="language">
        <v-expansion-panel-title class="filter-section-title">
          Language
          <v-chip
            v-if="filters.selectedLanguages.length || filters.excludedLanguages.length"
            size="x-small"
            color="primary"
            class="ml-2"
          >
            {{ filters.selectedLanguages.length + filters.excludedLanguages.length }}
          </v-chip>
        </v-expansion-panel-title>
        <v-expansion-panel-text>
          <p class="text-caption text-medium-emphasis mb-2">
            Click once to include, again to exclude, again to clear.
          </p>
          <v-text-field
            v-model="languageSearch"
            placeholder="Search languages..."
            density="compact"
            hide-details
            prepend-inner-icon="mdi-magnify"
            clearable
            class="mb-2"
          />
          <div class="d-flex flex-wrap ga-1">
            <v-chip
              v-for="lang in filteredLanguages"
              :key="lang"
              size="small"
              :color="languageChipColor(lang)"
              :variant="languageChipVariant(lang)"
              class="genre-chip"
              @click="toggleLanguage(lang)"
            >
              {{ lang }}
            </v-chip>
          </div>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Quality -->
      <v-expansion-panel value="quality">
        <v-expansion-panel-title class="filter-section-title">Quality</v-expansion-panel-title>
        <v-expansion-panel-text>
          <p class="text-caption text-medium-emphasis mb-1">
            Min IMDB Rating: {{ filters.minImdbRating.toFixed(1) }}
          </p>
          <v-slider
            v-model="filters.minImdbRating"
            data-e2e="slider-min-imdb-rating"
            :min="0"
            :max="10"
            :step="0.5"
            hide-details
            thumb-label
            class="mb-3"
          />

          <p class="text-caption text-medium-emphasis mb-1">
            Min Predicted Score: {{ filters.minPredictedScore.toFixed(1) }}
          </p>
          <v-slider
            v-model="filters.minPredictedScore"
            data-e2e="slider-min-predicted-score"
            :min="1"
            :max="10"
            :step="0.5"
            hide-details
            thumb-label
            class="mb-3"
          />

          <p class="text-caption text-medium-emphasis mb-1">
            Min Vote Count: {{ filters.minVoteCount.toLocaleString() }}
          </p>
          <v-slider
            v-model="filters.minVoteCount"
            data-e2e="slider-min-vote-count"
            :min="0"
            :max="500000"
            :step="1000"
            hide-details
            thumb-label
          >
            <template #prepend>
              <v-btn
                icon="mdi-minus"
                size="x-small"
                variant="text"
                :disabled="filters.minVoteCount <= 0"
                @click="filters.minVoteCount = Math.max(0, filters.minVoteCount - 1000)"
              />
            </template>
            <template #append>
              <v-btn
                icon="mdi-plus"
                size="x-small"
                variant="text"
                :disabled="filters.minVoteCount >= 500000"
                @click="filters.minVoteCount = Math.min(500000, filters.minVoteCount + 1000)"
              />
            </template>
          </v-slider>
        </v-expansion-panel-text>
      </v-expansion-panel>

      <!-- Extension point for page-specific filter panels -->
      <slot name="extra-panels" />
    </v-expansion-panels>
  </v-navigation-drawer>
</template>

<style scoped>
.filter-sidebar {
  border-right: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.filter-section-title {
  font-size: 0.8125rem;
  font-weight: 600;
  min-height: 40px !important;
}

.genre-chip {
  cursor: pointer;
}
</style>
