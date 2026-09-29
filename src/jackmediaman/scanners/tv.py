"""TV show scanner for episode files."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Iterator, List, Optional, Tuple

from jackmediaman.models.media import Episode
from jackmediaman.models.quality import Quality, QualityParser

if TYPE_CHECKING:
    from jackmediaman.services.metadata_prober import MetadataProber

# Video file extensions to scan
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".ts", ".mov"}


class TVScanner:
    """Scan TV show library for episode files."""

    # Pattern for season folders - handles variants like:
    # "Season 05", "Season.05", "Season05", "Season 5"
    SEASON_PATTERN = re.compile(r"[Ss]eason[\s.]*(\d+)", re.IGNORECASE)

    # Patterns for episode numbers (ordered by specificity)
    EPISODE_PATTERNS = [
        # S01E01 format (most common), with optional range like E01-03 or E01-E03
        re.compile(r"[Ss](\d{1,2})[Ee](\d{1,3})(?:-[Ee]?(\d{1,3}))?"),
        # 1x01 format
        re.compile(r"(\d{1,2})[xX](\d{1,3})(?:-(\d{1,3}))?"),
        # Season X Episode Y format
        re.compile(
            r"[Ss]eason\s*(\d+)\s*[Ee]pisode\s*(\d+)", re.IGNORECASE
        ),
    ]

    # Pattern for multi-episode (S01E01E02E03)
    MULTI_EPISODE_PATTERN = re.compile(r"[Ss](\d{1,2})((?:[Ee]\d{1,3})+)")

    def __init__(
        self,
        quality_parser: Optional[QualityParser] = None,
        metadata_prober: Optional[MetadataProber] = None,
    ):
        """Initialize the TV scanner.

        Args:
            quality_parser: Parser for extracting quality from filenames
            metadata_prober: Optional prober for accurate metadata via ffprobe
        """
        self.quality_parser = quality_parser or QualityParser()
        self._metadata_prober = metadata_prober
        # Video paths skipped because they are symlinks to files that no longer exist
        self.broken_links: List[Path] = []

    def scan(self, root: Path) -> Iterator[Episode]:
        """Scan TV library: root/ShowName/Season X/episodes."""
        self.broken_links = []
        if not root.exists():
            return

        for show_dir in sorted(root.iterdir()):
            if not show_dir.is_dir():
                continue

            series_name = show_dir.name

            for season_dir in sorted(show_dir.iterdir()):
                if not season_dir.is_dir():
                    continue

                season_num = self._parse_season_number(season_dir.name)
                if season_num is None:
                    continue

                for file_path in sorted(season_dir.iterdir()):
                    if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
                        continue

                    # Dangling symlink (e.g. its torrent was deleted)
                    if not file_path.exists():
                        self.broken_links.append(file_path)
                        continue

                    episode_nums = self._parse_episode_numbers(file_path.name)
                    if not episode_nums:
                        # Try to get season from filename if not found
                        season_from_file, episode_nums = self._parse_episode_from_filename(
                            file_path.name
                        )
                        if season_from_file:
                            season_num = season_from_file

                    if not episode_nums:
                        continue

                    try:
                        yield self._create_episode(
                            file_path, series_name, season_num, episode_nums
                        )
                    except (FileNotFoundError, OSError):
                        # Skip files that no longer exist or can't be accessed
                        continue

    def scan_with_metadata(
        self,
        root: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Episode]:
        """Scan TV library with accurate metadata from ffprobe.

        This method collects all files first, then batch probes them
        for more efficient processing.

        Args:
            root: Root directory of TV library
            progress_callback: Optional callback(current, total, filename)

        Returns:
            List of Episode objects with accurate quality info
        """
        self.broken_links = []
        if not root.exists():
            return []

        # First pass: collect all episode data without quality
        episode_data: List[Tuple[Path, str, int, List[int]]] = []

        for show_dir in sorted(root.iterdir()):
            if not show_dir.is_dir():
                continue

            series_name = show_dir.name

            for season_dir in sorted(show_dir.iterdir()):
                if not season_dir.is_dir():
                    continue

                season_num = self._parse_season_number(season_dir.name)
                if season_num is None:
                    continue

                for file_path in sorted(season_dir.iterdir()):
                    if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
                        continue

                    # Dangling symlink (e.g. its torrent was deleted)
                    if not file_path.exists():
                        self.broken_links.append(file_path)
                        continue

                    episode_nums = self._parse_episode_numbers(file_path.name)
                    if not episode_nums:
                        season_from_file, episode_nums = self._parse_episode_from_filename(
                            file_path.name
                        )
                        if season_from_file:
                            season_num = season_from_file

                    if not episode_nums:
                        continue

                    episode_data.append((file_path, series_name, season_num, episode_nums))

        if not episode_data:
            return []

        # Second pass: batch probe for quality if prober available
        paths = [data[0] for data in episode_data]
        qualities: Dict[Path, Optional[Quality]] = {}

        if self._metadata_prober and self._metadata_prober.is_available:
            qualities = self._metadata_prober.probe_batch_quality(paths, progress_callback)
        else:
            # Fall back to filename parsing
            for i, path in enumerate(paths):
                qualities[path] = self.quality_parser.parse(path.name)
                if progress_callback:
                    progress_callback(i + 1, len(paths), path.name)

        # Create episodes with quality
        episodes = []
        for path, series_name, season_num, episode_nums in episode_data:
            quality = qualities.get(path) or self.quality_parser.parse(path.name)
            try:
                episodes.append(
                    self._create_episode(path, series_name, season_num, episode_nums, quality)
                )
            except (FileNotFoundError, OSError):
                # Skip files that no longer exist or can't be accessed
                # (broken symlinks, moved files, special chars in names)
                continue

        return episodes

    def _parse_season_number(self, name: str) -> Optional[int]:
        """Parse season number from folder name."""
        match = self.SEASON_PATTERN.search(name)
        if match:
            return int(match.group(1))
        # Try just a number (e.g., "01", "1")
        if name.isdigit():
            return int(name)
        return None

    def _parse_episode_numbers(self, filename: str) -> List[int]:
        """Parse episode number(s) from filename."""
        # Try multi-episode pattern first (S01E01E02E03)
        multi_match = self.MULTI_EPISODE_PATTERN.search(filename)
        if multi_match:
            ep_part = multi_match.group(2)
            eps = re.findall(r"[Ee](\d{1,3})", ep_part)
            # Only use multi-episode match if there are 2+ episodes
            if len(eps) >= 2:
                return [int(e) for e in eps]

        # Try standard patterns (handles ranges like S01E01-03)
        for pattern in self.EPISODE_PATTERNS:
            match = pattern.search(filename)
            if match:
                groups = match.groups()
                # groups[0] is season (ignored here), groups[1] is first episode
                if len(groups) >= 2 and groups[1]:
                    episodes = [int(groups[1])]
                    # Check for episode range (e.g., S01E01-03)
                    if len(groups) >= 3 and groups[2]:
                        end_ep = int(groups[2])
                        start_ep = episodes[0]
                        if end_ep > start_ep:
                            episodes = list(range(start_ep, end_ep + 1))
                    return episodes

        return []

    def _parse_episode_from_filename(
        self, filename: str
    ) -> Tuple[Optional[int], List[int]]:
        """Parse both season and episode from filename."""
        for pattern in self.EPISODE_PATTERNS:
            match = pattern.search(filename)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    season = int(groups[0])
                    episodes = [int(groups[1])]
                    if len(groups) >= 3 and groups[2]:
                        end_ep = int(groups[2])
                        if end_ep > episodes[0]:
                            episodes = list(range(episodes[0], end_ep + 1))
                    return season, episodes
        return None, []

    def _create_episode(
        self,
        path: Path,
        series_name: str,
        season: int,
        episodes: List[int],
        quality: Optional[Quality] = None,
    ) -> Episode:
        """Create an Episode object from file path.

        Args:
            path: Path to episode file
            series_name: Name of the TV series
            season: Season number
            episodes: List of episode numbers
            quality: Optional pre-computed quality (falls back to filename parsing)
        """
        stat = path.stat()
        is_symlink = path.is_symlink()

        return Episode(
            path=path,
            filename=path.name,
            size_bytes=stat.st_size,
            quality=quality or self.quality_parser.parse(path.name),
            created_at=datetime.fromtimestamp(stat.st_ctime),
            is_symlink=is_symlink,
            symlink_target=path.resolve() if is_symlink else None,
            series_name=series_name,
            season_number=season,
            episode_numbers=episodes,
        )
