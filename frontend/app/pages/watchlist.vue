<script setup lang="ts">
import { useWatchlistStore } from '../stores/watchlist'

const store = useWatchlistStore()

onMounted(() => {
  store.fetchList()
})

async function handleRemove(imdbId: string) {
  try {
    await store.remove(imdbId)
  } catch {
    // error handled inside store
  }
}
</script>

<template>
  <div class="pa-4">
    <div class="d-flex align-center mb-4">
      <v-icon icon="mdi-bookmark-multiple" color="primary" class="me-2" />
      <h1 data-e2e="watchlist-title" class="text-h5 font-weight-bold">My Watchlist</h1>
      <v-chip v-if="store.count" size="small" class="ms-3" color="primary" variant="tonal">
        {{ store.count }}
      </v-chip>
      <v-spacer />
      <v-btn data-e2e="btn-back-to-recommendations" variant="text" to="/" prepend-icon="mdi-arrow-left">
        Back to Recommendations
      </v-btn>
    </div>

    <v-progress-linear
      v-if="store.loading"
      data-e2e="watchlist-loading"
      indeterminate
      color="primary"
      class="mb-4"
      height="2"
    />

    <v-alert v-if="store.error" type="error" variant="tonal" class="mb-4">
      {{ store.error }}
    </v-alert>

    <v-alert
      v-if="!store.loading && !store.titles.length && !store.error"
      data-e2e="watchlist-empty"
      type="info"
      variant="tonal"
    >
      Your watchlist is empty. Tap the bookmark icon on any recommendation to save it here.
    </v-alert>

    <v-row v-else dense>
      <v-col
        v-for="item in store.titles"
        :key="item.imdb_id"
        cols="12"
        sm="6"
        md="4"
        lg="3"
      >
        <v-card
          :data-e2e="`watchlist-item-${item.imdb_id}`"
          class="h-100 d-flex flex-column watchlist-card"
          variant="elevated"
          rounded="lg"
        >
          <v-card-item>
            <v-card-title class="text-body-1 font-weight-bold text-wrap">
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
            </v-card-title>
            <v-card-subtitle class="d-flex align-center ga-1 flex-wrap mt-1">
              <span v-if="item.year" class="text-caption">{{ item.year }}</span>
              <v-chip v-if="item.title_type" size="x-small" label>{{ item.title_type }}</v-chip>
              <v-chip
                v-if="item.imdb_rating != null"
                size="x-small"
                color="warning"
                variant="flat"
                prepend-icon="mdi-star"
              >
                {{ item.imdb_rating.toFixed(1) }}
              </v-chip>
              <v-chip
                v-if="item.predicted_score != null"
                size="x-small"
                color="success"
                variant="flat"
              >
                ★ {{ item.predicted_score.toFixed(1) }}
              </v-chip>
            </v-card-subtitle>
          </v-card-item>

          <v-card-text class="flex-grow-1 pt-0">
            <div class="d-flex flex-wrap ga-1 mb-2">
              <v-chip
                v-for="genre in item.genres.slice(0, 3)"
                :key="genre"
                size="x-small"
                variant="tonal"
              >
                {{ genre }}
              </v-chip>
            </div>
            <div v-if="item.director" class="text-caption text-medium-emphasis">
              Directed by {{ item.director }}
            </div>
            <div v-if="item.actors?.length" class="text-caption text-medium-emphasis text-truncate">
              {{ item.actors.slice(0, 3).join(', ') }}
            </div>
          </v-card-text>

          <v-card-actions>
            <v-btn
              :data-e2e="`btn-remove-watchlist-${item.imdb_id}`"
              size="small"
              variant="text"
              color="error"
              prepend-icon="mdi-bookmark-remove"
              :loading="store.isPending(item.imdb_id)"
              @click="handleRemove(item.imdb_id)"
            >
              Remove
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<style scoped>
.watchlist-card {
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}
.watchlist-card:hover {
  transform: translateY(-2px);
}
</style>
