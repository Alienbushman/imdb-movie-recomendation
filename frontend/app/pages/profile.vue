<script setup lang="ts">
// T3.14: Taste-profile visualization page.
//
// Renders horizontal-bar charts via v-progress-linear (avoids pulling in a
// chart library for the MVP) for: top genres, directors, actors, decade
// distribution, language histogram, and a rating distribution heatmap. A
// "Model health" footer reports the latest training metrics.

import type { TasteProfileResponse, TastePersonStat, TasteGenreStat, TasteDecadeStat } from '../types'

useHead({ title: 'Taste Profile · IMDB Recs' })

const api = useApi()
const profile = ref<TasteProfileResponse | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)

async function load() {
  loading.value = true
  error.value = null
  try {
    profile.value = await api.getProfile()
  } catch (e: unknown) {
    const err = e as { data?: { detail?: string }; message?: string }
    error.value = err.data?.detail || err.message || 'Failed to load taste profile.'
  } finally {
    loading.value = false
  }
}

onMounted(load)

const ratingHistogram = computed(() => {
  const dist = profile.value?.rating_distribution ?? {}
  const max = Math.max(1, ...Object.values(dist))
  return Array.from({ length: 10 }, (_, i) => {
    const r = i + 1
    const c = (dist as Record<string, number>)[String(r)] ?? 0
    return { rating: r, count: c, pct: (c / max) * 100 }
  })
})

function bestPersonBarValue(s: TastePersonStat | TasteGenreStat) {
  // Map mean rating in [1, 10] to a percentage of the bar (0..100).
  return Math.max(0, Math.min(100, (s.mean_rating - 1) * (100 / 9)))
}

function decadeBarValue(s: TasteDecadeStat) {
  return Math.max(0, Math.min(100, (s.mean_rating - 1) * (100 / 9)))
}

function ratingColor(r: number) {
  if (r >= 8) return 'success'
  if (r >= 7) return 'primary'
  if (r >= 5) return 'warning'
  return 'error'
}

function navToPerson(name: string) {
  navigateTo({ path: '/person', query: { name_id: name.toLowerCase(), name } })
}

function fmt(n: number | null | undefined, digits = 3) {
  if (n == null || Number.isNaN(n)) return '—'
  return n.toFixed(digits)
}
</script>

<template>
  <v-container max-width="1200" class="py-6">
    <div class="d-flex align-center mb-6">
      <v-icon size="32" color="primary" class="mr-3">mdi-chart-pie</v-icon>
      <h1 class="text-h4 font-weight-bold">Your Taste Profile</h1>
      <v-spacer />
      <v-btn variant="text" :loading="loading" prepend-icon="mdi-refresh" @click="load">
        Refresh
      </v-btn>
    </div>

    <v-alert v-if="error" type="error" variant="tonal" class="mb-4" closable>
      {{ error }}
    </v-alert>

    <v-progress-linear v-if="loading && !profile" indeterminate color="primary" height="3" class="mb-4" />

    <template v-if="profile">
      <v-row v-if="!profile.rated_count">
        <v-col cols="12">
          <v-empty-state
            icon="mdi-emoticon-confused-outline"
            title="No rated titles yet"
            text="Once you connect your IMDB ratings the taste profile will populate."
          />
        </v-col>
      </v-row>

      <template v-else>
        <!-- Summary header -->
        <v-row dense class="mb-2">
          <v-col cols="6" md="3">
            <v-card class="pa-4 text-center" variant="tonal" color="primary">
              <div class="text-overline">Rated titles</div>
              <div class="text-h4 font-weight-bold">{{ profile.rated_count }}</div>
            </v-card>
          </v-col>
          <v-col cols="6" md="3">
            <v-card class="pa-4 text-center" variant="tonal" color="success">
              <div class="text-overline">Distinct genres</div>
              <div class="text-h4 font-weight-bold">{{ profile.top_genres.length }}</div>
            </v-card>
          </v-col>
          <v-col cols="6" md="3">
            <v-card class="pa-4 text-center" variant="tonal" color="warning">
              <div class="text-overline">Top language</div>
              <div class="text-h6 font-weight-bold">
                {{ profile.language_distribution[0]?.language ?? '—' }}
              </div>
            </v-card>
          </v-col>
          <v-col cols="6" md="3">
            <v-card class="pa-4 text-center" variant="tonal" color="info">
              <div class="text-overline">NDCG@k</div>
              <div class="text-h6 font-weight-bold">{{ fmt(profile.health.ndcg_at_k, 4) }}</div>
            </v-card>
          </v-col>
        </v-row>

        <!-- Rating distribution -->
        <v-card class="mb-4 pa-4">
          <h2 class="text-h6 mb-3">Rating distribution</h2>
          <div class="rating-histogram">
            <div
              v-for="bucket in ratingHistogram"
              :key="bucket.rating"
              class="rating-bar-wrap"
            >
              <div class="rating-bar-label text-caption">{{ bucket.rating }}</div>
              <div class="rating-bar">
                <div
                  class="rating-bar-fill"
                  :class="`bg-${ratingColor(bucket.rating)}`"
                  :style="{ height: `${bucket.pct}%` }"
                />
              </div>
              <div class="rating-bar-count text-caption">{{ bucket.count }}</div>
            </div>
          </div>
        </v-card>

        <v-row dense>
          <!-- Top genres -->
          <v-col cols="12" md="6">
            <v-card class="pa-4 h-100">
              <h2 class="text-h6 mb-3">Top genres</h2>
              <div v-for="g in profile.top_genres.slice(0, 12)" :key="g.name" class="mb-2">
                <div class="d-flex align-center justify-space-between text-body-2">
                  <span class="font-weight-medium">{{ g.name }}</span>
                  <span class="text-caption text-medium-emphasis">
                    ★ {{ g.mean_rating.toFixed(2) }} · {{ g.count }}
                  </span>
                </div>
                <v-progress-linear
                  :model-value="bestPersonBarValue(g)"
                  :color="ratingColor(g.mean_rating)"
                  height="6"
                  rounded
                />
              </div>
            </v-card>
          </v-col>

          <!-- Decade distribution -->
          <v-col cols="12" md="6">
            <v-card class="pa-4 h-100">
              <h2 class="text-h6 mb-3">Decade preferences</h2>
              <div v-for="d in profile.decade_distribution" :key="d.decade" class="mb-2">
                <div class="d-flex align-center justify-space-between text-body-2">
                  <span class="font-weight-medium">{{ d.decade }}s</span>
                  <span class="text-caption text-medium-emphasis">
                    ★ {{ d.mean_rating.toFixed(2) }} · {{ d.count }}
                  </span>
                </div>
                <v-progress-linear
                  :model-value="decadeBarValue(d)"
                  :color="ratingColor(d.mean_rating)"
                  height="6"
                  rounded
                />
              </div>
            </v-card>
          </v-col>

          <!-- Top directors -->
          <v-col cols="12" md="6">
            <v-card class="pa-4 h-100">
              <h2 class="text-h6 mb-3">Top directors</h2>
              <div v-if="!profile.top_directors.length" class="text-medium-emphasis text-body-2">
                Rate a few more titles to surface director-level patterns.
              </div>
              <div v-for="p in profile.top_directors" :key="p.name" class="mb-2">
                <div class="d-flex align-center justify-space-between text-body-2">
                  <a class="font-weight-medium chip-clickable" @click="navToPerson(p.name)">{{ p.name }}</a>
                  <span class="text-caption text-medium-emphasis">
                    ★ {{ p.mean_rating.toFixed(2) }} · {{ p.count }} titles
                  </span>
                </div>
                <v-progress-linear
                  :model-value="bestPersonBarValue(p)"
                  :color="ratingColor(p.mean_rating)"
                  height="6"
                  rounded
                />
              </div>
            </v-card>
          </v-col>

          <!-- Top actors -->
          <v-col cols="12" md="6">
            <v-card class="pa-4 h-100">
              <h2 class="text-h6 mb-3">Top actors</h2>
              <div v-if="!profile.top_actors.length" class="text-medium-emphasis text-body-2">
                Actor data populates after the first pipeline run that fetches cast info.
              </div>
              <div v-for="p in profile.top_actors" :key="p.name" class="mb-2">
                <div class="d-flex align-center justify-space-between text-body-2">
                  <a class="font-weight-medium chip-clickable" @click="navToPerson(p.name)">{{ p.name }}</a>
                  <span class="text-caption text-medium-emphasis">
                    ★ {{ p.mean_rating.toFixed(2) }} · {{ p.count }} titles
                  </span>
                </div>
                <v-progress-linear
                  :model-value="bestPersonBarValue(p)"
                  :color="ratingColor(p.mean_rating)"
                  height="6"
                  rounded
                />
              </div>
            </v-card>
          </v-col>

          <!-- Top composers -->
          <v-col cols="12" md="6">
            <v-card class="pa-4 h-100">
              <h2 class="text-h6 mb-3">Top composers</h2>
              <div v-if="!profile.top_composers.length" class="text-medium-emphasis text-body-2">
                No composer data yet.
              </div>
              <div v-for="p in profile.top_composers" :key="p.name" class="mb-2">
                <div class="d-flex align-center justify-space-between text-body-2">
                  <a class="font-weight-medium chip-clickable" @click="navToPerson(p.name)">{{ p.name }}</a>
                  <span class="text-caption text-medium-emphasis">
                    ★ {{ p.mean_rating.toFixed(2) }} · {{ p.count }} titles
                  </span>
                </div>
                <v-progress-linear
                  :model-value="bestPersonBarValue(p)"
                  :color="ratingColor(p.mean_rating)"
                  height="6"
                  rounded
                />
              </div>
            </v-card>
          </v-col>

          <!-- Runtime + languages -->
          <v-col cols="12" md="6">
            <v-card class="pa-4 h-100">
              <h2 class="text-h6 mb-3">Runtime + languages</h2>
              <div class="text-overline text-medium-emphasis mb-1">Runtime histogram</div>
              <div v-for="b in profile.runtime_histogram" :key="b.label" class="mb-2">
                <div class="d-flex align-center justify-space-between text-body-2">
                  <span>{{ b.label }}</span>
                  <span class="text-caption text-medium-emphasis">{{ b.count }}</span>
                </div>
                <v-progress-linear
                  :model-value="b.count"
                  :max="profile.rated_count"
                  color="primary"
                  height="6"
                  rounded
                />
              </div>
              <v-divider class="my-3" />
              <div class="text-overline text-medium-emphasis mb-1">Languages</div>
              <div v-for="l in profile.language_distribution" :key="l.language" class="mb-2">
                <div class="d-flex align-center justify-space-between text-body-2">
                  <span>{{ l.language }}</span>
                  <span class="text-caption text-medium-emphasis">{{ l.count }}</span>
                </div>
                <v-progress-linear
                  :model-value="l.count"
                  :max="profile.rated_count"
                  color="info"
                  height="6"
                  rounded
                />
              </div>
            </v-card>
          </v-col>
        </v-row>

        <!-- Model health footer -->
        <v-card class="mt-4 pa-4" variant="tonal" color="surface">
          <h2 class="text-h6 mb-2">
            <v-icon class="mr-2" color="primary">mdi-pulse</v-icon>
            Model health
          </h2>
          <v-row dense>
            <v-col cols="6" md="3">
              <div class="text-overline text-medium-emphasis">Objective</div>
              <div>{{ profile.health.objective ?? '—' }}</div>
            </v-col>
            <v-col cols="6" md="3">
              <div class="text-overline text-medium-emphasis">NDCG@k</div>
              <div>{{ fmt(profile.health.ndcg_at_k, 4) }}</div>
            </v-col>
            <v-col cols="6" md="3">
              <div class="text-overline text-medium-emphasis">MAP@k</div>
              <div>{{ fmt(profile.health.map_at_k, 4) }}</div>
            </v-col>
            <v-col cols="6" md="3">
              <div class="text-overline text-medium-emphasis">Spearman</div>
              <div>{{ fmt(profile.health.spearman, 4) }}</div>
            </v-col>
            <v-col cols="6" md="3">
              <div class="text-overline text-medium-emphasis">Features</div>
              <div>{{ profile.health.feature_count ?? '—' }}</div>
            </v-col>
            <v-col cols="6" md="9">
              <div class="text-overline text-medium-emphasis">Trained at</div>
              <div>{{ profile.health.trained_at ?? '—' }}</div>
            </v-col>
          </v-row>
        </v-card>
      </template>
    </template>
  </v-container>
</template>

<style scoped>
.chip-clickable {
  cursor: pointer;
  color: rgb(var(--v-theme-primary));
}
.chip-clickable:hover {
  text-decoration: underline;
}

.rating-histogram {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  height: 160px;
}
.rating-bar-wrap {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
}
.rating-bar-label {
  font-weight: 600;
  margin-bottom: 4px;
}
.rating-bar {
  flex: 1;
  width: 100%;
  background: rgba(var(--v-theme-on-surface), 0.06);
  border-radius: 4px;
  display: flex;
  align-items: flex-end;
  overflow: hidden;
}
.rating-bar-fill {
  width: 100%;
  transition: height 0.4s ease;
}
.rating-bar-count {
  margin-top: 4px;
  opacity: 0.8;
}
</style>
