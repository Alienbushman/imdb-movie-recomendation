import logging
import pickle
import time

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from app.core.config import PROJECT_ROOT, get_settings
from app.models.schemas import FeatureVector, RatedTitle, TasteProfile
from app.services.features import (
    build_taste_profile,
    features_to_dataframe,
    rated_title_to_features,
)

logger = logging.getLogger(__name__)

MODEL_PATH = PROJECT_ROOT / "data" / "taste_model.pkl"


def train_taste_model(
    titles: list[RatedTitle],
    rated_actors: dict[str, list[str]] | None = None,
    rated_composers: dict[str, list[str]] | None = None,
    rated_cinematographers: dict[str, list[str]] | None = None,
) -> tuple[lgb.LGBMRegressor, float, list[str], TasteProfile]:
    """Train a LightGBM model to predict the user's rating from title features.

    Returns the trained model, MAE on test set, feature names, and taste profile.
    """
    t0 = time.perf_counter()
    settings = get_settings()
    cfg = settings.model

    taste = build_taste_profile(titles, rated_actors, rated_composers, rated_cinematographers)
    logger.info(
        "Taste profile: %d directors, %d actors",
        len(taste.director_avg),
        len(taste.actor_avg),
    )

    logger.info("Building feature vectors for %d titles", len(titles))
    features = [rated_title_to_features(t, taste) for t in titles]
    X = features_to_dataframe(features)
    y = pd.Series([t.user_rating for t in titles])

    feature_names = list(X.columns)
    logger.info("Feature matrix: %d samples × %d features", X.shape[0], X.shape[1])
    logger.info(
        "Target distribution: mean=%.2f, std=%.2f, min=%d, max=%d",
        y.mean(),
        y.std(),
        y.min(),
        y.max(),
    )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=cfg.test_size, random_state=cfg.random_state
    )
    logger.info(
        "Train/test split: %d train, %d test (test_size=%.2f)",
        len(X_train),
        len(X_test),
        cfg.test_size,
    )

    logger.info(
        "Training LightGBM: n_estimators=%d, lr=%.4f, "
        "max_depth=%d, num_leaves=%d, min_child_samples=%d",
        cfg.n_estimators,
        cfg.learning_rate,
        cfg.max_depth,
        cfg.num_leaves,
        cfg.min_child_samples,
    )
    model = lgb.LGBMRegressor(
        n_estimators=cfg.n_estimators,
        learning_rate=cfg.learning_rate,
        max_depth=cfg.max_depth,
        num_leaves=cfg.num_leaves,
        min_child_samples=cfg.min_child_samples,
        random_state=cfg.random_state,
        verbose=-1,
    )

    fit_start = time.perf_counter()
    model.fit(X_train, y_train)
    logger.info("Model fitting completed in %.2fs", time.perf_counter() - fit_start)

    predictions = model.predict(X_test)
    mae = float(np.mean(np.abs(predictions - y_test)))
    logger.info(
        "Model evaluation — MAE: %.3f, prediction range: [%.2f, %.2f] on %d test samples",
        mae,
        float(predictions.min()),
        float(predictions.max()),
        len(y_test),
    )

    # Save model + taste profile
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(
            {
                "model": model,
                "feature_names": feature_names,
                "taste_profile": taste.model_dump(),
            },
            f,
        )
    model_size = MODEL_PATH.stat().st_size / 1024
    logger.info(
        "Model saved to %s (%.1f KB) — total training time: %.2fs",
        MODEL_PATH,
        model_size,
        time.perf_counter() - t0,
    )

    return model, mae, feature_names, taste


def load_taste_model() -> tuple[lgb.LGBMRegressor, list[str], TasteProfile] | None:
    """Load a previously trained model and taste profile from disk."""
    if not MODEL_PATH.exists():
        logger.info("No saved model found at %s", MODEL_PATH)
        return None
    t0 = time.perf_counter()
    with open(MODEL_PATH, "rb") as f:
        data = pickle.load(f)  # noqa: S301
    taste_data = data.get("taste_profile")
    taste = TasteProfile(**taste_data) if taste_data else TasteProfile()
    model_kb = MODEL_PATH.stat().st_size / 1024
    logger.info(
        "Loaded model from %s in %.2fs (%d features, %.1f KB, taste: %d dirs/%d actors)",
        MODEL_PATH,
        time.perf_counter() - t0,
        len(data["feature_names"]),
        model_kb,
        len(taste.director_avg),
        len(taste.actor_avg),
    )
    return data["model"], data["feature_names"], taste


def predict_scores(
    model: lgb.LGBMRegressor,
    feature_names: list[str],
    features: list[FeatureVector],
) -> list[float]:
    """Predict user ratings for a list of feature vectors."""
    t0 = time.perf_counter()
    X = features_to_dataframe(features)
    # Ensure columns match training features
    missing_cols = [col for col in feature_names if col not in X.columns]
    if missing_cols:
        logger.debug("Adding %d missing columns: %s", len(missing_cols), missing_cols)
        X = X.assign(**{col: 0 for col in missing_cols})
    X = X[feature_names]

    raw = model.predict(X)
    scores = [float(np.clip(score, 1.0, 10.0)) for score in raw]
    clamped = sum(1 for r, s in zip(raw, scores) if float(r) != s)
    logger.info(
        "Predicted scores for %d candidates in %.2fs — mean=%.2f, min=%.2f, max=%.2f, clamped=%d",
        len(scores),
        time.perf_counter() - t0,
        np.mean(scores),
        min(scores),
        max(scores),
        clamped,
    )
    return scores


def get_feature_importances(
    model: lgb.LGBMRegressor,
    feature_names: list[str],
) -> dict[str, float]:
    """Return feature importances as a name->importance dict."""
    importances = model.feature_importances_
    total = sum(importances)
    if total == 0:
        return {}
    return {
        name: float(imp / total)
        for name, imp in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
    }
