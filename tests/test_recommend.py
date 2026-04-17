"""Unit tests for app.services.recommend — filtering, director matching, explanations."""


from app.models.schemas import CandidateTitle, FeatureVector, RatedTitle, RecommendationFilters, SimilarToRef
from app.services.features import ALL_GENRES, candidate_to_features
from app.services.recommend import _apply_runtime_filters, _explain_prediction, _find_director_match

# --- Helpers ---


def _make_candidate(
    imdb_id="tt9999999",
    title="Test Movie",
    genres=None,
    year=2020,
    language=None,
    country_code=None,
    imdb_rating=7.5,
    runtime_mins=120,
    directors=None,
    actors=None,
    **kwargs,
) -> CandidateTitle:
    return CandidateTitle(
        imdb_id=imdb_id,
        title=title,
        original_title=title,
        title_type="movie",
        imdb_rating=imdb_rating,
        year=year,
        genres=genres or ["Drama"],
        num_votes=100_000,
        runtime_mins=runtime_mins,
        language=language,
        country_code=country_code,
        directors=directors or [],
        actors=actors or [],
        **kwargs,
    )


def _make_rated(
    imdb_id="tt0000001",
    title="Rated Movie",
    directors=None,
    user_rating=8,
) -> RatedTitle:
    return RatedTitle(
        imdb_id=imdb_id,
        title=title,
        original_title=title,
        title_type="movie",
        user_rating=user_rating,
        date_rated="2024-01-01",
        imdb_rating=7.5,
        runtime_mins=120,
        year=2020,
        genres=["Drama"],
        num_votes=100_000,
        release_date="2020-01-01",
        directors=directors or [],
        url="https://www.imdb.com/title/tt0000001/",
    )


def _scored_entry(candidate, score=7.0):
    """Create a (candidate, feature_vector, score) tuple for filter tests."""
    fv = candidate_to_features(candidate)
    return (candidate, fv, score)


# --- _apply_runtime_filters ---


class TestApplyRuntimeFilters:
    def test_no_filters_returns_all(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1")),
            _scored_entry(_make_candidate(imdb_id="tt2")),
        ]
        filters = RecommendationFilters()
        result = _apply_runtime_filters(candidates, filters)
        assert len(result) == 2

    def test_min_year_filter(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1", year=2010)),
            _scored_entry(_make_candidate(imdb_id="tt2", year=2020)),
            _scored_entry(_make_candidate(imdb_id="tt3", year=2005)),
        ]
        filters = RecommendationFilters(min_year=2010)
        result = _apply_runtime_filters(candidates, filters)
        years = {c.year for c, _, _ in result}
        assert years == {2010, 2020}

    def test_max_year_filter(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1", year=2010)),
            _scored_entry(_make_candidate(imdb_id="tt2", year=2025)),
        ]
        filters = RecommendationFilters(max_year=2020)
        result = _apply_runtime_filters(candidates, filters)
        assert len(result) == 1
        assert result[0][0].year == 2010

    def test_genres_filter_includes_matching(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1", genres=["Action", "Drama"])),
            _scored_entry(_make_candidate(imdb_id="tt2", genres=["Comedy"])),
            _scored_entry(_make_candidate(imdb_id="tt3", genres=["Action"])),
        ]
        filters = RecommendationFilters(genres=["Action"])
        result = _apply_runtime_filters(candidates, filters)
        assert len(result) == 2

    def test_exclude_genres_filter(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1", genres=["Action"])),
            _scored_entry(_make_candidate(imdb_id="tt2", genres=["Horror", "Drama"])),
            _scored_entry(_make_candidate(imdb_id="tt3", genres=["Comedy"])),
        ]
        filters = RecommendationFilters(exclude_genres=["Horror"])
        result = _apply_runtime_filters(candidates, filters)
        ids = {c.imdb_id for c, _, _ in result}
        assert ids == {"tt1", "tt3"}

    def test_language_filter(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1", language="English")),
            _scored_entry(_make_candidate(imdb_id="tt2", language="French")),
            _scored_entry(_make_candidate(imdb_id="tt3", language=None)),
        ]
        filters = RecommendationFilters(languages=["English"])
        result = _apply_runtime_filters(candidates, filters)
        assert len(result) == 1
        assert result[0][0].language == "English"

    def test_country_code_filter(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1", country_code="US")),
            _scored_entry(_make_candidate(imdb_id="tt2", country_code="FR")),
            _scored_entry(_make_candidate(imdb_id="tt3", country_code=None)),
        ]
        filters = RecommendationFilters(country_code="us")  # lowercase should work
        result = _apply_runtime_filters(candidates, filters)
        assert len(result) == 1
        assert result[0][0].country_code == "US"

    def test_exclude_languages_filter(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1", language="English")),
            _scored_entry(_make_candidate(imdb_id="tt2", language="Hindi")),
            _scored_entry(_make_candidate(imdb_id="tt3", language=None)),
        ]
        filters = RecommendationFilters(exclude_languages=["Hindi"])
        result = _apply_runtime_filters(candidates, filters)
        ids = {c.imdb_id for c, _, _ in result}
        # None language is kept (not excluded)
        assert ids == {"tt1", "tt3"}

    def test_min_imdb_rating_filter(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1", imdb_rating=8.5)),
            _scored_entry(_make_candidate(imdb_id="tt2", imdb_rating=6.0)),
            _scored_entry(_make_candidate(imdb_id="tt3", imdb_rating=7.0)),
        ]
        filters = RecommendationFilters(min_imdb_rating=7.0)
        result = _apply_runtime_filters(candidates, filters)
        ids = {c.imdb_id for c, _, _ in result}
        assert ids == {"tt1", "tt3"}

    def test_max_runtime_filter(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1", runtime_mins=90)),
            _scored_entry(_make_candidate(imdb_id="tt2", runtime_mins=180)),
            _scored_entry(_make_candidate(imdb_id="tt3", runtime_mins=None)),
        ]
        filters = RecommendationFilters(max_runtime=120)
        result = _apply_runtime_filters(candidates, filters)
        # None runtime excluded (not <= 120)
        assert len(result) == 1
        assert result[0][0].imdb_id == "tt1"

    def test_combined_filters(self):
        candidates = [
            _scored_entry(_make_candidate(imdb_id="tt1", year=2020, genres=["Action"])),
            _scored_entry(_make_candidate(imdb_id="tt2", year=2005, genres=["Action"])),
            _scored_entry(_make_candidate(imdb_id="tt3", year=2020, genres=["Comedy"])),
        ]
        filters = RecommendationFilters(min_year=2010, genres=["Action"])
        result = _apply_runtime_filters(candidates, filters)
        assert len(result) == 1
        assert result[0][0].imdb_id == "tt1"


# --- _find_director_match ---


class TestFindDirectorMatch:
    def test_match_found(self):
        candidate = _make_candidate(directors=["Nolan"])
        rated = [_make_rated(title="Inception", directors=["Nolan"])]
        result = _find_director_match(candidate, rated)
        assert result is not None
        assert "Nolan" in result
        assert "Inception" in result

    def test_no_match(self):
        candidate = _make_candidate(directors=["Villeneuve"])
        rated = [_make_rated(directors=["Nolan"])]
        assert _find_director_match(candidate, rated) is None

    def test_no_candidate_directors(self):
        candidate = _make_candidate(directors=[])
        rated = [_make_rated(directors=["Nolan"])]
        assert _find_director_match(candidate, rated) is None

    def test_multiple_directors_first_match_used(self):
        candidate = _make_candidate(directors=["Unknown", "Nolan"])
        rated = [_make_rated(title="Tenet", directors=["Nolan"])]
        result = _find_director_match(candidate, rated)
        assert "Nolan" in result


# --- _explain_prediction ---


class TestExplainPrediction:
    def _make_feature_vector(self, **overrides):
        defaults = dict(
            title="Test",
            title_type="movie",
            imdb_rating=7.0,
            runtime_mins=120.0,
            year=2020,
            num_votes=100_000,
            genre_flags={f"genre_{g.lower().replace('-', '_')}": 0 for g in ALL_GENRES},
            decade=2020,
            rating_vote_ratio=0.5,
            is_anime=False,
            director_taste_score=0.0,
            has_known_director=False,
            actor_taste_score=0.0,
            has_known_actor=False,
        )
        defaults.update(overrides)
        return FeatureVector(**defaults)

    def test_high_imdb_rating_explanation(self):
        fv = self._make_feature_vector(imdb_rating=8.5)
        candidate = _make_candidate()
        explanations = _explain_prediction(fv, {}, candidate, [], [])
        assert any("High IMDb rating" in e for e in explanations)

    def test_director_match_explanation(self):
        fv = self._make_feature_vector(has_known_director=True)
        candidate = _make_candidate(directors=["Nolan"])
        rated = [_make_rated(title="Inception", directors=["Nolan"])]
        explanations = _explain_prediction(fv, {}, candidate, rated, [])
        assert any("Nolan" in e for e in explanations)

    def test_known_actor_explanation(self):
        fv = self._make_feature_vector(has_known_actor=True)
        candidate = _make_candidate()
        explanations = _explain_prediction(fv, {}, candidate, [], [])
        assert any("actors" in e.lower() for e in explanations)

    def test_animation_explanation(self):
        fv = self._make_feature_vector(is_anime=True)
        candidate = _make_candidate(genres=["Animation"])
        explanations = _explain_prediction(fv, {}, candidate, [], [])
        assert any("anime" in e.lower() for e in explanations)

    def test_similar_titles_explanation(self):
        fv = self._make_feature_vector()
        candidate = _make_candidate()
        similar = [
            SimilarToRef(imdb_id="tt0468569", title="Inception", title_type="movie", year=2010),
            SimilarToRef(imdb_id="tt6723592", title="Tenet", title_type="movie", year=2020),
        ]
        explanations = _explain_prediction(fv, {}, candidate, [], similar)
        assert any("Inception" in e for e in explanations)

    def test_actors_listed(self):
        fv = self._make_feature_vector()
        candidate = _make_candidate(actors=["DiCaprio", "Hardy"])
        explanations = _explain_prediction(fv, {}, candidate, [], [])
        assert any("DiCaprio" in e for e in explanations)

    def test_fallback_explanation(self):
        fv = self._make_feature_vector(imdb_rating=5.0)
        candidate = _make_candidate(actors=[], directors=[])
        explanations = _explain_prediction(fv, {}, candidate, [], [])
        assert any("general taste" in e.lower() for e in explanations)

    def test_max_explanations_capped(self):
        fv = self._make_feature_vector(
            imdb_rating=8.5,
            has_known_director=True,
            has_known_actor=True,
            is_anime=True,
        )
        genre_flags = {f"genre_{g.lower().replace('-', '_')}": 0 for g in ALL_GENRES}
        genre_flags["genre_action"] = 1
        fv = self._make_feature_vector(
            imdb_rating=8.5,
            has_known_director=True,
            has_known_actor=True,
            is_anime=True,
            genre_flags=genre_flags,
        )
        importances = {"genre_action": 0.5}
        candidate = _make_candidate(
            directors=["Nolan"],
            actors=["DiCaprio", "Hardy", "Page"],
            genres=["Action", "Animation"],
        )
        rated = [_make_rated(title="Inception", directors=["Nolan"])]
        similar = [SimilarToRef(imdb_id="tt6723592", title="Tenet", title_type="movie", year=2020)]
        explanations = _explain_prediction(fv, importances, candidate, rated, similar)
        assert len(explanations) <= 5

    def test_genre_importance_explanation(self):
        genre_flags = {f"genre_{g.lower().replace('-', '_')}": 0 for g in ALL_GENRES}
        genre_flags["genre_action"] = 1
        fv = self._make_feature_vector(imdb_rating=5.0, genre_flags=genre_flags)
        importances = {"genre_action": 0.3, "genre_drama": 0.1}
        candidate = _make_candidate(actors=[], directors=[], genres=["Action"])
        explanations = _explain_prediction(fv, importances, candidate, [], [])
        assert any("Action" in e for e in explanations)
