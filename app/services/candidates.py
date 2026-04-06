import gc
import json
import logging
import subprocess
import time
from pathlib import Path

import pandas as pd

from app.core.config import PROJECT_ROOT, get_settings
from app.models.schemas import CandidateTitle

logger = logging.getLogger(__name__)

DATASET_URLS = {
    "title.basics.tsv.gz": "https://datasets.imdbws.com/title.basics.tsv.gz",
    "title.ratings.tsv.gz": "https://datasets.imdbws.com/title.ratings.tsv.gz",
    "title.principals.tsv.gz": "https://datasets.imdbws.com/title.principals.tsv.gz",
    "title.akas.tsv.gz": "https://datasets.imdbws.com/title.akas.tsv.gz",
    "name.basics.tsv.gz": "https://datasets.imdbws.com/name.basics.tsv.gz",
    "title.crew.tsv.gz": "https://datasets.imdbws.com/title.crew.tsv.gz",
}

ANIME_LIST_URL = "https://raw.githubusercontent.com/Fribb/anime-lists/master/anime-list-mini.json"

# BCP 47 language codes / IMDB region codes → human-readable language names
_LANG_CODE_TO_NAME: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "hi": "Hindi",
    "ru": "Russian",
    "ar": "Arabic",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
    "nl": "Dutch",
    "pl": "Polish",
    "cs": "Czech",
    "hu": "Hungarian",
    "tr": "Turkish",
    "th": "Thai",
    "he": "Hebrew",
    "fa": "Persian",
    "uk": "Ukrainian",
    "ro": "Romanian",
    "el": "Greek",
    "bg": "Bulgarian",
    "hr": "Croatian",
    "sr": "Serbian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "et": "Estonian",
    "vi": "Vietnamese",
    "id": "Indonesian",
    "ms": "Malay",
    "tl": "Filipino",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "ml": "Malayalam",
    "kn": "Kannada",
    "mr": "Marathi",
    "pa": "Punjabi",
    "gu": "Gujarati",
    "ur": "Urdu",
    "ne": "Nepali",
    "si": "Sinhala",
    "my": "Burmese",
    "km": "Khmer",
    "ka": "Georgian",
    "hy": "Armenian",
    "az": "Azerbaijani",
    "uz": "Uzbek",
    "kk": "Kazakh",
    "mn": "Mongolian",
    "sw": "Swahili",
    "am": "Amharic",
    "yo": "Yoruba",
    "ig": "Igbo",
    "zu": "Zulu",
    "af": "Afrikaans",
    "ca": "Catalan",
    "gl": "Galician",
    "eu": "Basque",
    "cy": "Welsh",
    "ga": "Irish",
    "is": "Icelandic",
    "lb": "Luxembourgish",
    "mt": "Maltese",
    "sq": "Albanian",
    "mk": "Macedonian",
    "bs": "Bosnian",
    "cnr": "Montenegrin",
    "cmn": "Chinese",
    "yue": "Cantonese",
    "nb": "Norwegian",
    "nn": "Norwegian",
}

_REGION_TO_LANG: dict[str, str] = {
    "US": "English",
    "GB": "English",
    "AU": "English",
    "CA": "English",
    "NZ": "English",
    "IE": "English",
    "ZA": "English",
    "FR": "French",
    "BE": "French",
    "DE": "German",
    "AT": "German",
    "CH": "German",
    "ES": "Spanish",
    "MX": "Spanish",
    "AR": "Spanish",
    "CO": "Spanish",
    "CL": "Spanish",
    "PE": "Spanish",
    "VE": "Spanish",
    "IT": "Italian",
    "PT": "Portuguese",
    "BR": "Portuguese",
    "JP": "Japanese",
    "KR": "Korean",
    "CN": "Chinese",
    "TW": "Chinese",
    "HK": "Chinese",
    "IN": "Hindi",
    "RU": "Russian",
    "TR": "Turkish",
    "SE": "Swedish",
    "DK": "Danish",
    "NO": "Norwegian",
    "FI": "Finnish",
    "NL": "Dutch",
    "PL": "Polish",
    "CZ": "Czech",
    "HU": "Hungarian",
    "TH": "Thai",
    "IL": "Hebrew",
    "IR": "Persian",
    "EG": "Arabic",
    "SA": "Arabic",
    "AE": "Arabic",
    "GR": "Greek",
    "RO": "Romanian",
    "UA": "Ukrainian",
    "PH": "Filipino",
    "ID": "Indonesian",
    "MY": "Malay",
    "VN": "Vietnamese",
    "XWW": "English",
}

_AMBIGUOUS_REGIONS: frozenset[str] = frozenset({
    "IN",  # Hindi, Tamil, Telugu, Malayalam, Kannada, ...
    "BE",  # French and Dutch (Flemish)
    "CH",  # German, French, Italian
    "CA",  # English and French
    "NG",  # Hausa, Yoruba, Igbo, English, ...
    "ZW",  # Shona, Ndebele, English, ...
})

# Rows per chunk when streaming large TSV files. 500K rows keeps each chunk
# under ~100 MB in memory while scanning title.principals (100M+ rows total).
_CHUNK_SIZE = 500_000

# Categories we need from title.principals (directors moved to title.crew)
_PRINCIPAL_CATEGORIES = frozenset(["actor", "actress", "composer", "cinematographer"])


def _dataset_dir() -> Path:
    return PROJECT_ROOT / "data" / "datasets"


def _download_anime_list() -> None:
    """Download the Fribb/anime-lists JSON if not already present."""
    dest = _dataset_dir() / "anime-list-mini.json"
    if dest.exists():
        logger.info("Anime list already exists: %s", dest)
        return
    logger.info("Downloading anime list from Fribb/anime-lists ...")
    subprocess.run(["curl", "-L", "-o", str(dest), ANIME_LIST_URL], check=True)
    logger.info("Downloaded anime list (%d bytes)", dest.stat().st_size)


def _load_anime_ids() -> set[str]:
    """Return a set of IMDB tconst values for known anime titles."""
    path = _dataset_dir() / "anime-list-mini.json"
    if not path.exists():
        logger.warning(
            "Anime list not found — is_anime will fall back to country/language heuristic"
        )
        return set()
    with open(path) as f:
        entries = json.load(f)
    ids = {entry["imdb_id"] for entry in entries if entry.get("imdb_id")}
    logger.info("Loaded %d anime IMDB IDs from whitelist", len(ids))
    return ids


def download_datasets() -> None:
    """Download IMDB dataset files if they don't already exist."""
    dest = _dataset_dir()
    dest.mkdir(parents=True, exist_ok=True)
    logger.info("Dataset directory: %s", dest)

    for filename, url in DATASET_URLS.items():
        filepath = dest / filename
        if filepath.exists():
            size_mb = filepath.stat().st_size / 1e6
            logger.info("Dataset already exists: %s (%.1f MB)", filepath, size_mb)
            continue

        logger.info("Downloading %s ...", url)
        t0 = time.perf_counter()
        subprocess.run(
            ["curl", "-L", "-o", str(filepath), url],
            check=True,
        )
        elapsed = time.perf_counter() - t0
        size_mb = filepath.stat().st_size / 1e6
        speed = size_mb / elapsed if elapsed > 0 else 0
        logger.info(
            "Downloaded %s (%.1f MB) in %.1fs (%.1f MB/s)",
            filename,
            size_mb,
            elapsed,
            speed,
        )

    _download_anime_list()


def _cache_path() -> Path:
    settings = get_settings()
    cache_dir = PROJECT_ROOT / settings.data.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "imdb_candidates.json"


def _load_cache() -> list[dict] | None:
    path = _cache_path()
    if path.exists():
        t0 = time.perf_counter()
        logger.info("Loading cached candidates from %s (%.1f MB)", path, path.stat().st_size / 1e6)
        with open(path) as f:
            data = json.load(f)
        logger.info("Cache loaded: %d candidates in %.2fs", len(data), time.perf_counter() - t0)
        return data
    logger.info("No candidate cache found at %s", path)
    return None


def _save_cache(data: list[dict]) -> None:
    path = _cache_path()
    with open(path, "w") as f:
        json.dump(data, f)
    logger.info("Cached %d candidates to %s", len(data), path)


_REQUIRED_CACHE_FIELDS = {"language", "writers", "composers", "cinematographers", "is_anime"}


def invalidate_stale_cache() -> bool:
    """Delete the candidate cache if it's missing required fields.

    Reads only the first 16 KB to inspect the first object — avoids loading
    hundreds of MB just to check a single entry's keys.

    Returns True if the cache was deleted, False if it was already up to date or absent.
    """
    path = _cache_path()
    if not path.exists():
        return False
    try:
        with open(path) as f:
            chunk = f.read(16384)
        start = chunk.find("{")
        if start == -1:
            raise ValueError("no JSON object found")
        first, _ = json.JSONDecoder().raw_decode(chunk, start)
        missing = _REQUIRED_CACHE_FIELDS - set(first.keys())
        if missing:
            path.unlink()
            logger.info(
                "Deleted stale candidate cache (missing fields: %s)", sorted(missing)
            )
            return True
    except (json.JSONDecodeError, ValueError, KeyError):
        path.unlink()
        logger.info("Deleted corrupt candidate cache")
        return True
    return False


def _imdb_type_to_category(title_type: str) -> str:
    """Map IMDB dataset titleType values to our internal types."""
    return title_type


def _load_crew_data(
    title_ids: set[str],
) -> tuple[dict[str, list[str]], dict[str, list[str]], set[str]]:
    """Load writer and director nconsts from title.crew.tsv.gz (80.9 MB compressed).

    title.crew is small enough to load in one shot. Returns raw nconst IDs —
    resolve to names after building the filtered name lookup.

    Returns (raw_writers_by_title, raw_directors_by_title, needed_nconsts).
    """
    settings = get_settings()
    crew_path = PROJECT_ROOT / settings.imdb_datasets.title_crew

    if not crew_path.exists():
        logger.warning(
            "title.crew not found — writer/director features unavailable. "
            "Run POST /api/v1/download-datasets to fetch it."
        )
        return {}, {}, set()

    t0 = time.perf_counter()
    logger.info("Loading title.crew for writer and director data (%s)", crew_path)

    crew = pd.read_csv(
        crew_path,
        sep="\t",
        na_values="\\N",
        dtype={"tconst": str, "directors": str, "writers": str},
        usecols=["tconst", "directors", "writers"],
    )
    crew = crew[crew["tconst"].isin(title_ids)]

    raw_writers: dict[str, list[str]] = {}
    raw_directors: dict[str, list[str]] = {}
    needed_nconsts: set[str] = set()

    for tconst, directors_val, writers_val in zip(
        crew["tconst"], crew["directors"], crew["writers"]
    ):
        if pd.notna(writers_val):
            nconsts = [n.strip() for n in str(writers_val).split(",") if n.strip()]
            if nconsts:
                raw_writers[tconst] = nconsts
                needed_nconsts.update(nconsts)
        if pd.notna(directors_val):
            nconsts = [n.strip() for n in str(directors_val).split(",") if n.strip()]
            if nconsts:
                raw_directors[tconst] = nconsts
                needed_nconsts.update(nconsts)

    logger.info(
        "Crew data loaded in %.2fs: %d titles with writers, %d with directors",
        time.perf_counter() - t0,
        len(raw_writers),
        len(raw_directors),
    )
    return raw_writers, raw_directors, needed_nconsts


def _collect_principal_rows(principals_path: Path, title_ids: set[str]) -> pd.DataFrame:
    """Stream title.principals in chunks, returning only rows for title_ids.

    Loads one chunk (~500K rows, ~20 MB) at a time instead of the full
    ~4 GB uncompressed file. Peak memory: one chunk + accumulated matches.
    """
    t0 = time.perf_counter()
    logger.info("Streaming title.principals for actor/composer/cinematographer data")

    relevant: list[pd.DataFrame] = []
    total_rows = 0
    for chunk in pd.read_csv(
        principals_path,
        sep="\t",
        na_values="\\N",
        dtype={"tconst": str, "nconst": str, "ordering": "Int16", "category": str},
        usecols=["tconst", "nconst", "ordering", "category"],
        chunksize=_CHUNK_SIZE,
    ):
        total_rows += len(chunk)
        filtered = chunk[
            chunk["tconst"].isin(title_ids) & chunk["category"].isin(_PRINCIPAL_CATEGORIES)
        ]
        if not filtered.empty:
            relevant.append(filtered)

    if not relevant:
        logger.info("  No principal rows found for our title IDs (scanned %d rows)", total_rows)
        return pd.DataFrame(columns=["tconst", "nconst", "ordering", "category"])

    result = pd.concat(relevant, ignore_index=True)
    del relevant
    gc.collect()

    logger.info(
        "  Scanned %d rows, kept %d relevant principal rows in %.2fs",
        total_rows,
        len(result),
        time.perf_counter() - t0,
    )
    return result


def _load_name_lookup_for_nconsts(names_path: Path, nconsts: set[str]) -> dict[str, str]:
    """Stream name.basics in chunks, returning only names for the requested nconsts.

    Avoids loading all 15M rows (~750 MB dict) when we only need a small fraction.
    """
    if not nconsts:
        return {}

    t0 = time.perf_counter()
    logger.info("Building name lookup for %d nconsts from %s", len(nconsts), names_path)

    result: dict[str, str] = {}
    remaining = set(nconsts)

    for chunk in pd.read_csv(
        names_path,
        sep="\t",
        na_values="\\N",
        dtype={"nconst": str, "primaryName": str},
        usecols=["nconst", "primaryName"],
        chunksize=_CHUNK_SIZE,
    ):
        filtered = chunk[chunk["nconst"].isin(remaining)]
        if not filtered.empty:
            batch = dict(zip(filtered["nconst"], filtered["primaryName"]))
            result.update(batch)
            remaining -= batch.keys()
        if not remaining:
            break  # found all needed nconsts

    logger.info(
        "  Resolved %d / %d names in %.2fs",
        len(result),
        len(nconsts),
        time.perf_counter() - t0,
    )
    return result


def _build_person_dicts(
    principals: pd.DataFrame, name_lookup: dict[str, str]
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    """Resolve names and build actors, composers, cinematographers dicts."""
    principals = principals.copy()
    principals["name"] = principals["nconst"].map(name_lookup)
    principals = principals.dropna(subset=["name"])

    actors_by_title: dict[str, list[str]] = {}
    is_actor = principals["category"].isin(["actor", "actress"])
    actors_df = principals[is_actor].sort_values("ordering")
    for tconst, group in actors_df.groupby("tconst"):
        actors_by_title[str(tconst)] = group["name"].head(3).tolist()

    composers_by_title: dict[str, list[str]] = {}
    composers_df = principals[principals["category"] == "composer"].sort_values("ordering")
    for tconst, group in composers_df.groupby("tconst"):
        composers_by_title[str(tconst)] = group["name"].tolist()

    cinematographers_by_title: dict[str, list[str]] = {}
    cine_df = principals[principals["category"] == "cinematographer"].sort_values("ordering")
    for tconst, group in cine_df.groupby("tconst"):
        cinematographers_by_title[str(tconst)] = group["name"].tolist()

    return actors_by_title, composers_by_title, cinematographers_by_title


def _resolve_names(
    raw: dict[str, list[str]], name_lookup: dict[str, str]
) -> dict[str, list[str]]:
    """Resolve a dict of tconst → [nconst, ...] to tconst → [name, ...]."""
    resolved: dict[str, list[str]] = {}
    for tconst, nconsts in raw.items():
        names = [name_lookup[n] for n in nconsts if n in name_lookup]
        if names:
            resolved[tconst] = names
    return resolved


def _load_language_data(title_ids: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Load the original language and country code for titles from title.akas.

    Streams in chunks to avoid holding the full ~2 GB uncompressed file in memory.

    Returns (lang_by_title, country_by_title).
    """
    settings = get_settings()
    akas_path = PROJECT_ROOT / settings.imdb_datasets.title_akas

    if not akas_path.exists():
        logger.warning(
            "title.akas not found — language info unavailable. "
            "Run POST /api/v1/download-datasets to fetch it."
        )
        return {}, {}

    t0 = time.perf_counter()
    logger.info("Streaming title.akas for language data (%s)", akas_path)

    relevant: list[pd.DataFrame] = []
    for chunk in pd.read_csv(
        akas_path,
        sep="\t",
        na_values="\\N",
        dtype={
            "titleId": str,
            "region": str,
            "language": str,
            "isOriginalTitle": str,
        },
        usecols=["titleId", "region", "language", "isOriginalTitle"],
        chunksize=_CHUNK_SIZE,
    ):
        filtered = chunk[chunk["titleId"].isin(title_ids)]
        if not filtered.empty:
            relevant.append(filtered)

    if not relevant:
        return {}, {}

    akas = pd.concat(relevant, ignore_index=True)
    del relevant
    gc.collect()

    # Country code: from isOriginalTitle == "1" rows with a region
    originals = akas[akas["isOriginalTitle"] == "1"].dropna(subset=["region"])
    country_by_title: dict[str, str] = originals.groupby("titleId")["region"].first().to_dict()

    # Language: prefer explicit language code over region mapping, prefer original rows
    akas["_lang"] = akas["language"].map(_LANG_CODE_TO_NAME)
    akas["_region_lang"] = akas["region"].map(_REGION_TO_LANG)
    akas.loc[akas["region"].isin(_AMBIGUOUS_REGIONS), "_region_lang"] = None
    akas["_resolved"] = akas["_lang"].fillna(akas["_region_lang"])
    akas = akas.dropna(subset=["_resolved"])
    akas["_is_orig"] = (akas["isOriginalTitle"] == "1").astype(int)

    # Primary: most common resolved language among isOriginalTitle=1 rows
    lang_by_title: dict[str, str] = (
        akas[akas["_is_orig"] == 1]
        .dropna(subset=["_resolved"])
        .groupby("titleId")["_resolved"]
        .agg(lambda s: s.mode().iloc[0])
        .to_dict()
    )

    # Fallback: for titles with no original-title match, use mode across all rows
    no_orig = title_ids - lang_by_title.keys()
    if no_orig:
        fallback = (
            akas[akas["titleId"].isin(no_orig)]
            .dropna(subset=["_resolved"])
            .groupby("titleId")["_resolved"]
            .agg(lambda s: s.mode().iloc[0])
            .to_dict()
        )
        lang_by_title.update(fallback)

    logger.info(
        "Resolved language for %d / %d titles, country for %d titles in %.2fs",
        len(lang_by_title),
        len(title_ids),
        len(country_by_title),
        time.perf_counter() - t0,
    )
    null_count = len(title_ids) - len(lang_by_title)
    logger.info(
        "  Language null rate: %d / %d titles (%.1f%%) have no language resolved",
        null_count,
        len(title_ids),
        100 * null_count / max(len(title_ids), 1),
    )
    return lang_by_title, country_by_title


RatedPersonData = dict[str, list[str]] | None


def load_candidates_from_datasets(
    seen_ids: set[str],
) -> tuple[list[CandidateTitle], RatedPersonData, RatedPersonData, RatedPersonData]:
    """Load candidate titles from IMDB bulk dataset files.

    Merges title.basics with title.ratings, filters by quality thresholds
    and excludes titles the user has already rated.

    All large files (title.principals, name.basics, title.akas) are streamed
    in chunks to keep peak memory well under 1 GB.

    Returns (candidates, rated_actors, rated_composers, rated_cinematographers).
    All three dicts are None on a cache hit — taste profile comes from the saved model.
    """
    settings = get_settings()
    ds_cfg = settings.imdb_datasets

    t_total = time.perf_counter()

    # Check cache first
    cached = _load_cache()
    if cached is not None:
        candidates = [CandidateTitle(**c) for c in cached]
        before = len(candidates)
        candidates = [c for c in candidates if c.imdb_id not in seen_ids]
        logger.info(
            "Using cached candidates: %d total, %d after excluding %d seen IDs (%.2fs)",
            before,
            len(candidates),
            len(seen_ids),
            time.perf_counter() - t_total,
        )
        return candidates, None, None, None

    basics_path = PROJECT_ROOT / ds_cfg.title_basics
    ratings_path = PROJECT_ROOT / ds_cfg.title_ratings

    if not basics_path.exists() or not ratings_path.exists():
        raise FileNotFoundError(
            f"IMDB dataset files not found. Run the download first.\n"
            f"  Expected: {basics_path}\n"
            f"  Expected: {ratings_path}\n"
            f"  Use: POST /api/v1/download-datasets or run download_datasets()"
        )

    # Load title.basics — only columns we need, with type filtering
    logger.info("Loading title.basics from %s", basics_path)
    t0 = time.perf_counter()
    basics = pd.read_csv(
        basics_path,
        sep="\t",
        na_values="\\N",
        dtype={
            "tconst": str,
            "titleType": str,
            "primaryTitle": str,
            "originalTitle": str,
            "isAdult": str,
            "startYear": str,
            "runtimeMinutes": str,
            "genres": str,
        },
        usecols=[
            "tconst",
            "titleType",
            "primaryTitle",
            "originalTitle",
            "isAdult",
            "startYear",
            "runtimeMinutes",
            "genres",
        ],
    )

    logger.info("  Read title.basics: %d rows in %.2fs", len(basics), time.perf_counter() - t0)

    # Filter: non-adult, desired title types, minimum year
    pre = len(basics)
    basics = basics[basics["isAdult"] != "1"]
    logger.info("  After adult filter: %d → %d", pre, len(basics))
    pre = len(basics)
    basics = basics[basics["titleType"].isin(ds_cfg.include_title_types)]
    logger.info("  After type filter (%s): %d → %d", ds_cfg.include_title_types, pre, len(basics))
    if ds_cfg.min_year > 0:
        pre = len(basics)
        basics["_year"] = pd.to_numeric(basics["startYear"], errors="coerce")
        basics = basics[basics["_year"] >= ds_cfg.min_year]
        basics = basics.drop(columns=["_year"])
        logger.info("  After year filter (>=%d): %d → %d", ds_cfg.min_year, pre, len(basics))

    # Load title.ratings
    logger.info("Loading title.ratings from %s", ratings_path)
    t0 = time.perf_counter()
    ratings = pd.read_csv(
        ratings_path,
        sep="\t",
        na_values="\\N",
        dtype={"tconst": str, "averageRating": float, "numVotes": int},
    )

    logger.info("  Read title.ratings: %d rows in %.2fs", len(ratings), time.perf_counter() - t0)

    # Filter by vote count and rating thresholds
    pre = len(ratings)
    ratings = ratings[ratings["numVotes"] >= ds_cfg.min_vote_count]
    logger.info("  After vote filter (>=%d): %d → %d", ds_cfg.min_vote_count, pre, len(ratings))
    pre = len(ratings)
    ratings = ratings[ratings["averageRating"] >= ds_cfg.min_rating]
    logger.info("  After rating filter (>=%.1f): %d → %d", ds_cfg.min_rating, pre, len(ratings))

    # Merge
    merged = basics.merge(ratings, on="tconst", how="inner")
    del basics, ratings
    gc.collect()
    logger.info("Merged basics+ratings: %d titles", len(merged))

    # Exclude already-seen titles
    merged = merged[~merged["tconst"].isin(seen_ids)]
    logger.info("After excluding seen titles: %d candidates", len(merged))

    candidate_ids = set(merged["tconst"].tolist())
    all_title_ids = candidate_ids | seen_ids

    # --- Step 1: Load crew (small file — writers + directors) ---
    raw_writers, raw_directors, crew_nconsts = _load_crew_data(all_title_ids)

    # --- Step 2: Stream title.principals for actors/composers/cinematographers ---
    principals_path = PROJECT_ROOT / ds_cfg.title_principals
    if principals_path.exists():
        principals_df = _collect_principal_rows(principals_path, all_title_ids)
        principal_nconsts = set(principals_df["nconst"].dropna().tolist())
    else:
        logger.warning(
            "title.principals not found — actor/composer/cinematographer info unavailable. "
            "Run POST /api/v1/download-datasets to fetch it."
        )
        principals_df = pd.DataFrame(columns=["tconst", "nconst", "ordering", "category"])
        principal_nconsts = set()

    # --- Step 3: Build name lookup for only the nconsts we actually need ---
    names_path = PROJECT_ROOT / ds_cfg.name_basics
    all_needed_nconsts = crew_nconsts | principal_nconsts
    if names_path.exists() and all_needed_nconsts:
        name_lookup = _load_name_lookup_for_nconsts(names_path, all_needed_nconsts)
    else:
        if not names_path.exists():
            logger.warning("name.basics not found — person names unavailable")
        name_lookup = {}

    # --- Step 4: Resolve names ---
    writers_by_title = _resolve_names(raw_writers, name_lookup)
    directors_by_title = _resolve_names(raw_directors, name_lookup)
    del raw_writers, raw_directors

    actors_by_title, composers_by_title, cinematographers_by_title = _build_person_dicts(
        principals_df, name_lookup
    )
    del principals_df, name_lookup
    gc.collect()

    # --- Step 5: Stream title.akas for language/country ---
    lang_by_title, country_by_title = _load_language_data(candidate_ids)

    # --- Step 6: Load anime whitelist ---
    anime_ids = _load_anime_ids()

    # --- Step 7: Build CandidateTitle objects ---
    candidates = []
    for _, row in merged.iterrows():
        year = None
        if pd.notna(row["startYear"]):
            try:
                year = int(float(row["startYear"]))
            except (ValueError, OverflowError):
                pass

        runtime = None
        if pd.notna(row["runtimeMinutes"]):
            try:
                runtime = int(float(row["runtimeMinutes"]))
            except (ValueError, OverflowError):
                pass

        genres = []
        if pd.notna(row["genres"]):
            genres = [g.strip() for g in str(row["genres"]).split(",") if g.strip()]

        tconst = row["tconst"]

        is_anime = tconst in anime_ids
        if not is_anime and "Animation" in genres:
            is_anime = (
                country_by_title.get(tconst) == "JP"
                or lang_by_title.get(tconst) == "Japanese"
            )

        candidates.append(
            CandidateTitle(
                imdb_id=tconst,
                title=str(row["primaryTitle"]),
                original_title=str(row["originalTitle"]),
                title_type=_imdb_type_to_category(row["titleType"]),
                imdb_rating=float(row["averageRating"]),
                runtime_mins=runtime,
                year=year,
                genres=genres,
                num_votes=int(row["numVotes"]),
                directors=directors_by_title.get(tconst, []),
                actors=actors_by_title.get(tconst, []),
                language=lang_by_title.get(tconst),
                country_code=country_by_title.get(tconst),
                writers=writers_by_title.get(tconst, []),
                composers=composers_by_title.get(tconst, []),
                cinematographers=cinematographers_by_title.get(tconst, []),
                is_anime=is_anime,
            )
        )

    # Cache for next time
    _save_cache([c.model_dump() for c in candidates])

    # Extract per-person data for rated (seen) titles — used to build taste profile
    rated_actors = {tid: actors_by_title[tid] for tid in seen_ids if tid in actors_by_title}
    rated_composers = {
        tid: composers_by_title[tid] for tid in seen_ids if tid in composers_by_title
    }
    rated_cinematographers = {
        tid: cinematographers_by_title[tid]
        for tid in seen_ids
        if tid in cinematographers_by_title
    }
    logger.info(
        "Loaded %d candidate titles from IMDB datasets in %.2fs "
        "(rated: %d actors, %d composers, %d cinematographers)",
        len(candidates),
        time.perf_counter() - t_total,
        len(rated_actors),
        len(rated_composers),
        len(rated_cinematographers),
    )
    return candidates, rated_actors, rated_composers, rated_cinematographers
