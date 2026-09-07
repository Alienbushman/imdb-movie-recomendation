from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class ImdbDatasetsConfig(BaseModel):
    title_basics: str = "data/datasets/title.basics.tsv.gz"
    title_ratings: str = "data/datasets/title.ratings.tsv.gz"
    title_principals: str = "data/datasets/title.principals.tsv.gz"
    title_akas: str = "data/datasets/title.akas.tsv.gz"
    name_basics: str = "data/datasets/name.basics.tsv.gz"
    title_crew: str = "data/datasets/title.crew.tsv.gz"
    anime_list: str = "data/datasets/anime-list-mini.json"
    anime_list_url: str = (
        "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-mini.json"
    )
    min_vote_count: int = 100
    min_rating: float = 5.0
    min_year: int = 1970
    include_title_types: list[str] = ["movie", "tvSeries", "tvMiniSeries", "tvMovie"]


class FeaturesConfig(BaseModel):
    popularity_tiers: list[int] = [25000, 100000, 500000]
    top_languages: list[str] = [
        "English",
        "French",
        "German",
        "Japanese",
        "Korean",
        "Spanish",
        "Italian",
        "Hindi",
        "Chinese",
        "Portuguese",
        "Swedish",
        "Danish",
        "Turkish",
        "Russian",
    ]
    max_genre_pairs: int = 15


class ModelSplitConfig(BaseModel):
    """T1.3: Temporal vs random train/test split."""

    mode: str = "temporal"  # "temporal" | "random"


class ModelDecayConfig(BaseModel):
    """T1.4: Per-row sample_weight as exp(-days_since / half_life)."""

    enabled: bool = True
    half_life_days: int = 730
    min_weight: float = 0.05
    fallback_weight: float = 0.5


class ModelCVConfig(BaseModel):
    """T2.9: K-fold cross-validation (expanding window or random)."""

    enabled: bool = False
    n_folds: int = 5
    strategy: str = "temporal"  # "temporal" | "random"


class ModelOptunaConfig(BaseModel):
    """T1.2: Optuna TPE hyperparameter search."""

    enabled: bool = False
    n_trials: int = 25
    timeout_seconds: int = 600


class ModelTrainingConfig(BaseModel):
    """T2.8 + T3.13: Implicit negatives + feedback signals merged into training."""

    use_dismissals: bool = True
    dismissal_label: float = 2.0
    dismissal_weight: float = 0.3
    use_feedback: bool = True
    feedback_up_label: float = 9.0
    feedback_down_label: float = 3.0
    feedback_not_interested_label: float = 2.0
    feedback_weight: float = 0.3


class ModelShapConfig(BaseModel):
    """T1.5: SHAP TreeExplainer for per-recommendation explanations."""

    enabled: bool = True
    top_k: int = 3


class ModelConfig(BaseModel):
    # T1.1: ranking objective + ranking metric
    objective: str = "lambdarank"  # "lambdarank" | "regression"
    metric: str = "ndcg"  # "ndcg" | "map" | "mae" | "rmse"
    ndcg_at_k: int = 10
    # Rating at or above which a holdout title counts as "relevant" for
    # map/mrr/recall. 7.0 made both pin to 1.0000 on a library where ~47% of
    # ratings are 7+, so the metrics discriminated nothing.
    relevance_threshold: float = 8.0

    # Core LGB hyperparameters
    n_estimators: int = 200
    learning_rate: float = 0.05
    max_depth: int = 6
    num_leaves: int = 31
    min_child_samples: int = 5
    reg_alpha: float = 0.0
    reg_lambda: float = 0.0
    feature_fraction: float = 1.0
    bagging_fraction: float = 1.0
    bagging_freq: int = 0

    test_size: float = 0.2
    random_state: int = 42

    split: ModelSplitConfig = ModelSplitConfig()
    decay: ModelDecayConfig = ModelDecayConfig()
    cv: ModelCVConfig = ModelCVConfig()
    optuna: ModelOptunaConfig = ModelOptunaConfig()
    training: ModelTrainingConfig = ModelTrainingConfig()
    shap: ModelShapConfig = ModelShapConfig()


class SimilarityConfig(BaseModel):
    """T2.7: similarity engine for /similar/{id}."""

    method: str = "leaves"  # "leaves" | "jaccard"


class MMRConfig(BaseModel):
    """T2.6: Maximal Marginal Relevance re-ranking."""

    enabled: bool = True
    lambda_: float = 0.7
    pool_size: int = 200


class RecommendationsConfig(BaseModel):
    top_n_movies: int = 20
    top_n_series: int = 10
    top_n_anime: int = 10
    min_predicted_score: float = 6.5


class CategoryConfig(BaseModel):
    title_types: list[str]
    label: str
    genre_filter: str | None = None


class DataConfig(BaseModel):
    watchlist_path: str = "data/watchlist.csv"
    cache_dir: str = "data/cache"


class Settings(BaseSettings):
    imdb_datasets: ImdbDatasetsConfig = ImdbDatasetsConfig()
    model: ModelConfig = ModelConfig()
    similarity: SimilarityConfig = SimilarityConfig()
    mmr: MMRConfig = MMRConfig()
    recommendations: RecommendationsConfig = RecommendationsConfig()
    categories: dict[str, CategoryConfig] = {}
    data: DataConfig = DataConfig()
    features: FeaturesConfig = FeaturesConfig()


def load_yaml_config() -> dict:
    config_path = PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


@lru_cache
def get_settings() -> Settings:
    yaml_data = load_yaml_config()
    return Settings(**yaml_data)
