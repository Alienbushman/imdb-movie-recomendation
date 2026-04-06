from pydantic import BaseModel, Field


class RatedTitle(BaseModel):
    """A title from the user's IMDB export with their personal rating."""

    imdb_id: str
    title: str
    original_title: str
    title_type: str
    user_rating: int
    date_rated: str
    imdb_rating: float
    runtime_mins: int | None
    year: int
    genres: list[str]
    num_votes: int
    release_date: str
    directors: list[str]
    url: str
    language: str | None = None
    writers: list[str] = []


class CandidateTitle(BaseModel):
    """A title from IMDB datasets that the user hasn't rated."""

    imdb_id: str
    title: str
    original_title: str
    title_type: str
    imdb_rating: float
    runtime_mins: int | None = None
    year: int | None = None
    genres: list[str]
    num_votes: int = 0
    directors: list[str] = []
    actors: list[str] = []
    language: str | None = None
    languages: list[str] = []
    country_code: str | None = None
    writers: list[str] = []
    composers: list[str] = []
    cinematographers: list[str] = []
    is_anime: bool = False


class TasteProfile(BaseModel):
    """Aggregated taste signals derived from the user's rated titles."""

    director_avg: dict[str, float] = Field(
        default={},
        description="Director name → average user rating across their titles.",
    )
    actor_avg: dict[str, float] = Field(
        default={},
        description="Actor name → average user rating across their titles.",
    )
    genre_avg: dict[str, float] = Field(
        default={},
        description="Genre name → average user rating across titles in that genre.",
    )
    writer_avg: dict[str, float] = Field(
        default={},
        description="Writer name → average user rating across their titles.",
    )
    composer_avg: dict[str, float] = Field(
        default={},
        description="Composer name → average user rating across their titles.",
    )
    cinematographer_avg: dict[str, float] = Field(
        default={},
        description="Cinematographer name → average user rating across their titles.",
    )
    genre_pairs: list[str] = Field(
        default=[],
        description="Top genre interaction pairs derived from user's watchlist.",
    )


class FeatureVector(BaseModel):
    """Engineered features ready for model input."""

    imdb_id: str | None = None
    title: str
    title_type: str
    imdb_rating: float
    runtime_mins: float
    year: int
    num_votes: int
    genre_flags: dict[str, int]
    director_encoded: int | None = None
    decade: int = 2000
    rating_vote_ratio: float = 0.0
    is_anime: bool = False
    director_taste_score: float = 0.0
    has_known_director: bool = False
    actor_taste_score: float = 0.0
    has_known_actor: bool = False
    # Subtask 1: Genre affinity scores
    genre_affinity: dict[str, float] = {}
    # Subtask 2: Director/actor count + mean
    director_taste_count: int = 0
    director_taste_mean: float = 0.0
    actor_taste_count: int = 0
    actor_taste_mean: float = 0.0
    # Subtask 3: Language features
    language_flags: dict[str, int] = {}
    # Subtask 4: Writer taste features
    writer_taste_score: float = 0.0
    has_known_writer: bool = False
    writer_taste_count: int = 0
    writer_taste_mean: float = 0.0
    # Subtask 5: Title type features
    type_flags: dict[str, int] = {}
    # Subtask 6: Genre interaction pairs
    genre_pair_flags: dict[str, int] = {}
    # Subtask 7: Popularity tier, title age, log votes
    popularity_tier: int = 0
    title_age: int = 0
    log_votes: float = 0.0
    # Subtask 8: Composer/cinematographer taste features
    composer_taste_score: float = 0.0
    has_known_composer: bool = False
    cinematographer_taste_score: float = 0.0
    has_known_cinematographer: bool = False
    # Subtask 9: TMDB keyword features
    keyword_affinity_score: float = 0.0
    has_known_keywords: bool = False
    keyword_overlap_count: int = 0
    # Subtask 10: OMDb critic score features
    rt_score: float = 0.0
    metacritic_score: float = 0.0
    imdb_rt_gap: float = 0.0
    imdb_metacritic_gap: float = 0.0


class TitleSearchResult(BaseModel):
    """Lightweight title info for search autocomplete."""

    imdb_id: str
    title: str
    year: int | None = None
    title_type: str
    is_rated: bool = Field(
        default=False,
        description="True if this title is in the user's rated watchlist.",
    )


class PersonSearchResult(BaseModel):
    """Lightweight person info for search autocomplete."""

    name_id: str
    name: str
    primary_profession: str | None = None
    title_count: int = Field(
        description="Number of scored titles featuring this person."
    )


class SimilarTitle(BaseModel):
    """A title similar to the seed, with similarity details."""

    title: str
    title_type: str
    year: int | None = None
    genres: list[str] = []
    imdb_rating: float | None = None
    predicted_score: float | None = None
    similarity_score: float = Field(
        description="Content-based similarity score in [0.0, 1.0].",
    )
    similarity_explanation: list[str] = Field(
        default=[],
        description="Human-readable reasons why this title is similar to the seed.",
    )
    actors: list[str] = []
    director: str | None = None
    language: str | None = None
    imdb_id: str | None = None
    imdb_url: str | None = None
    num_votes: int = 0
    country_code: str | None = None
    is_rated: bool = False


class SimilarResponse(BaseModel):
    """Response from the find-similar endpoint."""

    seed_title: str
    seed_imdb_id: str
    results: list[SimilarTitle]
    total_candidates: int = Field(
        description="How many candidates were considered before top-N.",
    )


class Recommendation(BaseModel):
    """A single title recommendation with score and explanation."""

    title: str = Field(
        description="Primary English title of the recommended title.",
        examples=["Inception"],
    )
    title_type: str = Field(
        description="IMDB title type: `movie`, `tvSeries`, `tvMiniSeries`, or `tvMovie`.",
        examples=["movie"],
    )
    year: int | None = Field(
        description="Release year (or first air year for series).",
        examples=[2010],
    )
    genres: list[str] = Field(
        description="List of IMDB genre tags for this title.",
        examples=[["Action", "Sci-Fi", "Thriller"]],
    )
    predicted_score: float = Field(
        description=(
            "Predicted rating on a 1–10 scale, based on the LightGBM taste model "
            "trained on your personal IMDB ratings. Higher is better."
        ),
        examples=[8.7],
        ge=1.0,
        le=10.0,
    )
    imdb_rating: float | None = Field(
        description="Community average rating on IMDB (1–10).",
        examples=[8.8],
    )
    explanation: list[str] = Field(
        description=(
            "Human-readable reasons why this title was recommended. "
            "Derived from the model's top feature importances."
        ),
        examples=[["Strong match on Sci-Fi genre preference", "High IMDb rating (8.8)"]],
    )
    actors: list[str] = Field(
        default=[],
        description="Top 3 billed actors for this title.",
        examples=[["Leonardo DiCaprio", "Joseph Gordon-Levitt", "Elliot Page"]],
    )
    director: str | None = Field(
        default=None,
        description="Director of this title.",
        examples=["Christopher Nolan"],
    )
    similar_to: list[str] = Field(
        default=[],
        description="Up to 3 titles from your ratings that are similar to this recommendation.",
        examples=[["Interstellar", "The Prestige", "Memento"]],
    )
    imdb_id: str | None = Field(
        default=None,
        description="IMDB title identifier (tconst), e.g. `tt1375666`.",
        examples=["tt1375666"],
    )
    language: str | None = Field(
        default=None,
        description="Original language of the title (e.g. 'English', 'Japanese').",
        examples=["English"],
    )
    imdb_url: str | None = Field(
        default=None,
        description="Direct link to the title's IMDB page.",
        examples=["https://www.imdb.com/title/tt1375666"],
    )
    num_votes: int = Field(
        default=0,
        description="Number of IMDB user votes for this title.",
        examples=[2000000],
    )
    country_code: str | None = Field(
        default=None,
        description="Country of origin code (e.g. 'US', 'JP').",
        examples=["US"],
    )


class RecommendationResponse(BaseModel):
    """Full recommendation response grouped by category."""

    movies: list[Recommendation] = Field(
        default=[],
        description="Ranked movie recommendations, sorted by predicted score descending.",
    )
    series: list[Recommendation] = Field(
        default=[],
        description="Ranked TV series / mini-series recommendations.",
    )
    anime: list[Recommendation] = Field(
        default=[],
        description="Ranked anime recommendations (Japanese animation), sorted by predicted score.",
    )
    model_accuracy: float | None = Field(
        default=None,
        description=(
            "Mean Absolute Error of the taste model on the held-out test split of your "
            "rated titles. A lower value means predictions are closer to your actual ratings. "
            "`null` when a previously saved model was loaded without retraining."
        ),
        examples=[1.557],
    )


class PipelineStatus(BaseModel):
    """Snapshot of the current pipeline state."""

    rated_titles_count: int = Field(
        description="Number of titles loaded from your IMDB export.",
        examples=[2141],
    )
    candidates_count: int = Field(
        description="Number of unseen candidate titles loaded from the IMDB datasets.",
        examples=[11677],
    )
    model_trained: bool = Field(
        description="Whether a taste model is currently loaded in memory.",
        examples=[True],
    )
    last_run: str | None = Field(
        default=None,
        description="ISO 8601 UTC timestamp of the most recent pipeline run.",
        examples=["2026-04-05T14:23:00+00:00"],
    )


class DatasetDownloadResponse(BaseModel):
    """Response from the dataset download endpoint."""

    status: str = Field(
        description="Human-readable result of the download operation.",
        examples=["Datasets ready."],
    )


# --- Feature 1: Runtime Filtering ---


class RecommendationFilters(BaseModel):
    """Optional runtime filters applied on top of config-based defaults."""

    min_year: int | None = Field(
        default=None,
        description="Exclude titles released before this year.",
        examples=[2000],
    )
    max_year: int | None = Field(
        default=None,
        description="Exclude titles released after this year.",
        examples=[2024],
    )
    genres: list[str] | None = Field(
        default=None,
        description="Only include titles matching at least one of these genres.",
        examples=[["Action", "Sci-Fi"]],
    )
    exclude_genres: list[str] | None = Field(
        default=None,
        description="Exclude titles matching any of these genres.",
        examples=[["Horror", "Romance"]],
    )
    languages: list[str] | None = Field(
        default=None,
        description="Only include titles in one of these languages.",
        examples=[["English", "French"]],
    )
    exclude_languages: list[str] | None = Field(
        default=None,
        description="Exclude titles in any of these languages.",
        examples=[["Hindi", "Korean"]],
    )
    min_imdb_rating: float | None = Field(
        default=None,
        description="Minimum community IMDB rating.",
        ge=0.0,
        le=10.0,
        examples=[7.0],
    )
    max_runtime: int | None = Field(
        default=None,
        description="Maximum runtime in minutes.",
        ge=0,
        examples=[180],
    )
    min_predicted_score: float | None = Field(
        default=None,
        description="Override the config min_predicted_score threshold.",
        ge=1.0,
        le=10.0,
        examples=[7.5],
    )
    top_n_movies: int | None = Field(
        default=None,
        description="Override number of movie recommendations to return (default: config value).",
        ge=0,
        le=100,
    )
    top_n_series: int | None = Field(
        default=None,
        description="Override number of series recommendations to return (default: config value).",
        ge=0,
        le=100,
    )
    top_n_anime: int | None = Field(
        default=None,
        description="Override number of anime recommendations to return (default: config value).",
        ge=0,
        le=100,
    )
    min_vote_count: int | None = Field(
        default=None,
        description="Override the minimum IMDB vote count for candidates (default: config value).",
        ge=0,
        examples=[10000],
    )
    country_code: str | None = Field(
        default=None,
        description="Only include titles from this country (e.g. 'US', 'JP'). Case-insensitive.",
        examples=["US"],
    )


# --- Feature 2: Dismiss Recommendations ---


class DismissResponse(BaseModel):
    """Response from dismiss/restore operations."""

    imdb_id: str = Field(
        description="The IMDB title identifier.",
        examples=["tt1375666"],
    )
    action: str = Field(
        description="Action performed: 'dismissed' or 'restored'.",
        examples=["dismissed"],
    )


class DismissedTitle(BaseModel):
    """Metadata for a dismissed title."""

    imdb_id: str
    title: str | None = None
    year: int | None = None
    title_type: str | None = None
    genres: list[str] = []
    imdb_url: str | None = None


class DismissedListResponse(BaseModel):
    """List of all dismissed IMDB IDs."""

    dismissed_ids: list[str] = Field(
        default=[],
        description="IMDB IDs that have been dismissed.",
    )
    dismissed_titles: list[DismissedTitle] = Field(
        default=[],
        description="Dismissed titles with metadata (when available).",
    )
    count: int = Field(
        description="Total number of dismissed titles.",
        examples=[5],
    )
