"""Duplicate group model for tracking duplicate media items."""

from dataclasses import dataclass, field
from typing import List, Optional

from jackmediaman.models.media import MediaItem


@dataclass
class DuplicateGroup:
    """A group of media items that are duplicates of each other."""

    identity_key: str
    items: List[MediaItem] = field(default_factory=list)

    @property
    def has_duplicates(self) -> bool:
        """Return True if group has more than one item."""
        return len(self.items) > 1

    @property
    def count(self) -> int:
        """Return number of items in the group."""
        return len(self.items)

    @property
    def best_quality(self) -> Optional[MediaItem]:
        """Return the highest quality item in the group.

        When quality scores are equal, prefers protected files (symlinks to
        seeding torrents) since they cannot be safely removed.
        """
        if not self.items:
            return None
        # Sort by (quality_score, is_protected) - protected wins ties
        return max(self.items, key=lambda x: (x.quality.score, x.is_protected))

    @property
    def protected_items(self) -> List[MediaItem]:
        """Return items that cannot be removed."""
        return [item for item in self.items if item.is_protected]

    @property
    def removable_items(self) -> List[MediaItem]:
        """Return items that can be safely removed."""
        best = self.best_quality
        return [item for item in self.items if item != best and not item.is_protected]

    @property
    def removable_size_bytes(self) -> int:
        """Return total size of removable items in bytes."""
        return sum(item.size_bytes for item in self.removable_items)

    @property
    def display_name(self) -> str:
        """Return display name for the group."""
        if self.items:
            return self.items[0].display_name
        return self.identity_key

    def add(self, item: MediaItem) -> None:
        """Add an item to the group if not already present."""
        if item not in self.items:
            self.items.append(item)

    def sort_by_quality(self) -> None:
        """Sort items by quality, highest first."""
        self.items.sort(key=lambda x: x.quality.score, reverse=True)

    def get_action(self, item: MediaItem) -> str:
        """Get the action for a specific item."""
        if item == self.best_quality:
            return "KEEP"
        elif item.is_protected:
            return "PROTECTED"
        elif item.is_symlink:
            return "REMOVE (symlink)"
        else:
            return "REMOVE"
