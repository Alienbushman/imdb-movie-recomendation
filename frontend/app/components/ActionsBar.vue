<script setup lang="ts">
defineProps<{
  loading: boolean
  lastOperation: 'filter' | 'generate' | null
  modelAccuracy: number | null
}>()

const emit = defineEmits<{
  generate: [retrain: boolean, imdbUrl?: string]
  csvUploaded: [file: File]
}>()

const imdbUrl = ref<string>('')
const showDataSource = ref(false)

function handleCsvUpload(files: File | File[] | null) {
  const file = Array.isArray(files) ? files[0] : files
  if (!file) return
  emit('csvUploaded', file)
}
</script>

<template>
  <!-- Actions bar -->
  <div data-e2e="actions-bar" class="d-flex align-center ga-3 mb-4 flex-wrap">
    <v-btn
      data-e2e="btn-generate"
      color="primary"
      prepend-icon="mdi-play"
      :loading="loading"
      @click="emit('generate', false, imdbUrl || undefined)"
    >
      Generate
    </v-btn>
    <v-btn
      data-e2e="btn-retrain"
      variant="outlined"
      prepend-icon="mdi-refresh"
      :loading="loading"
      @click="emit('generate', true, imdbUrl || undefined)"
    >
      Retrain Model
    </v-btn>
    <v-btn
      variant="text"
      size="small"
      :prepend-icon="showDataSource ? 'mdi-chevron-up' : 'mdi-database-import-outline'"
      @click="showDataSource = !showDataSource"
    >
      Data Source
    </v-btn>
    <v-spacer />
    <v-chip v-if="lastOperation" data-e2e="chip-last-operation" :color="lastOperation === 'filter' ? 'success' : 'info'" variant="tonal" size="small">
      {{ lastOperation === 'filter' ? '⚡ from cache' : '🔄 full run' }}
    </v-chip>
    <v-chip v-if="modelAccuracy" data-e2e="chip-model-accuracy" variant="outlined" size="small">
      MAE: {{ modelAccuracy }}
    </v-chip>
  </div>

  <!-- Collapsible data source inputs -->
  <v-expand-transition>
    <div v-if="showDataSource" class="mb-4">
      <v-card variant="outlined" class="pa-4">
        <v-text-field
          v-model="imdbUrl"
          label="IMDB Ratings URL"
          placeholder="https://www.imdb.com/user/ur.../ratings/"
          hint="Your IMDB ratings must be set to public"
          persistent-hint
          persistent-placeholder
          clearable
          variant="outlined"
          prepend-inner-icon="mdi-link"
          density="compact"
          class="mb-2"
        />
        <v-file-input
          label="Or upload CSV manually"
          accept=".csv"
          hint="Export from IMDB → Your ratings → Export"
          persistent-hint
          variant="outlined"
          prepend-icon="mdi-upload"
          density="compact"
          @update:model-value="handleCsvUpload"
        />
      </v-card>
    </div>
  </v-expand-transition>
</template>
