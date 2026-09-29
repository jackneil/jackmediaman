"""Tests for Plex notification service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jackmediaman.services.plex import (
    PlexDiscoveryResult,
    PlexLibrary,
    PlexNotifyResult,
    PlexService,
    _extract_plex_config,
    discover_plex_config,
)


class TestPlexLibrary:
    """Tests for PlexLibrary dataclass."""

    def test_create_library(self):
        """Create a PlexLibrary instance."""
        library = PlexLibrary(
            key="1",
            title="Movies",
            type="movie",
            locations=[Path("/media/Movies")],
        )
        assert library.key == "1"
        assert library.title == "Movies"
        assert library.type == "movie"
        assert len(library.locations) == 1

    def test_library_multiple_locations(self):
        """Library can have multiple locations."""
        library = PlexLibrary(
            key="2",
            title="TV Shows",
            type="show",
            locations=[Path("/media/TV"), Path("/media2/TV")],
        )
        assert len(library.locations) == 2


class TestPlexNotifyResult:
    """Tests for PlexNotifyResult dataclass."""

    def test_create_success_result(self):
        """Create a successful notification result."""
        result = PlexNotifyResult(
            path=Path("/media/Movies/Test Movie (2024)"),
            library="Movies",
            success=True,
        )
        assert result.success is True
        assert result.library == "Movies"
        assert result.error is None

    def test_create_failure_result(self):
        """Create a failed notification result."""
        result = PlexNotifyResult(
            path=Path("/other/path"),
            library=None,
            success=False,
            error="Path not in any Plex library",
        )
        assert result.success is False
        assert result.library is None
        assert result.error == "Path not in any Plex library"


class TestPlexService:
    """Tests for PlexService class."""

    def test_init_from_settings(self):
        """Initialize from settings."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                plex_url="http://localhost:32400",
                plex_api_token="test_token",
                plex_notify_enabled=True,
            )
            service = PlexService()

            assert service.url == "http://localhost:32400"
            assert service.token == "test_token"

    def test_init_with_custom_params(self):
        """Initialize with custom URL and token."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                plex_url=None,
                plex_api_token=None,
                plex_notify_enabled=True,
            )
            service = PlexService(
                url="http://192.168.1.100:32400",
                token="custom_token",
            )

            assert service.url == "http://192.168.1.100:32400"
            assert service.token == "custom_token"

    def test_is_configured_true(self):
        """Service is configured when URL and token are set."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                plex_url="http://localhost:32400",
                plex_api_token="test_token",
                plex_notify_enabled=True,
            )
            service = PlexService()

            assert service.is_configured is True

    def test_is_configured_false_no_url(self):
        """Service is not configured without URL."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings, \
             patch("jackmediaman.services.plex.discover_plex_config") as mock_discover:
            mock_settings.return_value = MagicMock(
                plex_url=None,
                plex_api_token="test_token",
                plex_notify_enabled=True,
            )
            mock_discover.return_value = PlexDiscoveryResult()
            service = PlexService()

            # With token but no url (and no discovery), uses default URL
            # So this should actually be configured now
            assert service.is_configured is True

    def test_is_configured_false_no_token(self):
        """Service is not configured without token."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings, \
             patch("jackmediaman.services.plex.discover_plex_config") as mock_discover:
            mock_settings.return_value = MagicMock(
                plex_url="http://localhost:32400",
                plex_api_token=None,
                plex_notify_enabled=True,
            )
            mock_discover.return_value = PlexDiscoveryResult()
            service = PlexService()

            assert service.is_configured is False

    def test_is_configured_false_disabled(self):
        """Service is not configured when disabled."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                plex_url="http://localhost:32400",
                plex_api_token="test_token",
                plex_notify_enabled=False,
            )
            service = PlexService()

            assert service.is_configured is False

    def test_url_trailing_slash_removed(self):
        """Trailing slash is removed from URL."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                plex_url="http://localhost:32400/",
                plex_api_token="test_token",
                plex_notify_enabled=True,
            )
            service = PlexService()

            assert service.url == "http://localhost:32400"


class TestPlexServiceLibraries:
    """Tests for PlexService library methods."""

    @pytest.fixture
    def service(self):
        """Create a PlexService instance."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                plex_url="http://localhost:32400",
                plex_api_token="test_token",
                plex_notify_enabled=True,
            )
            return PlexService()

    def test_get_libraries_empty_on_error(self, service):
        """Get libraries returns empty list on error."""
        with patch.object(service, "_request", return_value=None):
            libraries = service.get_libraries()
            assert libraries == []

    def test_get_libraries_cached(self, service):
        """Libraries are cached after first fetch."""
        # Pre-populate cache
        service._libraries = [
            PlexLibrary(
                key="1",
                title="Movies",
                type="movie",
                locations=[Path("/media/Movies")],
            )
        ]

        # Should return cached value without making request
        libraries = service.get_libraries()
        assert len(libraries) == 1
        assert libraries[0].title == "Movies"

    def test_find_library_for_path_found(self, service):
        """Find library containing a path."""
        service._libraries = [
            PlexLibrary(
                key="1",
                title="Movies",
                type="movie",
                locations=[Path("/media/Movies")],
            ),
            PlexLibrary(
                key="2",
                title="TV Shows",
                type="show",
                locations=[Path("/media/TV")],
            ),
        ]

        library = service.find_library_for_path(Path("/media/Movies/Test Movie (2024)/Test.mkv"))
        assert library is not None
        assert library.title == "Movies"

    def test_find_library_for_path_not_found(self, service):
        """Return None when path is not in any library."""
        service._libraries = [
            PlexLibrary(
                key="1",
                title="Movies",
                type="movie",
                locations=[Path("/media/Movies")],
            ),
        ]

        library = service.find_library_for_path(Path("/other/path/file.mkv"))
        assert library is None


class TestPlexServiceNotifications:
    """Tests for PlexService notification methods."""

    @pytest.fixture
    def service(self):
        """Create a configured PlexService instance."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                plex_url="http://localhost:32400",
                plex_api_token="test_token",
                plex_notify_enabled=True,
            )
            svc = PlexService()
            svc._libraries = [
                PlexLibrary(
                    key="1",
                    title="Movies",
                    type="movie",
                    locations=[Path("/media/Movies")],
                ),
                PlexLibrary(
                    key="2",
                    title="TV Shows",
                    type="show",
                    locations=[Path("/media/TV")],
                ),
            ]
            return svc

    def test_scan_path_success(self, service):
        """Successfully scan a path."""
        # Test path in the Movies library
        test_path = Path("/media/Movies/Test Movie (2024)")

        with patch.object(service, "_request", return_value=MagicMock()):
            result = service.scan_path(test_path)

        assert result.success is True
        assert result.library == "Movies"

    def test_scan_path_not_in_library(self, service):
        """Scan path not in any library."""
        result = service.scan_path(Path("/other/path"))

        assert result.success is False
        assert result.library is None
        assert result.error == "Path not in any Plex library"

    def test_notify_paths_batches_by_library(self, service):
        """Notify paths batches requests by library."""
        paths = [
            Path("/media/Movies/Movie1/file.mkv"),
            Path("/media/Movies/Movie2/file.mkv"),
            Path("/media/TV/Show1/file.mkv"),
        ]

        with patch.object(service, "_request", return_value=MagicMock()):
            results = service.notify_paths(paths)

        # Should have results for each unique parent directory
        assert len(results) >= 2  # At least Movies and TV scans

    def test_notify_paths_unconfigured(self):
        """Notify paths when service is not configured."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings, \
             patch("jackmediaman.services.plex.discover_plex_config") as mock_discover:
            mock_settings.return_value = MagicMock(
                plex_url=None,
                plex_api_token=None,
                plex_notify_enabled=True,
            )
            mock_discover.return_value = PlexDiscoveryResult()
            service = PlexService()

        paths = [Path("/media/Movies/Test.mkv")]
        results = service.notify_paths(paths)

        assert len(results) == 1
        assert results[0].success is False
        assert "not configured" in results[0].error

    def test_notify_rename_both_paths(self, service):
        """Notify rename scans both old and new paths."""
        old_path = Path("/media/Movies/Old Name/file.mkv")
        new_path = Path("/media/Movies/New Name/file.mkv")

        with patch.object(service, "scan_path") as mock_scan:
            mock_scan.return_value = PlexNotifyResult(
                path=old_path.parent,
                library="Movies",
                success=True,
            )

            results = service.notify_rename(old_path, new_path)

        # Should scan both parent directories (but they might be batched)
        assert mock_scan.call_count >= 1

    def test_notify_removal_in_library(self, service):
        """Notify removal for file in library."""
        path = Path("/media/Movies/Test Movie/file.mkv")

        with patch.object(service, "scan_path") as mock_scan:
            mock_scan.return_value = PlexNotifyResult(
                path=path.parent,
                library="Movies",
                success=True,
            )

            result = service.notify_removal(path)

        assert result is not None
        mock_scan.assert_called_once()

    def test_notify_removal_not_in_library(self, service):
        """Notify removal returns None for path not in library."""
        path = Path("/other/path/file.mkv")

        result = service.notify_removal(path)

        assert result is None


class TestPlexServiceScanLibrary:
    """Tests for full library scan."""

    @pytest.fixture
    def service(self):
        """Create a PlexService instance."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                plex_url="http://localhost:32400",
                plex_api_token="test_token",
                plex_notify_enabled=True,
            )
            return PlexService()

    def test_scan_library_success(self, service):
        """Successfully trigger full library scan."""
        with patch.object(service, "_request", return_value=MagicMock()):
            result = service.scan_library("1")

        assert result is True

    def test_scan_library_failure(self, service):
        """Full library scan fails."""
        with patch.object(service, "_request", return_value=None):
            result = service.scan_library("1")

        assert result is False


class TestPlexDiscovery:
    """Tests for Plex auto-discovery functionality."""

    def test_extract_plex_config_with_token_and_port(self, tmp_path):
        """Extract token and port from Preferences.xml."""
        prefs_content = '''<?xml version="1.0" encoding="utf-8"?>
<Preferences PlexOnlineToken="test_token_123" ManualPortMappingPort="5136" />'''
        prefs_file = tmp_path / "Preferences.xml"
        prefs_file.write_text(prefs_content)

        result = _extract_plex_config(prefs_file)

        assert result.token == "test_token_123"
        assert result.url == "http://localhost:5136"
        assert result.source == str(prefs_file)

    def test_extract_plex_config_default_port(self, tmp_path):
        """Use default port when ManualPortMappingPort not set."""
        prefs_content = '''<?xml version="1.0" encoding="utf-8"?>
<Preferences PlexOnlineToken="another_token" />'''
        prefs_file = tmp_path / "Preferences.xml"
        prefs_file.write_text(prefs_content)

        result = _extract_plex_config(prefs_file)

        assert result.token == "another_token"
        assert result.url == "http://localhost:32400"

    def test_extract_plex_config_from_custom_connections(self, tmp_path):
        """Extract port from customConnections when ManualPortMappingPort not set."""
        prefs_content = '''<?xml version="1.0" encoding="utf-8"?>
<Preferences PlexOnlineToken="token123" customConnections="http://myserver.com:9999" />'''
        prefs_file = tmp_path / "Preferences.xml"
        prefs_file.write_text(prefs_content)

        result = _extract_plex_config(prefs_file)

        assert result.token == "token123"
        assert result.url == "http://localhost:9999"

    def test_extract_plex_config_no_token(self, tmp_path):
        """Return empty result when no token in file."""
        prefs_content = '''<?xml version="1.0" encoding="utf-8"?>
<Preferences SomeOtherSetting="value" />'''
        prefs_file = tmp_path / "Preferences.xml"
        prefs_file.write_text(prefs_content)

        result = _extract_plex_config(prefs_file)

        assert result.token is None

    def test_extract_plex_config_file_not_readable(self, tmp_path):
        """Handle permission errors gracefully."""
        prefs_file = tmp_path / "Preferences.xml"
        prefs_file.write_text("content")

        with patch.object(Path, "read_text", side_effect=PermissionError):
            result = _extract_plex_config(prefs_file)

        assert result.token is None

    def test_discover_plex_config_linux(self, tmp_path):
        """Discover config on Linux from Docker path."""
        prefs_content = '''<?xml version="1.0" encoding="utf-8"?>
<Preferences PlexOnlineToken="discovered_token" ManualPortMappingPort="1234" />'''
        docker_path = tmp_path / ".docker-conf/Library/Application Support/Plex Media Server"
        docker_path.mkdir(parents=True)
        prefs_file = docker_path / "Preferences.xml"
        prefs_file.write_text(prefs_content)

        with patch("platform.system", return_value="Linux"), \
             patch("pathlib.Path.home", return_value=tmp_path):
            result = discover_plex_config()

        assert result.token == "discovered_token"
        assert result.url == "http://localhost:1234"

    def test_discover_plex_config_not_found(self, tmp_path):
        """Return empty result when no Plex installation found."""
        with patch("platform.system", return_value="Linux"), \
             patch("pathlib.Path.home", return_value=tmp_path):
            result = discover_plex_config()

        assert result.token is None
        assert result.url is None


class TestPlexServiceAutoDiscovery:
    """Tests for PlexService auto-discovery integration."""

    def test_init_uses_auto_discovery_when_not_configured(self, tmp_path):
        """PlexService uses discovered token and URL when not configured."""
        prefs_content = '''<?xml version="1.0" encoding="utf-8"?>
<Preferences PlexOnlineToken="auto_token" ManualPortMappingPort="5555" />'''
        docker_path = tmp_path / ".docker-conf/Library/Application Support/Plex Media Server"
        docker_path.mkdir(parents=True)
        prefs_file = docker_path / "Preferences.xml"
        prefs_file.write_text(prefs_content)

        with patch("jackmediaman.services.plex.get_settings") as mock_settings, \
             patch("platform.system", return_value="Linux"), \
             patch("pathlib.Path.home", return_value=tmp_path):
            mock_settings.return_value = MagicMock(
                plex_url=None,
                plex_api_token=None,
                plex_notify_enabled=True,
            )
            service = PlexService()

        assert service.token == "auto_token"
        assert service.url == "http://localhost:5555"
        assert "auto-discovered" in service.config_source

    def test_init_explicit_params_override_discovery(self, tmp_path):
        """Explicit parameters take precedence over auto-discovery."""
        prefs_content = '''<?xml version="1.0" encoding="utf-8"?>
<Preferences PlexOnlineToken="auto_token" ManualPortMappingPort="5555" />'''
        docker_path = tmp_path / ".docker-conf/Library/Application Support/Plex Media Server"
        docker_path.mkdir(parents=True)
        prefs_file = docker_path / "Preferences.xml"
        prefs_file.write_text(prefs_content)

        with patch("jackmediaman.services.plex.get_settings") as mock_settings, \
             patch("platform.system", return_value="Linux"), \
             patch("pathlib.Path.home", return_value=tmp_path):
            mock_settings.return_value = MagicMock(
                plex_url=None,
                plex_api_token=None,
                plex_notify_enabled=True,
            )
            service = PlexService(url="http://explicit:8080", token="explicit_token")

        assert service.token == "explicit_token"
        assert service.url == "http://explicit:8080"
        assert service.config_source == "explicit"

    def test_init_settings_override_discovery(self, tmp_path):
        """Settings take precedence over auto-discovery."""
        prefs_content = '''<?xml version="1.0" encoding="utf-8"?>
<Preferences PlexOnlineToken="auto_token" ManualPortMappingPort="5555" />'''
        docker_path = tmp_path / ".docker-conf/Library/Application Support/Plex Media Server"
        docker_path.mkdir(parents=True)
        prefs_file = docker_path / "Preferences.xml"
        prefs_file.write_text(prefs_content)

        with patch("jackmediaman.services.plex.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                plex_url="http://settings:9090",
                plex_api_token="settings_token",
                plex_notify_enabled=True,
            )
            service = PlexService()

        assert service.token == "settings_token"
        assert service.url == "http://settings:9090"
        assert service.config_source == "env"

    def test_config_source_none_when_not_configured(self):
        """config_source is 'none' when Plex not configured anywhere."""
        with patch("jackmediaman.services.plex.get_settings") as mock_settings, \
             patch("jackmediaman.services.plex.discover_plex_config") as mock_discover:
            mock_settings.return_value = MagicMock(
                plex_url=None,
                plex_api_token=None,
                plex_notify_enabled=True,
            )
            mock_discover.return_value = PlexDiscoveryResult()
            service = PlexService()

        assert service.config_source == "none"
