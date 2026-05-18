"""T2.8 + T3.13: Build auxiliary training rows from dismissals and feedback.

The two signal sources have the same shape — a list of imdb_ids tagged with a
label (and optionally a recorded timestamp). This module looks each one up in
the scored-candidates DB (and falls back to the candidate JSON cache) so the
trainer gets full ``CandidateTitle`` metadata for feature extraction.

It's intentionally tolerant: IDs that can't be resolved are skipped with a
debug log rather than failing the pipeline. That matters because dismissed.json
accumulates across many runs and may contain IDs that no longer pass the
candidate filters.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterable

from app.core.config import PROJECT_ROOT, get_settings
from app.models.schemas import CandidateTitle, TasteProfile
from app.services.dismissed import get_dismissed_ids
from app.services.features import candidate_to_features
from app.services.feedback import get_feedback_map
from app.services.model import ExtraTrainingRow

logger = logging.getLogger(__name__)

_SCORED_DB_PATH = PROJECT_ROOT / "data" / "cache" / "scored_candidates.db"
_CANDIDATES_CACHE = PROJECT_ROOT / "data" / "cache" / "imdb_candidates.json"


def _lookup_from_db(imdb_ids: set[str]) -> dict[str, CandidateTitle]:
    """Pull CandidateTitle rows from scored_candidates.db for the given IDs."""
    if not imdb_ids or not _SCORED_DB_PATH.exists():
        return {}
    try:
        conn = sqlite3.connect(str(_SCORED_DB_PATH))
        conn.row_factory = sqlite3.Row
        placeholders = ",".join("?" * len(imdb_ids))
        rows = conn.execute(
            f"SELECT * FROM scored_candidates WHERE imdb_id IN ({placeholders})",
            sorted(imdb_ids),
        ).fetchall()
        conn.close()
    except sqlite3.OperationalError as e:
        logger.warning("scored DB lookup failed: %s", e)
        return {}

    out: dict[str, CandidateTitle] = {}
    for row in rows:
        try:
            out[row["imdb_id"]] = CandidateTitle(
                imdb_id=row["imdb_id"],
                title=row["title"],
                original_title=row["title"],
                title_type=row["title_type"],
                imdb_rating=row["imdb_rating"] or 0.0,
                runtime_mins=row["runtime_mins"],
                year=row["year"],
                genres=json.loads(row["genres"] or "[]"),
                num_votes=row["num_votes"] or 0,
                directors=json.loads(row["directors"] or "[]"),
                actors=json.loads(row["actors"] or "[]"),
                language=row["language"],
                languages=json.loads(row["languages"] or "[]") if "languages" in row.keys() else [],
                country_code=row["country_code"],
                writers=json.loads(row["writers"] or "[]") if "writers" in row.keys() else [],
                composers=json.loads(row["composers"] or "[]") if "composers" in row.keys() else [],
                cinematographers=(
                    json.loads(row["cinematographers"] or "[]")
                    if "cinematographers" in row.keys()
                    else []
                ),
                is_anime=bool(row["is_anime"]) if "is_anime" in row.keys() else False,
            )
        except (KeyError, json.JSONDecodeError, ValueError) as e:
            logger.debug("Skipping malformed scored row for %s: %s", row.get("imdb_id"), e)
    return out


def _lookup_from_cache(imdb_ids: set[str]) -> dict[str, CandidateTitle]:
    """Fallback: pull CandidateTitle rows from the candidate JSON cache."""
    if not imdb_ids or not _CANDIDATES_CACHE.exists():
        return {}
    try:
        with open(_CANDIDATES_CACHE) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    by_id = {c.get("imdb_id"): c for c in data if c.get("imdb_id") in imdb_ids}
    out: dict[str, CandidateTitle] = {}
    for imdb_id, c in by_id.items():
        try:
            out[imdb_id] = CandidateTitle(**c)
        except Exception as e:  # noqa: BLE001
            logger.debug("Skipping malformed cache row for %s: %s", imdb_id, e)
    return out


def _build_rows(
    imdb_ids: Iterable[str],
    taste: TasteProfile,
    label: float,
    weight: float,
    source: str,
) -> list[ExtraTrainingRow]:
    ids = {i for i in imdb_ids if i}
    if not ids:
        return []
    candidates = _lookup_from_db(ids)
    missing = ids - candidates.keys()
    if missing:
        candidates.update(_lookup_from_cache(missing))
    rows: list[ExtraTrainingRow] = []
    for imdb_id in sorted(candidates.keys()):
        fv = candidate_to_features(candidates[imdb_id], taste)
        rows.append(
            ExtraTrainingRow(
                feature_vector=fv,
                label=label,
                weight=weight,
                source=source,
            )
        )
    unresolved = ids - candidates.keys()
    if unresolved:
        logger.info(
            "%s: %d of %d IDs unresolved (not in scored DB or candidate cache).",
            source,
            len(unresolved),
            len(ids),
        )
    return rows


def build_implicit_training_rows(taste: TasteProfile) -> list[ExtraTrainingRow]:
    """Assemble all implicit-signal rows for the next training pass.

    Pulls config flags from ``settings.model.training`` so each signal source
    can be toggled independently.
    """
    cfg = get_settings().model.training
    rows: list[ExtraTrainingRow] = []

    if cfg.use_dismissals:
        dismissed = get_dismissed_ids()
        rows.extend(
            _build_rows(
                dismissed,
                taste=taste,
                label=cfg.dismissal_label,
                weight=cfg.dismissal_weight,
                source="dismissal",
            )
        )

    if cfg.use_feedback:
        feedback = get_feedback_map()
        ups = [i for i, r in feedback.items() if r.get("kind") == "up"]
        downs = [i for i, r in feedback.items() if r.get("kind") == "down"]
        nots = [i for i, r in feedback.items() if r.get("kind") == "not_interested"]
        rows.extend(
            _build_rows(ups, taste, cfg.feedback_up_label, cfg.feedback_weight, "feedback_up")
        )
        rows.extend(
            _build_rows(downs, taste, cfg.feedback_down_label, cfg.feedback_weight, "feedback_down")
        )
        rows.extend(
            _build_rows(
                nots,
                taste,
                cfg.feedback_not_interested_label,
                cfg.feedback_weight,
                "feedback_not_interested",
            )
        )

    if rows:
        logger.info("Implicit-signal training rows assembled: %d total.", len(rows))
    return rows
