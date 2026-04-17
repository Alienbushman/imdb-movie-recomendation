import type { RecommendationFilters, RecommendationResponse, DismissResponse, DismissedListResponse, PipelineStatus, TitleSearchResult, SimilarResponse, PersonSearchResult, PersonTitlesResponse, WatchlistResponse, WatchlistListResponse, TitleMedia } from '../types'

export function useApi() {
  const config = useRuntimeConfig()
  const baseURL = config.public.apiBase as string

  async function fetchApi<T>(path: string, options?: Parameters<typeof $fetch>[1]): Promise<T> {
    const method = (options?.method as string) || 'GET'
    console.log(`[api] ${method} ${path}`, options?.query ?? '')
    try {
      const result = await $fetch<T>(path, { baseURL, ...options })
      console.log(`[api] ${method} ${path} — OK`)
      return result
    } catch (e) {
      console.error(`[api] ${method} ${path} — FAILED`, e)
      throw e
    }
  }

  function buildFilterQuery(filters?: RecommendationFilters): Record<string, unknown> {
    const query: Record<string, unknown> = {}
    if (!filters) return query
    if (filters.min_year != null) query.min_year = filters.min_year
    if (filters.max_year != null) query.max_year = filters.max_year
    if (filters.genres?.length) query.genres = filters.genres
    if (filters.exclude_genres?.length) query.exclude_genres = filters.exclude_genres
    if (filters.languages?.length) query.languages = filters.languages
    if (filters.exclude_languages?.length) query.exclude_languages = filters.exclude_languages
    if (filters.min_imdb_rating != null) query.min_imdb_rating = filters.min_imdb_rating
    if (filters.min_runtime != null) query.min_runtime = filters.min_runtime
    if (filters.max_runtime != null) query.max_runtime = filters.max_runtime
    if (filters.min_predicted_score != null) query.min_predicted_score = filters.min_predicted_score
    if (filters.top_n_movies != null) query.top_n_movies = filters.top_n_movies
    if (filters.top_n_series != null) query.top_n_series = filters.top_n_series
    if (filters.top_n_anime != null) query.top_n_anime = filters.top_n_anime
    if (filters.min_vote_count != null) query.min_vote_count = filters.min_vote_count
    if (filters.keywords?.length) query.keywords = filters.keywords
    if (filters.exclude_keywords?.length) query.exclude_keywords = filters.exclude_keywords
    return query
  }

  function getRecommendations(filters?: RecommendationFilters, retrain = false, imdbUrl?: string) {
    const query: Record<string, unknown> = { ...buildFilterQuery(filters), retrain }
    if (imdbUrl) {
      query.imdb_url = imdbUrl
    }
    return fetchApi<RecommendationResponse>('/recommendations', { method: 'POST', query })
  }

  async function uploadWatchlist(file: File): Promise<{ message: string }> {
    const formData = new FormData()
    formData.append('file', file)
    return fetchApi<{ message: string }>('/upload-watchlist', {
      method: 'POST',
      body: formData,
    })
  }

  function filterRecommendations(filters?: RecommendationFilters) {
    const query = buildFilterQuery(filters)
    return fetchApi<RecommendationResponse>('/recommendations/filter', { method: 'POST', query })
  }

  function dismissTitle(imdbId: string) {
    return fetchApi<DismissResponse>(`/dismiss/${imdbId}`, { method: 'POST' })
  }

  function restoreTitle(imdbId: string) {
    return fetchApi<DismissResponse>(`/dismiss/${imdbId}`, { method: 'DELETE' })
  }

  function getDismissedList() {
    return fetchApi<DismissedListResponse>('/dismissed')
  }

  function addToWatchlist(imdbId: string) {
    return fetchApi<WatchlistResponse>(`/watchlist/${imdbId}`, { method: 'POST' })
  }

  function removeFromWatchlist(imdbId: string) {
    return fetchApi<WatchlistResponse>(`/watchlist/${imdbId}`, { method: 'DELETE' })
  }

  function getWatchlist() {
    return fetchApi<WatchlistListResponse>('/watchlist')
  }

  function getTitleMedia(imdbId: string) {
    return fetchApi<TitleMedia>(`/title/${imdbId}/media`)
  }

  function getPopularKeywords(limit = 60) {
    return fetchApi<string[]>('/keywords/popular', { query: { limit } })
  }

  function downloadDatasets() {
    return fetchApi<{ status: string }>('/download-datasets', { method: 'POST' })
  }

  function getStatus() {
    return fetchApi<PipelineStatus>('/status')
  }

  function searchTitles(query: string, limit = 20) {
    return fetchApi<TitleSearchResult[]>('/search', { query: { q: query, limit } })
  }

  function searchPeople(q: string): Promise<PersonSearchResult[]> {
    if (q.length < 2) return Promise.resolve([])
    return fetchApi<PersonSearchResult[]>('/people/search', { query: { q } })
  }

  function getTitlesByPerson(
    nameId: string,
    filters: Record<string, unknown> = {},
  ): Promise<PersonTitlesResponse> {
    return fetchApi<PersonTitlesResponse>(`/people/${nameId}`, { query: filters })
  }

  function getSimilarTitles(
    imdbId: string,
    filters?: RecommendationFilters,
    topN = 50,
    seen?: boolean | null,
  ) {
    const query: Record<string, unknown> = { ...buildFilterQuery(filters), top_n: topN }
    if (seen != null) query.seen = seen
    return fetchApi<SimilarResponse>(`/similar/${imdbId}`, { query })
  }

  return {
    getRecommendations,
    filterRecommendations,
    uploadWatchlist,
    dismissTitle,
    restoreTitle,
    getDismissedList,
    downloadDatasets,
    getStatus,
    searchTitles,
    getSimilarTitles,
    searchPeople,
    getTitlesByPerson,
    addToWatchlist,
    removeFromWatchlist,
    getWatchlist,
    getTitleMedia,
    getPopularKeywords,
  }
}
