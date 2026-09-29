"""Duplicate finder service - orchestrates scanning, matching, and protection."""

from pathlib import Path
from typing import Iterator, List, Optional, Protocol

from jackmediaman.models.media import MediaItem
from jackmediaman.models.duplicates import DuplicateGroup


class Scanner(Protocol):
    """Protocol for media scanners."""

    def scan(self, root: Path) -> Iterator[MediaItem]:
        """Scan directory and yield media items."""
        ...


class Matcher(Protocol):
    """Protocol for duplicate matchers."""

    def match(self, items: List[MediaItem]) -> List[DuplicateGroup]:
        """Group items into duplicate sets."""
        ...


class Protector(Protocol):
    """Protocol for file protectors."""

    def protect(self, items: List[MediaItem]) -> int:
        """Mark protected items. Returns count of protected items."""
        ...


class DuplicateFinder:
    """Orchestrates scanning, matching, and protection analysis."""

    def __init__(
        self,
        scanner: Scanner,
        matcher: Matcher,
        protectors: Optional[List[Protector]] = None,
    ):
        """
        Initialize the duplicate finder.

        Args:
            scanner: Scanner to find media files
            matcher: Matcher to identify duplicates
            protectors: List of protectors to check for protected files
        """
        self.scanner = scanner
        self.matcher = matcher
        self.protectors = protectors or []

    def find(
        self,
        root: Path,
        progress_callback: Optional[callable] = None,
    ) -> List[DuplicateGroup]:
        """
        Find duplicate media items in a directory.

        Args:
            root: Root directory to scan
            progress_callback: Optional callback(phase, current, total, info)

        Returns:
            List of duplicate groups found
        """
        # Phase 1: Scan for media items
        if progress_callback:
            progress_callback("scan", 0, 0, "Scanning...")

        items = list(self.scanner.scan(root))

        if progress_callback:
            progress_callback("scan", len(items), len(items), f"Found {len(items)} files")

        if not items:
            return []

        # Phase 2: Mark protected items
        if progress_callback:
            progress_callback("protect", 0, len(self.protectors), "Checking protection...")

        for i, protector in enumerate(self.protectors):
            protector.protect(items)
            if progress_callback:
                progress_callback("protect", i + 1, len(self.protectors), protector.name)

        # Phase 3: Find duplicates
        if progress_callback:
            progress_callback("match", 0, 0, "Finding duplicates...")

        groups = self.matcher.match(items)

        if progress_callback:
            progress_callback("match", len(groups), len(groups), f"Found {len(groups)} groups")

        return groups

    def find_all(
        self,
        roots: List[Path],
        progress_callback: Optional[callable] = None,
    ) -> List[DuplicateGroup]:
        """
        Find duplicates across multiple directories.

        Args:
            roots: List of root directories to scan
            progress_callback: Optional callback

        Returns:
            Combined list of duplicate groups
        """
        all_items = []

        for root in roots:
            items = list(self.scanner.scan(root))
            all_items.extend(items)

        if not all_items:
            return []

        # Mark protected items
        for protector in self.protectors:
            protector.protect(all_items)

        # Find duplicates
        return self.matcher.match(all_items)
