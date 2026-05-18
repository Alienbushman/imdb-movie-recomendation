// T3.13: Pinia store for per-title thumbs feedback.
//
// Mirrors the watchlist store shape so RecommendationCard can use the same
// patterns: `current(id)` returns the recorded kind (or null), `set(id, kind)`
// persists optimistically, `clear(id)` removes the record.

import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { FeedbackEntry, FeedbackKind } from '../types'

export const useFeedbackStore = defineStore('feedback', () => {
  const api = useApi()

  const byId = ref<Record<string, FeedbackKind>>({})
  const loading = ref(false)
  const error = ref<string | null>(null)
  const pendingIds = ref<Set<string>>(new Set())

  const count = computed(() => Object.keys(byId.value).length)

  function current(imdbId: string | null | undefined): FeedbackKind | null {
    if (!imdbId) return null
    return byId.value[imdbId] ?? null
  }

  function isPending(imdbId: string | null | undefined): boolean {
    if (!imdbId) return false
    return pendingIds.value.has(imdbId)
  }

  async function fetchList() {
    loading.value = true
    error.value = null
    try {
      const res = await api.listFeedback()
      const next: Record<string, FeedbackKind> = {}
      for (const e of res.entries as FeedbackEntry[]) next[e.imdb_id] = e.kind
      byId.value = next
    } catch (e: unknown) {
      const err = e as { data?: { detail?: string }; message?: string }
      error.value = err.data?.detail || err.message || 'Failed to load feedback'
    } finally {
      loading.value = false
    }
  }

  function withoutKey(map: Record<string, FeedbackKind>, key: string): Record<string, FeedbackKind> {
    // Build a new object so we don't trip TS's strict-rest-element inference
    // (which would widen the value type to FeedbackKind | undefined).
    const next: Record<string, FeedbackKind> = {}
    for (const k in map) {
      if (k !== key) next[k] = map[k]!
    }
    return next
  }

  async function set(imdbId: string, kind: FeedbackKind) {
    if (!imdbId) return
    const prev = byId.value[imdbId]
    pendingIds.value.add(imdbId)
    byId.value = { ...byId.value, [imdbId]: kind }
    try {
      await api.recordFeedback(imdbId, kind)
    } catch (e) {
      if (prev === undefined) {
        byId.value = withoutKey(byId.value, imdbId)
      } else {
        byId.value = { ...byId.value, [imdbId]: prev }
      }
      console.error('[feedback] set failed:', imdbId, kind, e)
      throw e
    } finally {
      pendingIds.value.delete(imdbId)
    }
  }

  async function clear(imdbId: string) {
    if (!imdbId || !(imdbId in byId.value)) return
    const prev = byId.value[imdbId]!
    pendingIds.value.add(imdbId)
    byId.value = withoutKey(byId.value, imdbId)
    try {
      await api.clearFeedback(imdbId)
    } catch (e) {
      byId.value = { ...byId.value, [imdbId]: prev }
      console.error('[feedback] clear failed:', imdbId, e)
      throw e
    } finally {
      pendingIds.value.delete(imdbId)
    }
  }

  /** Toggle: clicking the same kind twice clears; clicking a different kind switches. */
  async function toggle(imdbId: string, kind: FeedbackKind) {
    if (byId.value[imdbId] === kind) {
      await clear(imdbId)
    } else {
      await set(imdbId, kind)
    }
  }

  return {
    byId,
    loading,
    error,
    count,
    current,
    isPending,
    fetchList,
    set,
    clear,
    toggle,
  }
})
