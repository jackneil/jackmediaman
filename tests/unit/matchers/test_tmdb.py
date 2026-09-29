"""Tests for TMDb matcher with mocked API calls."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from jackmediaman.matchers.tmdb import TMDbClient, TMDbMatcher
from jackmediaman.core.exceptions import TMDbError
from jackmediaman.core.tmdb_cache import TMDbCache
from jackmediaman.models.media import Movie, Episode
from jackmediaman.models.quality import Quality, Resolution


class TestTMDbClient:
    """Tests for TMDbClient class."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create a TMDb client with test API key and fresh cache."""
        cache = TMDbCache(tmp_path / "tmdb.db")
        return TMDbClient(api_key="test_key", cache=cache)

    def test_search_movie_no_api_key(self, tmp_path):
        """Returns None if no API key configured."""
        cache = TMDbCache(tmp_path / "tmdb.db")
        with patch("jackmediaman.matchers.tmdb.get_settings") as mock_settings:
            mock_settings.return_value.tmdb_api_key = None
            mock_settings.return_value.cache_dir = tmp_path / "cache"
            client = TMDbClient(api_key=None, cache=cache)
            result = client.search_movie("Inception", 2010)
            assert result is None

    @patch("httpx.get")
    def test_search_movie_success(self, mock_get, client):
        """Successful search returns TMDb ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"id": 27205, "title": "Inception"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.search_movie("Inception", 2010)

        assert result == 27205
        mock_get.assert_called_once()
        # Verify API was called with correct params
        call_args = mock_get.call_args
        assert "api_key" in str(call_args)
        assert "Inception" in str(call_args)

    @patch("httpx.get")
    def test_search_movie_not_found(self, mock_get, client):
        """Returns None if movie not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.search_movie("NonexistentMovie12345", 2099)

        assert result is None

    @patch("httpx.get")
    def test_search_movie_caching(self, mock_get, client):
        """Results are cached."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"id": 27205, "title": "Inception"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # First call
        result1 = client.search_movie("Inception", 2010)
        # Second call (should use cache)
        result2 = client.search_movie("Inception", 2010)

        assert result1 == result2 == 27205
        # Should only call API once
        assert mock_get.call_count == 1

    @patch("httpx.get")
    def test_search_movie_api_error(self, mock_get, client):
        """Raises TMDbError on API failure."""
        import httpx
        mock_get.side_effect = httpx.HTTPError("API Error")

        with pytest.raises(TMDbError):
            client.search_movie("Inception", 2010)

    @patch("httpx.get")
    def test_search_movie_with_year(self, mock_get, client):
        """Year is passed to API when provided."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"id": 27205, "title": "Inception"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        client.search_movie("Inception", 2010)

        call_args = mock_get.call_args
        # Year should be in params
        assert "year" in str(call_args) or "2010" in str(call_args)

    @patch("httpx.get")
    def test_search_movie_without_year(self, mock_get, client):
        """Works without year."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"id": 27205, "title": "Inception"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.search_movie("Inception", year=None)
        assert result == 27205

    def test_cache_database_created(self, tmp_path):
        """Cache database is created on init."""
        cache = TMDbCache(tmp_path / "new_cache" / "tmdb.db")
        client = TMDbClient(api_key="test", cache=cache)
        assert (tmp_path / "new_cache" / "tmdb.db").exists()


class TestTMDbMatcher:
    """Tests for TMDbMatcher class."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock TMDb client."""
        client = MagicMock()
        client.api_key = "test_key"
        # Return same ID for same title
        def search_movie(title, year=None):
            if "inception" in title.lower():
                return 27205
            elif "matrix" in title.lower():
                return 603
            return None
        client.search_movie = MagicMock(side_effect=search_movie)
        return client

    @pytest.fixture
    def matcher(self, mock_client):
        """Create a TMDb matcher with mock client."""
        matcher = TMDbMatcher()
        matcher.client = mock_client
        return matcher

    def test_matches_by_tmdb_id(self, matcher, tmp_path):
        """Groups movies with same TMDb ID."""
        quality = Quality(resolution=Resolution.FHD)
        movies = []

        for i in range(3):
            path = tmp_path / f"inception_{i}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title="Inception",
                year=2010,
            ))

        groups = matcher.match(movies)

        assert len(groups) == 1
        assert groups[0].count == 3

    def test_different_movies_separate(self, matcher, tmp_path):
        """Different movies are in separate groups."""
        quality = Quality(resolution=Resolution.FHD)
        movies = []

        for title, year in [("Inception", 2010), ("Inception", 2010),
                           ("The Matrix", 1999), ("The Matrix", 1999)]:
            path = tmp_path / f"{title}_{year}_{len(movies)}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title=title,
                year=year,
            ))

        groups = matcher.match(movies)

        assert len(groups) == 2  # One group per movie

    def test_filters_non_movies(self, matcher, tmp_path, sample_episode):
        """Filters out non-Movie items."""
        groups = matcher.match([sample_episode])
        assert len(groups) == 0

    def test_empty_list(self, matcher):
        """Empty list returns empty results."""
        assert matcher.match([]) == []

    def test_unmatched_movies_not_grouped(self, matcher, tmp_path):
        """Movies not found in TMDb are not grouped."""
        quality = Quality(resolution=Resolution.FHD)
        movies = []

        # Two movies with unknown titles
        for i in range(2):
            path = tmp_path / f"unknown_{i}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title="Unknown Movie That Doesnt Exist",
                year=2099,
            ))

        groups = matcher.match(movies)
        # Should have no groups since TMDb returns None
        assert len(groups) == 0

    def test_sorts_by_quality(self, matcher, tmp_path):
        """Groups are sorted by quality."""
        quality_1080 = Quality(resolution=Resolution.FHD)
        quality_720 = Quality(resolution=Resolution.HD)

        movies = []
        for quality in [quality_720, quality_1080]:  # Wrong order
            path = tmp_path / f"inception_{quality.resolution.name}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title="Inception",
                year=2010,
            ))

        groups = matcher.match(movies)
        assert len(groups) == 1
        # First item should be highest quality
        assert groups[0].items[0].quality.resolution == Resolution.FHD

    def test_sets_tmdb_id_on_movies(self, matcher, tmp_path):
        """Matcher sets tmdb_id on matched movies."""
        quality = Quality(resolution=Resolution.FHD)

        path = tmp_path / "inception.mkv"
        path.write_bytes(b"0" * 200)
        movie = Movie(
            path=path,
            filename=path.name,
            size_bytes=200,
            quality=quality,
            title="Inception",
            year=2010,
        )

        matcher.match([movie])
        assert movie.tmdb_id == 27205

    def test_matcher_attributes(self, matcher):
        """Matcher has expected attributes."""
        assert matcher.name == "tmdb"
        assert "tmdb" in matcher.description.lower()


class TestTMDbMatcherEditions:
    """Tests for edition handling in TMDb matcher."""

    @pytest.fixture
    def matcher_editions_as_dupes(self, tmp_path):
        """Create matcher with editions as duplicates."""
        matcher = TMDbMatcher(include_editions_as_dupes=True)
        # Mock the client
        client = MagicMock()
        client.api_key = "test"
        client.search_movie = MagicMock(return_value=27205)
        matcher.client = client
        return matcher

    @pytest.fixture
    def matcher_editions_separate(self, tmp_path):
        """Create matcher with editions separate."""
        matcher = TMDbMatcher(include_editions_as_dupes=False)
        # Mock the client
        client = MagicMock()
        client.api_key = "test"
        client.search_movie = MagicMock(return_value=27205)
        matcher.client = client
        return matcher

    def test_editions_grouped_by_default(self, matcher_editions_as_dupes, tmp_path):
        """Different editions are grouped when include_editions_as_dupes=True."""
        quality = Quality(resolution=Resolution.FHD)
        movies = []

        for edition in [None, "directors_cut"]:
            path = tmp_path / f"movie_{edition}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title="Blade Runner",
                year=1982,
                edition=edition,
            ))

        groups = matcher_editions_as_dupes.match(movies)
        assert len(groups) == 1

    def test_editions_separate_when_configured(self, matcher_editions_separate, tmp_path):
        """Different editions are separate when include_editions_as_dupes=False."""
        quality = Quality(resolution=Resolution.FHD)
        movies = []

        for edition in [None, "directors_cut"]:
            path = tmp_path / f"movie_{edition}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title="Blade Runner",
                year=1982,
                edition=edition,
            ))

        groups = matcher_editions_separate.match(movies)
        # No groups because editions are separate
        assert len(groups) == 0
