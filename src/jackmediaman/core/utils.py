"""Shared utility functions for filename and media operations."""

import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from jackmediaman.models.media import MediaItem


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string for use in a filename.

    Removes or replaces characters not allowed in filenames.
    - Replace : / \\ < > | " with ' - ' (space-dash-space)
    - Remove ? and * entirely

    Args:
        name: String to sanitize

    Returns:
        Sanitized string safe for filenames

    Examples:
        >>> sanitize_filename("Movie: Subtitle")
        'Movie - Subtitle'
        >>> sanitize_filename("Mission: Impossible")
        'Mission - Impossible'
        >>> sanitize_filename("What If...?")
        'What If...'
        >>> sanitize_filename("File*Name")
        'FileName'
        >>> sanitize_filename("  Movie  ")
        'Movie'
    """
    # Characters to replace with ' - '
    replace_with_dash = r'[:<>/\\|"]'
    result = re.sub(replace_with_dash, " - ", name)
    # Characters to remove entirely
    remove_chars = r"[?*]"
    result = re.sub(remove_chars, "", result)
    # Normalize multiple spaces
    result = re.sub(r"\s+", " ", result)
    # Collapse multiple dashes or dashes with spaces into single ' - '
    # But preserve hyphens without spaces (e.g., "Spider-Man")
    result = re.sub(r"(?:\s+-\s*|\s*-\s+|-{2,})+", " - ", result)
    # Strip leading/trailing whitespace and dashes
    result = result.strip(" -")
    # Limit length (leave room for extension)
    if len(result) > 240:
        result = result[:240]
    return result


def get_resolution_tag(item: "MediaItem") -> Optional[str]:
    """
    Get resolution tag for filename from a media item.

    Args:
        item: Media item with quality info

    Returns:
        Resolution string like '2160p', '1080p', etc. or None if unknown
    """
    from jackmediaman.models.quality import Resolution

    if not item.quality:
        return None

    if item.quality.resolution == Resolution.UNKNOWN:
        return None

    # Prefer raw resolution string if available (e.g., "2160p")
    if item.quality.resolution_raw:
        return item.quality.resolution_raw

    # Fall back to resolution name mapping
    resolution_map = {
        Resolution.UHD: "2160p",
        Resolution.FHD: "1080p",
        Resolution.HD: "720p",
        Resolution.SD: "480p",
    }
    return resolution_map.get(item.quality.resolution)
