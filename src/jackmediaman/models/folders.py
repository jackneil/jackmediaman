"""Folder models for duplicate folder detection and consolidation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class MediaFolder:
    """A media folder (movie or TV show directory)."""

    path: Path
    name: str
    parsed_title: str
    parsed_year: Optional[int] = None
    tmdb_id: Optional[int] = None
    canonical_name: Optional[str] = None
    file_count: int = 0
    size_bytes: int = 0
    media_type: str = "movie"  # "movie" or "tv"

    @property
    def has_files(self) -> bool:
        """Return True if folder contains files."""
        return self.file_count > 0

    @property
    def is_empty(self) -> bool:
        """Return True if folder is empty."""
        return self.file_count == 0

    @property
    def size_mb(self) -> float:
        """Return size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    @property
    def size_gb(self) -> float:
        """Return size in gigabytes."""
        return self.size_bytes / (1024 * 1024 * 1024)

    @property
    def display_name(self) -> str:
        """Return display name for the folder."""
        if self.canonical_name:
            return self.canonical_name
        if self.parsed_year:
            return f"{self.parsed_title} ({self.parsed_year})"
        return self.parsed_title


@dataclass
class FolderGroup:
    """A group of folders that represent the same media item."""

    tmdb_id: int
    canonical_name: str
    media_type: str  # "movie" or "tv"
    folders: List[MediaFolder] = field(default_factory=list)

    @property
    def has_duplicates(self) -> bool:
        """Return True if group has more than one folder."""
        return len(self.folders) > 1

    @property
    def count(self) -> int:
        """Return number of folders in the group."""
        return len(self.folders)

    @property
    def total_files(self) -> int:
        """Return total file count across all folders."""
        return sum(f.file_count for f in self.folders)

    @property
    def total_size_bytes(self) -> int:
        """Return total size across all folders."""
        return sum(f.size_bytes for f in self.folders)

    @property
    def best_folder(self) -> Optional[MediaFolder]:
        """Return the best folder to keep (most files, then largest size)."""
        if not self.folders:
            return None
        # Prefer folder with canonical name first
        for folder in self.folders:
            if folder.name == self.canonical_name:
                return folder
        # Otherwise, prefer folder with most files, then largest
        return max(self.folders, key=lambda f: (f.file_count, f.size_bytes))

    @property
    def duplicate_folders(self) -> List[MediaFolder]:
        """Return folders that should be consolidated (not the best folder)."""
        best = self.best_folder
        return [f for f in self.folders if f != best]

    def add(self, folder: MediaFolder) -> None:
        """Add a folder to the group."""
        if folder not in self.folders:
            self.folders.append(folder)


@dataclass
class ConsolidationResult:
    """Result of consolidating a folder group."""

    group: FolderGroup
    target_folder: Path
    files_moved: int = 0
    files_skipped: int = 0
    folders_removed: int = 0
    errors: List[str] = field(default_factory=list)
    success: bool = True
    dry_run: bool = False

    @property
    def has_errors(self) -> bool:
        """Return True if there were errors during consolidation."""
        return len(self.errors) > 0
