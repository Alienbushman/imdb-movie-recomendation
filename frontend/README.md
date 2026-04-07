# Frontend — IMDB Movie Recommendation Engine

Nuxt 4 + Vuetify 4 web UI for the IMDB recommendation engine.

## Stack

- **Nuxt 4** (Vue 3, TypeScript)
- **Vuetify 4** — dark-theme component library
- **Nitro** — server-side proxy for backend API calls

## Project Structure

```
frontend/
├── app/
│   ├── app.vue                    # Root layout + page router
│   ├── layouts/default.vue        # App bar with navigation links
│   ├── pages/
│   │   ├── index.vue              # Main recommendations page
│   │   ├── dismissed.vue          # Manage dismissed titles
│   │   ├── similar/[id].vue       # Find similar titles
│   │   └── person/[id].vue        # Browse titles by director or actor
│   ├── components/                # Shared UI components
│   ├── composables/
│   │   └── useApi.ts              # Typed API client wrapping $fetch
│   └── types/
│       └── index.ts               # TypeScript interfaces matching backend schemas
├── server/routes/api/[...path].ts # Nitro catch-all proxy → backend
├── nuxt.config.ts                 # Vuetify module, proxy, runtime config
├── Dockerfile                     # Multi-stage Node 22 build
└── package.json
```

## Development

```bash
npm install          # Install dependencies
npm run dev          # Dev server on http://localhost:3000
npx nuxt typecheck   # TypeScript type check
```

In development, `/api` requests are proxied to `http://localhost:8562` (the backend).
No CORS issues — the backend also allows `localhost:3000`.

## Docker

In Docker Compose the frontend is exposed on port **9137**. The Nitro server routes
`/api/*` requests to `http://api:8080` inside the Docker network, so both SSR and
client-side requests reach the backend correctly.

## API Integration

All backend calls go through `useApi()` in `composables/useApi.ts`, which provides
typed wrappers for every endpoint. Never call `$fetch('/api/...')` directly from pages
or components — always use `useApi()`.
