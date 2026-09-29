"""Pipeline context and data models for torrent processing."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional

from jackmediaman.models.media import MediaItem, MediaType


class ActionMode(str, Enum):
    """File action modes (like filebot --action)."""

    MOVE = "move"  # Move files to library
    COPY = "copy"  # Copy files to library
    HARDLINK = "hardlink"  # Create hardlinks in library
    SYMLINK = "symlink"  # Create symlinks in library (original stays for seeding)
    KEEPLINK = "keeplink"  # Move to library, leave symlink in original for seeding


@dataclass
class IdentifiedMedia:
    """Result of media identification."""

    source_path: Path
    media_type: MediaType
    media_item: MediaItem
    confidence: float = 1.0
    identification_method: str = "filename"  # "filename", "tmdb", "folder"
    tmdb_id: Optional[int] = None
    canonical_title: Optional[str] = None
    canonical_year: Optional[int] = None


@dataclass
class FileMapping:
    """Mapping from source file to destination."""

    source: Path
    destination: Path
    media_item: MediaItem
    identified: IdentifiedMedia
    create_directories: List[Path] = field(default_factory=list)


@dataclass
class LinkOperation:
    """Record of a completed file operation."""

    source: Path
    destination: Path
    action: ActionMode
    success: bool
    error: Optional[str] = None
    original_link: Optional[Path] = None  # For keeplink mode, where symlink was created


@dataclass
class StageError:
    """Error from a pipeline stage."""

    stage: str
    error: str
    path: Optional[Path] = None
    recoverable: bool = True
    details: Optional[dict] = None


@dataclass
class ProcessContext:
    """Shared context passed through pipeline stages."""

    # Input parameters
    source_path: Path
    action: ActionMode
    dry_run: bool = False

    # Session tracking for logging
    session_id: str = ""

    # Options
    skip_extraction: bool = False
    skip_tmdb: bool = False
    skip_subtitles: bool = False
    skip_artwork: bool = False
    skip_nfo: bool = False
    skip_plex: bool = False

    # Work directory for extraction
    work_dir: Optional[Path] = None

    # Populated by Extractor stage
    extracted_files: List[Path] = field(default_factory=list)

    # Populated by Identifier stage
    identified_media: List[IdentifiedMedia] = field(default_factory=list)

    # Populated by Organizer stage
    file_mappings: List[FileMapping] = field(default_factory=list)

    # Populated by Linker stage
    completed_operations: List[LinkOperation] = field(default_factory=list)

    # Error tracking for rollback
    errors: List[StageError] = field(default_factory=list)

    # Track cleanup needed for rollback
    _cleanup_paths: List[Path] = field(default_factory=list)
    _rollback_data: dict = field(default_factory=dict)

    def add_error(
        self,
        stage: str,
        error: str,
        path: Optional[Path] = None,
        recoverable: bool = True,
    ) -> None:
        """Add an error to the context."""
        self.errors.append(
            StageError(stage=stage, error=error, path=path, recoverable=recoverable)
        )

    def has_fatal_errors(self) -> bool:
        """Check if there are any non-recoverable errors."""
        return any(not e.recoverable for e in self.errors)

    @property
    def video_files(self) -> List[Path]:
        """Get all video files to process (extracted or original)."""
        if self.extracted_files:
            return self.extracted_files
        # If no extraction happened, use source path
        if self.source_path.is_file():
            return [self.source_path]
        # Directory: find video files
        video_exts = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".ts", ".mov"}
        return [
            f
            for f in self.source_path.rglob("*")
            if f.is_file() and f.suffix.lower() in video_exts
        ]
