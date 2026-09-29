"""NFO metadata models for Kodi-compatible XML files."""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import List, Optional


class NFOType(Enum):
    """Type of NFO file."""

    MOVIE = "movie"
    TVSHOW = "tvshow"
    EPISODE = "episode"


@dataclass
class NFOMovieMetadata:
    """Movie metadata for NFO generation."""

    title: str
    year: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    plot: Optional[str] = None
    rating: Optional[float] = None
    runtime: Optional[int] = None  # minutes
    genres: List[str] = field(default_factory=list)
    director: Optional[str] = None
    studio: Optional[str] = None
    tagline: Optional[str] = None


@dataclass
class NFOTVShowMetadata:
    """TV show metadata for NFO generation."""

    title: str
    year: Optional[int] = None
    tmdb_id: Optional[int] = None
    imdb_id: Optional[str] = None
    tvdb_id: Optional[int] = None
    plot: Optional[str] = None
    rating: Optional[float] = None
    genres: List[str] = field(default_factory=list)
    studio: Optional[str] = None
    status: Optional[str] = None  # "Ended", "Returning Series"


@dataclass
class NFOEpisodeMetadata:
    """Episode metadata for NFO generation."""

    title: str
    season: int
    episode: int
    show_title: Optional[str] = None
    aired: Optional[date] = None
    plot: Optional[str] = None
    rating: Optional[float] = None
    runtime: Optional[int] = None
    director: Optional[str] = None
    tmdb_id: Optional[int] = None  # Show's TMDb ID


@dataclass
class NFOResult:
    """Result of NFO generation operation."""

    path: Path
    success: bool = False
    skipped: bool = False
    reason: Optional[str] = None
    nfo_type: Optional[NFOType] = None

    @property
    def status(self) -> str:
        """Human-readable status."""
        if self.success:
            return "generated"
        elif self.skipped:
            return "skipped"
        else:
            return f"failed: {self.reason or 'unknown'}"


@dataclass
class NFOScanResult:
    """Result of scanning for missing NFO files."""

    path: Path
    media_type: NFOType
    title: str
    has_nfo: bool
    nfo_path: Optional[Path] = None

    @property
    def needs_nfo(self) -> bool:
        """Whether this item needs an NFO file."""
        return not self.has_nfo


@dataclass
class NFOBatchResult:
    """Result of batch NFO generation."""

    total: int = 0
    generated: int = 0
    skipped: int = 0
    failed: int = 0
    results: List[NFOResult] = field(default_factory=list)

    def add(self, result: NFOResult) -> None:
        """Add a result to the batch."""
        self.results.append(result)
        self.total += 1
        if result.success:
            self.generated += 1
        elif result.skipped:
            self.skipped += 1
        else:
            self.failed += 1

    @property
    def success_rate(self) -> float:
        """Percentage of successful generations."""
        if self.total == 0:
            return 0.0
        return (self.generated / self.total) * 100
