"""Data models for media items."""

from jackmediaman.models.media import Episode, MediaItem, MediaType, Movie
from jackmediaman.models.quality import Quality, Resolution
from jackmediaman.models.duplicates import DuplicateGroup
from jackmediaman.models.nfo import (
    NFOType,
    NFOMovieMetadata,
    NFOTVShowMetadata,
    NFOEpisodeMetadata,
    NFOResult,
    NFOScanResult,
    NFOBatchResult,
)

__all__ = [
    "MediaItem",
    "Movie",
    "Episode",
    "MediaType",
    "Quality",
    "Resolution",
    "DuplicateGroup",
    "NFOType",
    "NFOMovieMetadata",
    "NFOTVShowMetadata",
    "NFOEpisodeMetadata",
    "NFOResult",
    "NFOScanResult",
    "NFOBatchResult",
]
