<script setup lang="ts">
import type { CardDisplayItem } from '../types'

const props = defineProps<{
  item: CardDisplayItem
}>()

const emit = defineEmits<{
  dismissed: [imdbId: string]
  excludeGenre: [genre: string]
  includeLanguage: [language: string]
}>()

const api = useApi()
const dismissing = ref(false)
const showAllExplanations = ref(false)
const dialogOpen = ref(false)

const visibleGenres = computed(() => props.item.genres.slice(0, 4))
const extraGenres = computed(() => Math.max(0, props.item.genres.length - 4))

const visibleExplanations = computed(() =>
  showAllExplanations.value
    ? props.item.display_explanations
    : props.item.display_explanations.slice(0, 3),
)
const extraExplanations = computed(() => Math.max(0, props.item.display_explanations.length - 3))

async function handleDismiss() {
  if (!props.item.imdb_id) return
  console.log('[card] dismiss:', props.item.imdb_id, props.item.title)
  dismissing.value = true
  try {
    await api.dismissTitle(props.item.imdb_id)
    emit('dismissed', props.item.imdb_id)
  }
  catch (e) {
    console.error('[card] dismiss failed:', props.item.imdb_id, e)
  }
  finally {
    dismissing.value = false
  }
}
</script>

<template>
  <v-card
    :data-e2e="`recommendation-card-${item.imdb_id}`"
    elevation="2"
    class="recommendation-card d-flex flex-column h-100"
    @click="dialogOpen = true"
  >
    <v-card-title class="d-flex align-center card-title-row pt-3 pb-1">
      <span class="title-text">
        <a
          v-if="item.imdb_url"
          data-e2e="card-title"
          :href="item.imdb_url"
          target="_blank"
          rel="noopener"
          class="text-decoration-none text-on-surface"
          @click.stop
        >
          {{ item.title }}
        </a>
        <span v-else data-e2e="card-title">{{ item.title }}</span>
      </span>
      <v-chip
        data-e2e="card-predicted-score"
        :color="item.score_color"
        size="small"
        variant="flat"
        class="ml-2 font-weight-bold flex-shrink-0 score-chip elevation-1"
      >
        {{ item.score_label }}
      </v-chip>
    </v-card-title>

    <v-card-subtitle class="d-flex align-center ga-1 flex-wrap pb-2">
      <span v-if="item.year" data-e2e="card-year">{{ item.year }}</span>
      <v-chip data-e2e="card-title-type" size="x-small" label>{{ item.title_type }}</v-chip>
      <v-chip
        v-for="badge in item.extra_badges"
        :key="badge.label"
        size="x-small"
        :color="badge.color"
        variant="flat"
      >
        {{ badge.label }}
      </v-chip>
      <span v-if="item.imdb_rating" data-e2e="card-imdb-rating" class="text-caption">
        IMDB {{ item.imdb_rating }}
      </span>
      <span v-if="item.num_votes" data-e2e="card-num-votes" class="text-caption text-medium-emphasis">
        ({{ item.num_votes.toLocaleString() }} votes)
      </span>
    </v-card-subtitle>

    <v-card-text class="flex-grow-1 pt-1">
      <!-- Genres (click to exclude) — max 4 visible -->
      <div data-e2e="card-genres" class="mb-2">
        <v-tooltip v-for="genre in visibleGenres" :key="genre" :text="`Exclude ${genre}`" location="top">
          <template #activator="{ props: tp }">
            <v-chip
              v-bind="tp"
              size="x-small"
              variant="outlined"
              class="mr-1 mb-1 chip-exclude"
              append-icon="mdi-close-circle-outline"
              @click.stop="emit('excludeGenre', genre)"
            >
              {{ genre }}
            </v-chip>
          </template>
        </v-tooltip>
        <v-chip v-if="extraGenres > 0" size="x-small" variant="text" class="mr-1 mb-1 text-medium-emphasis">
          +{{ extraGenres }}
        </v-chip>
        <v-tooltip v-if="item.language" :text="`Filter to ${item.language}`" location="top">
          <template #activator="{ props: tp }">
            <v-chip
              v-bind="tp"
              size="x-small"
              variant="tonal"
              color="info"
              class="mr-1 mb-1"
              prepend-icon="mdi-translate"
              @click.stop="emit('includeLanguage', item.language!)"
            >
              {{ item.language }}
            </v-chip>
          </template>
        </v-tooltip>
      </div>

      <!-- Director & Actors -->
      <div v-if="item.director" data-e2e="card-director" class="text-body-2 mb-1">
        <v-icon size="x-small" class="mr-1">mdi-movie-open</v-icon>
        {{ item.director }}
      </div>
      <div v-if="item.actors.length" data-e2e="card-actors" class="text-body-2 mb-1">
        <v-icon size="x-small" class="mr-1">mdi-account-group</v-icon>
        {{ item.actors.join(', ') }}
      </div>

      <!-- Similar titles (recommendation mode only) -->
      <div v-if="item.similar_to?.length" data-e2e="card-similar-to" class="text-body-2 mb-2 text-medium-emphasis text-truncate">
        <v-icon size="x-small" class="mr-1">mdi-movie-filter</v-icon>
        Similar to: {{ item.similar_to.join(', ') }}
      </div>

      <!-- Explanations / similarity reasons — max 3 visible -->
      <v-list data-e2e="card-explanations" density="compact" class="bg-transparent pa-0">
        <v-list-item
          v-for="(reason, i) in visibleExplanations"
          :key="i"
          :title="reason"
          :prepend-icon="item.score_label?.includes('match') ? 'mdi-link-variant' : 'mdi-check-circle-outline'"
          class="px-0"
        />
      </v-list>
      <v-btn
        v-if="extraExplanations > 0"
        size="x-small"
        variant="text"
        class="text-medium-emphasis mt-n1 ml-n1"
        @click.stop="showAllExplanations = !showAllExplanations"
      >
        {{ showAllExplanations ? 'Show less' : `+${extraExplanations} more` }}
      </v-btn>
    </v-card-text>

    <v-card-actions class="pt-0">
      <v-spacer />
      <v-btn
        data-e2e="btn-dismiss"
        size="small"
        variant="text"
        color="error"
        prepend-icon="mdi-close-circle"
        :loading="dismissing"
        @click.stop="handleDismiss"
      >
        Dismiss
      </v-btn>
    </v-card-actions>
  </v-card>

  <!-- Detail dialog -->
  <v-dialog v-model="dialogOpen" max-width="600" scrollable>
    <v-card class="detail-dialog">
      <!-- Header -->
      <v-card-title class="d-flex align-center pt-4 pb-2">
        <span class="dialog-title flex-grow-1">{{ item.title }}</span>
        <v-chip
          :color="item.score_color"
          size="large"
          variant="flat"
          class="ml-3 font-weight-bold elevation-2"
        >
          {{ item.score_label }}
        </v-chip>
        <v-btn icon="mdi-close" variant="text" size="small" class="ml-2" @click="dialogOpen = false" />
      </v-card-title>

      <v-divider />

      <v-card-text class="pt-4">
        <!-- Meta row -->
        <div class="d-flex align-center ga-2 flex-wrap mb-4">
          <v-chip v-if="item.year" size="small" variant="tonal">{{ item.year }}</v-chip>
          <v-chip size="small" label variant="tonal" color="primary">{{ item.title_type }}</v-chip>
          <v-chip v-if="item.imdb_rating" size="small" variant="tonal" color="amber">
            <v-icon size="x-small" start>mdi-star</v-icon>
            IMDB {{ item.imdb_rating }}
          </v-chip>
          <span v-if="item.num_votes" class="text-caption text-medium-emphasis">
            {{ item.num_votes.toLocaleString() }} votes
          </span>
          <v-chip v-if="item.language" size="small" variant="tonal" color="info" prepend-icon="mdi-translate">
            {{ item.language }}
          </v-chip>
        </div>

        <!-- All genres -->
        <div v-if="item.genres.length" class="mb-4">
          <div class="text-overline text-medium-emphasis mb-1">Genres</div>
          <div class="d-flex flex-wrap ga-1">
            <v-chip
              v-for="genre in item.genres"
              :key="genre"
              size="small"
              variant="outlined"
            >
              {{ genre }}
            </v-chip>
          </div>
        </div>

        <!-- Director -->
        <div v-if="item.director" class="mb-3">
          <div class="text-overline text-medium-emphasis mb-1">Director</div>
          <div class="text-body-1">
            <v-icon size="small" class="mr-1">mdi-movie-open</v-icon>
            {{ item.director }}
          </div>
        </div>

        <!-- Actors -->
        <div v-if="item.actors.length" class="mb-3">
          <div class="text-overline text-medium-emphasis mb-1">Cast</div>
          <div class="text-body-1">
            <v-icon size="small" class="mr-1">mdi-account-group</v-icon>
            {{ item.actors.join(', ') }}
          </div>
        </div>

        <!-- Similar titles (recommendation mode only) -->
        <div v-if="item.similar_to?.length" class="mb-4">
          <div class="text-overline text-medium-emphasis mb-1">Similar To</div>
          <div class="d-flex flex-wrap ga-1">
            <v-chip
              v-for="title in item.similar_to"
              :key="title"
              size="small"
              variant="tonal"
              prepend-icon="mdi-movie-filter"
            >
              {{ title }}
            </v-chip>
          </div>
        </div>

        <!-- All explanations / similarity reasons -->
        <div v-if="item.display_explanations.length">
          <div class="text-overline text-medium-emphasis mb-1">
            {{ item.score_label?.includes('match') ? 'Why It\'s Similar' : 'Why We Recommend This' }}
          </div>
          <v-list density="compact" class="bg-transparent pa-0">
            <v-list-item
              v-for="(reason, i) in item.display_explanations"
              :key="i"
              :title="reason"
              :prepend-icon="item.score_label?.includes('match') ? 'mdi-link-variant' : 'mdi-check-circle-outline'"
              class="px-0"
            />
          </v-list>
        </div>
      </v-card-text>

      <v-divider />

      <v-card-actions class="pa-3">
        <v-btn
          v-if="item.imdb_url"
          variant="tonal"
          color="primary"
          prepend-icon="mdi-open-in-new"
          :href="item.imdb_url"
          target="_blank"
          rel="noopener"
        >
          View on IMDB
        </v-btn>
        <v-spacer />
        <v-btn
          variant="tonal"
          color="error"
          prepend-icon="mdi-close-circle"
          :loading="dismissing"
          @click="handleDismiss(); dialogOpen = false"
        >
          Dismiss
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.recommendation-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  cursor: pointer;
}

.recommendation-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.2) !important;
}

.recommendation-card:hover .score-chip {
  transform: scale(1.08);
}

.score-chip {
  transition: transform 0.2s ease;
}

.card-title-row {
  min-height: 48px;
}

.title-text {
  flex: 1;
  min-width: 0;
  font-size: 0.9375rem;
  font-weight: 600;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.chip-exclude {
  cursor: pointer;
}

.chip-exclude :deep(.v-chip__append .v-icon) {
  font-size: 12px;
  opacity: 0.5;
  margin-left: 2px;
}

.chip-exclude:hover :deep(.v-chip__append .v-icon) {
  opacity: 1;
  color: rgb(var(--v-theme-error));
}

.dialog-title {
  font-size: 1.25rem;
  font-weight: 700;
  line-height: 1.3;
  word-break: break-word;
}
</style>
