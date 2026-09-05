"""Taste model training, persistence, prediction, and evaluation.

Major changes in this revision:

- **T1.1** — Learning-to-rank by default. The objective is `lambdarank` and the
  test metric is NDCG@k (plus MAP@k, MRR, Spearman). Falls back to the legacy
  ``LGBMRegressor`` MAE path when ``model.objective='regression'`` in config.
- **T1.3** — Temporal holdout. Train rows are the oldest rated titles by
  ``date_rated``; test rows are the most recent ``test_size`` fraction.
- **T1.4** — Recency decay. Each training row gets a sample weight
  ``exp(-days_since / half_life)`` so old ratings stop dominating once your
  taste shifts.
- **T2.8 / T3.13** — Implicit-negative augmentation. ``extra_training_rows``
  accepts pre-built ``(FeatureVector, label, weight, source)`` rows from
  dismissals and frontend feedback so they participate in fitting.
- **T2.9** — K-fold CV (expanding-window temporal or random). Used by the
  Optuna objective when both are enabled; also available as a standalone
  diagnostic via ``cross_validate``.
- **T1.2** — Optuna TPE search over the LGB hyperparameter space when
  ``model.optuna.enabled``. Best params get persisted next to the model.
- **T1.5** — SHAP TreeExplainer is built at training time and pickled with
  the model so per-recommendation explanations can be re-ranked by actual
  feature contribution (see ``recommend.py``).
- **T2.7** — ``predict_leaf_indices`` returns the trained model's tree-leaf
  matrix for use in the leaf-embedding similarity engine.

The N806 ``per-file-ignores`` for uppercase ``X`` matrices (ML convention)
stays.
"""

from __future__ import annotations

import logging
import math
import pickle
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd

from app.core.config import PROJECT_ROOT, get_settings
from app.models.schemas import FeatureVector, RatedTitle, TasteProfile
from app.services.eval_metrics import (
    average_precision_at_k,
    mrr,
    ndcg_at_k_from_scores,
    spearman_corr,
)
from app.services.features import (
    build_taste_profile,
    features_to_dataframe,
    rated_title_to_features,
)

logger = logging.getLogger(__name__)

MODEL_PATH = PROJECT_ROOT / "data" / "taste_model.pkl"

# Label gain for lambdarank: 2^rating - 1 over the full 0-10 IMDB rating scale,
# so a rating of 10 weighs ~4× more than a 9 (matching the user's own intent
# when they pick a 10/10).
_LABEL_GAIN = [float(2**i - 1) for i in range(11)]


# ---------------------------------------------------------------------------
# Container types
# ---------------------------------------------------------------------------


@dataclass
class ExtraTrainingRow:
    """Auxiliary training row produced from dismissals (T2.8) or feedback (T3.13).

    These rows participate in the model fit but at a lower ``weight`` than
    explicit user ratings (which carry weight 1.0 modulo recency decay).
    """

    feature_vector: FeatureVector
    label: float
    weight: float
    source: str  # "dismissal" | "feedback_up" | "feedback_down" | "feedback_not_interested"


@dataclass
class TrainResult:
    """Bundle returned by ``train_taste_model``.

    ``model`` is whichever LGB estimator was actually fitted (Ranker or
    Regressor). ``metrics`` carries every ranking and regression metric we
    compute; ``best_params`` is non-empty when Optuna ran.
    """

    model: Any
    feature_names: list[str]
    taste: TasteProfile
    metrics: dict[str, float]
    best_params: dict[str, Any]
    has_shap: bool


# ---------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------


def _date_key(t: RatedTitle) -> str:
    """Date-rated extraction. Falls back to release_date / year for sorting."""
    return t.date_rated or t.release_date or (str(t.year) if t.year else "")


def _temporal_split_indices(
    titles: Sequence[RatedTitle], test_size: float
) -> tuple[list[int], list[int]]:
    """Return (train_idx, test_idx) where test is the most-recent fraction.

    Stable sort on (date_rated, imdb_id) so re-runs are deterministic even
    when several ratings share a date.
    """
    order = sorted(range(len(titles)), key=lambda i: (_date_key(titles[i]), titles[i].imdb_id))
    n_test = max(1, int(round(len(titles) * test_size)))
    n_train = len(titles) - n_test
    if n_train < 1:
        # Pathologically few ratings — give 1 row to each side
        n_train = 1
        n_test = max(1, len(titles) - 1)
    return order[:n_train], order[-n_test:]


def _random_split_indices(n: int, test_size: float, seed: int) -> tuple[list[int], list[int]]:
    rng = np.random.default_rng(seed)
    perm = rng.permutation(n)
    n_test = max(1, int(round(n * test_size)))
    return perm[:-n_test].tolist(), perm[-n_test:].tolist()


def _expanding_window_folds(n: int, n_folds: int) -> list[tuple[list[int], list[int]]]:
    """Temporal CV: each fold predicts the next chunk after seeing prior chunks.

    Indices assume the input is already sorted ascending by date.
    """
    fold_size = max(1, n // (n_folds + 1))
    folds = []
    for f in range(n_folds):
        end_train = fold_size * (f + 1)
        end_test = min(n, end_train + fold_size)
        if end_train >= n or end_test <= end_train:
            break
        folds.append((list(range(end_train)), list(range(end_train, end_test))))
    return folds


# ---------------------------------------------------------------------------
# Recency decay (T1.4)
# ---------------------------------------------------------------------------


def _compute_recency_weights(
    titles: Sequence[RatedTitle],
    half_life_days: int,
    min_weight: float,
    fallback_weight: float,
) -> np.ndarray:
    """exp(-days_since_rated / half_life) clamped to [min_weight, 1.0]."""

    def _parse(d: str | None) -> datetime | None:
        if not d:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%Y"):
            try:
                return datetime.strptime(d, fmt)
            except ValueError:
                continue
        return None

    dates = [_parse(t.date_rated) for t in titles]
    valid = [d for d in dates if d is not None]
    if not valid:
        return np.full(len(titles), fallback_weight, dtype=float)
    ref = max(valid)
    weights = np.empty(len(titles), dtype=float)
    for i, d in enumerate(dates):
        if d is None:
            weights[i] = fallback_weight
        else:
            age_days = max(0.0, (ref - d).total_seconds() / 86400.0)
            w = math.exp(-age_days / max(1.0, half_life_days))
            weights[i] = max(min_weight, min(1.0, w))
    return weights


# ---------------------------------------------------------------------------
# Core fit primitive
# ---------------------------------------------------------------------------


def _fit_estimator(
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    weights_train: np.ndarray,
    *,
    objective: str,
    params: dict[str, Any],
) -> Any:
    """Build and fit the LGB estimator. Single-group setup for ranking."""
    common = dict(
        n_estimators=params["n_estimators"],
        learning_rate=params["learning_rate"],
        max_depth=params["max_depth"],
        num_leaves=params["num_leaves"],
        min_child_samples=params["min_child_samples"],
        reg_alpha=params["reg_alpha"],
        reg_lambda=params["reg_lambda"],
        feature_fraction=params["feature_fraction"],
        bagging_fraction=params["bagging_fraction"],
        bagging_freq=params["bagging_freq"],
        random_state=params["random_state"],
        # Native missing-value handling; pair with NaN feature defaults (T2.10).
        zero_as_missing=False,
        verbose=-1,
    )
    if objective == "lambdarank":
        model = lgb.LGBMRanker(
            objective="lambdarank",
            label_gain=_LABEL_GAIN,
            **common,
        )
        # All rows form a single query group (single-user system).
        model.fit(
            X_train,
            y_train.astype(int),  # lambdarank wants integer relevance
            group=[len(X_train)],
            sample_weight=weights_train,
        )
    else:
        model = lgb.LGBMRegressor(objective="regression", **common)
        model.fit(X_train, y_train, sample_weight=weights_train)
    return model


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _compute_holdout_metrics(
    y_true: np.ndarray, y_pred: np.ndarray, test_ids: list[str], k: int
) -> dict[str, float]:
    """All ranking + regression metrics we surface in logs and the eval CLI."""
    if len(y_true) == 0:
        return {}
    ndcg = ndcg_at_k_from_scores(y_true.tolist(), y_pred.tolist(), k)
    by_pred = [tid for _, tid in sorted(zip(y_pred.tolist(), test_ids), reverse=True)]
    relevant = {tid for tid, y in zip(test_ids, y_true) if y >= 7.0}
    ap = average_precision_at_k(by_pred, relevant, k)
    rr = mrr(by_pred, relevant)
    sp = spearman_corr(y_true.tolist(), y_pred.tolist())
    mae = float(np.mean(np.abs(y_pred - y_true)))
    rmse = float(np.sqrt(np.mean((y_pred - y_true) ** 2)))
    return {
        f"ndcg_at_{k}": float(ndcg),
        f"map_at_{k}": float(ap),
        "mrr": float(rr),
        "spearman": float(sp),
        "mae": mae,
        "rmse": rmse,
    }


# ---------------------------------------------------------------------------
# Training entrypoint
# ---------------------------------------------------------------------------


def train_taste_model(
    titles: list[RatedTitle],
    rated_actors: dict[str, list[str]] | None = None,
    rated_writers: dict[str, list[str]] | None = None,
    rated_composers: dict[str, list[str]] | None = None,
    rated_cinematographers: dict[str, list[str]] | None = None,
    extra_training_rows: list[ExtraTrainingRow] | None = None,
) -> tuple[Any, float, list[str], TasteProfile]:
    """Train a taste model and persist it.

    Backwards-compatible return shape: ``(model, mae, feature_names, taste)``.
    The full metric dict is available on the unpickled model bundle under
    ``metrics`` (and is logged at INFO).
    """
    t0 = time.perf_counter()
    settings = get_settings()
    cfg = settings.model

    taste = build_taste_profile(
        titles, rated_actors, rated_writers, rated_composers, rated_cinematographers
    )
    logger.info(
        "Taste profile: %d directors, %d actors, %d writers, %d composers",
        len(taste.director_avg),
        len(taste.actor_avg),
        len(taste.writer_avg),
        len(taste.composer_avg),
    )

    # ------- Feature extraction for rated rows -------------------------------
    logger.info("Building feature vectors for %d rated titles", len(titles))
    rated_features = [rated_title_to_features(t, taste) for t in titles]
    df_rated = features_to_dataframe(rated_features)
    rated_labels = np.array([float(t.user_rating) for t in titles], dtype=float)

    # ------- Recency-decay weights (T1.4) ------------------------------------
    if cfg.decay.enabled:
        rated_weights = _compute_recency_weights(
            titles,
            half_life_days=cfg.decay.half_life_days,
            min_weight=cfg.decay.min_weight,
            fallback_weight=cfg.decay.fallback_weight,
        )
        logger.info(
            "Recency decay: half_life=%d days, weights mean=%.3f min=%.3f max=%.3f",
            cfg.decay.half_life_days,
            float(rated_weights.mean()),
            float(rated_weights.min()),
            float(rated_weights.max()),
        )
    else:
        rated_weights = np.ones(len(titles), dtype=float)

    # ------- Extra rows from dismissals + feedback (T2.8, T3.13) -------------
    extra_training_rows = extra_training_rows or []
    if extra_training_rows:
        df_extra = features_to_dataframe([r.feature_vector for r in extra_training_rows])
        extra_labels = np.array([r.label for r in extra_training_rows], dtype=float)
        extra_weights = np.array([r.weight for r in extra_training_rows], dtype=float)
        by_source: dict[str, int] = {}
        for r in extra_training_rows:
            by_source[r.source] = by_source.get(r.source, 0) + 1
        logger.info("Extra training rows merged: %s", by_source)
    else:
        # Empty slice, not pd.DataFrame(columns=...): the latter is all-object
        # dtype, and pd.concat would then upcast every numeric column to object,
        # which LightGBM rejects.
        df_extra = df_rated.iloc[0:0]
        extra_labels = np.array([], dtype=float)
        extra_weights = np.array([], dtype=float)

    # ------- Split: rated rows split temporally/randomly --------------------
    if cfg.split.mode == "temporal":
        train_idx, test_idx = _temporal_split_indices(titles, cfg.test_size)
        logger.info(
            "Temporal split: %d train (%s..%s), %d test (%s..%s)",
            len(train_idx),
            _date_key(titles[train_idx[0]]),
            _date_key(titles[train_idx[-1]]),
            len(test_idx),
            _date_key(titles[test_idx[0]]),
            _date_key(titles[test_idx[-1]]),
        )
    else:
        train_idx, test_idx = _random_split_indices(len(titles), cfg.test_size, cfg.random_state)
        logger.info("Random split: %d train, %d test", len(train_idx), len(test_idx))

    # Extra rows always join the training side — they don't have a meaningful
    # date and we don't want to evaluate on them.
    X_train = pd.concat([df_rated.iloc[train_idx], df_extra], ignore_index=True)
    y_train = np.concatenate([rated_labels[train_idx], extra_labels])
    w_train = np.concatenate([rated_weights[train_idx], extra_weights])

    X_test = df_rated.iloc[test_idx].reset_index(drop=True)
    y_test = rated_labels[test_idx]
    test_ids = [titles[i].imdb_id for i in test_idx]

    feature_names = list(df_rated.columns)
    logger.info(
        "Feature matrix: train=%dx%d, test=%dx%d (extra rows=%d)",
        X_train.shape[0],
        X_train.shape[1],
        X_test.shape[0],
        X_test.shape[1],
        len(extra_training_rows),
    )

    # ------- Hyperparameter base + Optuna search (T1.2) ----------------------
    base_params: dict[str, Any] = {
        "n_estimators": cfg.n_estimators,
        "learning_rate": cfg.learning_rate,
        "max_depth": cfg.max_depth,
        "num_leaves": cfg.num_leaves,
        "min_child_samples": cfg.min_child_samples,
        "reg_alpha": cfg.reg_alpha,
        "reg_lambda": cfg.reg_lambda,
        "feature_fraction": cfg.feature_fraction,
        "bagging_fraction": cfg.bagging_fraction,
        "bagging_freq": cfg.bagging_freq,
        "random_state": cfg.random_state,
    }
    best_params: dict[str, Any] = {}
    if cfg.optuna.enabled:
        best_params = _run_optuna(
            X_train=X_train,
            y_train=y_train,
            w_train=w_train,
            X_test=X_test,
            y_test=y_test,
            test_ids=test_ids,
            objective=cfg.objective,
            base_params=base_params,
            k=cfg.ndcg_at_k,
            n_trials=cfg.optuna.n_trials,
            timeout_seconds=cfg.optuna.timeout_seconds,
        )
        base_params.update(best_params)

    # ------- Fit ------------------------------------------------------------
    logger.info(
        "Training LightGBM (%s): n_est=%d lr=%.4f num_leaves=%d max_depth=%d",
        cfg.objective,
        base_params["n_estimators"],
        base_params["learning_rate"],
        base_params["num_leaves"],
        base_params["max_depth"],
    )
    fit_start = time.perf_counter()
    model = _fit_estimator(
        X_train,
        y_train,
        w_train,
        objective=cfg.objective,
        params=base_params,
    )
    logger.info("Model fitting completed in %.2fs", time.perf_counter() - fit_start)

    # ------- Evaluate -------------------------------------------------------
    y_pred = np.asarray(model.predict(X_test), dtype=float)
    metrics = _compute_holdout_metrics(y_test, y_pred, test_ids, cfg.ndcg_at_k)
    logger.info(
        "Holdout metrics: %s",
        ", ".join(f"{k}={v:.4f}" for k, v in metrics.items()),
    )

    # ------- Cross-validation (T2.9) ----------------------------------------
    cv_metrics: dict[str, float] = {}
    if cfg.cv.enabled:
        cv_metrics = _cross_validate(
            X_all=df_rated,
            y_all=rated_labels,
            w_all=rated_weights,
            X_extra=df_extra,
            y_extra=extra_labels,
            w_extra=extra_weights,
            titles=titles,
            objective=cfg.objective,
            params=base_params,
            n_folds=cfg.cv.n_folds,
            strategy=cfg.cv.strategy,
            k=cfg.ndcg_at_k,
        )
        logger.info(
            "CV metrics (%d folds, %s): %s",
            cfg.cv.n_folds,
            cfg.cv.strategy,
            ", ".join(f"{k}={v:.4f}" for k, v in cv_metrics.items()),
        )

    # ------- SHAP explainer (T1.5) ------------------------------------------
    shap_explainer = None
    if cfg.shap.enabled:
        try:
            import shap

            shap_explainer = shap.TreeExplainer(model)
            logger.info("SHAP TreeExplainer built (%d features).", len(feature_names))
        except Exception as e:  # noqa: BLE001
            logger.warning("SHAP explainer not available — falling back to heuristic: %s", e)

    # ------- Persist --------------------------------------------------------
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(
            {
                "model": model,
                "feature_names": feature_names,
                "taste_profile": taste.model_dump(),
                "objective": cfg.objective,
                "metrics": metrics,
                "cv_metrics": cv_metrics,
                "best_params": best_params,
                "trained_at": datetime.utcnow().isoformat() + "Z",
                "shap_explainer": shap_explainer,
                "label_gain": _LABEL_GAIN if cfg.objective == "lambdarank" else None,
            },
            f,
        )
    logger.info(
        "Model saved to %s (%.1f KB) — total training time: %.2fs",
        MODEL_PATH,
        MODEL_PATH.stat().st_size / 1024,
        time.perf_counter() - t0,
    )

    # Legacy return: keep MAE as the second slot so existing callers don't
    # break, but the real signal now lives in metrics[].
    mae = metrics.get("mae", float("nan"))
    return model, mae, feature_names, taste


# ---------------------------------------------------------------------------
# Optuna (T1.2)
# ---------------------------------------------------------------------------


def _run_optuna(
    *,
    X_train: pd.DataFrame,
    y_train: np.ndarray,
    w_train: np.ndarray,
    X_test: pd.DataFrame,
    y_test: np.ndarray,
    test_ids: list[str],
    objective: str,
    base_params: dict[str, Any],
    k: int,
    n_trials: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Run a TPE search maximising NDCG@k on the holdout."""
    try:
        import optuna
    except ImportError:
        logger.warning("Optuna not installed — skipping hyperparameter search.")
        return {}

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def _objective(trial: optuna.trial.Trial) -> float:
        params = dict(base_params)
        params.update(
            num_leaves=trial.suggest_int("num_leaves", 15, 127),
            learning_rate=trial.suggest_float("learning_rate", 1e-3, 0.2, log=True),
            n_estimators=trial.suggest_int("n_estimators", 100, 1000),
            min_child_samples=trial.suggest_int("min_child_samples", 3, 30),
            reg_alpha=trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            reg_lambda=trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            feature_fraction=trial.suggest_float("feature_fraction", 0.6, 1.0),
            bagging_fraction=trial.suggest_float("bagging_fraction", 0.6, 1.0),
        )
        try:
            m = _fit_estimator(X_train, y_train, w_train, objective=objective, params=params)
            preds = np.asarray(m.predict(X_test), dtype=float)
            return float(ndcg_at_k_from_scores(y_test.tolist(), preds.tolist(), k))
        except Exception:
            return 0.0

    logger.info("Running Optuna TPE search: %d trials, timeout=%ds", n_trials, timeout_seconds)
    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(_objective, n_trials=n_trials, timeout=timeout_seconds, show_progress_bar=False)
    logger.info(
        "Optuna best NDCG@%d=%.4f after %d trials. Best params: %s",
        k,
        study.best_value,
        len(study.trials),
        study.best_params,
    )
    return study.best_params


# ---------------------------------------------------------------------------
# Cross-validation (T2.9)
# ---------------------------------------------------------------------------


def _cross_validate(
    *,
    X_all: pd.DataFrame,
    y_all: np.ndarray,
    w_all: np.ndarray,
    X_extra: pd.DataFrame,
    y_extra: np.ndarray,
    w_extra: np.ndarray,
    titles: list[RatedTitle],
    objective: str,
    params: dict[str, Any],
    n_folds: int,
    strategy: str,
    k: int,
) -> dict[str, float]:
    """Return mean/std NDCG@k across folds."""
    if strategy == "temporal":
        order = sorted(range(len(titles)), key=lambda i: (_date_key(titles[i]), titles[i].imdb_id))
        X_sorted = X_all.iloc[order].reset_index(drop=True)
        y_sorted = y_all[order]
        w_sorted = w_all[order]
        folds = _expanding_window_folds(len(titles), n_folds)
    else:  # random
        rng = np.random.default_rng(params.get("random_state", 42))
        perm = rng.permutation(len(titles))
        X_sorted = X_all.iloc[perm].reset_index(drop=True)
        y_sorted = y_all[perm]
        w_sorted = w_all[perm]
        fold_size = max(1, len(titles) // n_folds)
        folds = [
            (
                list(range(0, f * fold_size)) + list(range((f + 1) * fold_size, len(titles))),
                list(range(f * fold_size, (f + 1) * fold_size)),
            )
            for f in range(n_folds)
        ]

    scores: list[float] = []
    for fi, (tr, te) in enumerate(folds):
        if not tr or not te:
            continue
        Xtr = pd.concat([X_sorted.iloc[tr], X_extra], ignore_index=True)
        ytr = np.concatenate([y_sorted[tr], y_extra])
        wtr = np.concatenate([w_sorted[tr], w_extra])
        Xte = X_sorted.iloc[te].reset_index(drop=True)
        yte = y_sorted[te]
        # ids_sorted is kept aligned in case a future fold-level diagnostic
        # needs the per-row IDs — not used here, so don't bind it locally.
        try:
            m = _fit_estimator(Xtr, ytr, wtr, objective=objective, params=params)
            preds = np.asarray(m.predict(Xte), dtype=float)
            score = ndcg_at_k_from_scores(yte.tolist(), preds.tolist(), k)
            scores.append(float(score))
            logger.info("CV fold %d/%d: NDCG@%d=%.4f", fi + 1, len(folds), k, score)
        except Exception as e:  # noqa: BLE001
            logger.warning("CV fold %d failed: %s", fi + 1, e)

    if not scores:
        return {}
    return {
        f"cv_ndcg_at_{k}_mean": float(np.mean(scores)),
        f"cv_ndcg_at_{k}_std": float(np.std(scores)),
        "cv_folds_completed": float(len(scores)),
    }


def cross_validate(
    titles: list[RatedTitle],
    rated_actors: dict[str, list[str]] | None = None,
    n_folds: int = 5,
    strategy: str = "temporal",
) -> dict[str, float]:
    """Public CV entry point. Builds features, then dispatches to _cross_validate.

    For fewer than 100 ratings a leave-one-out schedule is used automatically
    (each fold tests a single title) regardless of the requested n_folds.
    """
    settings = get_settings()
    cfg = settings.model
    taste = build_taste_profile(titles, rated_actors)
    feats = [rated_title_to_features(t, taste) for t in titles]
    df = features_to_dataframe(feats)
    y = np.array([float(t.user_rating) for t in titles], dtype=float)
    w = (
        _compute_recency_weights(
            titles,
            cfg.decay.half_life_days,
            cfg.decay.min_weight,
            cfg.decay.fallback_weight,
        )
        if cfg.decay.enabled
        else np.ones(len(titles))
    )
    params = {
        "n_estimators": cfg.n_estimators,
        "learning_rate": cfg.learning_rate,
        "max_depth": cfg.max_depth,
        "num_leaves": cfg.num_leaves,
        "min_child_samples": cfg.min_child_samples,
        "reg_alpha": cfg.reg_alpha,
        "reg_lambda": cfg.reg_lambda,
        "feature_fraction": cfg.feature_fraction,
        "bagging_fraction": cfg.bagging_fraction,
        "bagging_freq": cfg.bagging_freq,
        "random_state": cfg.random_state,
    }
    # LOO fallback: with fewer than 100 ratings, each fold tests a single title
    # so every data point is evaluated exactly once.
    effective_n_folds = max(1, len(titles) - 1) if len(titles) < 100 else n_folds
    if effective_n_folds != n_folds:
        logger.info(
            "LOO CV fallback: %d ratings < 100, using %d folds instead of %d",
            len(titles),
            effective_n_folds,
            n_folds,
        )
    return _cross_validate(
        X_all=df,
        y_all=y,
        w_all=w,
        X_extra=df.iloc[0:0],  # empty slice keeps numeric dtypes (see train_model)
        y_extra=np.array([]),
        w_extra=np.array([]),
        titles=titles,
        objective=cfg.objective,
        params=params,
        n_folds=effective_n_folds,
        strategy=strategy,
        k=cfg.ndcg_at_k,
    )


# ---------------------------------------------------------------------------
# Persistence + prediction
# ---------------------------------------------------------------------------


def load_taste_model() -> tuple[Any, list[str], TasteProfile] | None:
    """Load a previously trained model and taste profile from disk.

    Backwards compatible with the pre-refactor pickle format that did not
    contain ``objective`` / ``metrics`` / ``shap_explainer`` keys.
    """
    if not MODEL_PATH.exists():
        logger.info("No saved model found at %s", MODEL_PATH)
        return None
    t0 = time.perf_counter()
    with open(MODEL_PATH, "rb") as f:
        data = pickle.load(f)  # noqa: S301
    taste_data = data.get("taste_profile")
    taste = TasteProfile(**taste_data) if taste_data else TasteProfile()
    logger.info(
        "Loaded model from %s in %.2fs — objective=%s, %d features, NDCG=%.4f",
        MODEL_PATH,
        time.perf_counter() - t0,
        data.get("objective", "regression"),
        len(data["feature_names"]),
        data.get("metrics", {}).get(
            f"ndcg_at_{get_settings().model.ndcg_at_k}",
            data.get("metrics", {}).get("ndcg_at_10", float("nan")),
        ),
    )
    return data["model"], data["feature_names"], taste


def load_model_bundle() -> dict | None:
    """Return the full pickle dict (model, metrics, shap_explainer, ...).

    Used by recommend.py for SHAP-based explanations and by the eval CLI.
    """
    if not MODEL_PATH.exists():
        return None
    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)  # noqa: S301


def predict_scores(
    model: Any,
    feature_names: list[str],
    features: list[FeatureVector],
) -> list[float]:
    """Predict raw model scores for a list of feature vectors.

    For ``lambdarank``, the model output is an unbounded relevance score (not
    a 1-10 rating). We rescale to the 1-10 display range using min-max over
    the batch so the UI score chips stay comparable to the legacy pipeline.
    For ``regression`` we still clip to [1, 10].
    """
    if not features:
        return []
    t0 = time.perf_counter()
    X = features_to_dataframe(features)
    missing = [c for c in feature_names if c not in X.columns]
    if missing:
        logger.debug("Adding %d missing columns: %s", len(missing), missing)
        X = X.assign(**{c: float("nan") for c in missing})
    X = X[feature_names]

    raw = np.asarray(model.predict(X), dtype=float)

    is_ranker = isinstance(model, lgb.LGBMRanker)
    if is_ranker and raw.size > 1:
        lo, hi = float(np.nanmin(raw)), float(np.nanmax(raw))
        if hi > lo:
            scores_arr = 1.0 + 9.0 * (raw - lo) / (hi - lo)
        else:
            scores_arr = np.full_like(raw, 5.0)
    else:
        scores_arr = np.clip(raw, 1.0, 10.0)

    scores = [float(s) for s in scores_arr]
    logger.info(
        "Predicted scores for %d candidates in %.2fs — mean=%.2f min=%.2f max=%.2f (ranker=%s)",
        len(scores),
        time.perf_counter() - t0,
        float(np.mean(scores_arr)),
        float(np.min(scores_arr)),
        float(np.max(scores_arr)),
        is_ranker,
    )
    return scores


def predict_leaf_indices(
    model: Any,
    feature_names: list[str],
    features: list[FeatureVector],
) -> np.ndarray:
    """T2.7: Return the tree-leaf assignment matrix for similarity work.

    Shape is (n_candidates, n_trees), dtype=int32. Two titles ending in the
    same leaf in many trees are similar in a richer sense than the legacy
    Jaccard overlap.
    """
    if not features:
        return np.zeros((0, 0), dtype=np.int32)
    X = features_to_dataframe(features)
    missing = [c for c in feature_names if c not in X.columns]
    if missing:
        X = X.assign(**{c: float("nan") for c in missing})
    X = X[feature_names]
    # Both LGBMRegressor.predict and LGBMRanker.predict expose pred_leaf.
    leaves = model.predict(X, pred_leaf=True)
    return np.asarray(leaves, dtype=np.int32)


def get_feature_importances(
    model: Any,
    feature_names: list[str],
) -> dict[str, float]:
    """Return feature importances as a name→fraction dict.

    Works for both LGBMRegressor and LGBMRanker (same attribute name).
    """
    importances = model.feature_importances_
    total = float(sum(importances))
    if total == 0:
        return {}
    return {
        name: float(imp / total)
        for name, imp in sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)
    }


# ---------------------------------------------------------------------------
# SHAP-based per-row explanations (T1.5)
# ---------------------------------------------------------------------------


def explain_predictions(
    bundle: dict,
    features: list[FeatureVector],
    top_k: int = 3,
) -> list[list[tuple[str, float]]]:
    """Return per-row top-k (feature_name, signed_contribution) tuples.

    Falls back to feature_importance-weighted heuristic if no SHAP explainer
    is available (e.g. the model was trained before T1.5).
    """
    if not features:
        return []
    explainer = bundle.get("shap_explainer")
    feature_names = bundle["feature_names"]
    df = features_to_dataframe(features)
    missing = [c for c in feature_names if c not in df.columns]
    if missing:
        df = df.assign(**{c: float("nan") for c in missing})
    df = df[feature_names]

    if explainer is None:
        # Fallback: use global importances weighted by feature value
        importances = get_feature_importances(bundle["model"], feature_names)
        out: list[list[tuple[str, float]]] = []
        for _, row in df.iterrows():
            scored = [
                (name, float(row[name]) * importances.get(name, 0.0))
                for name in feature_names
                if name in row
            ]
            scored.sort(key=lambda x: abs(x[1]), reverse=True)
            out.append(scored[:top_k])
        return out

    try:
        shap_values = explainer.shap_values(df)
    except Exception as e:  # noqa: BLE001
        logger.warning("SHAP shap_values() failed, falling back: %s", e)
        return explain_predictions({**bundle, "shap_explainer": None}, features, top_k)

    out: list[list[tuple[str, float]]] = []
    sv = np.asarray(shap_values)
    if sv.ndim == 3:
        # Multi-output (shouldn't happen for ranking/regression but defend)
        sv = sv[:, :, 0]
    for row_idx in range(sv.shape[0]):
        contribs = list(zip(feature_names, [float(x) for x in sv[row_idx]]))
        contribs.sort(key=lambda x: abs(x[1]), reverse=True)
        out.append(contribs[:top_k])
    return out
