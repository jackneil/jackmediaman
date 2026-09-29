"""Auto-setup service for zero-config installation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from jackmediaman.core.config import get_settings, reload_settings, save_setting


@dataclass
class AutoSetupResult:
    """Result of auto-setup operation."""

    # Overall status
    ran: bool = False

    # Plex discovery
    plex_discovered: bool = False
    plex_url: Optional[str] = None
    plex_token_found: bool = False
    movies_dir: Optional[Path] = None
    tv_dir: Optional[Path] = None
    plex_source: Optional[str] = None

    # Deluge setup
    deluge_configured: bool = False
    deluge_already_exists: bool = False
    deluge_error: Optional[str] = None

    # Config file
    settings_written: List[str] = field(default_factory=list)

    # Errors (non-fatal)
    errors: List[str] = field(default_factory=list)


class AutoSetupService:
    """Handles zero-config auto-setup.

    Discovers Plex (token, URL, library paths) and configures Deluge Execute
    plugin silently. All errors are caught and logged but never block execution.
    """

    def run(self, skip_deluge: bool = False) -> AutoSetupResult:
        """Execute auto-setup: discover Plex, configure Deluge, write config.

        Args:
            skip_deluge: If True, skip Deluge Execute plugin configuration

        Returns:
            AutoSetupResult with status of all operations
        """
        result = AutoSetupResult(ran=True)

        # Phase 1: Discover Plex and extract library paths
        self._discover_plex(result)

        # Phase 2: Configure Deluge Execute plugin (check for duplicates first)
        if not skip_deluge:
            self._configure_deluge(result)

        # Phase 3: Write discovered values to config
        self._write_config(result)

        return result

    def _discover_plex(self, result: AutoSetupResult) -> None:
        """Discover Plex and extract movie/TV library paths."""
        try:
            from jackmediaman.services.plex import PlexService, discover_plex_config

            discovered = discover_plex_config()

            if not discovered.token:
                return

            result.plex_discovered = True
            result.plex_url = discovered.url
            result.plex_token_found = True
            result.plex_source = discovered.source

            # Get libraries and extract paths
            # Use discovered URL/token directly to avoid settings interference
            service = PlexService(url=discovered.url, token=discovered.token)
            libraries = service.get_libraries()

            for lib in libraries:
                # lib.type is "movie" or "show"
                # lib.locations is List[Path]
                if lib.type == "movie" and lib.locations and not result.movies_dir:
                    result.movies_dir = lib.locations[0]
                elif lib.type == "show" and lib.locations and not result.tv_dir:
                    result.tv_dir = lib.locations[0]

        except Exception as e:
            result.errors.append(f"Plex discovery: {e}")

    def _configure_deluge(self, result: AutoSetupResult) -> None:
        """Configure Deluge Execute plugin (skip if already exists)."""
        try:
            from jackmediaman.services.deluge_setup import DelugeExecuteSetup

            settings = get_settings()
            action = settings.process_default_action or "symlink"

            # Create setup with current settings (defaults to localhost:58846)
            setup = DelugeExecuteSetup(
                host=settings.deluge_host,
                port=settings.deluge_port,
                username=settings.deluge_username,
                password=settings.deluge_password,
                action=action,
            )

            # Create the hook script first
            setup.create_hook_script()

            # Configure Execute plugin
            setup_result = setup.setup_execute_plugin()

            if setup_result.existing_command:
                result.deluge_already_exists = True
                result.deluge_configured = True
            elif setup_result.success:
                result.deluge_configured = True
            else:
                result.deluge_error = setup_result.error

        except ImportError:
            # Deluge library not installed - skip silently
            result.errors.append("Deluge library not installed")
        except Exception as e:
            result.errors.append(f"Deluge setup: {e}")

    def _write_config(self, result: AutoSetupResult) -> None:
        """Write discovered values to config file."""
        try:
            # Plex settings
            if result.plex_url:
                save_setting("JMM_PLEX_URL", result.plex_url)
                result.settings_written.append("JMM_PLEX_URL")

            if result.plex_token_found:
                # Don't save the actual token for security - let PlexService use auto-discovery
                save_setting("JMM_PLEX_NOTIFY_ENABLED", "true")
                result.settings_written.append("JMM_PLEX_NOTIFY_ENABLED")

            # Library paths from Plex
            if result.movies_dir:
                save_setting("JMM_MOVIES_DIR", str(result.movies_dir))
                result.settings_written.append("JMM_MOVIES_DIR")

            if result.tv_dir:
                save_setting("JMM_TV_DIR", str(result.tv_dir))
                result.settings_written.append("JMM_TV_DIR")

            # Reload settings to pick up changes
            if result.settings_written:
                reload_settings()

        except Exception as e:
            result.errors.append(f"Config write: {e}")
