export type ContentTab = 'movies' | 'series' | 'anime'

export type SortOption = 'score' | 'imdb_rating' | 'year_desc' | 'year_asc' | 'votes' | 'title'

export const CONTENT_TABS: ContentTab[] = ['movies', 'series', 'anime']

export interface ApiError {
  status?: number
  data?: { detail?: string }
  message?: string
}

export interface Recommendation {
  title: string
  title_type: string
  year: number | null
  genres: string[]
  predicted_score: number
  imdb_rating: number | null
  explanation: string[]
  actors: string[]
  director: string | null
  similar_to: string[]
  language: string | null
  imdb_id: string | null
  imdb_url: string | null
  num_votes: number
}

export interface RecommendationResponse {
  movies: Recommendation[]
  series: Recommendation[]
  anime: Recommendation[]
  model_accuracy: number | null
}

export interface RecommendationFilters {
  min_year?: number | null
  max_year?: number | null
  genres?: string[] | null
  exclude_genres?: string[] | null
  languages?: string[] | null
  exclude_languages?: string[] | null
  min_imdb_rating?: number | null
  max_runtime?: number | null
  min_predicted_score?: number | null
  top_n_movies?: number | null
  top_n_series?: number | null
  top_n_anime?: number | null
  min_vote_count?: number | null
}

export interface DismissResponse {
  imdb_id: string
  action: string
}

export interface DismissedTitle {
  imdb_id: string
  title: string | null
  year: number | null
  title_type: string | null
  genres: string[]
  imdb_url: string | null
}

export interface DismissedListResponse {
  dismissed_ids: string[]
  dismissed_titles: DismissedTitle[]
  count: number
}

export interface TitleSearchResult {
  imdb_id: string
  title: string
  year: number | null
  title_type: string
  is_rated: boolean
}

export interface SimilarTitle {
  title: string
  title_type: string
  year: number | null
  genres: string[]
  imdb_rating: number | null
  predicted_score: number | null
  similarity_score: number
  similarity_explanation: string[]
  actors: string[]
  director: string | null
  language: string | null
  imdb_id: string | null
  imdb_url: string | null
  num_votes: number
  country_code: string | null
  is_rated: boolean
}

export interface SimilarResponse {
  seed_title: string
  seed_imdb_id: string
  results: SimilarTitle[]
  total_candidates: number
}

export interface PersonSearchResult {
  name_id: string
  name: string
  primary_profession: string | null
  title_count: number
}

export interface PersonTitleResult {
  imdb_id: string
  title: string
  year: number | null
  title_type: string
  imdb_rating: number | null
  num_votes: number | null
  runtime_mins: number | null
  genres: string[]
  predicted_score: number
  languages: string[]
  roles: string[]
  is_rated: boolean
}

export interface PersonTitlesResponse {
  name_id: string
  name: string
  primary_profession: string | null
  total: number
  results: PersonTitleResult[]
}

export interface PipelineStatus {
  rated_titles_count: number
  candidates_count: number
  model_trained: boolean
  last_run: string | null
  datasets_ready: boolean
  datasets_downloading: boolean
  watchlist_ready: boolean
  scored_db_ready: boolean
}

/** Shared interface for items displayed in RecommendationCard */
export interface CardDisplayItem {
  title: string
  title_type: string
  year: number | null
  genres: string[]
  imdb_rating: number | null
  actors: string[]
  director: string | null
  language: string | null
  imdb_id: string | null
  imdb_url: string | null
  num_votes: number
  // Display fields — different per source
  display_score: number        // predicted_score or similarity_score
  display_explanations: string[] // explanation or similarity_explanation
  similar_to?: string[]        // only for Recommendation
  score_label?: string         // e.g. "★ 8.2" or "87% match"
  score_color?: string         // e.g. "success" or "info"
  extra_badges?: Array<{ label: string; color: string }>  // e.g. "Seen" chip
  roles?: string[]             // only for PersonTitleResult
}

export function toCardItem(rec: Recommendation): CardDisplayItem {
  return {
    ...rec,
    display_score: rec.predicted_score,
    display_explanations: rec.explanation,
    similar_to: rec.similar_to,
    score_label: `★ ${rec.predicted_score.toFixed(1)}`,
    score_color: rec.predicted_score >= 8 ? 'success' : rec.predicted_score >= 7 ? 'warning' : 'error',
    extra_badges: [],
  }
}

export function toPersonCardItem(person: PersonTitleResult): CardDisplayItem {
  return {
    title: person.title,
    title_type: person.title_type,
    year: person.year,
    genres: person.genres,
    imdb_rating: person.imdb_rating,
    actors: [],
    director: null,
    language: person.languages[0] ?? null,
    imdb_id: person.imdb_id,
    imdb_url: `https://www.imdb.com/title/${person.imdb_id}`,
    num_votes: person.num_votes ?? 0,
    display_score: person.predicted_score,
    display_explanations: [],
    score_label: `★ ${person.predicted_score.toFixed(1)}`,
    score_color: person.predicted_score >= 8 ? 'success' : person.predicted_score >= 7 ? 'warning' : 'error',
    extra_badges: person.is_rated ? [{ label: 'Seen', color: 'success' }] : [],
    roles: person.roles,
  }
}

export function toSimilarCardItem(sim: SimilarTitle): CardDisplayItem {
  const score = sim.predicted_score ?? sim.imdb_rating ?? 0
  const pct = Math.round(sim.similarity_score * 100)
  return {
    ...sim,
    display_score: score,
    display_explanations: sim.similarity_explanation,
    score_label: `${pct}% match`,
    score_color: pct >= 50 ? 'success' : pct >= 30 ? 'warning' : 'default',
    extra_badges: sim.is_rated ? [{ label: 'Seen', color: 'success' }] : [],
  }
}
