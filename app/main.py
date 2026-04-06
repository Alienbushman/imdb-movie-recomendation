import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.routes import router
from app.services.candidates import download_datasets, invalidate_stale_cache

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

logger = logging.getLogger(__name__)


def _startup_downloads():
    """Download missing datasets in the background so the server starts immediately."""
    try:
        download_datasets()
    except Exception:
        logger.exception("Background dataset download failed")
    invalidate_stale_cache()


@asynccontextmanager
async def lifespan(app: FastAPI):
    invalidate_stale_cache()
    thread = threading.Thread(target=_startup_downloads, daemon=True)
    thread.start()
    logger.info("Startup: dataset download running in background")
    yield


app = FastAPI(
    lifespan=lifespan,
    title="IMDB Recommendation API",
    summary="Personalized recommendations based on your IMDB rating history.",
    description="""
## Overview

This API generates personalized **movie**, **series**, and **anime** recommendations
by learning your taste profile from your IMDB export and scoring unseen titles from
IMDB's public bulk datasets.

## How it works

1. A **LightGBM model** is trained on your rated titles (2000+ ratings), learning
   which combinations of genre, year, runtime, and IMDB rating predict a high score from you.
2. **Candidate titles** are sourced from IMDB's bulk datasets (~11k titles after filtering),
   excluding anything you've already rated.
3. Each candidate is **scored** by the model and returned ranked by predicted rating,
   split across three categories.

## Quick start

```
POST /api/v1/download-datasets   ← run once to fetch IMDB data files
POST /api/v1/recommendations     ← run the pipeline and get results
```

## Configuration

Filters (min vote count, min year, min rating) and model hyperparameters
are all controlled via `config.yaml` — no code changes needed.
""",
    version="0.1.0",
    openapi_tags=[
        {
            "name": "Setup",
            "description": (
                "One-time setup operations: downloading the IMDB dataset files "
                "and checking pipeline status."
            ),
        },
        {
            "name": "Recommendations",
            "description": (
                "Endpoints that run the recommendation pipeline and return results. "
                "All recommendation endpoints share the same pipeline run — calling "
                "one category endpoint does not re-run the model."
            ),
        },
        {
            "name": "Dismiss",
            "description": (
                "Dismiss or restore individual recommendations. "
                "Dismissed titles are excluded from all future recommendation results."
            ),
        },
    ],
    license_info={
        "name": "MIT",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:9137"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["Setup"], summary="Health check")
def health():
    """Returns `ok` when the server is running. Used by Docker healthcheck."""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    """Redirect bare root to the interactive API docs."""
    return RedirectResponse(url="/docs")
