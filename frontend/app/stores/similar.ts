import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { TitleSearchResult, SimilarResponse } from '../types'
import { useFiltersStore } from './filters'

export const useSimilarStore = defineStore('similar', () => {
  const api = useApi()
  const filters = useFiltersStore()

  // Search state
  const searchResults = ref<TitleSearchResult[]>([])
  const searchLoading = ref(false)

  // Selected seed
  const selectedSeed = ref<TitleSearchResult | null>(null)

  // Similar results
  const similarResults = ref<SimilarResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Seen filter: null = all, true = only seen, false = only unseen
  const seenFilter = ref<boolean | null>(null)

  async function search(query: string) {
    if (!query || query.length < 2) {
      searchResults.value = []
      return
    }
    searchLoading.value = true
    try {
      searchResults.value = await api.searchTitles(query)
    } catch {
      searchResults.value = []
    } finally {
      searchLoading.value = false
    }
  }

  async function fetchSimilar() {
    if (!selectedSeed.value) return
    loading.value = true
    error.value = null
    try {
      similarResults.value = await api.getSimilarTitles(
        selectedSeed.value.imdb_id,
        filters.buildFilters(),
        50,
        seenFilter.value,
      )
    } catch (e: unknown) {
      const err = e as { data?: { detail?: string }; message?: string }
      error.value = err.data?.detail || err.message || 'Failed to fetch similar titles'
      similarResults.value = null
    } finally {
      loading.value = false
    }
  }

  async function applyFilters() {
    if (selectedSeed.value) {
      await fetchSimilar()
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    searchResults,
    searchLoading,
    selectedSeed,
    similarResults,
    loading,
    error,
    seenFilter,
    search,
    fetchSimilar,
    applyFilters,
    clearError,
  }
})
