import { defineStore } from 'pinia'
import type { RecommendationResponse, ContentTab, ApiError, SortOption } from '../types'
import { CONTENT_TABS } from '../types'
import { useFiltersStore } from './filters'

export const useRecommendationsStore = defineStore('recommendations', () => {
  const filtersStore = useFiltersStore()
  const api = useApi()

  const data = ref<RecommendationResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const tab = ref<ContentTab>('movies')
  // pipelineReady tracks whether generate() has been called at least once this session.
  // When false, applyFilters() falls back to generate() since there are no cached scores to filter.
  // Set to true after a successful generate(), never reset to false.
  const pipelineReady = ref(false)
  const lastOperation = ref<'filter' | 'generate' | null>(null)

  const sortBy = ref<Record<ContentTab, SortOption>>({
    movies: 'score',
    series: 'score',
    anime: 'score',
  })

  const currentList = computed(() => {
    if (!data.value) return []
    const list = [...(data.value[tab.value] || [])]
    const sort = sortBy.value[tab.value]
    switch (sort) {
      case 'imdb_rating':
        return list.sort((a, b) => (b.imdb_rating ?? -1) - (a.imdb_rating ?? -1))
      case 'year_desc':
        return list.sort((a, b) => (b.year ?? -1) - (a.year ?? -1))
      case 'year_asc':
        return list.sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999))
      case 'votes':
        return list.sort((a, b) => b.num_votes - a.num_votes)
      case 'title':
        return list.sort((a, b) => a.title.localeCompare(b.title))
      default: // 'score'
        return list.sort((a, b) => b.predicted_score - a.predicted_score)
    }
  })

  function extractErrorMessage(e: unknown, fallback: string): string {
    const err = e as ApiError
    return err.data?.detail || err.message || fallback
  }

  async function generate(retrain = false, imdbUrl?: string) {
    console.log('[recommendations] generate — retrain:', retrain, '| pipelineReady:', pipelineReady.value)
    loading.value = true
    error.value = null
    try {
      data.value = await api.getRecommendations(filtersStore.buildFilters(), retrain, imdbUrl)
      pipelineReady.value = true
      lastOperation.value = 'generate'
      console.log('[recommendations] generate — OK |', data.value.movies.length, 'movies,', data.value.series.length, 'series,', data.value.anime.length, 'anime')
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, 'Failed to generate recommendations')
      console.error('[recommendations] generate — FAILED:', error.value)
    } finally {
      loading.value = false
    }
  }

  async function applyFilters() {
    console.log('[recommendations] applyFilters — pipelineReady:', pipelineReady.value)
    if (!pipelineReady.value) {
      console.log('[recommendations] applyFilters — no cached scores, falling back to generate()')
      return generate()
    }
    loading.value = true
    error.value = null
    let shouldGenerate = false
    try {
      data.value = await api.filterRecommendations(filtersStore.buildFilters())
      lastOperation.value = 'filter'
      console.log('[recommendations] applyFilters — OK |', data.value.movies.length, 'movies,', data.value.series.length, 'series,', data.value.anime.length, 'anime')
    } catch (e: unknown) {
      const err = e as ApiError
      // 409 = backend has no cached scores yet; fall back to full pipeline run
      if (err.status === 409) {
        console.log('[recommendations] applyFilters — 409 from backend, falling back to generate()')
        shouldGenerate = true
      } else {
        error.value = extractErrorMessage(e, 'Failed to filter recommendations')
        console.error('[recommendations] applyFilters — FAILED:', error.value)
      }
    } finally {
      loading.value = false
    }
    if (shouldGenerate) {
      return generate()
    }
  }

  async function loadOrGenerate() {
    console.log('[recommendations] loadOrGenerate — trying fast path first')
    loading.value = true
    error.value = null
    let shouldGenerate = false
    try {
      data.value = await api.filterRecommendations(filtersStore.buildFilters())
      pipelineReady.value = true
      lastOperation.value = 'filter'
      console.log('[recommendations] loadOrGenerate — fast path OK')
    } catch (e: unknown) {
      const err = e as ApiError
      if (err.status === 409) {
        pipelineReady.value = false
        console.log('[recommendations] loadOrGenerate — no cached scores, running full pipeline')
        shouldGenerate = true
      } else {
        error.value = extractErrorMessage(e, 'Failed to load recommendations')
        console.error('[recommendations] loadOrGenerate — FAILED:', error.value)
      }
    } finally {
      loading.value = false
    }
    if (shouldGenerate) {
      return generate()
    }
  }

  function handleDismissed(imdbId: string) {
    console.log('[recommendations] handleDismissed:', imdbId)
    if (!data.value) return
    for (const cat of CONTENT_TABS) {
      data.value[cat] = data.value[cat].filter(r => r.imdb_id !== imdbId)
    }
  }

  function clearError() {
    error.value = null
  }

  return {
    data,
    loading,
    error,
    tab,
    sortBy,
    pipelineReady,
    lastOperation,
    currentList,
    generate,
    loadOrGenerate,
    applyFilters,
    handleDismissed,
    clearError,
  }
}, {
  persist: {
    pick: ['pipelineReady', 'lastOperation', 'sortBy'],
  },
})
