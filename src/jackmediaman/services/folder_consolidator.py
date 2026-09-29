"""Folder consolidator service for merging duplicate media folders."""

import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from jackmediaman.core.config import get_settings
from jackmediaman.models.folders import (
    ConsolidationResult,
    FolderGroup,
    MediaFolder,
)
from jackmediaman.scanners.folders import FolderScanner, VIDEO_EXTENSIONS
from jackmediaman.services.renamer import TMDbTVClient

logger = logging.getLogger(__name__)

# Pattern to match season folder variants
SEASON_FOLDER_PATTERN = re.compile(r"[Ss]eason[\s.]*(\d+)", re.IGNORECASE)


@dataclass
class SeasonConsolidationResult:
    """Result of season folder consolidation operation."""

    files_moved: int = 0
    folders_removed: int = 0
    symlinks_updated: int = 0
    seasons_processed: List[Tuple[str, int]] = field(default_factory=list)  # (show_name, season_num)


class FolderConsolidator:
    """Service for finding and consolidating duplicate media folders."""

    def __init__(
        self,
        movies_dir: Optional[Path] = None,
        tv_dir: Optional[Path] = None,
        tmdb_client: Optional[TMDbTVClient] = None,
    ):
        """Initialize folder consolidator.

        Args:
            movies_dir: Path to movies directory (defaults to settings)
            tv_dir: Path to TV directory (defaults to settings)
            tmdb_client: Optional TMDb client (creates one if not provided)
        """
        settings = get_settings()
        self.movies_dir = movies_dir or settings.movies_dir
        self.tv_dir = tv_dir or settings.tv_dir
        self._tmdb_client = tmdb_client
        self._plex_service: Optional["PlexService"] = None

    def _get_tmdb_client(self) -> TMDbTVClient:
        """Lazy-load TMDb client."""
        if self._tmdb_client is None:
            self._tmdb_client = TMDbTVClient()
        return self._tmdb_client

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

    def _notify_plex(self, path: Path) -> None:
        """Notify Plex about changes to a path."""
        plex = self._get_plex_service()
        if plex:
            plex.notify_path_change(path)

    def find_duplicate_folders(
        self,
        media_type: str = "movie",
        tmdb_lookup: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[FolderGroup]:
        """Find duplicate folders in the media library.

        Args:
            media_type: "movie" or "tv"
            tmdb_lookup: Whether to use TMDb for accurate matching
            progress_callback: Optional callback(current, total, name)

        Returns:
            List of FolderGroup objects containing duplicates
        """
        scanner = FolderScanner(self._get_tmdb_client() if tmdb_lookup else None)

        # Scan folders
        if media_type in ("movie", "movies"):
            folders = scanner.scan_movie_folders(self.movies_dir, progress_callback)
        else:
            folders = scanner.scan_tv_folders(self.tv_dir, progress_callback)

        if not folders:
            return []

        # Group by similarity
        return scanner.group_by_similarity(
            folders,
            tmdb_lookup=tmdb_lookup,
            progress_callback=progress_callback,
        )

    def get_canonical_folder_name(self, group: FolderGroup) -> str:
        """Get the canonical folder name for a group.

        Args:
            group: FolderGroup to get name for

        Returns:
            Canonical folder name string
        """
        return group.canonical_name

    def consolidate_group(
        self,
        group: FolderGroup,
        dry_run: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> ConsolidationResult:
        """Consolidate files from duplicate folders into the best folder.

        Args:
            group: FolderGroup to consolidate
            dry_run: If True, don't actually move files
            progress_callback: Optional callback(current, total, name)

        Returns:
            ConsolidationResult with details
        """
        result = ConsolidationResult(
            group=group,
            target_folder=Path(""),
            dry_run=dry_run,
        )

        if not group.has_duplicates:
            return result

        # Find target folder (the "best" one to keep)
        best = group.best_folder
        if not best:
            result.success = False
            result.errors.append("No best folder found")
            return result

        # Get root directory
        root_dir = best.path.parent

        # Check if we need to rename to canonical name
        canonical_name = self.get_canonical_folder_name(group)
        target_path = root_dir / canonical_name

        # Handle target folder
        if best.path.name == canonical_name:
            # Best folder already has canonical name
            result.target_folder = best.path
        elif target_path.exists() and target_path != best.path:
            # Another folder already has canonical name - use it as target
            result.target_folder = target_path
        else:
            # Need to rename best folder to canonical name
            result.target_folder = target_path
            if not dry_run:
                try:
                    if target_path.exists():
                        # Target exists but different from best - this shouldn't happen
                        result.errors.append(f"Target folder already exists: {target_path}")
                        result.success = False
                        return result
                    best.path.rename(target_path)
                except OSError as e:
                    result.errors.append(f"Failed to rename {best.path} to {target_path}: {e}")
                    result.success = False
                    return result

        # Get list of duplicate folders to consolidate
        duplicates = [f for f in group.folders if f.path != result.target_folder and f.path != best.path]

        # Also include best.path if it was renamed
        if best.path != result.target_folder and best.path.exists():
            # This means rename failed or dry_run - in dry_run, treat best as target
            pass

        total_files = sum(f.file_count for f in duplicates)
        processed = 0

        # Process each duplicate folder
        for folder in duplicates:
            if not folder.path.exists():
                continue

            # Move files from duplicate to target
            files_to_move = self._get_video_files(folder.path, recursive=(folder.media_type == "tv"))

            for src_file in files_to_move:
                processed += 1
                if progress_callback:
                    progress_callback(processed, total_files, src_file.name)

                # Determine destination path
                if folder.media_type == "tv":
                    # Preserve subdirectory structure for TV shows
                    rel_path = src_file.relative_to(folder.path)
                    dst_file = result.target_folder / rel_path
                else:
                    # Movies go directly in the folder
                    dst_file = result.target_folder / src_file.name

                if dst_file.exists():
                    # File conflict - compare and decide
                    action = self._resolve_conflict(src_file, dst_file)
                    if action == "skip":
                        result.files_skipped += 1
                        continue
                    elif action == "replace":
                        if not dry_run:
                            try:
                                dst_file.unlink()
                            except OSError as e:
                                result.errors.append(f"Failed to remove {dst_file}: {e}")
                                continue

                if not dry_run:
                    try:
                        # Ensure parent directory exists
                        dst_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src_file), str(dst_file))
                        result.files_moved += 1
                    except (shutil.Error, OSError) as e:
                        result.errors.append(f"Failed to move {src_file} to {dst_file}: {e}")
                else:
                    result.files_moved += 1

            # Try to remove empty folder
            if not dry_run:
                if self._remove_empty_folder(folder.path):
                    result.folders_removed += 1
            else:
                # In dry run, assume folder will be removed if all files moved
                if folder.file_count > 0 and folder.file_count <= result.files_moved:
                    result.folders_removed += 1

        # Notify Plex about target folder changes
        if not dry_run and result.files_moved > 0:
            self._notify_plex(result.target_folder)

        result.success = len(result.errors) == 0
        return result

    def consolidate_all(
        self,
        media_type: str = "movie",
        dry_run: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[ConsolidationResult]:
        """Consolidate all duplicate folder groups.

        Args:
            media_type: "movie" or "tv"
            dry_run: If True, don't actually move files
            progress_callback: Optional callback(current, total, name)

        Returns:
            List of ConsolidationResult objects
        """
        # Find all duplicate groups
        groups = self.find_duplicate_folders(
            media_type=media_type,
            tmdb_lookup=True,
            progress_callback=progress_callback,
        )

        results = []
        for i, group in enumerate(groups):
            if progress_callback:
                progress_callback(i + 1, len(groups), group.canonical_name)

            result = self.consolidate_group(group, dry_run=dry_run)
            results.append(result)

        return results

    def _get_video_files(self, folder: Path, recursive: bool = False) -> List[Path]:
        """Get all video files in a folder.

        Args:
            folder: Folder to scan
            recursive: Whether to scan subdirectories

        Returns:
            List of video file paths
        """
        files = []
        try:
            if recursive:
                for f in folder.rglob("*"):
                    if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                        files.append(f)
            else:
                for f in folder.iterdir():
                    if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                        files.append(f)
        except OSError:
            pass
        return sorted(files)

    def _resolve_conflict(self, src: Path, dst: Path) -> str:
        """Resolve a file conflict.

        Args:
            src: Source file path
            dst: Destination file path (already exists)

        Returns:
            "skip" to keep destination, "replace" to use source
        """
        # Simple heuristic: keep the larger file (likely higher quality)
        try:
            src_size = src.stat().st_size
            dst_size = dst.stat().st_size

            if src_size > dst_size:
                return "replace"
            else:
                return "skip"
        except OSError:
            return "skip"

    def _remove_empty_folder(self, folder: Path) -> bool:
        """Remove a folder if it's empty (recursively removes empty subdirs first).

        Args:
            folder: Folder to remove

        Returns:
            True if folder was removed
        """
        if not folder.exists():
            return False

        try:
            # First remove empty subdirectories
            for subdir in sorted(folder.rglob("*"), reverse=True):
                if subdir.is_dir():
                    try:
                        subdir.rmdir()  # Only succeeds if empty
                    except OSError:
                        pass

            # Check if folder is now empty
            remaining = list(folder.iterdir())
            if not remaining:
                folder.rmdir()
                return True

            # Check if only non-video files remain (like .nfo, .txt, etc)
            video_files = [f for f in remaining if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]
            if not video_files:
                # Remove remaining non-video files and folder
                shutil.rmtree(folder)
                return True

            return False
        except OSError:
            return False

    # =========================================================================
    # Season Folder Consolidation (e.g., 'Season.05' -> 'Season 05')
    # =========================================================================

    def find_season_folder_variants(
        self,
        show_filter: Optional[str] = None,
    ) -> List[Tuple[Path, int, List[Path]]]:
        """Find all season folder variants that need consolidation.

        Args:
            show_filter: Optional filter to limit to specific show

        Returns:
            List of (show_folder, season_num, variant_folders) tuples
        """
        variants_to_process = []

        if not self.tv_dir or not self.tv_dir.exists():
            return variants_to_process

        for show_folder in sorted(self.tv_dir.iterdir()):
            if not show_folder.is_dir():
                continue

            if show_filter and show_filter.lower() not in show_folder.name.lower():
                continue

            variants = self._find_season_variants_for_show(show_folder)

            # Find seasons with multiple folders
            for season_num, folders in variants.items():
                if len(folders) > 1:
                    variants_to_process.append((show_folder, season_num, folders))

        return variants_to_process

    def consolidate_season_folders(
        self,
        torrent_dir: Optional[Path] = None,
        show_filter: Optional[str] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> SeasonConsolidationResult:
        """Consolidate all season folder variants (e.g., 'Season.05' -> 'Season 05').

        Args:
            torrent_dir: Optional path to torrent directory (for updating symlinks)
            show_filter: Optional filter to limit to specific show
            progress_callback: Optional callback(show_name, season_num, file_count)

        Returns:
            SeasonConsolidationResult with statistics
        """
        result = SeasonConsolidationResult()
        variants_to_process = self.find_season_folder_variants(show_filter)

        if not variants_to_process:
            return result

        for show_folder, season_num, folders in variants_to_process:
            canonical = self._get_canonical_season_folder(show_folder, season_num)

            if progress_callback:
                file_count = sum(
                    len([f for f in folder.iterdir() if f.is_file()])
                    for folder in folders
                )
                progress_callback(show_folder.name, season_num, file_count)

            # Ensure canonical folder exists
            if not canonical.exists():
                canonical.mkdir(parents=True)

            # Move files from variant folders to canonical
            for folder in folders:
                if folder == canonical:
                    continue

                for file_path in folder.iterdir():
                    if not file_path.is_file():
                        continue

                    new_path = canonical / file_path.name

                    # Handle naming conflicts
                    if new_path.exists():
                        # Skip if same file (same size)
                        if file_path.stat().st_size == new_path.stat().st_size:
                            logger.debug(f"Skipping duplicate: {file_path.name}")
                            file_path.unlink()
                            continue
                        # Otherwise keep both (will be handled by duplicate scanner)
                        base = new_path.stem
                        ext = new_path.suffix
                        counter = 1
                        while new_path.exists():
                            new_path = canonical / f"{base}_{counter}{ext}"
                            counter += 1

                    # Move file
                    shutil.move(str(file_path), str(new_path))
                    result.files_moved += 1
                    logger.debug(f"Moved: {file_path} -> {new_path}")

                    # Update symlinks pointing to old location
                    if torrent_dir and torrent_dir.exists():
                        result.symlinks_updated += self._update_symlinks_for_moved_file(
                            file_path, new_path, torrent_dir
                        )

                # Remove empty folder
                try:
                    folder.rmdir()
                    result.folders_removed += 1
                    logger.debug(f"Removed empty folder: {folder}")
                except OSError:
                    # Folder not empty (has subdirs or other files)
                    pass

            result.seasons_processed.append((show_folder.name, season_num))

        return result

    def _find_season_variants_for_show(self, show_dir: Path) -> Dict[int, List[Path]]:
        """Find all season folder variants for a show.

        Returns:
            Dict mapping season number to list of folder paths
        """
        variants: Dict[int, List[Path]] = {}

        for folder in show_dir.iterdir():
            if not folder.is_dir():
                continue

            match = SEASON_FOLDER_PATTERN.search(folder.name)
            if match:
                season_num = int(match.group(1))
                if season_num not in variants:
                    variants[season_num] = []
                variants[season_num].append(folder)

        return variants

    def _get_canonical_season_folder(self, show_dir: Path, season_num: int) -> Path:
        """Get the canonical season folder name (e.g., 'Season 05')."""
        return show_dir / f"Season {season_num:02d}"

    def _update_symlinks_for_moved_file(
        self,
        old_path: Path,
        new_path: Path,
        torrent_dir: Path,
    ) -> int:
        """Find and update symlinks that pointed to old_path to point to new_path.

        Returns:
            Number of symlinks updated
        """
        updated = 0

        for symlink in torrent_dir.rglob("*"):
            if not symlink.is_symlink():
                continue

            try:
                target = Path(os.readlink(symlink))
                if not target.is_absolute():
                    target = (symlink.parent / target).resolve()

                if target == old_path or target.resolve() == old_path.resolve():
                    # Update symlink to point to new location
                    symlink.unlink()
                    rel_target = os.path.relpath(new_path, symlink.parent)
                    os.symlink(rel_target, symlink)
                    updated += 1
                    logger.debug(f"Updated symlink {symlink} -> {new_path}")
            except OSError:
                continue

        return updated
