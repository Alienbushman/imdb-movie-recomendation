<script setup lang="ts">
import type { PipelineStatus } from '../types'

const props = defineProps<{
  status: PipelineStatus | null
}>()

const emit = defineEmits<{
  started: [imdbUrl: string | undefined, file: File | undefined]
}>()

const imdbUrl = ref('')
const csvFile = ref<File | null>(null)

const datasetsReady = computed(() => props.status?.datasets_ready ?? false)
const datasetsDownloading = computed(() => props.status?.datasets_downloading ?? false)

// Step 1 state
const step1Icon = computed(() => {
  if (datasetsDownloading.value) return null           // show spinner
  if (datasetsReady.value) return 'mdi-check-circle'  // green check
  return 'mdi-clock-outline'                           // waiting
})
const step1Color = computed(() => datasetsReady.value ? 'success' : 'medium-emphasis')
const step1Label = computed(() => {
  if (datasetsDownloading.value) return 'Downloading dataset files… (this takes a few minutes)'
  if (datasetsReady.value) return 'Dataset files ready'
  return 'Waiting for dataset files…'
})

function handleCsvChange(files: File | File[] | null) {
  const file = Array.isArray(files) ? files[0] : files
  csvFile.value = file ?? null
}

function handleStart() {
  emit('started', imdbUrl.value || undefined, csvFile.value ?? undefined)
}
</script>

<template>
  <div
    class="setup-wizard-overlay d-flex align-center justify-center"
    style="position: fixed; inset: 0; z-index: 100; background: rgba(var(--v-theme-background), 0.97)"
  >
    <v-card
      class="setup-wizard-card pa-8"
      max-width="540"
      width="100%"
      variant="flat"
    >
      <!-- Header -->
      <div class="d-flex align-center mb-8">
        <v-icon color="primary" size="36" class="mr-3">mdi-movie-open-star</v-icon>
        <div>
          <div class="text-h5 font-weight-bold">IMDB Recommendations</div>
          <div class="text-body-2 text-medium-emphasis">First-time setup</div>
        </div>
      </div>

      <!-- Step 1: Datasets -->
      <div class="d-flex align-start mb-6">
        <div class="step-icon-col mr-4 mt-1">
          <v-progress-circular
            v-if="datasetsDownloading"
            indeterminate
            color="primary"
            size="24"
            width="3"
          />
          <v-icon v-else :color="step1Color" size="24">{{ step1Icon }}</v-icon>
        </div>
        <div class="flex-grow-1">
          <div class="text-subtitle-1 font-weight-medium mb-1">Dataset files</div>
          <div class="text-body-2 text-medium-emphasis">{{ step1Label }}</div>
        </div>
      </div>

      <!-- Step 2: Ratings input -->
      <div class="d-flex align-start mb-8">
        <div class="step-icon-col mr-4 mt-1">
          <v-icon
            :color="datasetsReady ? 'primary' : 'medium-emphasis'"
            size="24"
          >
            mdi-account-star
          </v-icon>
        </div>
        <div class="flex-grow-1">
          <div class="text-subtitle-1 font-weight-medium mb-3">Your IMDB ratings</div>
          <v-text-field
            v-model="imdbUrl"
            label="IMDB Ratings URL"
            placeholder="https://www.imdb.com/user/ur.../ratings/"
            hint="Your IMDB ratings page must be set to public"
            persistent-hint
            persistent-placeholder
            clearable
            variant="outlined"
            prepend-inner-icon="mdi-link"
            density="compact"
            :disabled="!datasetsReady"
            class="mb-3"
          />
          <div class="text-caption text-medium-emphasis mb-2">Or upload a CSV instead</div>
          <v-file-input
            label="Upload ratings CSV"
            accept=".csv"
            hint="Export from IMDB → Your ratings → Export"
            persistent-hint
            variant="outlined"
            prepend-icon="mdi-upload"
            density="compact"
            :disabled="!datasetsReady"
            @update:model-value="handleCsvChange"
          />
        </div>
      </div>

      <!-- Action -->
      <v-btn
        color="primary"
        size="large"
        block
        prepend-icon="mdi-play"
        :disabled="!datasetsReady || (!imdbUrl && !csvFile)"
        @click="handleStart"
      >
        Get Started
      </v-btn>

      <div class="text-caption text-center text-medium-emphasis mt-3">
        Need help? See the
        <a
          href="https://github.com/Alienbushman/imdb-movie-recomendation"
          target="_blank"
          class="text-primary"
        >README</a>
        for instructions.
      </div>
    </v-card>
  </div>
</template>

<style scoped>
.step-icon-col {
  flex-shrink: 0;
  width: 28px;
  display: flex;
  justify-content: center;
}
</style>
