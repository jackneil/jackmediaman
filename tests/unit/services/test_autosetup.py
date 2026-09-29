"""Tests for AutoSetupService."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jackmediaman.services.autosetup import AutoSetupResult, AutoSetupService


class TestAutoSetupResult:
    """Tests for AutoSetupResult dataclass."""

    def test_default_values(self):
        """Result has sensible defaults."""
        result = AutoSetupResult()
        assert result.ran is False
        assert result.plex_discovered is False
        assert result.plex_url is None
        assert result.movies_dir is None
        assert result.tv_dir is None
        assert result.deluge_configured is False
        assert result.deluge_already_exists is False
        assert result.settings_written == []
        assert result.errors == []

    def test_can_set_values(self):
        """Result fields can be set."""
        result = AutoSetupResult(
            ran=True,
            plex_discovered=True,
            plex_url="http://localhost:5136",
            movies_dir=Path("/media/Movies"),
            tv_dir=Path("/media/TV Shows"),
        )
        assert result.ran is True
        assert result.plex_discovered is True
        assert result.plex_url == "http://localhost:5136"
        assert result.movies_dir == Path("/media/Movies")
        assert result.tv_dir == Path("/media/TV Shows")


class TestAutoSetupServicePlexDiscovery:
    """Tests for Plex auto-discovery."""

    def test_discovers_plex_token_and_url(self, tmp_path):
        """Discovers Plex token and URL from Preferences.xml."""
        from jackmediaman.services.plex import PlexDiscoveryResult, PlexLibrary

        mock_discovery = PlexDiscoveryResult(
            token="test_token",
            url="http://localhost:5136",
            source="/path/to/Preferences.xml",
        )
        mock_libraries = [
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
                locations=[Path("/media/TV Shows")],
            ),
        ]

        with patch("jackmediaman.services.plex.discover_plex_config") as mock_discover, \
             patch("jackmediaman.services.plex.PlexService") as mock_plex_service, \
             patch("jackmediaman.core.config.save_setting"), \
             patch("jackmediaman.core.config.reload_settings"):
            mock_discover.return_value = mock_discovery
            mock_plex_service.return_value.get_libraries.return_value = mock_libraries

            service = AutoSetupService()
            result = service.run(skip_deluge=True)

        assert result.ran is True
        assert result.plex_discovered is True
        assert result.plex_url == "http://localhost:5136"
        assert result.plex_token_found is True
        assert result.movies_dir == Path("/media/Movies")
        assert result.tv_dir == Path("/media/TV Shows")

    def test_skips_when_no_plex_found(self):
        """Gracefully handles missing Plex installation."""
        from jackmediaman.services.plex import PlexDiscoveryResult

        with patch("jackmediaman.services.plex.discover_plex_config") as mock_discover, \
             patch("jackmediaman.core.config.save_setting"), \
             patch("jackmediaman.core.config.reload_settings"):
            mock_discover.return_value = PlexDiscoveryResult()  # No token

            service = AutoSetupService()
            result = service.run(skip_deluge=True)

        assert result.ran is True
        assert result.plex_discovered is False
        assert result.plex_url is None
        assert result.movies_dir is None
        assert result.tv_dir is None

    def test_handles_plex_discovery_error(self):
        """Logs error but continues when Plex discovery fails."""
        with patch("jackmediaman.services.plex.discover_plex_config") as mock_discover, \
             patch("jackmediaman.core.config.save_setting"), \
             patch("jackmediaman.core.config.reload_settings"):
            mock_discover.side_effect = Exception("Connection failed")

            service = AutoSetupService()
            result = service.run(skip_deluge=True)

        assert result.ran is True
        assert result.plex_discovered is False
        assert len(result.errors) == 1
        assert "Plex discovery" in result.errors[0]


class TestAutoSetupServiceDeluge:
    """Tests for Deluge auto-configuration."""

    def test_configures_deluge_execute_plugin(self):
        """Configures Deluge Execute plugin."""
        from jackmediaman.services.deluge_setup import ExecuteSetupResult
        from jackmediaman.services.plex import PlexDiscoveryResult

        mock_deluge_result = ExecuteSetupResult(
            success=True,
            plugin_enabled=False,
            command_added=True,
            existing_command=False,
        )

        with patch("jackmediaman.services.plex.discover_plex_config") as mock_plex, \
             patch("jackmediaman.services.deluge_setup.DelugeExecuteSetup") as mock_deluge, \
             patch("jackmediaman.core.config.get_settings") as mock_settings, \
             patch("jackmediaman.core.config.save_setting"), \
             patch("jackmediaman.core.config.reload_settings"):
            mock_plex.return_value = PlexDiscoveryResult()
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
                process_default_action="symlink",
            )
            mock_deluge.return_value.setup_execute_plugin.return_value = mock_deluge_result

            service = AutoSetupService()
            result = service.run()

        assert result.deluge_configured is True
        assert result.deluge_already_exists is False
        mock_deluge.return_value.create_hook_script.assert_called_once()
        mock_deluge.return_value.setup_execute_plugin.assert_called_once()

    def test_detects_existing_deluge_hook(self):
        """Detects when Deluge hook already exists."""
        from jackmediaman.services.deluge_setup import ExecuteSetupResult
        from jackmediaman.services.plex import PlexDiscoveryResult

        mock_deluge_result = ExecuteSetupResult(
            success=True,
            plugin_enabled=False,
            command_added=False,
            existing_command=True,
        )

        with patch("jackmediaman.services.plex.discover_plex_config") as mock_plex, \
             patch("jackmediaman.services.deluge_setup.DelugeExecuteSetup") as mock_deluge, \
             patch("jackmediaman.core.config.get_settings") as mock_settings, \
             patch("jackmediaman.core.config.save_setting"), \
             patch("jackmediaman.core.config.reload_settings"):
            mock_plex.return_value = PlexDiscoveryResult()
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
                process_default_action="symlink",
            )
            mock_deluge.return_value.setup_execute_plugin.return_value = mock_deluge_result

            service = AutoSetupService()
            result = service.run()

        assert result.deluge_configured is True
        assert result.deluge_already_exists is True

    def test_skips_deluge_when_requested(self):
        """Skips Deluge setup when skip_deluge=True."""
        from jackmediaman.services.plex import PlexDiscoveryResult

        with patch("jackmediaman.services.plex.discover_plex_config") as mock_plex, \
             patch("jackmediaman.core.config.save_setting"), \
             patch("jackmediaman.core.config.reload_settings"):
            mock_plex.return_value = PlexDiscoveryResult()

            service = AutoSetupService()
            result = service.run(skip_deluge=True)

        assert result.deluge_configured is False

    def test_handles_deluge_setup_error(self):
        """Gracefully handles Deluge setup errors."""
        from jackmediaman.services.plex import PlexDiscoveryResult

        with patch("jackmediaman.services.plex.discover_plex_config") as mock_plex, \
             patch("jackmediaman.services.deluge_setup.DelugeExecuteSetup") as mock_deluge, \
             patch("jackmediaman.core.config.get_settings") as mock_settings, \
             patch("jackmediaman.core.config.save_setting"), \
             patch("jackmediaman.core.config.reload_settings"):
            mock_plex.return_value = PlexDiscoveryResult()
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
                process_default_action="symlink",
            )
            mock_deluge.side_effect = Exception("Deluge not running")

            service = AutoSetupService()
            result = service.run()

        assert result.deluge_configured is False
        assert any("Deluge setup" in e for e in result.errors)


class TestAutoSetupServiceConfig:
    """Tests for configuration writing."""

    def test_writes_discovered_settings(self):
        """Writes discovered values to config file."""
        from jackmediaman.services.plex import PlexDiscoveryResult, PlexLibrary

        mock_discovery = PlexDiscoveryResult(
            token="test_token",
            url="http://localhost:5136",
            source="/path/to/Preferences.xml",
        )
        mock_libraries = [
            PlexLibrary(key="1", title="Movies", type="movie", locations=[Path("/media/Movies")]),
            PlexLibrary(key="2", title="TV", type="show", locations=[Path("/media/TV")]),
        ]

        saved_settings = {}

        def mock_save(key, value):
            saved_settings[key] = value

        # Patch at the module where the import happens (autosetup.py)
        with patch("jackmediaman.services.plex.discover_plex_config") as mock_plex, \
             patch("jackmediaman.services.plex.PlexService") as mock_service, \
             patch("jackmediaman.services.autosetup.save_setting", side_effect=mock_save), \
             patch("jackmediaman.services.autosetup.reload_settings"):
            mock_plex.return_value = mock_discovery
            mock_service.return_value.get_libraries.return_value = mock_libraries

            service = AutoSetupService()
            result = service.run(skip_deluge=True)

        assert "JMM_PLEX_URL" in saved_settings
        assert saved_settings["JMM_PLEX_URL"] == "http://localhost:5136"
        assert "JMM_PLEX_NOTIFY_ENABLED" in saved_settings
        assert saved_settings["JMM_PLEX_NOTIFY_ENABLED"] == "true"
        assert "JMM_MOVIES_DIR" in saved_settings
        assert saved_settings["JMM_MOVIES_DIR"] == "/media/Movies"
        assert "JMM_TV_DIR" in saved_settings
        assert saved_settings["JMM_TV_DIR"] == "/media/TV"

        assert "JMM_PLEX_URL" in result.settings_written
        assert "JMM_MOVIES_DIR" in result.settings_written
        assert "JMM_TV_DIR" in result.settings_written

    def test_handles_config_write_error(self):
        """Logs error but continues when config write fails."""
        from jackmediaman.services.plex import PlexDiscoveryResult

        mock_discovery = PlexDiscoveryResult(
            token="test_token",
            url="http://localhost:5136",
            source="/path/to/Preferences.xml",
        )

        # Patch at the module where the import happens (autosetup.py)
        with patch("jackmediaman.services.plex.discover_plex_config") as mock_plex, \
             patch("jackmediaman.services.plex.PlexService") as mock_service, \
             patch("jackmediaman.services.autosetup.save_setting", side_effect=Exception("Write failed")), \
             patch("jackmediaman.services.autosetup.reload_settings"):
            mock_plex.return_value = mock_discovery
            mock_service.return_value.get_libraries.return_value = []

            service = AutoSetupService()
            result = service.run(skip_deluge=True)

        assert result.ran is True
        assert any("Config write" in e for e in result.errors)


class TestAutoSetupServiceIntegration:
    """Integration-style tests for full auto-setup flow."""

    def test_full_auto_setup_with_plex_and_deluge(self):
        """Full auto-setup discovers Plex and configures Deluge."""
        from jackmediaman.services.deluge_setup import ExecuteSetupResult
        from jackmediaman.services.plex import PlexDiscoveryResult, PlexLibrary

        mock_plex_discovery = PlexDiscoveryResult(
            token="plex_token",
            url="http://localhost:32400",
            source="/var/lib/plex/Preferences.xml",
        )
        mock_libraries = [
            PlexLibrary(key="1", title="Movies", type="movie", locations=[Path("/media/Movies")]),
        ]
        mock_deluge_result = ExecuteSetupResult(
            success=True,
            plugin_enabled=True,
            command_added=True,
            existing_command=False,
        )

        with patch("jackmediaman.services.plex.discover_plex_config") as mock_plex, \
             patch("jackmediaman.services.plex.PlexService") as mock_plex_service, \
             patch("jackmediaman.services.deluge_setup.DelugeExecuteSetup") as mock_deluge, \
             patch("jackmediaman.core.config.get_settings") as mock_settings, \
             patch("jackmediaman.core.config.save_setting"), \
             patch("jackmediaman.core.config.reload_settings"):
            mock_plex.return_value = mock_plex_discovery
            mock_plex_service.return_value.get_libraries.return_value = mock_libraries
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
                process_default_action="symlink",
            )
            mock_deluge.return_value.setup_execute_plugin.return_value = mock_deluge_result

            service = AutoSetupService()
            result = service.run()

        assert result.ran is True
        assert result.plex_discovered is True
        assert result.plex_url == "http://localhost:32400"
        assert result.movies_dir == Path("/media/Movies")
        assert result.deluge_configured is True
        assert len(result.errors) == 0
