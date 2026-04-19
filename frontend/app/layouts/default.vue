<script setup lang="ts">
import { useWatchlistStore } from '../stores/watchlist'

const watchlist = useWatchlistStore()

onMounted(() => {
  if (!watchlist.titles.length) {
    watchlist.fetchList()
  }
})
</script>

<template>
  <v-app>
    <v-app-bar data-e2e="app-bar" class="app-bar-gradient" elevation="0" border="b">
      <template #prepend>
        <v-icon color="primary" size="28" class="ml-4">mdi-movie-open-star</v-icon>
      </template>
      <v-app-bar-title>
        <NuxtLink data-e2e="app-title" to="/" class="text-decoration-none text-on-surface font-weight-bold">
          IMDB Recommendations
        </NuxtLink>
      </v-app-bar-title>
      <template #append>
        <v-btn data-e2e="nav-person" to="/person" variant="text" prepend-icon="mdi-account-search">
          By Person
        </v-btn>
        <v-btn data-e2e="nav-similar" to="/similar" variant="text" prepend-icon="mdi-movie-search">
          Find Similar
        </v-btn>
        <v-btn data-e2e="nav-watchlist" to="/watchlist" variant="text" prepend-icon="mdi-bookmark-multiple">
          Watchlist
          <v-badge
            v-if="watchlist.count"
            :content="watchlist.count"
            color="primary"
            inline
            class="ms-2"
          />
        </v-btn>
        <v-btn data-e2e="nav-dismissed" to="/dismissed" variant="text" prepend-icon="mdi-eye-off">
          Dismissed
        </v-btn>
      </template>
    </v-app-bar>

    <v-main>
      <slot />
    </v-main>
  </v-app>
</template>

<style scoped>
.app-bar-gradient {
  background: linear-gradient(135deg, rgb(var(--v-theme-surface)) 0%, rgba(var(--v-theme-primary), 0.08) 100%) !important;
  backdrop-filter: blur(8px);
}
</style>
