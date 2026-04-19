// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  app: {
    head: {
      link: [
        { rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' },
        { rel: 'icon', type: 'image/x-icon', href: '/favicon.ico' },
      ],
    },
  },

  modules: ['vuetify-nuxt-module', '@pinia/nuxt', 'pinia-plugin-persistedstate/nuxt', '@nuxt/eslint'],

  vuetify: {
    vuetifyOptions: {
      theme: {
        defaultTheme: 'dark',
        themes: {
          dark: {
            colors: {
              background: '#0a0a0f',
              surface: '#14141f',
              'surface-variant': '#1e1e2e',
              primary: '#6366f1',
              secondary: '#a78bfa',
              error: '#ef4444',
              warning: '#f59e0b',
              info: '#3b82f6',
              success: '#22c55e',
              'on-background': '#e2e8f0',
              'on-surface': '#e2e8f0',
            },
          },
        },
      },
    },
  },

  runtimeConfig: {
    public: {
      // Client always uses relative /api/v1 (proxied by Nitro)
      apiBase: '/api/v1',
    },
  },

})
