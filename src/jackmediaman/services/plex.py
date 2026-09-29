"""Plex notification service for media library updates."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import httpx

from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger

logger = get_logger("plex")


@dataclass
class PlexDiscoveryResult:
    """Result of Plex auto-discovery."""

    token: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None  # Path where config was found


def discover_plex_config() -> PlexDiscoveryResult:
    """
    Auto-discover Plex token and URL from local installation.

    Checks common Plex configuration locations for PlexOnlineToken and port.
    Returns PlexDiscoveryResult with token, url, and source path.
    """
    import platform

    system = platform.system()

    if system == "Linux":
        return _discover_plex_linux()
    elif system == "Darwin":  # macOS
        return _discover_plex_macos()
    elif system == "Windows":
        return _discover_plex_windows()

    return PlexDiscoveryResult()


def _discover_plex_linux() -> PlexDiscoveryResult:
    """Find Plex config from Linux installation."""
    candidates = []

    # Check PLEX_HOME env var first
    plex_home = os.environ.get("PLEX_HOME")
    if plex_home:
        candidates.append(
            Path(plex_home)
            / "Library/Application Support/Plex Media Server/Preferences.xml"
        )

    # Docker config (common for seedboxes/VPS)
    candidates.append(
        Path.home()
        / ".docker-conf/Library/Application Support/Plex Media Server/Preferences.xml"
    )

    # Standard system install
    candidates.append(
        Path(
            "/var/lib/plexmediaserver/Library/Application Support/Plex Media Server/Preferences.xml"
        )
    )

    # User install
    candidates.append(
        Path.home()
        / ".plex/Library/Application Support/Plex Media Server/Preferences.xml"
    )

    # Plex user home
    candidates.append(
        Path(
            "/home/plex/Library/Application Support/Plex Media Server/Preferences.xml"
        )
    )

    for prefs_path in candidates:
        if prefs_path.exists():
            result = _extract_plex_config(prefs_path)
            if result.token:
                return result

    return PlexDiscoveryResult()


def _discover_plex_macos() -> PlexDiscoveryResult:
    """Find Plex config from macOS installation."""
    candidates = [
        Path.home()
        / "Library/Application Support/Plex Media Server/Preferences.xml",
    ]

    for prefs_path in candidates:
        if prefs_path.exists():
            result = _extract_plex_config(prefs_path)
            if result.token:
                return result

    return PlexDiscoveryResult()


def _discover_plex_windows() -> PlexDiscoveryResult:
    """Find Plex config from Windows installation (registry)."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, r"Software\Plex, Inc.\Plex Media Server"
        )
        token, _ = winreg.QueryValueEx(key, "PlexOnlineToken")
        winreg.CloseKey(key)

        if token:
            return PlexDiscoveryResult(
                token=token,
                url="http://localhost:32400",
                source="Windows Registry",
            )
    except (ImportError, OSError, FileNotFoundError):
        pass

    return PlexDiscoveryResult()


def _extract_plex_config(path: Path) -> PlexDiscoveryResult:
    """Extract PlexOnlineToken and port from Preferences.xml."""
    result = PlexDiscoveryResult(source=str(path))

    try:
        content = path.read_text()

        # Extract token
        token_match = re.search(r'PlexOnlineToken="([^"]+)"', content)
        if token_match:
            result.token = token_match.group(1)

        # Extract port - try ManualPortMappingPort first, then customConnections
        port = 32400  # default
        port_match = re.search(r'ManualPortMappingPort="(\d+)"', content)
        if port_match:
            port = int(port_match.group(1))
        else:
            # Try customConnections (e.g., "http://host:5136")
            conn_match = re.search(r'customConnections="[^"]*:(\d+)"', content)
            if conn_match:
                port = int(conn_match.group(1))

        result.url = f"http://localhost:{port}"

    except (OSError, PermissionError):
        pass

    return result


@dataclass
class PlexLibrary:
    """Plex library section info."""

    key: str  # Section ID (e.g., "1", "2")
    title: str  # Library name (e.g., "Movies", "TV Shows")
    type: str  # "movie" or "show"
    locations: List[Path]  # Library paths


@dataclass
class PlexNotifyResult:
    """Result of Plex notification."""

    path: Path
    library: Optional[str]
    success: bool
    error: Optional[str] = None


class PlexService:
    """Interface with Plex server for library updates.

    Provides path-specific library scanning for fast updates when media
    files are added, renamed, or removed.
    """

    TIMEOUT = 10.0

    def __init__(self, url: Optional[str] = None, token: Optional[str] = None):
        """Initialize Plex service.

        Args:
            url: Plex server URL (uses settings if not provided)
            token: Plex API token (uses settings if not provided)

        Priority: explicit params > environment settings > auto-discovery
        """
        settings = get_settings()

        # Try auto-discovery if not fully configured via params or settings
        discovered = None
        if not (url and token) and not (settings.plex_url and settings.plex_api_token):
            discovered = discover_plex_config()

        self.url = (
            url
            or settings.plex_url
            or (discovered.url if discovered else None)
            or "http://localhost:32400"
        ).rstrip("/")
        self.token = (
            token or settings.plex_api_token or (discovered.token if discovered else None)
        )

        self._libraries: Optional[List[PlexLibrary]] = None
        self._enabled = settings.plex_notify_enabled
        self._config_source = self._determine_config_source(
            url, token, settings, discovered
        )

    def _determine_config_source(
        self,
        explicit_url: Optional[str],
        explicit_token: Optional[str],
        settings,
        discovered: Optional[PlexDiscoveryResult],
    ) -> str:
        """Track where the config came from for status display."""
        if explicit_url or explicit_token:
            return "explicit"
        elif settings.plex_url or settings.plex_api_token:
            return "env"
        elif discovered and discovered.token:
            return f"auto-discovered ({discovered.source})"
        return "none"

    @property
    def config_source(self) -> str:
        """Return how the config was obtained."""
        return self._config_source

    @property
    def is_configured(self) -> bool:
        """Check if Plex is configured and enabled."""
        return bool(self.url and self.token and self._enabled)

    def _request(
        self, endpoint: str, params: Optional[dict] = None
    ) -> Optional[httpx.Response]:
        """Make Plex API request.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters

        Returns:
            Response object if successful, None otherwise
        """
        if not self.url or not self.token:
            return None

        headers = {
            "X-Plex-Token": self.token,
            "Accept": "application/json",
        }

        try:
            response = httpx.get(
                f"{self.url}{endpoint}",
                headers=headers,
                params=params,
                timeout=self.TIMEOUT,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPError:
            return None

    def get_libraries(self) -> List[PlexLibrary]:
        """Get all Plex library sections.

        Returns:
            List of PlexLibrary objects with section info
        """
        if self._libraries is not None:
            return self._libraries

        response = self._request("/library/sections")
        if not response:
            return []

        libraries = []
        try:
            data = response.json()
            for section in data.get("MediaContainer", {}).get("Directory", []):
                locations = [
                    Path(loc["path"]) for loc in section.get("Location", [])
                ]
                libraries.append(
                    PlexLibrary(
                        key=section["key"],
                        title=section["title"],
                        type=section["type"],
                        locations=locations,
                    )
                )
        except (KeyError, ValueError):
            return []

        self._libraries = libraries
        return libraries

    def find_library_for_path(self, path: Path) -> Optional[PlexLibrary]:
        """Find which Plex library contains a given path.

        Args:
            path: File or directory path to check

        Returns:
            PlexLibrary if path is in a library, None otherwise
        """
        try:
            path = path.resolve()
        except (OSError, ValueError):
            return None

        for library in self.get_libraries():
            for location in library.locations:
                try:
                    path.relative_to(location)
                    return library
                except ValueError:
                    continue
        return None

    def scan_path(self, path: Path) -> PlexNotifyResult:
        """Trigger Plex to scan a specific path.

        Uses Plex's path-specific refresh which only scans the given
        subdirectory rather than the entire library.

        Args:
            path: Path to scan (file or directory)

        Returns:
            PlexNotifyResult with success status
        """
        library = self.find_library_for_path(path)

        if not library:
            return PlexNotifyResult(
                path=path,
                library=None,
                success=False,
                error="Path not in any Plex library",
            )

        # Use parent directory for single files
        scan_path = path if path.is_dir() else path.parent

        response = self._request(
            f"/library/sections/{library.key}/refresh",
            params={"path": str(scan_path)},
        )

        return PlexNotifyResult(
            path=path,
            library=library.title,
            success=response is not None,
            error=None if response else "Failed to trigger scan",
        )

    def scan_library(self, library_key: str) -> bool:
        """Trigger full library scan.

        Args:
            library_key: Library section key (e.g., "1")

        Returns:
            True if scan was triggered successfully
        """
        response = self._request(f"/library/sections/{library_key}/refresh")
        return response is not None

    def notify_paths(self, paths: List[Path]) -> List[PlexNotifyResult]:
        """Notify Plex about multiple paths (batched by library).

        Groups paths by their parent directories and libraries to
        minimize the number of API calls.

        Args:
            paths: List of file/directory paths to scan

        Returns:
            List of PlexNotifyResult for each unique scan
        """
        if not self.is_configured:
            return [
                PlexNotifyResult(
                    path=p,
                    library=None,
                    success=False,
                    error="Plex not configured",
                )
                for p in paths
            ]

        # Group paths by library to minimize API calls
        library_paths: dict[str, set[Path]] = {}
        results: List[PlexNotifyResult] = []

        for path in paths:
            library = self.find_library_for_path(path)
            if library:
                if library.key not in library_paths:
                    library_paths[library.key] = set()
                # Use parent folder to batch
                scan_path = path if path.is_dir() else path.parent
                library_paths[library.key].add(scan_path)
            else:
                results.append(
                    PlexNotifyResult(
                        path=path,
                        library=None,
                        success=False,
                        error="Path not in any Plex library",
                    )
                )

        # Scan each unique path
        for library_key, scan_paths in library_paths.items():
            for scan_path in scan_paths:
                result = self.scan_path(scan_path)
                results.append(result)

        return results

    def notify_rename(self, old_path: Path, new_path: Path) -> List[PlexNotifyResult]:
        """Notify Plex about a file rename.

        Scans both the old location (to remove stale entry) and new location
        (to add the new entry).

        Args:
            old_path: Original file path
            new_path: New file path after rename

        Returns:
            List of PlexNotifyResult for each scan
        """
        paths_to_scan: set[Path] = set()
        results: List[PlexNotifyResult] = []

        # Old path - check if in Plex library
        if self.find_library_for_path(old_path):
            paths_to_scan.add(old_path.parent if old_path.is_file() else old_path)

        # New path - check if in Plex library
        if self.find_library_for_path(new_path):
            paths_to_scan.add(new_path.parent if new_path.is_file() else new_path)

        # Trigger scans
        for path in paths_to_scan:
            result = self.scan_path(path)
            results.append(result)

        return results

    def notify_removal(self, path: Path) -> Optional[PlexNotifyResult]:
        """Notify Plex that a file was removed.

        Args:
            path: Path that was removed

        Returns:
            PlexNotifyResult if path was in a Plex library, None otherwise
        """
        if not self.find_library_for_path(path):
            return None

        scan_path = path.parent if path.is_file() else path
        return self.scan_path(scan_path)
