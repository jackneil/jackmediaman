"""Tests for renamer service."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from jackmediaman.services.renamer import (
    RenameService,
    RenameResult,
    RenameSummary,
    TMDbTVClient,
    sanitize_filename,
)
from jackmediaman.models.media import Movie, Episode
from jackmediaman.models.quality import Quality, Resolution


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    def test_removes_forbidden_chars(self):
        """Removes characters not allowed in filenames."""
        assert sanitize_filename("Movie: Subtitle") == "Movie - Subtitle"
        assert sanitize_filename("Movie/Part") == "Movie - Part"
        assert sanitize_filename("Movie?") == "Movie"
        assert sanitize_filename("Movie<>File") == "Movie - File"

    def test_removes_double_dashes(self):
        """Consolidates multiple dashes."""
        # Double dashes are preserved since they're valid filename chars
        # Only space-dash-space-dash-space sequences are consolidated
        assert sanitize_filename("Movie--Title") == "Movie - Title"
        assert sanitize_filename("Movie---Title") == "Movie - Title"

    def test_strips_whitespace_and_dashes(self):
        """Strips leading/trailing whitespace and dashes."""
        assert sanitize_filename("  Movie  ") == "Movie"
        assert sanitize_filename("-Movie-") == "Movie"

    def test_truncates_long_names(self):
        """Truncates very long filenames."""
        long_name = "A" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 240

    def test_preserves_valid_chars(self):
        """Preserves valid filename characters."""
        assert sanitize_filename("Movie 2020") == "Movie 2020"
        assert sanitize_filename("Movie (2020)") == "Movie (2020)"
        assert sanitize_filename("Movie [2020]") == "Movie [2020]"


class TestRenameResult:
    """Tests for RenameResult dataclass."""

    def test_successful_result(self, tmp_path, sample_movie):
        """Create successful rename result."""
        result = RenameResult(
            item=sample_movie,
            old_path=tmp_path / "old.mkv",
            new_path=tmp_path / "new.mkv",
            success=True,
        )
        assert result.success is True
        assert result.skipped is False

    def test_skipped_result(self, tmp_path, sample_movie):
        """Create skipped rename result."""
        result = RenameResult(
            item=sample_movie,
            old_path=tmp_path / "movie.mkv",
            new_path=tmp_path / "movie.mkv",
            success=True,
            skipped=True,
            skip_reason="Already named correctly",
        )
        assert result.skipped is True
        assert "Already" in result.skip_reason


class TestRenameSummary:
    """Tests for RenameSummary dataclass."""

    def test_summary_fields(self, tmp_path, sample_movie):
        """Summary has expected fields."""
        result = RenameResult(
            item=sample_movie,
            old_path=tmp_path / "old.mkv",
            new_path=tmp_path / "new.mkv",
            success=True,
        )
        summary = RenameSummary(
            total_files=5,
            renamed=3,
            skipped=1,
            failed=1,
            results=[result],
        )
        assert summary.total_files == 5
        assert summary.renamed == 3
        assert summary.skipped == 1
        assert summary.failed == 1


class TestTMDbTVClient:
    """Tests for TMDbTVClient class."""

    @pytest.fixture
    def client(self, tmp_path):
        """Create TMDb TV client with test API key."""
        return TMDbTVClient(api_key="test_key", cache_dir=tmp_path / "cache")

    def test_search_tv_no_api_key(self, tmp_path):
        """Returns None if no API key."""
        with patch("jackmediaman.matchers.tmdb.get_settings") as mock_settings:
            mock_settings.return_value.tmdb_api_key = None
            mock_settings.return_value.cache_dir = tmp_path / "cache"
            client = TMDbTVClient(api_key=None, cache_dir=tmp_path / "cache")
            result = client.search_tv("Breaking Bad")
            assert result is None

    @patch("httpx.get")
    def test_search_tv_success(self, mock_get, client):
        """Successful TV search returns ID."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [{"id": 1396, "name": "Breaking Bad"}]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.search_tv("Breaking Bad")

        assert result == 1396

    def test_get_episode_title_no_api_key(self, tmp_path):
        """Returns None if no API key."""
        with patch("jackmediaman.matchers.tmdb.get_settings") as mock_settings:
            mock_settings.return_value.tmdb_api_key = None
            mock_settings.return_value.cache_dir = tmp_path / "cache"
            client = TMDbTVClient(api_key=None, cache_dir=tmp_path / "cache")
            result = client.get_episode_title(1396, 1, 1)
            assert result is None

    @patch("httpx.get")
    def test_get_episode_title_success(self, mock_get, client):
        """Successful episode lookup returns title."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"name": "Pilot"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        result = client.get_episode_title(1396, 1, 1)

        assert result == "Pilot"

    def test_get_movie_details_no_api_key(self, tmp_path):
        """Returns None if no API key."""
        with patch("jackmediaman.matchers.tmdb.get_settings") as mock_settings:
            mock_settings.return_value.tmdb_api_key = None
            mock_settings.return_value.cache_dir = tmp_path / "cache"
            client = TMDbTVClient(api_key=None, cache_dir=tmp_path / "cache")
            result = client.get_movie_details(27205)
            assert result is None


class TestRenameService:
    """Tests for RenameService class."""

    @pytest.fixture
    def mock_tmdb(self):
        """Create mock TMDb client."""
        client = MagicMock()
        client.api_key = "test_key"
        client.search_tv = MagicMock(return_value=1396)
        client.get_episode_title = MagicMock(return_value="Pilot")
        client.search_movie = MagicMock(return_value=27205)
        client.get_movie_details = MagicMock(return_value={"title": "Inception", "year": "2010"})
        return client

    @pytest.fixture
    def mock_tmdb_no_key(self):
        """Create mock TMDb client without API key."""
        client = MagicMock()
        client.api_key = None
        return client

    @pytest.fixture
    def renamer(self, mock_tmdb):
        """Create rename service with mock TMDb."""
        service = RenameService(tmdb_client=mock_tmdb)
        return service

    @pytest.fixture
    def renamer_no_tmdb(self, mock_tmdb_no_key):
        """Create rename service without TMDb."""
        service = RenameService(tmdb_client=mock_tmdb_no_key)
        return service


class TestRenameServiceEpisodes:
    """Tests for renaming TV episodes."""

    @pytest.fixture
    def mock_tmdb(self):
        client = MagicMock()
        client.api_key = "test_key"
        client.search_tv = MagicMock(return_value=1396)
        client.get_episode_title = MagicMock(return_value="Pilot")
        return client

    @pytest.fixture
    def renamer(self, mock_tmdb):
        service = RenameService(tmdb_client=mock_tmdb)
        return service

    def test_generate_episode_name_with_title(self, renamer, sample_episode):
        """Generates episode name with TMDb title."""
        new_name = renamer.generate_new_name(sample_episode)

        assert "S01E01" in new_name
        assert "Pilot" in new_name
        assert new_name.endswith(".mkv")

    def test_generate_episode_name_without_tmdb(self, sample_episode, mock_settings):
        """Generates episode name without TMDb (no title)."""
        mock_client = MagicMock()
        mock_client.api_key = None
        renamer = RenameService(tmdb_client=mock_client)

        new_name = renamer.generate_new_name(sample_episode)

        assert "S01E01" in new_name
        assert "Pilot" not in new_name  # No TMDb lookup
        assert new_name.endswith(".mkv")

    def test_generate_multi_episode_name(self, tmp_path, mock_settings):
        """Generates name for multi-episode file."""
        mock_client = MagicMock()
        mock_client.api_key = None

        quality = Quality(resolution=Resolution.FHD)
        episode = Episode(
            path=tmp_path / "Show.S01E01E02E03.mkv",
            filename="Show.S01E01E02E03.mkv",
            size_bytes=100,
            quality=quality,
            series_name="Test Show",
            season_number=1,
            episode_numbers=[1, 2, 3],
        )

        renamer = RenameService(tmdb_client=mock_client)
        new_name = renamer.generate_new_name(episode)

        assert "S01E01-E03" in new_name


class TestRenameServiceMovies:
    """Tests for renaming movies."""

    @pytest.fixture
    def mock_tmdb(self):
        client = MagicMock()
        client.api_key = "test_key"
        client.search_movie = MagicMock(return_value=27205)
        client.get_movie_details = MagicMock(return_value={"title": "Inception", "year": "2010"})
        return client

    @pytest.fixture
    def renamer(self, mock_tmdb):
        service = RenameService(tmdb_client=mock_tmdb)
        return service

    def test_generate_movie_name_with_tmdb(self, renamer, sample_movie):
        """Generates movie name with TMDb info."""
        new_name = renamer.generate_new_name(sample_movie)

        assert "Inception" in new_name
        assert "(2010)" in new_name
        assert new_name.endswith(".mkv")

    def test_generate_movie_name_without_tmdb(self, tmp_path, mock_settings):
        """Generates movie name without TMDb."""
        mock_client = MagicMock()
        mock_client.api_key = None

        quality = Quality(resolution=Resolution.FHD)
        movie = Movie(
            path=tmp_path / "Movie.mkv",
            filename="Movie.mkv",
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
        )

        renamer = RenameService(tmdb_client=mock_client)
        new_name = renamer.generate_new_name(movie)

        assert "Test Movie" in new_name
        assert "(2020)" in new_name

    def test_generate_movie_name_no_year(self, tmp_path, mock_settings):
        """Generates movie name without year."""
        mock_client = MagicMock()
        mock_client.api_key = None

        quality = Quality(resolution=Resolution.FHD)
        movie = Movie(
            path=tmp_path / "Movie.mkv",
            filename="Movie.mkv",
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=None,
        )

        renamer = RenameService(tmdb_client=mock_client)
        new_name = renamer.generate_new_name(movie)

        assert "Test Movie" in new_name
        assert "()" not in new_name  # No empty parens


class TestRenameServiceOperations:
    """Tests for rename operations."""

    @pytest.fixture
    def mock_tmdb(self):
        client = MagicMock()
        client.api_key = None
        return client

    @pytest.fixture
    def renamer(self, mock_tmdb):
        service = RenameService(tmdb_client=mock_tmdb)
        return service

    def test_preview_rename(self, renamer, sample_movie):
        """Preview shows old and new names."""
        preview = renamer.preview_rename(sample_movie)

        if preview:  # May return None if name unchanged
            old_name, new_name = preview
            assert old_name == sample_movie.filename

    def test_preview_rename_unchanged(self, renamer, tmp_path, mock_settings):
        """Preview returns None if name unchanged (including resolution tag)."""
        quality = Quality(resolution=Resolution.FHD, resolution_raw="1080p")
        movie = Movie(
            path=tmp_path / "Test Movie (2020) [1080p].mkv",
            filename="Test Movie (2020) [1080p].mkv",
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
        )

        preview = renamer.preview_rename(movie)
        assert preview is None

    def test_rename_dry_run(self, renamer, sample_movie):
        """Dry run doesn't actually rename."""
        sample_movie.path.write_bytes(b"0" * 100)
        original_path = sample_movie.path

        result = renamer.rename(sample_movie, dry_run=True)

        assert original_path.exists()

    def test_rename_skip_if_unchanged(self, renamer, tmp_path, mock_settings):
        """Skips if name already correct (including resolution tag)."""
        quality = Quality(resolution=Resolution.FHD, resolution_raw="1080p")
        movie = Movie(
            path=tmp_path / "Test Movie (2020) [1080p].mkv",
            filename="Test Movie (2020) [1080p].mkv",
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
        )

        result = renamer.rename(movie, dry_run=True)

        assert result.skipped is True
        assert "correctly" in result.skip_reason.lower()

    def test_rename_skip_if_target_exists(self, renamer, tmp_path, mock_settings):
        """Fails if target already exists."""
        quality = Quality(resolution=Resolution.FHD, resolution_raw="1080p")
        old_name = "Old.Name.mkv"
        # New name includes resolution tag
        new_name = "Test Movie (2020) [1080p].mkv"

        # Create both files
        old_path = tmp_path / old_name
        new_path = tmp_path / new_name
        old_path.write_bytes(b"0" * 100)
        new_path.write_bytes(b"0" * 100)

        movie = Movie(
            path=old_path,
            filename=old_name,
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
        )

        result = renamer.rename(movie, dry_run=False)

        assert result.success is False
        assert "exists" in result.error.lower()


class TestRenameServiceBatch:
    """Tests for batch rename operations."""

    @pytest.fixture
    def mock_tmdb(self):
        client = MagicMock()
        client.api_key = None
        return client

    @pytest.fixture
    def renamer(self, mock_tmdb):
        service = RenameService(tmdb_client=mock_tmdb)
        return service

    def test_rename_items(self, renamer, tmp_path, mock_settings):
        """Batch rename returns summary."""
        quality = Quality(resolution=Resolution.FHD)
        movies = []

        for i in range(3):
            path = tmp_path / f"Movie{i}.mkv"
            path.write_bytes(b"0" * 100)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=100,
                quality=quality,
                title=f"Movie {i}",
                year=2020,
            ))

        summary = renamer.rename_items(movies, dry_run=True)

        assert isinstance(summary, RenameSummary)
        assert summary.total_files == 3
        assert len(summary.results) == 3

    def test_rename_items_progress_callback(self, renamer, tmp_path, mock_settings):
        """Batch rename calls progress callback."""
        quality = Quality(resolution=Resolution.FHD)
        path = tmp_path / "Movie.mkv"
        path.write_bytes(b"0" * 100)

        movie = Movie(
            path=path,
            filename=path.name,
            size_bytes=100,
            quality=quality,
            title="Movie",
            year=2020,
        )

        callback = MagicMock()
        renamer.rename_items([movie], dry_run=True, progress_callback=callback)

        callback.assert_called()


class TestAssociatedFileRenaming:
    """Tests for renaming associated subtitle files alongside videos."""

    @pytest.fixture
    def mock_tmdb(self):
        client = MagicMock()
        client.api_key = None
        return client

    @pytest.fixture
    def renamer(self, mock_tmdb):
        service = RenameService(tmdb_client=mock_tmdb)
        return service

    def test_find_associated_files_basic(self, renamer, tmp_path):
        """Find basic subtitle file."""
        video = tmp_path / "Movie.mkv"
        subtitle = tmp_path / "Movie.en.srt"
        video.touch()
        subtitle.touch()

        found = renamer._find_associated_files(video)

        assert len(found) == 1
        assert subtitle in found

    def test_find_associated_files_multiple(self, renamer, tmp_path):
        """Find multiple subtitle files."""
        video = tmp_path / "Movie.mkv"
        sub_en = tmp_path / "Movie.en.srt"
        sub_es = tmp_path / "Movie.es.srt"
        sub_forced = tmp_path / "Movie.en.forced.srt"
        video.touch()
        sub_en.touch()
        sub_es.touch()
        sub_forced.touch()

        found = renamer._find_associated_files(video)

        assert len(found) == 3
        assert sub_en in found
        assert sub_es in found
        assert sub_forced in found

    def test_find_associated_files_no_language_code(self, renamer, tmp_path):
        """Find subtitle without language code."""
        video = tmp_path / "Movie.mkv"
        subtitle = tmp_path / "Movie.srt"
        video.touch()
        subtitle.touch()

        found = renamer._find_associated_files(video)

        assert len(found) == 1
        assert subtitle in found

    def test_find_associated_files_ignores_unrelated(self, renamer, tmp_path):
        """Ignores subtitle files that don't match."""
        video = tmp_path / "Movie.mkv"
        unrelated1 = tmp_path / "MovieExtra.en.srt"  # Different base name
        unrelated2 = tmp_path / "Another.en.srt"  # Completely different
        video.touch()
        unrelated1.touch()
        unrelated2.touch()

        found = renamer._find_associated_files(video)

        assert len(found) == 0

    def test_find_associated_files_empty(self, renamer, tmp_path):
        """Returns empty list when no subtitles."""
        video = tmp_path / "Movie.mkv"
        video.touch()

        found = renamer._find_associated_files(video)

        assert len(found) == 0

    def test_rename_renames_subtitles(self, renamer, tmp_path, mock_settings):
        """Rename also renames associated subtitles."""
        quality = Quality(resolution=Resolution.FHD, resolution_raw="1080p")

        # Create video and subtitle
        video = tmp_path / "Old.Movie.mkv"
        subtitle = tmp_path / "Old.Movie.en.srt"
        video.write_bytes(b"video content")
        subtitle.write_text("subtitle content")

        movie = Movie(
            path=video,
            filename=video.name,
            size_bytes=100,
            quality=quality,
            title="New Movie",
            year=2020,
        )

        result = renamer.rename(movie, dry_run=False)

        assert result.success is True
        # Video renamed
        assert not video.exists()
        new_video = tmp_path / "New Movie (2020) [1080p].mkv"
        assert new_video.exists()
        # Subtitle also renamed
        assert not subtitle.exists()
        new_subtitle = tmp_path / "New Movie (2020) [1080p].en.srt"
        assert new_subtitle.exists()
        assert new_subtitle.read_text() == "subtitle content"

    def test_rename_renames_multiple_subtitles(self, renamer, tmp_path, mock_settings):
        """Rename renames all associated subtitle files."""
        quality = Quality(resolution=Resolution.FHD, resolution_raw="1080p")

        # Create video and multiple subtitles
        video = tmp_path / "Old.Movie.mkv"
        sub_en = tmp_path / "Old.Movie.en.srt"
        sub_es = tmp_path / "Old.Movie.es.srt"
        sub_forced = tmp_path / "Old.Movie.en.forced.srt"
        video.write_bytes(b"video content")
        sub_en.write_text("english")
        sub_es.write_text("spanish")
        sub_forced.write_text("forced")

        movie = Movie(
            path=video,
            filename=video.name,
            size_bytes=100,
            quality=quality,
            title="New Movie",
            year=2020,
        )

        result = renamer.rename(movie, dry_run=False)

        assert result.success is True
        # All old files gone
        assert not video.exists()
        assert not sub_en.exists()
        assert not sub_es.exists()
        assert not sub_forced.exists()
        # All new files exist
        assert (tmp_path / "New Movie (2020) [1080p].mkv").exists()
        assert (tmp_path / "New Movie (2020) [1080p].en.srt").exists()
        assert (tmp_path / "New Movie (2020) [1080p].es.srt").exists()
        assert (tmp_path / "New Movie (2020) [1080p].en.forced.srt").exists()

    def test_rename_dry_run_doesnt_rename_subtitles(self, renamer, tmp_path, mock_settings):
        """Dry run doesn't rename subtitles."""
        quality = Quality(resolution=Resolution.FHD, resolution_raw="1080p")

        video = tmp_path / "Old.Movie.mkv"
        subtitle = tmp_path / "Old.Movie.en.srt"
        video.write_bytes(b"video content")
        subtitle.write_text("subtitle content")

        movie = Movie(
            path=video,
            filename=video.name,
            size_bytes=100,
            quality=quality,
            title="New Movie",
            year=2020,
        )

        result = renamer.rename(movie, dry_run=True)

        assert result.success is True
        # Nothing actually renamed
        assert video.exists()
        assert subtitle.exists()
