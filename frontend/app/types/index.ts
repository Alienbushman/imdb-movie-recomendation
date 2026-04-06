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

export interface PipelineStatus {
  rated_titles_count: number
  candidates_count: number
  model_trained: boolean
  last_run: string | null
}
