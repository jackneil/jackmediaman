"""Symlink protector - protects files that are symlinks to torrent directory."""

from pathlib import Path
from typing import List

from jackmediaman.models.media import MediaItem
from jackmediaman.core.config import get_settings


class SymlinkProtector:
    """Protect files that are symlinks pointing to the torrent directory."""

    name = "symlink"
    description = "Protect files that are symlinks to the torrent directory"

    def __init__(self, torrent_dir: Path | None = None):
        """
        Initialize the protector.

        Args:
            torrent_dir: Path to torrent directory (defaults to settings)
        """
        settings = get_settings()
        self.torrent_dir = (torrent_dir or settings.torrent_dir).resolve()

    def check(self, item: MediaItem) -> bool:
        """
        Check if an item should be protected.

        Args:
            item: Media item to check

        Returns:
            True if item should be protected, False otherwise
        """
        if not item.is_symlink or not item.symlink_target:
            return False

        try:
            target = item.symlink_target.resolve()
            # Check if symlink points to torrent directory
            return str(target).startswith(str(self.torrent_dir))
        except (OSError, ValueError):
            return False

    def get_reason(self, item: MediaItem) -> str:
        """Get the protection reason for an item."""
        return f"Symlink to torrent directory: {item.symlink_target}"

    def protect(self, items: List[MediaItem]) -> int:
        """
        Mark protected items in a list.

        Args:
            items: List of media items to check

        Returns:
            Number of items marked as protected
        """
        protected_count = 0
        for item in items:
            if self.check(item):
                item.is_protected = True
                item.protection_reason = self.get_reason(item)
                protected_count += 1
        return protected_count
