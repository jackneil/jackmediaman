"""Cleanup service for moving duplicate files to trash."""

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from jackmediaman.models.media import MediaItem
from jackmediaman.models.duplicates import DuplicateGroup
from jackmediaman.core.config import get_settings
from jackmediaman.core.exceptions import CleanupError


@dataclass
class CleanupResult:
    """Result of a cleanup operation."""

    item: MediaItem
    destination: Path
    success: bool
    error: Optional[str] = None


@dataclass
class CleanupSummary:
    """Summary of cleanup operations."""

    total_groups: int
    total_files_removed: int
    total_bytes_freed: int
    results: List[CleanupResult]

    @property
    def total_gb_freed(self) -> float:
        """Return total space freed in GB."""
        return self.total_bytes_freed / (1024 * 1024 * 1024)


class CleanupService:
    """Service for cleaning up duplicate files."""

    def __init__(self, trash_dir: Optional[Path] = None):
        """
        Initialize the cleanup service.

        Args:
            trash_dir: Directory to move duplicates to (defaults to settings)
        """
        settings = get_settings()
        self.trash_dir = trash_dir or settings.trash_dir
        self._plex_service: Optional["PlexService"] = None

    def _get_plex_service(self) -> Optional["PlexService"]:
        """Lazy-load Plex service only if configured."""
        if self._plex_service is None:
            try:
                from jackmediaman.services.plex import PlexService

                service = PlexService()
                if service.is_configured:
                    self._plex_service = service
            except ImportError:
                pass
        return self._plex_service

    def _notify_plex_removal(self, path: Path) -> None:
        """Notify Plex that a file was removed."""
        plex = self._get_plex_service()
        if not plex:
            return

        # Use the service's notify_removal method
        plex.notify_removal(path)

    def prepare_trash(self) -> None:
        """Ensure trash directory exists."""
        self.trash_dir.mkdir(parents=True, exist_ok=True)

    def get_trash_path(self, item: MediaItem) -> Path:
        """Get the destination path in trash for an item."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.trash_dir / f"{timestamp}_{item.filename}"

    def move_to_trash(
        self,
        item: MediaItem,
        dry_run: bool = True,
    ) -> CleanupResult:
        """
        Move a file to the trash directory.

        Args:
            item: Media item to move
            dry_run: If True, don't actually move the file

        Returns:
            CleanupResult with success status
        """
        destination = self.get_trash_path(item)

        if dry_run:
            return CleanupResult(
                item=item,
                destination=destination,
                success=True,
            )

        try:
            original_path = item.path  # Save for Plex notification
            self.prepare_trash()
            shutil.move(str(item.path), str(destination))

            # Notify Plex about the removal
            self._notify_plex_removal(original_path)

            return CleanupResult(
                item=item,
                destination=destination,
                success=True,
            )
        except (shutil.Error, OSError) as e:
            return CleanupResult(
                item=item,
                destination=destination,
                success=False,
                error=str(e),
            )

    def cleanup_group(
        self,
        group: DuplicateGroup,
        dry_run: bool = True,
    ) -> List[CleanupResult]:
        """
        Clean up a duplicate group by moving removable items to trash.

        Args:
            group: Duplicate group to clean up
            dry_run: If True, don't actually move files

        Returns:
            List of cleanup results
        """
        results = []
        for item in group.removable_items:
            result = self.move_to_trash(item, dry_run=dry_run)
            results.append(result)
        return results

    def cleanup_groups(
        self,
        groups: List[DuplicateGroup],
        dry_run: bool = True,
        progress_callback: Optional[callable] = None,
    ) -> CleanupSummary:
        """
        Clean up multiple duplicate groups.

        Args:
            groups: List of duplicate groups to clean up
            dry_run: If True, don't actually move files
            progress_callback: Optional callback(current, total, group_name)

        Returns:
            CleanupSummary with results
        """
        all_results = []
        total_bytes = 0

        for i, group in enumerate(groups):
            if progress_callback:
                progress_callback(i + 1, len(groups), group.display_name)

            results = self.cleanup_group(group, dry_run=dry_run)
            all_results.extend(results)

            for result in results:
                if result.success:
                    total_bytes += result.item.size_bytes

        return CleanupSummary(
            total_groups=len(groups),
            total_files_removed=len([r for r in all_results if r.success]),
            total_bytes_freed=total_bytes,
            results=all_results,
        )

    def restore_from_trash(self, trash_path: Path, original_path: Path) -> bool:
        """
        Restore a file from trash to its original location.

        Args:
            trash_path: Path to file in trash
            original_path: Original file path

        Returns:
            True if restored successfully
        """
        try:
            # Ensure parent directory exists
            original_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(trash_path), str(original_path))
            return True
        except (shutil.Error, OSError):
            return False

    def list_trash(self) -> List[Tuple[Path, datetime]]:
        """
        List files in trash with their timestamps.

        Returns:
            List of (path, timestamp) tuples
        """
        if not self.trash_dir.exists():
            return []

        files = []
        for path in self.trash_dir.iterdir():
            if path.is_file():
                # Try to parse timestamp from filename
                try:
                    parts = path.name.split("_", 2)
                    if len(parts) >= 3:
                        timestamp_str = f"{parts[0]}_{parts[1]}"
                        timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                        files.append((path, timestamp))
                except ValueError:
                    files.append((path, datetime.fromtimestamp(path.stat().st_mtime)))

        return sorted(files, key=lambda x: x[1], reverse=True)

    def empty_trash(
        self,
        older_than_days: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> int:
        """
        Empty trash directory.

        Args:
            older_than_days: Only delete files older than this many days
            progress_callback: Optional callback(current, total, filename)

        Returns:
            Number of files deleted
        """
        if not self.trash_dir.exists():
            return 0

        deleted = 0
        cutoff = None
        if older_than_days:
            cutoff = datetime.now().timestamp() - (older_than_days * 86400)

        # Collect files to delete first (for accurate count)
        files_to_delete = []
        for path in self.trash_dir.iterdir():
            if path.is_file():
                if cutoff and path.stat().st_mtime > cutoff:
                    continue
                files_to_delete.append(path)

        total = len(files_to_delete)
        for i, path in enumerate(files_to_delete):
            if progress_callback:
                progress_callback(i + 1, total, path.name)
            try:
                path.unlink()
                deleted += 1
            except OSError:
                pass

        return deleted
