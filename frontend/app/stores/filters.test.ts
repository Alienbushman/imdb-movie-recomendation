import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { useFiltersStore } from './filters'

describe('useFiltersStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('buildFilters', () => {
    it('returns undefined when all values are at defaults', () => {
      const store = useFiltersStore()
      expect(store.buildFilters()).toBeUndefined()
    })

    it('includes min_year when set', () => {
      const store = useFiltersStore()
      store.minYear = 2010
      expect(store.buildFilters()).toMatchObject({ min_year: 2010 })
    })

    it('includes max_year when set', () => {
      const store = useFiltersStore()
      store.maxYear = 2024
      expect(store.buildFilters()).toMatchObject({ max_year: 2024 })
    })

    it('omits min_year when falsy (0, undefined)', () => {
      const store = useFiltersStore()
      store.minYear = 0 as unknown as undefined
      expect(store.buildFilters()).toBeUndefined()
    })

    it('includes genres when selected', () => {
      const store = useFiltersStore()
      store.selectedGenres = ['Action', 'Drama']
      expect(store.buildFilters()).toMatchObject({ genres: ['Action', 'Drama'] })
    })

    it('includes exclude_genres when set', () => {
      const store = useFiltersStore()
      store.excludedGenres = ['Horror']
      expect(store.buildFilters()).toMatchObject({ exclude_genres: ['Horror'] })
    })

    it('includes languages when set', () => {
      const store = useFiltersStore()
      store.selectedLanguages = ['English']
      expect(store.buildFilters()).toMatchObject({ languages: ['English'] })
    })

    it('includes exclude_languages when set', () => {
      const store = useFiltersStore()
      store.excludedLanguages = ['Hindi', 'Korean']
      expect(store.buildFilters()).toMatchObject({ exclude_languages: ['Hindi', 'Korean'] })
    })

    it('includes min_imdb_rating only when above 0', () => {
      const store = useFiltersStore()
      store.minImdbRating = 0
      expect(store.buildFilters()).toBeUndefined()

      store.minImdbRating = 7.5
      expect(store.buildFilters()).toMatchObject({ min_imdb_rating: 7.5 })
    })

    it('includes max_runtime only when below 300', () => {
      const store = useFiltersStore()
      store.maxRuntime = 300
      expect(store.buildFilters()).toBeUndefined()

      store.maxRuntime = 120
      expect(store.buildFilters()).toMatchObject({ max_runtime: 120 })
    })

    it('includes min_predicted_score only when different from default 6.5', () => {
      const store = useFiltersStore()
      store.minPredictedScore = 6.5
      expect(store.buildFilters()).toBeUndefined()

      store.minPredictedScore = 8.0
      expect(store.buildFilters()).toMatchObject({ min_predicted_score: 8.0 })
    })

    it('returns an object with only the set filters (no extra keys)', () => {
      const store = useFiltersStore()
      store.minYear = 2015
      store.minImdbRating = 7.0
      const result = store.buildFilters()
      expect(result).toEqual({ min_year: 2015, min_imdb_rating: 7.0 })
    })

    it('returns undefined after resetFilters', () => {
      const store = useFiltersStore()
      store.minYear = 2010
      store.selectedGenres = ['Action']
      store.minImdbRating = 7.0
      store.resetFilters()
      expect(store.buildFilters()).toBeUndefined()
    })
  })

  describe('activeFilterSummary', () => {
    it('is empty when no filters are set', () => {
      const store = useFiltersStore()
      expect(store.activeFilterSummary).toEqual([])
    })

    it('shows year range when both min and max are set', () => {
      const store = useFiltersStore()
      store.minYear = 2010
      store.maxYear = 2020
      expect(store.activeFilterSummary).toContain('2010–2020')
    })

    it('shows "from X" when only min year is set', () => {
      const store = useFiltersStore()
      store.minYear = 2010
      expect(store.activeFilterSummary).toContain('from 2010')
    })

    it('shows "up to X" when only max year is set', () => {
      const store = useFiltersStore()
      store.maxYear = 2020
      expect(store.activeFilterSummary).toContain('up to 2020')
    })

    it('shows joined genres when selected', () => {
      const store = useFiltersStore()
      store.selectedGenres = ['Action', 'Drama']
      expect(store.activeFilterSummary).toContain('Action, Drama')
    })

    it('shows IMDB rating filter', () => {
      const store = useFiltersStore()
      store.minImdbRating = 7.5
      expect(store.activeFilterSummary).toContain('IMDB ≥ 7.5')
    })

    it('shows runtime filter', () => {
      const store = useFiltersStore()
      store.maxRuntime = 90
      expect(store.activeFilterSummary).toContain('≤ 90 min')
    })

    it('shows score filter', () => {
      const store = useFiltersStore()
      store.minPredictedScore = 8.0
      expect(store.activeFilterSummary).toContain('score ≥ 8')
    })
  })

  describe('addExcludedGenre / removeExcludedGenre', () => {
    it('adds a genre to the exclusion list', () => {
      const store = useFiltersStore()
      store.addExcludedGenre('Horror')
      expect(store.excludedGenres).toEqual(['Horror'])
    })

    it('does not add duplicates', () => {
      const store = useFiltersStore()
      store.addExcludedGenre('Horror')
      store.addExcludedGenre('Horror')
      expect(store.excludedGenres).toEqual(['Horror'])
    })

    it('removes a genre from the exclusion list', () => {
      const store = useFiltersStore()
      store.addExcludedGenre('Horror')
      store.addExcludedGenre('Romance')
      store.removeExcludedGenre('Horror')
      expect(store.excludedGenres).toEqual(['Romance'])
    })

    it('is a no-op when removing a genre not in the list', () => {
      const store = useFiltersStore()
      store.addExcludedGenre('Horror')
      store.removeExcludedGenre('Comedy')
      expect(store.excludedGenres).toEqual(['Horror'])
    })
  })

  describe('addExcludedLanguage / removeExcludedLanguage', () => {
    it('adds a language to the exclusion list', () => {
      const store = useFiltersStore()
      store.addExcludedLanguage('Hindi')
      expect(store.excludedLanguages).toEqual(['Hindi'])
    })

    it('does not add duplicates', () => {
      const store = useFiltersStore()
      store.addExcludedLanguage('Hindi')
      store.addExcludedLanguage('Hindi')
      expect(store.excludedLanguages).toEqual(['Hindi'])
    })

    it('removes a language from the exclusion list', () => {
      const store = useFiltersStore()
      store.addExcludedLanguage('Hindi')
      store.addExcludedLanguage('Korean')
      store.removeExcludedLanguage('Hindi')
      expect(store.excludedLanguages).toEqual(['Korean'])
    })
  })

  describe('activeFilterSummary — language', () => {
    it('shows selected languages', () => {
      const store = useFiltersStore()
      store.selectedLanguages = ['French']
      expect(store.activeFilterSummary).toContain('French')
    })
  })

  describe('hasActiveFilters', () => {
    it('is false at defaults', () => {
      const store = useFiltersStore()
      expect(store.hasActiveFilters).toBe(false)
    })

    it('is true when any filter is set', () => {
      const store = useFiltersStore()
      store.minYear = 2010
      expect(store.hasActiveFilters).toBe(true)
    })

    it('is true with excluded genres', () => {
      const store = useFiltersStore()
      store.addExcludedGenre('Horror')
      expect(store.hasActiveFilters).toBe(true)
    })

    it('is true with excluded languages', () => {
      const store = useFiltersStore()
      store.addExcludedLanguage('Hindi')
      expect(store.hasActiveFilters).toBe(true)
    })

    it('returns to false after resetFilters', () => {
      const store = useFiltersStore()
      store.minYear = 2010
      store.resetFilters()
      expect(store.hasActiveFilters).toBe(false)
    })
  })

  describe('hasActiveExclusions', () => {
    it('is false at defaults', () => {
      const store = useFiltersStore()
      expect(store.hasActiveExclusions).toBe(false)
    })

    it('is true when excluded genres are present', () => {
      const store = useFiltersStore()
      store.addExcludedGenre('Horror')
      expect(store.hasActiveExclusions).toBe(true)
    })

    it('is true when excluded languages are present', () => {
      const store = useFiltersStore()
      store.addExcludedLanguage('Hindi')
      expect(store.hasActiveExclusions).toBe(true)
    })

    it('returns to false after resetFilters', () => {
      const store = useFiltersStore()
      store.addExcludedGenre('Horror')
      store.addExcludedLanguage('Hindi')
      store.resetFilters()
      expect(store.hasActiveExclusions).toBe(false)
    })
  })
})
