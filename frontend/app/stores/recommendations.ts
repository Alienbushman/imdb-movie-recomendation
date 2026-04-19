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

  // Progress reporting while a generate() call is running. Populated by polling
  // GET /status; cleared when the pipeline finishes (success or error).
  const generateProgress = ref<{ step: number | null, label: string | null } | null>(null)

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

  // Poll /status until the background pipeline finishes, then fetch results.
  // Tolerates transient status-poll failures (network blips, 502/504 on the proxy,
  // backend restart) by retrying — the pipeline itself runs on a backend daemon
  // thread and continues regardless of the frontend's connection state.
  async function waitForPipelineAndFetch() {
    const POLL_INTERVAL_MS = 1500
    let consecutiveFailures = 0
    const WARN_AFTER_FAILURES = 3  // show a reconnecting note after ~5s of flakes
    while (true) {
      await new Promise(resolve => setTimeout(resolve, POLL_INTERVAL_MS))
      try {
        const status = await api.getStatus()
        consecutiveFailures = 0
        if (status.pipeline_running) {
          generateProgress.value = {
            step: status.pipeline_step,
            label: status.pipeline_step_label,
          }
          continue
        }
        if (status.pipeline_error) {
          throw new Error(status.pipeline_error)
        }
        break
      } catch (e: unknown) {
        // Only bail if it's an error from the pipeline itself (already thrown above).
        // Transient /status failures get retried forever — the backend keeps running.
        if (e instanceof Error && !(e as ApiError).status) {
          // Pipeline-reported error — re-throw.
          throw e
        }
        consecutiveFailures++
        console.warn(`[recommendations] status poll failed (attempt ${consecutiveFailures})`, e)
        if (consecutiveFailures >= WARN_AFTER_FAILURES) {
          generateProgress.value = {
            step: generateProgress.value?.step ?? null,
            label: 'Reconnecting to server…',
          }
        }
        // keep polling indefinitely
      }
    }

    data.value = await api.filterRecommendations(filtersStore.buildFilters())
    pipelineReady.value = true
    lastOperation.value = 'generate'
    console.log('[recommendations] waitForPipelineAndFetch — OK |', data.value.movies.length, 'movies,', data.value.series.length, 'series,', data.value.anime.length, 'anime')
  }

  async function generate(retrain = false, imdbUrl?: string) {
    console.log('[recommendations] generate — retrain:', retrain, '| pipelineReady:', pipelineReady.value)
    if (loading.value) {
      console.log('[recommendations] generate — already running, ignoring duplicate call')
      return
    }
    loading.value = true
    error.value = null
    generateProgress.value = { step: 1, label: 'Starting…' }
    try {
      try {
        await api.startRecommendations(filtersStore.buildFilters(), retrain, imdbUrl)
      } catch (e: unknown) {
        const err = e as ApiError
        // 409 = a pipeline is already running (e.g. after a page refresh mid-run).
        // Attach to it by polling instead of surfacing an error.
        if (err.status !== 409) {
          throw e
        }
        console.log('[recommendations] generate — pipeline already running, attaching to it')
      }
      await waitForPipelineAndFetch()
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, 'Failed to generate recommendations')
      console.error('[recommendations] generate — FAILED:', error.value)
    } finally {
      loading.value = false
      generateProgress.value = null
    }
  }

  // Attach to a pipeline run that's already in progress (e.g. started in a prior
  // tab or before a page refresh). Just polls for progress and fetches results
  // when done — does NOT kick off a new run.
  async function attachToRunningPipeline() {
    console.log('[recommendations] attachToRunningPipeline — attaching to in-flight run')
    if (loading.value) return
    loading.value = true
    error.value = null
    generateProgress.value = { step: 1, label: 'Continuing…' }
    try {
      await waitForPipelineAndFetch()
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, 'Failed to generate recommendations')
      console.error('[recommendations] attachToRunningPipeline — FAILED:', error.value)
    } finally {
      loading.value = false
      generateProgress.value = null
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
    generateProgress,
    currentList,
    generate,
    attachToRunningPipeline,
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
