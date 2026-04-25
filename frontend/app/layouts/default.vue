<script setup lang="ts">
import { useDisplay } from 'vuetify'
import { useWatchlistStore } from '../stores/watchlist'
import { useFiltersStore } from '../stores/filters'

const watchlist = useWatchlistStore()
const filters = useFiltersStore()
const route = useRoute()
const { mobile } = useDisplay()

const FILTER_ROUTES = ['/', '/similar', '/person']
const hasFilterDrawer = computed(() => FILTER_ROUTES.includes(route.path))

function toggleFilterDrawer() {
  filters.drawerOpen = !filters.drawerOpen
}

onMounted(() => {
  if (!watchlist.titles.length) {
    watchlist.fetchList()
  }
})
</script>

<template>
  <v-app>
    <v-app-bar data-e2e="app-bar" class="app-bar-gradient" elevation="0" border="b" density="compact">
      <template #prepend>
        <v-app-bar-nav-icon
          v-if="mobile && hasFilterDrawer"
          data-e2e="btn-toggle-filters"
          icon="mdi-filter-variant"
          aria-label="Toggle filters"
          @click="toggleFilterDrawer"
        />
        <v-icon v-else color="primary" size="28" class="ml-4">mdi-movie-open-star</v-icon>
      </template>
      <v-app-bar-title>
        <NuxtLink data-e2e="app-title" to="/" class="text-decoration-none text-on-surface font-weight-bold app-title">
          <span class="app-title-full">IMDB Recommendations</span>
          <span class="app-title-short">IMDB Recs</span>
        </NuxtLink>
      </v-app-bar-title>
      <template #append>
        <template v-if="!mobile">
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
        <v-menu v-else location="bottom end">
          <template #activator="{ props: menuProps }">
            <v-btn
              v-bind="menuProps"
              data-e2e="nav-menu-toggle"
              icon="mdi-dots-vertical"
              aria-label="Open navigation menu"
            />
          </template>
          <v-list data-e2e="nav-menu-list" density="compact" min-width="220">
            <v-list-item
              data-e2e="nav-person"
              to="/person"
              prepend-icon="mdi-account-search"
              title="By Person"
            />
            <v-list-item
              data-e2e="nav-similar"
              to="/similar"
              prepend-icon="mdi-movie-search"
              title="Find Similar"
            />
            <v-list-item
              data-e2e="nav-watchlist"
              to="/watchlist"
              prepend-icon="mdi-bookmark-multiple"
            >
              <v-list-item-title class="d-flex align-center">
                <span>Watchlist</span>
                <v-badge
                  v-if="watchlist.count"
                  :content="watchlist.count"
                  color="primary"
                  inline
                  class="ms-2"
                />
              </v-list-item-title>
            </v-list-item>
            <v-list-item
              data-e2e="nav-dismissed"
              to="/dismissed"
              prepend-icon="mdi-eye-off"
              title="Dismissed"
            />
          </v-list>
        </v-menu>
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

.app-title-full {
  display: inline;
}

.app-title-short {
  display: none;
}

@media (max-width: 600px) {
  .app-title-full {
    display: none;
  }
  .app-title-short {
    display: inline;
  }
}
</style>
