import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import type { WatchlistedTitle } from '../types'

export const useWatchlistStore = defineStore('watchlist', () => {
  const api = useApi()

  const ids = ref<Set<string>>(new Set())
  const titles = ref<WatchlistedTitle[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const pendingIds = ref<Set<string>>(new Set())

  const count = computed(() => ids.value.size)

  function has(imdbId: string | null | undefined): boolean {
    if (!imdbId) return false
    return ids.value.has(imdbId)
  }

  async function fetchList() {
    loading.value = true
    error.value = null
    try {
      const res = await api.getWatchlist()
      ids.value = new Set(res.watchlist_ids)
      titles.value = res.watchlist_titles || []
    } catch (e: unknown) {
      const err = e as { data?: { detail?: string }; message?: string }
      error.value = err.data?.detail || err.message || 'Failed to load watchlist'
    } finally {
      loading.value = false
    }
  }

  async function add(imdbId: string) {
    if (!imdbId || ids.value.has(imdbId)) return
    pendingIds.value.add(imdbId)
    ids.value.add(imdbId)
    try {
      await api.addToWatchlist(imdbId)
    } catch (e) {
      ids.value.delete(imdbId)
      console.error('[watchlist] add failed:', imdbId, e)
      throw e
    } finally {
      pendingIds.value.delete(imdbId)
    }
  }

  async function remove(imdbId: string) {
    if (!imdbId || !ids.value.has(imdbId)) return
    pendingIds.value.add(imdbId)
    const prev = titles.value
    ids.value.delete(imdbId)
    titles.value = titles.value.filter(t => t.imdb_id !== imdbId)
    try {
      await api.removeFromWatchlist(imdbId)
    } catch (e) {
      ids.value.add(imdbId)
      titles.value = prev
      console.error('[watchlist] remove failed:', imdbId, e)
      throw e
    } finally {
      pendingIds.value.delete(imdbId)
    }
  }

  async function toggle(imdbId: string) {
    if (ids.value.has(imdbId)) {
      await remove(imdbId)
    } else {
      await add(imdbId)
    }
  }

  function isPending(imdbId: string | null | undefined): boolean {
    if (!imdbId) return false
    return pendingIds.value.has(imdbId)
  }

  return {
    ids,
    titles,
    loading,
    error,
    count,
    has,
    isPending,
    fetchList,
    add,
    remove,
    toggle,
  }
})
