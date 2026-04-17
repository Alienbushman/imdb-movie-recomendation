import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { PersonSearchResult, PersonTitlesResponse } from '../types'
import { useFiltersStore, FILTER_DEFAULTS } from './filters'

export const usePersonStore = defineStore('person', () => {
  const api = useApi()
  const filters = useFiltersStore()

  const searchResults = ref<PersonSearchResult[]>([])
  const searchLoading = ref(false)
  const selectedPerson = ref<PersonSearchResult | null>(null)
  const personResults = ref<PersonTitlesResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function search(query: string) {
    if (!query || query.length < 2) {
      searchResults.value = []
      return
    }
    searchLoading.value = true
    try {
      searchResults.value = await api.searchPeople(query)
    } catch {
      searchResults.value = []
    } finally {
      searchLoading.value = false
    }
  }

  async function fetchTitles() {
    if (!selectedPerson.value) return
    loading.value = true
    error.value = null
    try {
      const params: Record<string, unknown> = {}
      if (filters.minYear) params.min_year = filters.minYear
      if (filters.maxYear) params.max_year = filters.maxYear
      if (filters.minImdbRating > FILTER_DEFAULTS.minImdbRating) params.min_rating = filters.minImdbRating
      if (filters.minVoteCount > FILTER_DEFAULTS.minVoteCount) params.min_votes = filters.minVoteCount
      if (filters.maxRuntime < FILTER_DEFAULTS.maxRuntime) params.max_runtime = filters.maxRuntime
      personResults.value = await api.getTitlesByPerson(selectedPerson.value.name_id, params)
    } catch (e: unknown) {
      const err = e as { data?: { detail?: string }; message?: string }
      error.value = err.data?.detail || err.message || 'Failed to load titles. Has the pipeline been run?'
      personResults.value = null
    } finally {
      loading.value = false
    }
  }

  function selectPerson(person: PersonSearchResult | null) {
    selectedPerson.value = person
    personResults.value = null
    error.value = null
  }

  async function selectPersonById(selection: PersonSearchResult) {
    selectPerson(selection)
    await fetchTitles()
  }

  async function applyFilters() {
    if (selectedPerson.value) {
      await fetchTitles()
    }
  }

  function handleDismissed(imdbId: string) {
    if (!personResults.value) return
    personResults.value.results = personResults.value.results.filter(
      r => r.imdb_id !== imdbId,
    )
  }

  function clearError() {
    error.value = null
  }

  return {
    searchResults,
    searchLoading,
    selectedPerson,
    personResults,
    loading,
    error,
    search,
    fetchTitles,
    selectPerson,
    selectPersonById,
    applyFilters,
    handleDismissed,
    clearError,
  }
})
