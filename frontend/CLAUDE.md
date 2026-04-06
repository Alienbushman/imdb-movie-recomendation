# Frontend — Nuxt 4 + Vuetify 4

## Architecture

Single-page app with two pages, consuming the FastAPI backend API.

**Stack**: Nuxt 4, Vue 3, Vuetify 4 (dark theme), TypeScript

## Structure

```
frontend/
├── app/
│   ├── app.vue                         # Root: layout + page router
│   ├── layouts/default.vue             # App bar with nav (home, dismissed)
│   ├── pages/
│   │   ├── index.vue                   # Main recommendations page
│   │   └── dismissed.vue               # Manage dismissed titles
│   ├── components/
│   │   └── RecommendationCard.vue      # Movie/series card with dismiss
│   ├── composables/
│   │   └── useApi.ts                   # API client wrapping $fetch
│   └── types/
│       └── index.ts                    # TypeScript interfaces matching backend schemas
├── nuxt.config.ts                      # Vuetify module, API proxy, runtime config
├── Dockerfile                          # Multi-stage Node 22 build
└── package.json
```

## Pages

### `/` — Recommendations (index.vue)
- **Generate** button runs `POST /recommendations` with current filters
- **Retrain** button forces model retraining
- **Tabs**: Movies | Series | Animation (with counts)
- **Filter drawer** (right side): year range, genre chips, IMDB rating slider, runtime slider, predicted score slider
- Cards display in a responsive grid (1-4 columns)

### `/dismissed` — Dismissed Titles
- Lists all dismissed IMDB IDs with links
- Restore button per entry

## RecommendationCard Component
Displays: title (IMDB link), year, type badge, predicted score (color-coded), IMDB rating, genre chips, director, actors, similar titles, explanation list, dismiss button.

Dismiss is optimistic — card is removed immediately, restored on API error.

## API Integration

`useApi()` composable provides typed functions for all backend endpoints. Uses Nuxt's `$fetch` with `runtimeConfig.public.apiBase`.

### Dev proxy
In development, `/api` requests are proxied to `http://localhost:8562` via Nitro devProxy (configured in `nuxt.config.ts`). This avoids CORS issues — the backend also has CORSMiddleware allowing `localhost:3000` (dev) and `localhost:9137` (Docker).

### Docker
In Docker Compose, the frontend is exposed on port **9137**. It uses `NUXT_PUBLIC_API_BASE=/api/v1` with a Nitro server proxy to route API requests to the backend container. This way both SSR and client-side requests work correctly.

## Commands

```bash
npm install          # Install dependencies
npm run dev          # Dev server on port 3000
npm run build        # Production build to .output/
npx nuxt typecheck   # Type checking
```
