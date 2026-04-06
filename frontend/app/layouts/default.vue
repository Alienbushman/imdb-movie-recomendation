<template>
  <v-app>
    <v-app-bar data-e2e="app-bar" color="surface" elevation="0" border="b">
      <template #prepend>
        <v-icon color="primary" size="28" class="ml-4">mdi-movie-open-star</v-icon>
      </template>
      <v-app-bar-title>
        <NuxtLink data-e2e="app-title" to="/" class="text-decoration-none text-on-surface font-weight-bold">
          IMDB Recommendations
        </NuxtLink>
      </v-app-bar-title>
      <template #append>
        <v-btn data-e2e="nav-similar" to="/similar" variant="text" prepend-icon="mdi-movie-search">
          Find Similar
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
