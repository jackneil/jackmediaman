"""Media item models for movies and TV episodes."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional

from jackmediaman.models.quality import Quality


class MediaType(Enum):
    """Type of media item."""

    MOVIE = "movie"
    EPISODE = "episode"


@dataclass(eq=False)
class MediaItem:
    """Base class for all media items."""

    path: Path
    filename: str
    size_bytes: int
    quality: Quality
    created_at: Optional[datetime] = None
    is_symlink: bool = False
    symlink_target: Optional[Path] = None
    is_protected: bool = False
    protection_reason: Optional[str] = None
    edition: Optional[str] = None

    @property
    def media_type(self) -> MediaType:
        """Return the type of media item."""
        raise NotImplementedError

    @property
    def identity_key(self) -> str:
        """Return a unique key for grouping duplicates."""
        raise NotImplementedError

    @property
    def display_name(self) -> str:
        """Return a human-readable display name."""
        return self.filename

    @property
    def size_mb(self) -> float:
        """Return file size in megabytes."""
        return self.size_bytes / (1024 * 1024)

    @property
    def size_gb(self) -> float:
        """Return file size in gigabytes."""
        return self.size_bytes / (1024 * 1024 * 1024)

    def __hash__(self) -> int:
        return hash(self.path)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MediaItem):
            return NotImplemented
        return self.path == other.path


@dataclass(eq=False)
class Movie(MediaItem):
    """Represents a movie file."""

    title: str = ""
    year: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None

    @property
    def media_type(self) -> MediaType:
        return MediaType.MOVIE

    @property
    def identity_key(self) -> str:
        """Movies match by TMDb ID (preferred) or title+year."""
        if self.tmdb_id:
            return f"movie:tmdb:{self.tmdb_id}"
        normalized = self.title.lower().replace(" ", "_")
        # Remove special characters
        normalized = "".join(c for c in normalized if c.isalnum() or c == "_")
        year_str = str(self.year) if self.year else "unknown"
        return f"movie:title:{normalized}:{year_str}"

    @property
    def display_name(self) -> str:
        year_str = f" ({self.year})" if self.year else ""
        return f"{self.title}{year_str}"


@dataclass(eq=False)
class Episode(MediaItem):
    """Represents a TV episode file."""

    series_name: str = ""
    season_number: int = 0
    episode_numbers: List[int] = field(default_factory=list)
    episode_title: Optional[str] = None
    tvdb_id: Optional[int] = None

    @property
    def media_type(self) -> MediaType:
        return MediaType.EPISODE

    @property
    def identity_key(self) -> str:
        """Episodes match by show + season + episode number(s)."""
        normalized_name = self.series_name.lower().replace(" ", "_")
        normalized_name = "".join(c for c in normalized_name if c.isalnum() or c == "_")
        eps = "-".join(f"{e:02d}" for e in sorted(self.episode_numbers))
        return f"tv:{normalized_name}:s{self.season_number:02d}e{eps}"

    @property
    def display_name(self) -> str:
        if len(self.episode_numbers) == 1:
            ep_str = f"S{self.season_number:02d}E{self.episode_numbers[0]:02d}"
        else:
            eps = "-".join(f"E{e:02d}" for e in sorted(self.episode_numbers))
            ep_str = f"S{self.season_number:02d}{eps}"
        return f"{self.series_name} {ep_str}"

    @property
    def episode_number(self) -> int:
        """Return first episode number for compatibility."""
        return self.episode_numbers[0] if self.episode_numbers else 0
