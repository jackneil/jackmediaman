"""Tests for subtitles service."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

from jackmediaman.services.subtitles import (
    OpenSubtitlesComClient,
    OpenSubtitlesOrgClient,
    SubtitleService,
    SubtitleResult,
    VIDEO_EXTENSIONS,
)
from jackmediaman.core.exceptions import OpenSubtitlesError


class TestSubtitleResult:
    """Tests for SubtitleResult dataclass."""

    def test_successful_result(self, tmp_path):
        """Create successful subtitle result."""
        video = tmp_path / "video.mkv"
        subtitle = tmp_path / "video.en.srt"
        result = SubtitleResult(
            video_path=video,
            subtitle_path=subtitle,
            language="en",
            success=True,
        )
        assert result.success is True
        assert result.error is None
        assert result.skipped is False

    def test_skipped_result(self, tmp_path):
        """Create skipped result when subtitle exists."""
        video = tmp_path / "video.mkv"
        subtitle = tmp_path / "video.en.srt"
        result = SubtitleResult(
            video_path=video,
            subtitle_path=subtitle,
            language="en",
            success=True,
            skipped=True,
            skip_reason="Subtitle already exists",
        )
        assert result.success is True
        assert result.skipped is True
        assert result.skip_reason == "Subtitle already exists"

    def test_failed_result(self, tmp_path):
        """Create failed result."""
        video = tmp_path / "video.mkv"
        result = SubtitleResult(
            video_path=video,
            success=False,
            error="No subtitles found",
        )
        assert result.success is False
        assert result.error == "No subtitles found"


class TestOpenSubtitlesComClient:
    """Tests for OpenSubtitlesComClient class (REST API with api_key)."""

    def test_init_with_api_key(self):
        """Initialize client with API key."""
        client = OpenSubtitlesComClient(api_key="test_key")
        assert client.api_key == "test_key"

    def test_init_from_settings(self):
        """Initialize client from settings."""
        with patch("jackmediaman.services.subtitles.get_settings") as mock_settings:
            mock_settings.return_value.opensubtitles_api_key = "settings_key"
            mock_settings.return_value.opensubtitles_username = ""
            mock_settings.return_value.opensubtitles_password = ""
            mock_settings.return_value.opensubtitles_jwt_token = None
            mock_settings.return_value.opensubtitles_jwt_expires = None
            client = OpenSubtitlesComClient()
            assert client.api_key == "settings_key"

    def test_get_headers(self):
        """Get headers includes API key."""
        client = OpenSubtitlesComClient(api_key="test_key")
        headers = client._get_headers()
        assert headers["Api-Key"] == "test_key"
        assert "User-Agent" in headers
        assert "JackMediaMan" in headers["User-Agent"]

    def test_compute_hash(self, tmp_path):
        """Compute hash for video file."""
        from jackmediaman.services.subtitles import compute_hash
        # Create a test file with known content
        video = tmp_path / "test.mkv"
        # Need at least 128KB for the hash algorithm
        content = b"A" * 131072  # 128KB
        video.write_bytes(content)

        hash_value = compute_hash(video)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 16  # 64-bit hash as hex

    def test_compute_hash_small_file(self, tmp_path):
        """Compute hash for small file."""
        from jackmediaman.services.subtitles import compute_hash
        video = tmp_path / "small.mkv"
        video.write_bytes(b"small content")

        hash_value = compute_hash(video)
        assert isinstance(hash_value, str)
        assert len(hash_value) == 16

    def test_validate_credentials_success(self):
        """Validate credentials successfully via login."""
        client = OpenSubtitlesComClient(api_key="test_key", username="user", password="pass")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "jwt_token_123"}

        with patch("httpx.post", return_value=mock_response):
            result = client.validate_credentials()
            assert result is True

    def test_validate_credentials_invalid(self):
        """Invalid credentials returns False."""
        client = OpenSubtitlesComClient(api_key="bad_key", username="user", password="wrong")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {}

        with patch("httpx.post", return_value=mock_response):
            result = client.validate_credentials()
            assert result is False

    def test_validate_credentials_no_credentials(self):
        """No credentials returns False."""
        with patch("jackmediaman.services.subtitles.get_settings") as mock_settings:
            mock_settings.return_value.opensubtitles_api_key = ""
            mock_settings.return_value.opensubtitles_username = ""
            mock_settings.return_value.opensubtitles_password = ""
            mock_settings.return_value.opensubtitles_jwt_token = None
            mock_settings.return_value.opensubtitles_jwt_expires = None
            client = OpenSubtitlesComClient()
            result = client.validate_credentials()
            assert result is False

    def test_validate_credentials_network_error(self):
        """Network error returns False."""
        import httpx

        client = OpenSubtitlesComClient(api_key="test_key", username="user", password="pass")

        with patch("httpx.post") as mock_post:
            mock_post.side_effect = httpx.HTTPError("Connection failed")
            result = client.validate_credentials()
            assert result is False

    def test_search_http_error_401(self, tmp_path):
        """Search with invalid API key raises error."""
        import httpx

        client = OpenSubtitlesComClient(api_key="bad_key")
        video = tmp_path / "video.mkv"
        video.write_bytes(b"A" * 131072)

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_response
        )

        with patch("httpx.get", return_value=mock_response):
            with pytest.raises(OpenSubtitlesError, match="Search failed"):
                client.search(video, ["en"])

    def test_search_success(self, tmp_path):
        """Search returns results."""
        client = OpenSubtitlesComClient(api_key="test_key")
        video = tmp_path / "video.mkv"
        video.write_bytes(b"A" * 131072)

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "attributes": {
                        "language": "en",
                        "files": [{"file_id": 12345}],
                    }
                }
            ]
        }

        with patch("httpx.get", return_value=mock_response):
            results = client.search(video, ["en"])
            assert len(results) == 1
            assert results[0]["attributes"]["language"] == "en"

    def test_search_http_error(self, tmp_path):
        """Search HTTP error raises OpenSubtitlesError."""
        import httpx

        client = OpenSubtitlesComClient(api_key="test_key")
        video = tmp_path / "video.mkv"
        video.write_bytes(b"A" * 131072)

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        with patch("httpx.get", return_value=mock_response):
            with pytest.raises(OpenSubtitlesError, match="Search failed"):
                client.search(video, ["en"])

    def test_download_no_credentials(self):
        """Download without credentials raises error."""
        with patch("jackmediaman.services.subtitles.get_settings") as mock_settings:
            mock_settings.return_value.opensubtitles_api_key = ""
            mock_settings.return_value.opensubtitles_username = ""
            mock_settings.return_value.opensubtitles_password = ""
            mock_settings.return_value.opensubtitles_jwt_token = None
            mock_settings.return_value.opensubtitles_jwt_expires = None
            client = OpenSubtitlesComClient()

            with pytest.raises(OpenSubtitlesError, match="Could not authenticate"):
                client.download(12345)

    def test_download_success(self):
        """Download returns subtitle content."""
        client = OpenSubtitlesComClient(api_key="test_key")
        # Set JWT token directly to skip login
        client.jwt_token = "test_jwt_token"

        # Mock the download link request
        mock_link_response = MagicMock()
        mock_link_response.status_code = 200
        mock_link_response.json.return_value = {"link": "https://example.com/sub.srt"}
        mock_link_response.raise_for_status = MagicMock()

        # Mock the actual download
        mock_content_response = MagicMock()
        mock_content_response.status_code = 200
        mock_content_response.text = "1\n00:00:01,000 --> 00:00:03,000\nHello World"
        mock_content_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_link_response):
            with patch("httpx.get", return_value=mock_content_response):
                content = client.download(12345)
                assert content is not None
                assert "Hello World" in content

    def test_download_no_link(self):
        """Download returns None when no link provided."""
        client = OpenSubtitlesComClient(api_key="test_key")
        # Set JWT token directly to skip login
        client.jwt_token = "test_jwt_token"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # No link
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.post", return_value=mock_response):
            content = client.download(12345)
            assert content is None


class TestSubtitleService:
    """Tests for SubtitleService class."""

    @pytest.fixture
    def mock_client(self):
        """Create mock OpenSubtitles client."""
        return MagicMock(spec=OpenSubtitlesComClient)

    @pytest.fixture
    def service(self, mock_client):
        """Create subtitle service with mock client."""
        return SubtitleService(client=mock_client)

    def test_download_for_file_success(self, tmp_path, service, mock_client):
        """Download subtitle for single file."""
        video = tmp_path / "video.mkv"
        video.touch()

        mock_client.search.return_value = [
            {
                "attributes": {
                    "language": "en",
                    "files": [{"file_id": 12345}],
                }
            }
        ]
        mock_client.download.return_value = "1\n00:00:01,000 --> 00:00:03,000\nHello"

        result = service.download_for_file(video)

        assert result.success is True
        assert result.language == "en"
        assert result.subtitle_path.exists()
        assert result.subtitle_path.suffix == ".srt"

    def test_download_for_file_already_exists(self, tmp_path, service, mock_client):
        """Skip download when subtitle already exists."""
        video = tmp_path / "video.mkv"
        video.touch()
        subtitle = tmp_path / "video.en.srt"
        subtitle.write_text("existing subtitle")

        result = service.download_for_file(video, languages=["en"])

        assert result.success is True
        assert result.skipped is True
        assert result.skip_reason == "Subtitle already exists"
        mock_client.search.assert_not_called()

    def test_download_for_file_overwrite(self, tmp_path, service, mock_client):
        """Download overwrites existing subtitle."""
        video = tmp_path / "video.mkv"
        video.touch()
        subtitle = tmp_path / "video.en.srt"
        subtitle.write_text("old subtitle")

        mock_client.search.return_value = [
            {
                "attributes": {
                    "language": "en",
                    "files": [{"file_id": 12345}],
                }
            }
        ]
        mock_client.download.return_value = "new subtitle content"

        result = service.download_for_file(video, languages=["en"], overwrite=True)

        assert result.success is True
        assert result.skipped is False
        assert subtitle.read_text() == "new subtitle content"

    def test_download_for_file_no_results(self, tmp_path, service, mock_client):
        """Handle no search results."""
        video = tmp_path / "video.mkv"
        video.touch()

        mock_client.search.return_value = []

        result = service.download_for_file(video)

        assert result.success is False
        assert "No subtitles found" in result.error

    def test_download_for_file_no_files_in_result(self, tmp_path, service, mock_client):
        """Handle result with no files."""
        video = tmp_path / "video.mkv"
        video.touch()

        mock_client.search.return_value = [{"attributes": {"language": "en", "files": []}}]

        result = service.download_for_file(video)

        assert result.success is False
        assert "No subtitle files" in result.error

    def test_download_for_file_api_error(self, tmp_path, service, mock_client):
        """Handle API error gracefully."""
        video = tmp_path / "video.mkv"
        video.touch()

        mock_client.search.side_effect = OpenSubtitlesError("API error")

        result = service.download_for_file(video)

        assert result.success is False
        assert "API error" in result.error

    def test_download_for_directory(self, tmp_path, service, mock_client):
        """Download subtitles for directory."""
        # Create video files
        video1 = tmp_path / "video1.mkv"
        video1.touch()
        video2 = tmp_path / "video2.mp4"
        video2.touch()
        # Non-video file should be ignored
        other = tmp_path / "file.txt"
        other.touch()

        mock_client.search.return_value = [
            {
                "attributes": {
                    "language": "en",
                    "files": [{"file_id": 12345}],
                }
            }
        ]
        mock_client.download.return_value = "subtitle content"

        results = service.download_for_directory(tmp_path)

        assert len(results) == 2
        assert all(r.success for r in results)

    def test_download_for_directory_with_callback(self, tmp_path, service, mock_client):
        """Progress callback is called."""
        video = tmp_path / "video.mkv"
        video.touch()

        mock_client.search.return_value = [
            {"attributes": {"language": "en", "files": [{"file_id": 12345}]}}
        ]
        mock_client.download.return_value = "content"

        callback = MagicMock()
        service.download_for_directory(tmp_path, progress_callback=callback)

        callback.assert_called()

    def test_download_for_library_tv(self, tmp_path, mock_client):
        """Download for TV library only."""
        # Create directories
        tv_dir = tmp_path / "tv"
        movies_dir = tmp_path / "movies"
        tv_dir.mkdir()
        movies_dir.mkdir()

        # Create TV file
        tv_video = tv_dir / "episode.mkv"
        tv_video.touch()

        # Create mock settings
        mock_settings = MagicMock()
        mock_settings.tv_dir = tv_dir
        mock_settings.movies_dir = movies_dir
        mock_settings.subtitle_languages = "en"

        mock_client.search.return_value = [
            {"attributes": {"language": "en", "files": [{"file_id": 12345}]}}
        ]
        mock_client.download.return_value = "content"

        # Create service with mock settings
        with patch("jackmediaman.services.subtitles.get_settings", return_value=mock_settings):
            service = SubtitleService(client=mock_client)
            results = service.download_for_library("tv")

        # Only TV directory should be processed
        assert len(results) == 1

    def test_download_for_library_both(self, tmp_path, mock_client):
        """Download for both libraries."""
        # Create directories
        tv_dir = tmp_path / "tv"
        movies_dir = tmp_path / "movies"
        tv_dir.mkdir()
        movies_dir.mkdir()

        (tv_dir / "episode.mkv").touch()
        (movies_dir / "movie.mkv").touch()

        # Create mock settings
        mock_settings = MagicMock()
        mock_settings.tv_dir = tv_dir
        mock_settings.movies_dir = movies_dir
        mock_settings.subtitle_languages = "en"

        mock_client.search.return_value = [
            {"attributes": {"language": "en", "files": [{"file_id": 12345}]}}
        ]
        mock_client.download.return_value = "content"

        # Create service with mock settings
        with patch("jackmediaman.services.subtitles.get_settings", return_value=mock_settings):
            service = SubtitleService(client=mock_client)
            results = service.download_for_library("both")

        assert len(results) == 2


class TestVideoExtensions:
    """Tests for VIDEO_EXTENSIONS constant."""

    def test_common_extensions_included(self):
        """Common video extensions are included."""
        assert ".mkv" in VIDEO_EXTENSIONS
        assert ".mp4" in VIDEO_EXTENSIONS
        assert ".avi" in VIDEO_EXTENSIONS

    def test_lowercase_extensions(self):
        """All extensions are lowercase."""
        for ext in VIDEO_EXTENSIONS:
            assert ext == ext.lower()
            assert ext.startswith(".")
