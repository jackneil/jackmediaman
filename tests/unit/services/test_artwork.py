"""Tests for artwork service."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from jackmediaman.services.artwork import ArtworkService, ArtworkResult


class TestArtworkResult:
    """Tests for ArtworkResult dataclass."""

    def test_successful_result(self, tmp_path):
        """Create successful artwork result."""
        result = ArtworkResult(
            path=tmp_path / "poster.jpg",
            media_path=tmp_path / "movie.mkv",
            artwork_type="movie_poster",
            success=True,
        )
        assert result.success is True
        assert result.skipped is False
        assert result.error is None

    def test_skipped_result(self, tmp_path):
        """Create skipped result when artwork exists."""
        result = ArtworkResult(
            path=tmp_path / "poster.jpg",
            media_path=tmp_path / "movie.mkv",
            artwork_type="movie_poster",
            success=True,
            skipped=True,
            skip_reason="Poster already exists",
        )
        assert result.success is True
        assert result.skipped is True

    def test_failed_result(self, tmp_path):
        """Create failed result."""
        result = ArtworkResult(
            path=tmp_path / "poster.jpg",
            media_path=tmp_path / "movie.mkv",
            artwork_type="movie_poster",
            success=False,
            error="Movie not found on TMDb",
        )
        assert result.success is False
        assert result.error == "Movie not found on TMDb"


class TestArtworkService:
    """Tests for ArtworkService class."""

    @pytest.fixture
    def mock_cache(self):
        """Create mock TMDb cache."""
        cache = MagicMock()
        cache.get.return_value = None
        return cache

    @pytest.fixture
    def service(self, mock_cache):
        """Create artwork service with mock cache."""
        return ArtworkService(api_key="test_key", cache=mock_cache)

    def test_init_with_api_key(self, mock_cache):
        """Initialize service with API key."""
        service = ArtworkService(api_key="test_key", cache=mock_cache)
        assert service.api_key == "test_key"

    def test_init_from_settings(self, mock_cache):
        """Initialize service from settings."""
        with patch("jackmediaman.services.artwork.get_settings") as mock_settings:
            mock_settings.return_value.tmdb_api_key = "settings_key"
            service = ArtworkService(cache=mock_cache)
            assert service.api_key == "settings_key"

    def test_get_movie_poster_url_cached(self, service, mock_cache):
        """Get movie poster URL from cache."""
        mock_cache.get.return_value = {"poster_path": "/abc123.jpg"}

        url = service.get_movie_poster_url(12345)

        assert url == "https://image.tmdb.org/t/p/w500/abc123.jpg"

    def test_get_movie_poster_url_from_api(self, service, mock_cache):
        """Get movie poster URL from API."""
        mock_cache.get.return_value = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"poster_path": "/xyz789.jpg"}

        with patch("httpx.get", return_value=mock_response):
            url = service.get_movie_poster_url(12345)

        assert url == "https://image.tmdb.org/t/p/w500/xyz789.jpg"
        mock_cache.set.assert_called_once()

    def test_get_movie_poster_url_no_poster(self, service, mock_cache):
        """Returns None when no poster available."""
        mock_cache.get.return_value = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"poster_path": None}

        with patch("httpx.get", return_value=mock_response):
            url = service.get_movie_poster_url(12345)

        assert url is None

    def test_get_show_poster_url(self, service, mock_cache):
        """Get TV show poster URL."""
        mock_cache.get.return_value = {"poster_path": "/show123.jpg"}

        url = service.get_show_poster_url(12345)

        assert url == "https://image.tmdb.org/t/p/w500/show123.jpg"

    def test_get_season_poster_url(self, service, mock_cache):
        """Get season poster URL."""
        mock_cache.get.return_value = {"poster_path": "/season1.jpg"}

        url = service.get_season_poster_url(12345, 1)

        assert url == "https://image.tmdb.org/t/p/w500/season1.jpg"

    def test_search_movie(self, service, mock_cache):
        """Search for movie returns TMDb ID."""
        mock_cache.get.return_value = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": 99999}]}

        with patch("httpx.get", return_value=mock_response):
            tmdb_id = service.search_movie("Test Movie", 2020)

        assert tmdb_id == 99999

    def test_search_movie_no_results(self, service, mock_cache):
        """Search returns None when no results."""
        mock_cache.get.return_value = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch("httpx.get", return_value=mock_response):
            tmdb_id = service.search_movie("Unknown Movie")

        assert tmdb_id is None

    def test_search_tv(self, service, mock_cache):
        """Search for TV show returns TMDb ID."""
        mock_cache.get.return_value = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [{"id": 88888}]}

        with patch("httpx.get", return_value=mock_response):
            tmdb_id = service.search_tv("Test Show")

        assert tmdb_id == 88888

    def test_download_image(self, service, tmp_path):
        """Download image to file."""
        dest = tmp_path / "test.jpg"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake image data"

        with patch("httpx.get", return_value=mock_response):
            success = service.download_image("https://example.com/image.jpg", dest)

        assert success is True
        assert dest.exists()
        assert dest.read_bytes() == b"fake image data"

    def test_download_image_failure(self, service, tmp_path):
        """Download image handles failure."""
        import httpx

        dest = tmp_path / "test.jpg"

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Connection failed")
            success = service.download_image("https://example.com/image.jpg", dest)

        assert success is False
        assert not dest.exists()

    def test_download_movie_poster_success(self, service, tmp_path, mock_cache):
        """Download movie poster successfully."""
        movie_folder = tmp_path / "Movie (2020)"
        movie_folder.mkdir()
        movie_file = movie_folder / "Movie (2020).mkv"
        movie_file.touch()

        mock_cache.get.side_effect = [
            {"id": 12345},  # search cache
            {"poster_path": "/poster.jpg"},  # poster cache
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"poster data"

        with patch("httpx.get", return_value=mock_response):
            result = service.download_movie_poster(
                movie_path=movie_file,
                title="Movie",
                year=2020,
            )

        assert result.success is True
        assert (movie_folder / "poster.jpg").exists()

    def test_download_movie_poster_already_exists(self, service, tmp_path, mock_cache):
        """Skip download when poster exists."""
        movie_folder = tmp_path / "Movie (2020)"
        movie_folder.mkdir()
        movie_file = movie_folder / "Movie (2020).mkv"
        movie_file.touch()
        poster = movie_folder / "poster.jpg"
        poster.write_bytes(b"existing poster")

        result = service.download_movie_poster(
            movie_path=movie_file,
            title="Movie",
            year=2020,
        )

        assert result.success is True
        assert result.skipped is True
        assert result.skip_reason == "Poster already exists"

    def test_download_movie_poster_overwrite(self, service, tmp_path, mock_cache):
        """Download overwrites existing poster when requested."""
        movie_folder = tmp_path / "Movie (2020)"
        movie_folder.mkdir()
        movie_file = movie_folder / "Movie (2020).mkv"
        movie_file.touch()
        poster = movie_folder / "poster.jpg"
        poster.write_bytes(b"old poster")

        mock_cache.get.side_effect = [
            {"id": 12345},  # search cache
            {"poster_path": "/new.jpg"},  # poster cache
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"new poster data"

        with patch("httpx.get", return_value=mock_response):
            result = service.download_movie_poster(
                movie_path=movie_file,
                title="Movie",
                year=2020,
                overwrite=True,
            )

        assert result.success is True
        assert result.skipped is False
        assert poster.read_bytes() == b"new poster data"

    def test_download_movie_poster_not_found(self, service, tmp_path, mock_cache):
        """Handle movie not found on TMDb."""
        movie_folder = tmp_path / "Unknown (2020)"
        movie_folder.mkdir()
        movie_file = movie_folder / "Unknown (2020).mkv"
        movie_file.touch()

        mock_cache.get.return_value = None

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}

        with patch("httpx.get", return_value=mock_response):
            result = service.download_movie_poster(
                movie_path=movie_file,
                title="Unknown",
                year=2020,
            )

        assert result.success is False
        assert "not found" in result.error.lower()

    def test_find_season_numbers(self, service, tmp_path):
        """Find season numbers from folder names."""
        show_folder = tmp_path / "Test Show"
        show_folder.mkdir()
        (show_folder / "Season 1").mkdir()
        (show_folder / "Season 2").mkdir()
        (show_folder / "Season 10").mkdir()
        (show_folder / "Extras").mkdir()  # Not a season

        seasons = service._find_season_numbers(show_folder)

        assert seasons == [1, 2, 10]

    def test_parse_movie_name_with_year(self, service):
        """Parse movie name with year."""
        title, year = service._parse_movie_name("Movie Name (2020)")
        assert title == "Movie Name"
        assert year == 2020

    def test_parse_movie_name_with_brackets(self, service):
        """Parse movie name with brackets."""
        title, year = service._parse_movie_name("Movie Name [2020]")
        assert title == "Movie Name"
        assert year == 2020

    def test_parse_movie_name_no_year(self, service):
        """Parse movie name without year."""
        title, year = service._parse_movie_name("Movie Name")
        assert title == "Movie Name"
        assert year is None

    def test_get_artwork_stats(self, service, tmp_path):
        """Get artwork statistics."""
        with patch.object(service, "settings") as mock_settings:
            # Create movie structure
            movies_dir = tmp_path / "Movies"
            movies_dir.mkdir()
            movie1 = movies_dir / "Movie 1 (2020)"
            movie1.mkdir()
            (movie1 / "movie.mkv").touch()
            (movie1 / "poster.jpg").touch()  # Has poster

            movie2 = movies_dir / "Movie 2 (2021)"
            movie2.mkdir()
            (movie2 / "movie.mkv").touch()  # No poster

            # Create TV structure
            tv_dir = tmp_path / "TV"
            tv_dir.mkdir()
            show1 = tv_dir / "Show 1"
            show1.mkdir()
            (show1 / "poster.jpg").touch()  # Has poster
            (show1 / "Season 1").mkdir()
            (show1 / "Season 2").mkdir()
            (show1 / "season01-poster.jpg").touch()  # S1 has poster

            show2 = tv_dir / "Show 2"
            show2.mkdir()  # No poster

            mock_settings.movies_dir = movies_dir
            mock_settings.tv_dir = tv_dir

            stats = service.get_artwork_stats()

        assert stats["movies"]["total"] == 2
        assert stats["movies"]["with_poster"] == 1
        assert stats["movies"]["missing_poster"] == 1

        assert stats["tv"]["total"] == 2
        assert stats["tv"]["with_poster"] == 1
        assert stats["tv"]["missing_poster"] == 1
        assert stats["tv"]["seasons"] == 2
        assert stats["tv"]["seasons_with_poster"] == 1


class TestArtworkServiceNoApiKey:
    """Tests for ArtworkService without API key."""

    def test_search_movie_no_api_key(self):
        """Search returns None without API key."""
        with patch("jackmediaman.services.artwork.get_settings") as mock_settings:
            mock_settings.return_value.tmdb_api_key = None
            service = ArtworkService()
            result = service.search_movie("Test")
            assert result is None

    def test_get_poster_url_no_api_key(self):
        """Get poster URL returns None without API key."""
        with patch("jackmediaman.services.artwork.get_settings") as mock_settings:
            mock_settings.return_value.tmdb_api_key = None
            service = ArtworkService()
            url = service.get_movie_poster_url(12345)
            assert url is None
