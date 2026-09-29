"""Symlink target protector - protects files that are targets of symlinks in the scan."""

from pathlib import Path
from typing import List

from jackmediaman.models.media import MediaItem


class SymlinkTargetProtector:
    """Protect files that are targets of symlinks in the same scan.

    If a symlink in the library points to another file in the library,
    the target file should be protected from deletion to avoid breaking
    the symlink.
    """

    name = "symlink_target"
    description = "Protect files that symlinks point to"

    def check(self, item: MediaItem, symlink_targets: set) -> bool:
        """Check if an item should be protected.

        Args:
            item: Media item to check
            symlink_targets: Set of resolved paths that symlinks point to

        Returns:
            True if item should be protected, False otherwise
        """
        if item.is_symlink:
            return False

        try:
            return item.path.resolve() in symlink_targets
        except (OSError, ValueError):
            return False

    def get_reason(self, item: MediaItem) -> str:
        """Get the protection reason for an item."""
        return "Target of symlink in library"

    def protect(self, items: List[MediaItem]) -> int:
        """Mark protected items in a list.

        First builds a set of all symlink targets, then protects any
        real file that is a target.

        Args:
            items: List of media items to check

        Returns:
            Number of items marked as protected
        """
        # Build set of all symlink targets
        symlink_targets = set()
        for item in items:
            if item.is_symlink and item.symlink_target:
                try:
                    symlink_targets.add(item.symlink_target.resolve())
                except (OSError, ValueError):
                    pass

        # Protect any real file that is a symlink target
        protected_count = 0
        for item in items:
            if self.check(item, symlink_targets):
                item.is_protected = True
                item.protection_reason = self.get_reason(item)
                protected_count += 1

        return protected_count
