<script setup lang="ts">
import { usePersonStore } from '../stores/person'
import { useFiltersStore } from '../stores/filters'
import type { PersonSearchResult, PersonTitleResult } from '../types'
import { toPersonCardItem } from '../types'

const person = usePersonStore()
const filters = useFiltersStore()

// Debounced search
let _searchTimer: ReturnType<typeof setTimeout> | null = null
function onSearchUpdate(query: string) {
  if (_searchTimer) clearTimeout(_searchTimer)
  _searchTimer = setTimeout(() => {
    person.search(query)
  }, 150)
}

function onPersonSelected(selected: PersonSearchResult | null) {
  person.selectPerson(selected)
  if (selected) {
    person.fetchTitles()
  }
}

// Role filter
const roleFilter = ref<'any' | 'director' | 'actor' | 'writer'>('any')

// Seen filter
const seenFilter = ref<'all' | 'unseen' | 'seen'>('all')

// Sort
const sortBy = ref<keyof PersonTitleResult>('predicted_score')
const sortOptions = [
  { title: 'Best Match', value: 'predicted_score' },
  { title: 'IMDB Rating', value: 'imdb_rating' },
  { title: 'Newest', value: 'year' },
  { title: 'Most Votes', value: 'num_votes' },
]

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

function handleExcludeGenre(genre: string) {
  filters.addExcludedGenre(genre)
  person.applyFilters()
}

function handleIncludeLanguage(language: string) {
  filters.addSelectedLanguage(language)
  person.applyFilters()
}

// Deep-link support: if the page was opened with ?name_id=&name= (e.g. from a
// clickable director/actor chip on a card popup), bootstrap the selection and
// load titles immediately.
onMounted(() => {
  const route = useRoute()
  const q = route.query
  if (typeof q.name_id === 'string' && typeof q.name === 'string') {
    person.selectPersonById({
      name_id: q.name_id,
      name: q.name,
      primary_profession: null,
      title_count: 0,
    })
  }
})
</script>

<template>
  <div data-e2e="person-page" class="d-flex" style="min-height: calc(100vh - 64px)">
    <!-- Persistent filter sidebar -->
    <FilterDrawer />

    <!-- Main content area -->
    <div data-e2e="person-content" class="flex-grow-1 pa-4 overflow-auto">
      <!-- Search bar -->
      <v-autocomplete
        :model-value="person.selectedPerson"
        :items="person.searchResults"
        :loading="person.searchLoading"
        data-e2e="person-search"
        item-value="name_id"
        return-object
        no-filter
        clearable
        placeholder="Search for a director or actor..."
        prepend-inner-icon="mdi-account-search"
        variant="outlined"
        density="comfortable"
        hide-details
        class="mb-4"
        style="max-width: 600px"
        @update:search="onSearchUpdate"
        @update:model-value="onPersonSelected"
      >
        <template #item="{ item, props: itemProps }">
          <v-list-item v-bind="itemProps" :title="undefined">
            <v-list-item-title>{{ item.name }}</v-list-item-title>
            <template #append>
              <span class="text-caption text-medium-emphasis ml-2">
                {{ item.primary_profession }} · {{ item.title_count }} titles
              </span>
            </template>
          </v-list-item>
        </template>
        <template #selection="{ item }">
          {{ item.name }}
        </template>
      </v-autocomplete>

      <!-- Results header: person name + count + role toggle + sort -->
      <div v-if="person.selectedPerson && person.personResults" data-e2e="person-results-header" class="d-flex align-center flex-wrap ga-2 mb-3">
        <v-icon size="20">mdi-account-details</v-icon>
        <span data-e2e="person-name" class="font-weight-bold">{{ person.personResults.name }}</span>
        <span data-e2e="person-result-count" class="text-caption text-medium-emphasis">
          Showing {{ filteredResults.length }} of {{ person.personResults.total }}
        </span>
        <v-spacer />
        <v-btn-toggle
          v-model="roleFilter"
          data-e2e="person-role-toggle"
          density="compact"
          color="primary"
          mandatory
        >
          <v-btn data-e2e="person-role-any" value="any" size="small">Any</v-btn>
          <v-btn data-e2e="person-role-director" value="director" size="small">Director</v-btn>
          <v-btn data-e2e="person-role-actor" value="actor" size="small">Actor</v-btn>
          <v-btn data-e2e="person-role-writer" value="writer" size="small">Writer</v-btn>
        </v-btn-toggle>
        <v-btn-toggle
          v-model="seenFilter"
          data-e2e="person-seen-toggle"
          density="compact"
          color="secondary"
          mandatory
        >
          <v-btn data-e2e="person-seen-all" value="all" size="small">All</v-btn>
          <v-btn data-e2e="person-seen-unseen" value="unseen" size="small">Unseen</v-btn>
          <v-btn data-e2e="person-seen-seen" value="seen" size="small">Seen</v-btn>
        </v-btn-toggle>
        <v-select
          v-model="sortBy"
          :items="sortOptions"
          data-e2e="person-sort-select"
          density="compact"
          hide-details
          variant="outlined"
          style="max-width: 180px"
          prepend-inner-icon="mdi-sort"
        />
      </div>

      <!-- Loading -->
      <v-progress-linear
        v-if="person.loading"
        data-e2e="person-loading"
        indeterminate
        color="primary"
        class="mb-3"
        height="2"
      />

      <!-- Error -->
      <v-alert v-if="person.error" data-e2e="person-alert-error" type="error" closable class="mb-4" @click:close="person.clearError()">
        {{ person.error }}
      </v-alert>

      <!-- Empty state: no person selected -->
      <div v-if="!person.selectedPerson && !person.loading" data-e2e="person-empty-state" class="text-center py-16">
        <v-icon size="80" color="primary" class="mb-6 opacity-50">mdi-account-search</v-icon>
        <h2 class="text-h5 font-weight-bold mb-2">Browse by Person</h2>
        <p class="text-body-1 text-medium-emphasis">
          Search for a director or actor above to see their top-ranked titles
        </p>
      </div>

      <!-- Loading skeletons -->
      <div v-else-if="person.loading && !person.personResults" data-e2e="person-loading-skeletons" class="card-grid">
        <v-skeleton-loader v-for="i in 8" :key="i" type="card" />
      </div>

      <!-- Results grid -->
      <div v-else-if="filteredResults.length" data-e2e="person-results-grid" class="card-grid">
        <RecommendationCard
          v-for="item in filteredResults"
          :key="item.imdb_id"
          :item="toPersonCardItem(item)"
          @dismissed="person.handleDismissed"
          @exclude-genre="handleExcludeGenre"
          @include-language="handleIncludeLanguage"
        />
      </div>

      <!-- No results after filtering -->
      <v-alert
        v-else-if="person.personResults && !filteredResults.length && !person.loading"
        data-e2e="person-no-results"
        type="info"
        variant="tonal"
      >
        No titles found. Try adjusting the role filter or other filters.
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
