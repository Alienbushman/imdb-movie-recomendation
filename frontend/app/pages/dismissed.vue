<script setup lang="ts">
import type { DismissedTitle } from '../types'

const api = useApi()

const dismissedTitles = ref<DismissedTitle[]>([])
const loading = ref(true)
const restoringId = ref<string | null>(null)

async function fetchDismissed() {
  loading.value = true
  try {
    const res = await api.getDismissedList()
    dismissedTitles.value = res.dismissed_titles?.length
      ? res.dismissed_titles
      : res.dismissed_ids.map(id => ({
          imdb_id: id,
          title: null,
          year: null,
          title_type: null,
          genres: [],
          imdb_url: `https://www.imdb.com/title/${id}`,
        }))
    console.log('[dismissed] fetched', dismissedTitles.value.length, 'dismissed titles')
  }
  catch (e) {
    console.error('[dismissed] fetch failed:', e)
  }
  finally {
    loading.value = false
  }
}

async function restore(imdbId: string) {
  console.log('[dismissed] restore:', imdbId)
  restoringId.value = imdbId
  try {
    await api.restoreTitle(imdbId)
    dismissedTitles.value = dismissedTitles.value.filter(t => t.imdb_id !== imdbId)
  }
  catch (e) {
    console.error('[dismissed] restore failed:', imdbId, e)
  }
  finally {
    restoringId.value = null
  }
}

onMounted(fetchDismissed)
</script>

<template>
  <div class="pa-4">
    <div class="d-flex align-center mb-4">
      <h1 data-e2e="dismissed-title" class="text-h5 font-weight-bold">Dismissed Titles</h1>
      <v-spacer />
      <v-btn data-e2e="btn-back-to-recommendations" variant="text" to="/" prepend-icon="mdi-arrow-left">
        Back to Recommendations
      </v-btn>
    </div>

    <v-progress-linear v-if="loading" data-e2e="dismissed-loading" indeterminate color="primary" class="mb-4" height="2" />

    <v-alert v-if="!loading && !dismissedTitles.length" data-e2e="dismissed-empty" type="info" variant="tonal">
      No dismissed titles. Dismissed recommendations will appear here.
    </v-alert>

    <v-list v-else data-e2e="dismissed-list" lines="two">
      <v-list-item
        v-for="item in dismissedTitles"
        :key="item.imdb_id"
        :data-e2e="`dismissed-item-${item.imdb_id}`"
        rounded="lg"
        class="mb-1"
      >
        <template #prepend>
          <v-icon color="medium-emphasis">mdi-eye-off</v-icon>
        </template>

        <v-list-item-title>
          <a
            v-if="item.imdb_url"
            :href="item.imdb_url"
            target="_blank"
            rel="noopener"
            class="text-decoration-none text-on-surface"
          >
            {{ item.title || item.imdb_id }}
          </a>
          <span v-else>{{ item.title || item.imdb_id }}</span>
        </v-list-item-title>

        <v-list-item-subtitle class="d-flex align-center ga-1 flex-wrap mt-1">
          <span v-if="item.year" class="text-caption">{{ item.year }}</span>
          <v-chip v-if="item.title_type" size="x-small" label>{{ item.title_type }}</v-chip>
          <v-chip
            v-for="genre in item.genres.slice(0, 3)"
            :key="genre"
            size="x-small"
            variant="tonal"
          >
            {{ genre }}
          </v-chip>
          <span v-if="!item.title" class="text-caption text-medium-emphasis">{{ item.imdb_id }}</span>
        </v-list-item-subtitle>

        <template #append>
          <v-btn
            :data-e2e="`btn-restore-${item.imdb_id}`"
            size="small"
            variant="text"
            color="success"
            prepend-icon="mdi-restore"
            :loading="restoringId === item.imdb_id"
            @click="restore(item.imdb_id)"
          >
            Restore
          </v-btn>
        </template>
      </v-list-item>
    </v-list>
  </div>
</template>
