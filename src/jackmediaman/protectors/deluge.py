"""Deluge protector - protects files that are actively seeding in Deluge."""

from pathlib import Path
from typing import List, Optional, Set

from jackmediaman.models.media import MediaItem
from jackmediaman.core.config import get_settings


class DelugeProtector:
    """Protect files that are actively seeding in Deluge.

    Uses deluge-client for synchronous RPC communication.
    """

    name = "deluge"
    description = "Protect files that are actively seeding in Deluge"

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize the protector.

        Args:
            host: Deluge daemon host (defaults to settings)
            port: Deluge daemon port (defaults to settings)
            username: Deluge daemon username (defaults to settings)
            password: Deluge daemon password (defaults to settings)
        """
        settings = get_settings()
        self.host = host or settings.deluge_host
        self.port = port or settings.deluge_port
        self.username = username or settings.deluge_username or ""
        self.password = password or settings.deluge_password or ""
        self._seeding_files: Optional[Set[Path]] = None
        self._connected = False

    def connect(self) -> bool:
        """
        Connect to Deluge daemon and fetch seeding files.

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            from jackmediaman.services.deluge_client import create_deluge_client

            client = create_deluge_client(
                self.host, self.port, self.username, self.password
            )
            client.connect()

            # Get all torrents with state and files
            torrents = client.call(
                "core.get_torrents_status", {}, ["state", "save_path", "files"]
            )

            # Extract seeding files
            seeding_files: Set[Path] = set()
            for torrent_id, info in torrents.items():
                # Handle bytes keys
                state = info.get(b"state", info.get("state", b""))
                if isinstance(state, bytes):
                    state = state.decode("utf-8")

                if state.lower() != "seeding":
                    continue

                save_path = info.get(b"save_path", info.get("save_path", b""))
                if isinstance(save_path, bytes):
                    save_path = save_path.decode("utf-8")

                files = info.get(b"files", info.get("files", []))
                for file_info in files:
                    file_path = file_info.get(b"path", file_info.get("path", b""))
                    if isinstance(file_path, bytes):
                        file_path = file_path.decode("utf-8")
                    if file_path:
                        full_path = Path(save_path) / file_path
                        seeding_files.add(full_path.resolve())

            self._seeding_files = seeding_files
            self._connected = True
            client.disconnect()
            return True

        except Exception:
            return False

    def disconnect(self) -> None:
        """Disconnect from Deluge daemon."""
        self._connected = False

    def check(self, item: MediaItem) -> bool:
        """
        Check if an item should be protected.

        Args:
            item: Media item to check

        Returns:
            True if item should be protected, False otherwise
        """
        if self._seeding_files is None:
            return False

        # Check both the file path and symlink target
        paths_to_check = [item.path.resolve()]
        if item.symlink_target:
            paths_to_check.append(item.symlink_target.resolve())

        for path in paths_to_check:
            if path in self._seeding_files:
                return True

        return False

    def get_reason(self, item: MediaItem) -> str:
        """Get the protection reason for an item."""
        return "Actively seeding in Deluge"

    def protect(self, items: List[MediaItem]) -> int:
        """
        Mark protected items in a list.

        Args:
            items: List of media items to check

        Returns:
            Number of items marked as protected
        """
        if not self._connected:
            if not self.connect():
                return 0

        protected_count = 0
        for item in items:
            if self.check(item):
                item.is_protected = True
                item.protection_reason = self.get_reason(item)
                protected_count += 1

        return protected_count
