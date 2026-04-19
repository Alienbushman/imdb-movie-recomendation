import csv
import io
import json
import logging
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

_USER_ID_PATTERN = re.compile(r"ur\d+|p\.[a-z0-9]{8,}", re.IGNORECASE)

_PLAYWRIGHT_ARGS = ["--disable-blink-features=AutomationControlled"]
# Extra flags required in Docker (no hardware GPU, /dev/shm is limited)
_DOCKER_EXTRA_ARGS = ["--no-sandbox", "--disable-dev-shm-usage"]
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
_WEBDRIVER_PATCH = (
    'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'
)

# Delay between page navigations to avoid IMDB rate-limiting.
_PAGE_DELAY = 1.5  # seconds

# ── Docker / Xvfb helpers ────────────────────────────────────────────────────

_xvfb_proc: subprocess.Popen | None = None
_xvfb_lock = threading.Lock()


def _running_in_docker() -> bool:
    """Return True when the process is running inside a Docker container."""
    return os.path.exists("/.dockerenv")


def _start_xvfb_if_needed() -> None:
    """Start a virtual X display on :99 if not already running.

    Required in Docker where no physical display is available.
    Xvfb must be installed in the image (apt-get install xvfb).
    """
    global _xvfb_proc
    with _xvfb_lock:
        if _xvfb_proc is not None and _xvfb_proc.poll() is None:
            return  # already running
        logger.info("Starting Xvfb virtual display :99 for Playwright")
        _xvfb_proc = subprocess.Popen(
            ["Xvfb", ":99", "-screen", "0", "1280x720x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)  # give Xvfb time to initialise
        os.environ["DISPLAY"] = ":99"


def _extract_user_id(imdb_url: str) -> str:
    """Extract IMDB user ID from a URL or raw ID string.

    Accepts both IMDB user ID formats:
      - Legacy URL: https://www.imdb.com/user/ur38228117/ratings/
      - New URL:    https://www.imdb.com/user/p.arvu7rnrmdgia6petxotlpd7da/ratings/
      - Short URL:  imdb.com/user/ur38228117
      - Raw ID:     ur38228117 or p.arvu7rnrmdgia6petxotlpd7da

    Raises ValueError if no valid user ID found.
    """
    match = _USER_ID_PATTERN.search(imdb_url)
    if not match:
        raise ValueError(
            f"No valid IMDB user ID found in: {imdb_url!r}. "
            "Expected 'ur' followed by digits (e.g. ur38228117) "
            "or 'p.' followed by alphanumerics (e.g. p.arvu7rnrmdgia6petxotlpd7da)."
        )
    return match.group()


def _wait_for_real_page(page, timeout_s: float = 60.0) -> str:
    """Wait for the IMDB page to load past the WAF challenge.

    Polls every second until one of three outcomes:
      - ``__NEXT_DATA__`` appears → return ``"ok"``
      - Page title contains ``403`` or ``404`` → return ``"blocked"``
      - Page title contains ``503`` or ``Error`` → return ``"error"``
      - Timeout → return ``"timeout"``

    After detecting ``ok``, waits for ``networkidle`` so the
    ``PersonalizedUserData`` GraphQL response has time to arrive.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            content = page.content()
        except Exception:
            # Page is mid-navigation (WAF reload) — wait and retry
            time.sleep(1)
            continue
        if "__NEXT_DATA__" in content:
            try:
                page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass
            return "ok"
        try:
            title = page.title()
        except Exception:
            time.sleep(1)
            continue
        if "403" in title or "404" in title:
            return "blocked"
        if "503" in title or "Error" in title:
            return "error"
        time.sleep(1)
    return "timeout"


def _extract_page_data(page) -> tuple[list[dict], dict, int]:
    """Extract title metadata and pagination info from __NEXT_DATA__.

    Returns (edges, page_info, total_count).
    Returns ([], {}, 0) if the page doesn't contain valid data.
    """
    content = page.content()
    match = re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', content, re.DOTALL
    )
    if not match:
        return [], {}, 0

    data = json.loads(match.group(1))
    props = data["props"]["pageProps"]
    search = props.get("mainColumnData", {}).get("advancedTitleSearch", {})
    edges = search.get("edges", [])
    page_info = search.get("pageInfo", {})
    total = search.get("total", 0)
    return edges, page_info, total


def _extract_title_type(type_id: str) -> str:
    """Map IMDB titleType.id to the display text used in CSV exports."""
    mapping = {
        "movie": "Movie",
        "tvSeries": "TV Series",
        "tvMiniSeries": "TV Mini Series",
        "tvMovie": "TV Movie",
        "tvSpecial": "TV Special",
        "short": "Short",
        "tvShort": "TV Short",
        "tvEpisode": "TV Episode",
        "video": "Video",
        "videoGame": "Video Game",
        "musicVideo": "Music Video",
        "podcastSeries": "Podcast Series",
        "podcastEpisode": "Podcast Episode",
    }
    return mapping.get(type_id, type_id)


def _build_csv_row(title_data: dict, user_rating: dict | None) -> dict | None:
    """Build a single CSV row dict from GraphQL title + user rating data."""
    title = title_data.get("title", {})
    imdb_id = title.get("id", "")
    if not imdb_id or not user_rating:
        return None

    # Genres
    genres_list = []
    for g in (title.get("titleGenres") or {}).get("genres", []):
        genre_text = g.get("genre", {}).get("text")
        if genre_text:
            genres_list.append(genre_text)

    # Runtime in minutes
    runtime_secs = (title.get("runtime") or {}).get("seconds")
    runtime_mins = runtime_secs // 60 if runtime_secs else ""

    # Release date
    rd = title.get("releaseDate") or {}
    if rd.get("year") and rd.get("month") and rd.get("day"):
        release_date = f"{rd['year']}-{rd['month']:02d}-{rd['day']:02d}"
    else:
        release_date = ""

    # Directors from principalCreditsV2
    directors = []
    for credit_group in title.get("principalCreditsV2", []):
        group_text = (
            credit_group.get("grouping", {}).get("text", "").lower()
        )
        if "director" in group_text or "created by" in group_text:
            for credit in credit_group.get("credits", []):
                name = credit.get("name", {}).get("nameText", {}).get("text")
                if name:
                    directors.append(name)

    # Rating date — strip time portion
    date_rated = user_rating.get("date", "")
    if "T" in date_rated:
        date_rated = date_rated.split("T")[0]

    return {
        "Const": imdb_id,
        "Your Rating": user_rating.get("value", ""),
        "Date Rated": date_rated,
        "Title": (title.get("titleText") or {}).get("text", ""),
        "Original Title": (title.get("originalTitleText") or {}).get("text", ""),
        "URL": f"https://www.imdb.com/title/{imdb_id}",
        "Title Type": _extract_title_type(
            (title.get("titleType") or {}).get("id", "")
        ),
        "IMDb Rating": (title.get("ratingsSummary") or {}).get(
            "aggregateRating", ""
        ),
        "Runtime (mins)": runtime_mins,
        "Year": (title.get("releaseYear") or {}).get("year", ""),
        "Genres": ", ".join(genres_list),
        "Num Votes": (title.get("ratingsSummary") or {}).get("voteCount", 0),
        "Release Date": release_date,
        "Directors": ", ".join(directors),
    }


def _rows_to_csv(rows: list[dict]) -> str:
    """Convert a list of row dicts to CSV string matching IMDB export format."""
    fieldnames = [
        "Const",
        "Your Rating",
        "Date Rated",
        "Title",
        "Original Title",
        "URL",
        "Title Type",
        "IMDb Rating",
        "Runtime (mins)",
        "Year",
        "Genres",
        "Num Votes",
        "Release Date",
        "Directors",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def fetch_imdb_ratings_csv(imdb_url: str, timeout: float = 120.0) -> str:
    """Fetch IMDB ratings for a user by scraping their public ratings page.

    Uses Playwright with Chrome to bypass IMDB's WAF bot protection,
    then extracts ratings data from the page's embedded JSON and
    PersonalizedUserData GraphQL responses.

    Args:
        imdb_url: IMDB user ratings URL or user ID (e.g. ur38228117)
        timeout: Per-page navigation timeout in seconds

    Returns:
        CSV content as a string (same format as IMDB's legacy export)

    Raises:
        ValueError: Invalid URL or user ID format
        RuntimeError: Ratings page inaccessible (private, not found, etc.)
    """
    user_id = _extract_user_id(imdb_url)
    ratings_url = f"https://www.imdb.com/user/{user_id}/ratings/"

    all_rows: list[dict] = []

    if _running_in_docker():
        _start_xvfb_if_needed()

    with sync_playwright() as p:
        if _running_in_docker():
            # Inside Docker: use Playwright's bundled Chromium with a virtual display.
            # channel="chrome" requires system-installed Google Chrome which is absent.
            # Xvfb provides the X11 display required for headless=False.
            browser = p.chromium.launch(
                headless=False,
                args=_PLAYWRIGHT_ARGS + _DOCKER_EXTRA_ARGS,
            )
        else:
            # Local dev: use system Chrome for the best WAF bypass.
            browser = p.chromium.launch(
                headless=False,
                channel="chrome",
                args=_PLAYWRIGHT_ARGS,
            )
        try:
            context = browser.new_context(user_agent=_USER_AGENT)
            page = context.new_page()
            page.add_init_script(_WEBDRIVER_PATCH)

            # Capture PersonalizedUserData GraphQL responses for user ratings
            user_ratings_by_id: dict[str, dict] = {}

            def _capture_ratings(response):
                try:
                    req = response.request
                    if (
                        "graphql" in response.url
                        and req.method == "POST"
                        and req.post_data
                        and "PersonalizedUserData" in req.post_data
                    ):
                        body = response.json()
                        for t in body.get("data", {}).get("titles", []):
                            rating = t.get("otherUserRating")
                            if rating and t.get("id"):
                                user_ratings_by_id[t["id"]] = rating
                except Exception:
                    pass

            page.on("response", _capture_ratings)

            # Load first page
            logger.info("Scraping IMDB ratings for user %s", user_id)
            page.goto(ratings_url, timeout=int(timeout * 1000))
            status = _wait_for_real_page(page, timeout)

            if status == "blocked":
                raise RuntimeError(
                    f"Could not access ratings page for {user_id}. "
                    "The user may not exist or ratings may be private."
                )
            if status == "error":
                raise RuntimeError(
                    "IMDB returned a server error (503). "
                    "You may have been rate-limited. "
                    "Wait a few minutes and try again, or upload the CSV manually."
                )
            if status == "timeout":
                raise RuntimeError(
                    "Timed out waiting for IMDB to load. "
                    "IMDB may be down or blocking automated requests. "
                    "Try again later, or upload the CSV manually."
                )

            total_expected = 0
            page_num = 1
            max_retries = 2

            while True:
                logger.info("Scraping page %d...", page_num)
                edges, page_info, total = _extract_page_data(page)

                if total and not total_expected:
                    total_expected = total
                    logger.info("Total ratings reported by IMDB: %d", total_expected)

                if not edges:
                    logger.info(
                        "No data on page %d — collected %d/%d rows",
                        page_num,
                        len(all_rows),
                        total_expected,
                    )
                    break

                for edge in edges:
                    title_data = edge.get("node", {})
                    imdb_id = title_data.get("title", {}).get("id", "")
                    rating = user_ratings_by_id.get(imdb_id)
                    row = _build_csv_row(title_data, rating)
                    if row:
                        all_rows.append(row)

                logger.info(
                    "Page %d: %d edges, %d rows total",
                    page_num,
                    len(edges),
                    len(all_rows),
                )

                if not page_info.get("hasNextPage"):
                    break
                if total_expected and len(all_rows) >= total_expected:
                    break

                # Navigate to next page with rate-limit delay
                time.sleep(_PAGE_DELAY)
                page_num += 1
                next_cursor = page_info.get("endCursor", "")
                next_url = f"{ratings_url}?paginationToken={next_cursor}"

                retries = 0
                while retries <= max_retries:
                    page.goto(next_url, timeout=int(timeout * 1000))
                    nav_status = _wait_for_real_page(page, timeout)
                    if nav_status == "ok":
                        break
                    retries += 1
                    if retries <= max_retries:
                        wait = 5 * retries
                        logger.warning(
                            "Page %d: got %s, retrying in %ds (%d/%d)",
                            page_num,
                            nav_status,
                            wait,
                            retries,
                            max_retries,
                        )
                        time.sleep(wait)
                else:
                    logger.warning(
                        "Page %d: failed after %d retries — stopping with %d rows",
                        page_num,
                        max_retries,
                        len(all_rows),
                    )
                    break
        finally:
            browser.close()

    if not all_rows:
        raise RuntimeError(
            f"No ratings found for user {user_id}. "
            "The ratings may be private or the user has no ratings."
        )

    logger.info("Scraped %d ratings for user %s", len(all_rows), user_id)
    csv_content = _rows_to_csv(all_rows)
    return csv_content


def save_ratings_csv(csv_content: str, dest: Path) -> None:
    """Save fetched CSV content to disk for caching."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(csv_content, encoding="utf-8")
