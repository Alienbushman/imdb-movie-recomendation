<script setup lang="ts">
const tab = defineModel<string>({ required: true })

defineProps<{
  movieCount: number
  seriesCount: number
  animeCount: number
}>()
</script>

<template>
  <v-tabs v-model="tab" data-e2e="tabs-categories" class="mb-4">
    <v-tab data-e2e="tab-movies" value="movies">
      Movies
      <v-badge
        v-if="movieCount"
        :content="movieCount"
        color="primary"
        inline
      />
    </v-tab>
    <v-tab data-e2e="tab-series" value="series">
      Series
      <v-badge
        v-if="seriesCount"
        :content="seriesCount"
        color="primary"
        inline
      />
    </v-tab>
    <v-tab data-e2e="tab-anime" value="anime">
      Anime
      <v-badge
        v-if="animeCount"
        :content="animeCount"
        color="primary"
        inline
      />
    </v-tab>
  </v-tabs>
</template>
