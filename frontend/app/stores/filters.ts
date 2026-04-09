import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { RecommendationFilters } from '../types'

export const FILTER_DEFAULTS = {
  minImdbRating: 0,
  maxRuntime: 300,
  minPredictedScore: 6.5,
  minVoteCount: 1000,
} as const

export const ALL_GENRES = [
  'Action', 'Adventure', 'Animation', 'Biography', 'Comedy', 'Crime',
  'Documentary', 'Drama', 'Family', 'Fantasy', 'Film-Noir', 'History',
  'Horror', 'Music', 'Musical', 'Mystery', 'Romance', 'Sci-Fi',
  'Short', 'Sport', 'Thriller', 'War', 'Western',
]


export const ALL_LANGUAGES = [
  'English', 'French', 'German', 'Spanish', 'Italian', 'Portuguese',
  'Japanese', 'Korean', 'Chinese', 'Hindi', 'Russian', 'Arabic',
  'Swedish', 'Danish', 'Norwegian', 'Finnish', 'Dutch', 'Polish',
  'Czech', 'Hungarian', 'Turkish', 'Thai', 'Hebrew', 'Persian',
  'Greek', 'Romanian', 'Ukrainian', 'Indonesian', 'Vietnamese',
]

export const CURRENT_YEAR = new Date().getFullYear()
export const MIN_YEAR_BOUND = 1970

export const YEAR_PRESETS = [
  { label: 'Last 5 years', min: CURRENT_YEAR - 5, max: CURRENT_YEAR },
  { label: '2020s', min: 2020, max: 2029 },
  { label: '2010s', min: 2010, max: 2019 },
  { label: '2000s', min: 2000, max: 2009 },
  { label: '90s', min: 1990, max: 1999 },
  { label: '80s', min: 1980, max: 1989 },
  { label: 'Classic', min: 1970, max: 1979 },
  { label: 'All', min: MIN_YEAR_BOUND, max: CURRENT_YEAR },
]

export const useFiltersStore = defineStore('filters', () => {
  const minYear = ref<number | undefined>()
  const maxYear = ref<number | undefined>()
  const selectedGenres = ref<string[]>([])
  const excludedGenres = ref<string[]>([])
  const selectedLanguages = ref<string[]>([])
  const excludedLanguages = ref<string[]>([])
  const minImdbRating = ref<number>(FILTER_DEFAULTS.minImdbRating)
  const maxRuntime = ref<number>(FILTER_DEFAULTS.maxRuntime)
  const minPredictedScore = ref<number>(FILTER_DEFAULTS.minPredictedScore)
  const topNMovies = ref<number | undefined>()
  const topNSeries = ref<number | undefined>()
  const topNAnime = ref<number | undefined>()
  const minVoteCount = ref<number>(FILTER_DEFAULTS.minVoteCount)

  const yearRange = computed({
    get: () => [minYear.value ?? MIN_YEAR_BOUND, maxYear.value ?? CURRENT_YEAR] as [number, number],
    set: (val: [number, number]) => {
      minYear.value = val[0] === MIN_YEAR_BOUND ? undefined : val[0]
      maxYear.value = val[1] === CURRENT_YEAR ? undefined : val[1]
    },
  })

  function buildFilters(): RecommendationFilters | undefined {
    console.log('[filters] buildFilters — store state:', {
      minYear: minYear.value, maxYear: maxYear.value,
      selectedGenres: selectedGenres.value, excludedGenres: excludedGenres.value,
      selectedLanguages: selectedLanguages.value,
      excludedLanguages: excludedLanguages.value,
      minImdbRating: minImdbRating.value, maxRuntime: maxRuntime.value,
      minPredictedScore: minPredictedScore.value,
      topNMovies: topNMovies.value, topNSeries: topNSeries.value, topNAnime: topNAnime.value,
    })
    const f: RecommendationFilters = {}
    if (minYear.value) f.min_year = minYear.value
    if (maxYear.value) f.max_year = maxYear.value
    if (selectedGenres.value.length) f.genres = [...selectedGenres.value]
    if (excludedGenres.value.length) f.exclude_genres = [...excludedGenres.value]
    if (selectedLanguages.value.length) f.languages = [...selectedLanguages.value]
    if (excludedLanguages.value.length) f.exclude_languages = [...excludedLanguages.value]
    if (minImdbRating.value > FILTER_DEFAULTS.minImdbRating) f.min_imdb_rating = minImdbRating.value
    if (maxRuntime.value < FILTER_DEFAULTS.maxRuntime) f.max_runtime = maxRuntime.value
    if (minPredictedScore.value !== FILTER_DEFAULTS.minPredictedScore) f.min_predicted_score = minPredictedScore.value
    if (topNMovies.value != null) f.top_n_movies = topNMovies.value
    if (topNSeries.value != null) f.top_n_series = topNSeries.value
    if (topNAnime.value != null) f.top_n_anime = topNAnime.value
    if (minVoteCount.value > 0) f.min_vote_count = minVoteCount.value

    const result = Object.keys(f).length ? f : undefined
    console.log('[filters] buildFilters — result:', result)
    return result
  }

  function addExcludedGenre(genre: string) {
    if (!excludedGenres.value.includes(genre)) {
      excludedGenres.value.push(genre)
      console.log('[filters] excluded genre added:', genre, '| all excluded:', excludedGenres.value)
    }
  }

  function removeExcludedGenre(genre: string) {
    excludedGenres.value = excludedGenres.value.filter(g => g !== genre)
    console.log('[filters] excluded genre removed:', genre, '| remaining:', excludedGenres.value)
  }

  function addSelectedLanguage(language: string) {
    if (!selectedLanguages.value.includes(language)) {
      selectedLanguages.value.push(language)
      console.log('[filters] selected language added:', language, '| all selected:', selectedLanguages.value)
    }
  }

  function removeSelectedLanguage(language: string) {
    selectedLanguages.value = selectedLanguages.value.filter(l => l !== language)
    console.log('[filters] selected language removed:', language, '| remaining:', selectedLanguages.value)
  }

  function addExcludedLanguage(language: string) {
    if (!excludedLanguages.value.includes(language)) {
      excludedLanguages.value.push(language)
      console.log('[filters] excluded language added:', language, '| all excluded:', excludedLanguages.value)
    }
  }

  function removeExcludedLanguage(language: string) {
    excludedLanguages.value = excludedLanguages.value.filter(l => l !== language)
    console.log('[filters] excluded language removed:', language, '| remaining:', excludedLanguages.value)
  }

  function resetFilters() {
    console.log('[filters] resetFilters')
    minYear.value = undefined
    maxYear.value = undefined
    selectedGenres.value = []
    excludedGenres.value = []
    selectedLanguages.value = []
    excludedLanguages.value = []
    minImdbRating.value = FILTER_DEFAULTS.minImdbRating
    maxRuntime.value = FILTER_DEFAULTS.maxRuntime
    minPredictedScore.value = FILTER_DEFAULTS.minPredictedScore
    topNMovies.value = undefined
    topNSeries.value = undefined
    topNAnime.value = undefined
    minVoteCount.value = FILTER_DEFAULTS.minVoteCount
  }

  const activeFilterSummary = computed(() => {
    const labels: string[] = []
    if (minYear.value && maxYear.value) labels.push(`${minYear.value}–${maxYear.value}`)
    else if (minYear.value) labels.push(`from ${minYear.value}`)
    else if (maxYear.value) labels.push(`up to ${maxYear.value}`)
    if (selectedGenres.value.length) labels.push(selectedGenres.value.join(', '))
    if (selectedLanguages.value.length) labels.push(selectedLanguages.value.join(', '))
    if (minImdbRating.value > FILTER_DEFAULTS.minImdbRating) labels.push(`IMDB ≥ ${minImdbRating.value}`)
    if (maxRuntime.value < FILTER_DEFAULTS.maxRuntime) labels.push(`≤ ${maxRuntime.value} min`)
    if (minPredictedScore.value !== FILTER_DEFAULTS.minPredictedScore) labels.push(`score ≥ ${minPredictedScore.value}`)
    if (topNMovies.value != null) labels.push(`${topNMovies.value} movies`)
    if (topNSeries.value != null) labels.push(`${topNSeries.value} series`)
    if (topNAnime.value != null) labels.push(`${topNAnime.value} anime`)
    if (minVoteCount.value > FILTER_DEFAULTS.minVoteCount) labels.push(`≥ ${minVoteCount.value.toLocaleString()} votes`)
    return labels
  })

  const hasActiveFilters = computed(() => {
    return !!(
      minYear.value
      || maxYear.value
      || selectedGenres.value.length
      || excludedGenres.value.length
      || selectedLanguages.value.length
      || excludedLanguages.value.length
      || minImdbRating.value > FILTER_DEFAULTS.minImdbRating
      || maxRuntime.value < FILTER_DEFAULTS.maxRuntime
      || minPredictedScore.value !== FILTER_DEFAULTS.minPredictedScore
      || topNMovies.value != null
      || topNSeries.value != null
      || topNAnime.value != null
      || minVoteCount.value > FILTER_DEFAULTS.minVoteCount
    )
  })

  const hasActiveExclusions = computed(() =>
    excludedGenres.value.length > 0 || excludedLanguages.value.length > 0,
  )

  return {
    minYear,
    maxYear,
    yearRange,
    selectedGenres,
    excludedGenres,
    selectedLanguages,
    excludedLanguages,
    minImdbRating,
    maxRuntime,
    minPredictedScore,
    topNMovies,
    topNSeries,
    topNAnime,
    minVoteCount,
    buildFilters,
    addExcludedGenre,
    removeExcludedGenre,
    addSelectedLanguage,
    removeSelectedLanguage,
    addExcludedLanguage,
    removeExcludedLanguage,
    resetFilters,
    activeFilterSummary,
    hasActiveFilters,
    hasActiveExclusions,
  }
})
