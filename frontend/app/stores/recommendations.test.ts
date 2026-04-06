import { ref, computed } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { RecommendationResponse } from '../types'

// Stub Nuxt auto-imports so the store module can resolve them
const mockApi = {
  getRecommendations: vi.fn(),
  filterRecommendations: vi.fn(),
}
vi.stubGlobal('ref', ref)
vi.stubGlobal('computed', computed)
vi.stubGlobal('useApi', () => mockApi)

// Import stores after globals are in place
import { useRecommendationsStore } from './recommendations'
import { useFiltersStore } from './filters'

function makeFakeResponse(overrides: Partial<RecommendationResponse> = {}): RecommendationResponse {
  return {
    movies: [
      { title: 'Movie A', title_type: 'movie', year: 2020, genres: ['Action'], predicted_score: 8, imdb_rating: 7.5, explanation: [], actors: [], director: null, similar_to: [], language: null, imdb_id: 'tt0000001', imdb_url: null, num_votes: 0 },
    ],
    series: [
      { title: 'Series B', title_type: 'tvSeries', year: 2021, genres: ['Drama'], predicted_score: 7, imdb_rating: 8, explanation: [], actors: [], director: null, similar_to: [], language: null, imdb_id: 'tt0000002', imdb_url: null, num_votes: 0 },
    ],
    anime: [],
    model_accuracy: 0.85,
    ...overrides,
  }
}

describe('useRecommendationsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  describe('initial state', () => {
    it('starts with no data and loading false', () => {
      const store = useRecommendationsStore()
      expect(store.data).toBeNull()
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
      expect(store.tab).toBe('movies')
      expect(store.pipelineReady).toBe(false)
      expect(store.lastOperation).toBeNull()
    })
  })

  describe('currentList', () => {
    it('returns empty array when data is null', () => {
      const store = useRecommendationsStore()
      expect(store.currentList).toEqual([])
    })

    it('returns movies when tab is movies', () => {
      const store = useRecommendationsStore()
      const resp = makeFakeResponse()
      store.data = resp
      store.tab = 'movies'
      expect(store.currentList).toEqual(resp.movies)
    })

    it('returns series when tab is series', () => {
      const store = useRecommendationsStore()
      const resp = makeFakeResponse()
      store.data = resp
      store.tab = 'series'
      expect(store.currentList).toEqual(resp.series)
    })

    it('returns anime when tab is anime', () => {
      const store = useRecommendationsStore()
      const resp = makeFakeResponse()
      store.data = resp
      store.tab = 'anime'
      expect(store.currentList).toEqual([])
    })
  })

  describe('generate', () => {
    it('calls API and stores the response', async () => {
      const resp = makeFakeResponse()
      mockApi.getRecommendations.mockResolvedValue(resp)

      const store = useRecommendationsStore()
      await store.generate()

      expect(mockApi.getRecommendations).toHaveBeenCalledOnce()
      expect(store.data).toEqual(resp)
      expect(store.pipelineReady).toBe(true)
      expect(store.lastOperation).toBe('generate')
      expect(store.loading).toBe(false)
      expect(store.error).toBeNull()
    })

    it('passes filters from filters store to the API', async () => {
      mockApi.getRecommendations.mockResolvedValue(makeFakeResponse())

      const filtersStore = useFiltersStore()
      filtersStore.minYear = 2015

      const store = useRecommendationsStore()
      await store.generate()

      const passedFilters = mockApi.getRecommendations.mock.calls[0]![0]
      expect(passedFilters).toMatchObject({ min_year: 2015 })
    })

    it('passes retrain flag to the API', async () => {
      mockApi.getRecommendations.mockResolvedValue(makeFakeResponse())

      const store = useRecommendationsStore()
      await store.generate(true)

      expect(mockApi.getRecommendations.mock.calls[0]![1]).toBe(true)
    })

    it('sets error on API failure', async () => {
      mockApi.getRecommendations.mockRejectedValue({
        data: { detail: 'No watchlist found' },
      })

      const store = useRecommendationsStore()
      await store.generate()

      expect(store.error).toBe('No watchlist found')
      expect(store.data).toBeNull()
      expect(store.loading).toBe(false)
    })

    it('uses message when detail is absent', async () => {
      mockApi.getRecommendations.mockRejectedValue({
        message: 'Network error',
      })

      const store = useRecommendationsStore()
      await store.generate()

      expect(store.error).toBe('Network error')
    })

    it('uses fallback message when no detail or message', async () => {
      mockApi.getRecommendations.mockRejectedValue({})

      const store = useRecommendationsStore()
      await store.generate()

      expect(store.error).toBe('Failed to generate recommendations')
    })
  })

  describe('applyFilters', () => {
    it('delegates to generate when pipeline is not ready', async () => {
      const resp = makeFakeResponse()
      mockApi.getRecommendations.mockResolvedValue(resp)

      const store = useRecommendationsStore()
      expect(store.pipelineReady).toBe(false)

      await store.applyFilters()

      expect(mockApi.getRecommendations).toHaveBeenCalledOnce()
      expect(mockApi.filterRecommendations).not.toHaveBeenCalled()
      expect(store.data).toEqual(resp)
    })

    it('calls filterRecommendations when pipeline is ready', async () => {
      const genResp = makeFakeResponse()
      const filterResp = makeFakeResponse({ model_accuracy: 0.9 })
      mockApi.getRecommendations.mockResolvedValue(genResp)
      mockApi.filterRecommendations.mockResolvedValue(filterResp)

      const store = useRecommendationsStore()
      await store.generate() // make pipeline ready
      await store.applyFilters()

      expect(mockApi.filterRecommendations).toHaveBeenCalledOnce()
      expect(store.data).toEqual(filterResp)
      expect(store.lastOperation).toBe('filter')
    })

    it('falls back to generate on 409 (no cached scores)', async () => {
      const genResp = makeFakeResponse()
      mockApi.getRecommendations.mockResolvedValue(genResp)
      mockApi.filterRecommendations.mockRejectedValue({
        status: 409,
        data: { detail: 'No scored results available' },
      })

      const store = useRecommendationsStore()
      store.pipelineReady = true // simulate ready state
      await store.applyFilters()

      // Should have called filterRecommendations first, then fallen back to generate
      expect(mockApi.filterRecommendations).toHaveBeenCalledOnce()
      expect(mockApi.getRecommendations).toHaveBeenCalledOnce()
      expect(store.data).toEqual(genResp)
    })

    it('sets error on non-"No scored results" API failure', async () => {
      mockApi.getRecommendations.mockResolvedValue(makeFakeResponse())
      mockApi.filterRecommendations.mockRejectedValue({
        data: { detail: 'Internal server error' },
      })

      const store = useRecommendationsStore()
      await store.generate()
      await store.applyFilters()

      expect(store.error).toBe('Internal server error')
    })
  })

  describe('handleDismissed', () => {
    it('removes the title from all categories', () => {
      const store = useRecommendationsStore()
      store.data = makeFakeResponse()

      store.handleDismissed('tt0000001')
      expect(store.data!.movies).toEqual([])
      expect(store.data!.series).toHaveLength(1) // unaffected
    })

    it('is a no-op when data is null', () => {
      const store = useRecommendationsStore()
      store.handleDismissed('tt0000001') // should not throw
      expect(store.data).toBeNull()
    })
  })

  describe('clearError', () => {
    it('clears the error', async () => {
      mockApi.getRecommendations.mockRejectedValue({ message: 'fail' })

      const store = useRecommendationsStore()
      await store.generate()
      expect(store.error).toBeTruthy()

      store.clearError()
      expect(store.error).toBeNull()
    })
  })
})
