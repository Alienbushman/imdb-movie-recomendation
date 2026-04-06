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
    anime_list_url: str = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-mini.json"
    min_vote_count: int = 10000
    min_rating: float = 5.0
    min_year: int = 1970
    include_title_types: list[str] = ["movie", "tvSeries", "tvMiniSeries", "tvMovie"]


class FeaturesConfig(BaseModel):
    popularity_tiers: list[int] = [25000, 100000, 500000]
    top_languages: list[str] = [
        "English", "French", "German", "Japanese", "Korean", "Spanish",
        "Italian", "Hindi", "Chinese", "Portuguese", "Swedish", "Danish",
        "Turkish", "Russian",
    ]
    max_genre_pairs: int = 15


class ModelConfig(BaseModel):
    n_estimators: int = 200
    learning_rate: float = 0.05
    max_depth: int = 6
    num_leaves: int = 31
    min_child_samples: int = 5
    test_size: float = 0.2
    random_state: int = 42


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
