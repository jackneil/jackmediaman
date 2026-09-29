"""Folder scanner for detecting duplicate media folders."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from jackmediaman.models.folders import MediaFolder, FolderGroup

# Type checking only - avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from jackmediaman.services.renamer import TMDbTVClient

# Video file extensions
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".ts", ".mov"}


class FolderScanner:
    """Scan media directories for folders and group duplicates."""

    # Pattern for year in folder name
    YEAR_PATTERN = re.compile(r"[\(\[\{]?\s*(\d{4})\s*[\)\]\}]?")

    # Pattern to clean quality tags from title
    CLEAN_PATTERN = re.compile(
        r"\b("
        r"2160p|4k|1080p|1080i|720p|480p|576p|"
        r"bluray|blu-ray|bdrip|brrip|remux|"
        r"web-dl|webdl|webrip|"
        r"hdtv|hdrip|dvdrip|dvd|"
        r"x264|x265|h264|h265|hevc|avc|xvid|"
        r"aac|ac3|dts|dd5\.1|"
        r"hdr|hdr10|dolby[\s.]?vision|"
        r"proper|repack|internal|limited"
        r")\b",
        re.IGNORECASE,
    )

    # Pattern for region/country codes
    REGION_PATTERN = re.compile(r"\s*\(?(US|UK|AU|CA)\)?$", re.IGNORECASE)

    def __init__(self, tmdb_client: Optional["TMDbTVClient"] = None):
        """Initialize folder scanner.

        Args:
            tmdb_client: Optional TMDb client for canonical name lookups (should be TMDbTVClient)
        """
        self._tmdb_client = tmdb_client

    def scan_movie_folders(
        self,
        root: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[MediaFolder]:
        """Scan movie directory for folders.

        Args:
            root: Root movie directory
            progress_callback: Optional callback(current, total, name)

        Returns:
            List of MediaFolder objects
        """
        if not root.exists():
            return []

        folders = []
        subdirs = [d for d in sorted(root.iterdir()) if d.is_dir()]
        total = len(subdirs)

        for i, folder_path in enumerate(subdirs):
            if progress_callback:
                progress_callback(i + 1, total, folder_path.name)

            title, year = self._parse_folder_name(folder_path.name)
            file_count, size_bytes = self._get_folder_stats(folder_path)

            folder = MediaFolder(
                path=folder_path,
                name=folder_path.name,
                parsed_title=title,
                parsed_year=year,
                file_count=file_count,
                size_bytes=size_bytes,
                media_type="movie",
            )
            folders.append(folder)

        return folders

    def scan_tv_folders(
        self,
        root: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[MediaFolder]:
        """Scan TV directory for show folders.

        Args:
            root: Root TV directory
            progress_callback: Optional callback(current, total, name)

        Returns:
            List of MediaFolder objects
        """
        if not root.exists():
            return []

        folders = []
        subdirs = [d for d in sorted(root.iterdir()) if d.is_dir()]
        total = len(subdirs)

        for i, folder_path in enumerate(subdirs):
            if progress_callback:
                progress_callback(i + 1, total, folder_path.name)

            title, year = self._parse_folder_name(folder_path.name)
            file_count, size_bytes = self._get_folder_stats(folder_path, recursive=True)

            folder = MediaFolder(
                path=folder_path,
                name=folder_path.name,
                parsed_title=title,
                parsed_year=year,
                file_count=file_count,
                size_bytes=size_bytes,
                media_type="tv",
            )
            folders.append(folder)

        return folders

    def group_by_similarity(
        self,
        folders: List[MediaFolder],
        tmdb_lookup: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[FolderGroup]:
        """Group folders that likely represent the same media.

        Uses title normalization and optional TMDb lookup for accurate matching.

        Args:
            folders: List of folders to group
            tmdb_lookup: Whether to use TMDb for canonical names
            progress_callback: Optional callback(current, total, name)

        Returns:
            List of FolderGroup objects (only groups with 2+ folders)
        """
        # First pass: group by normalized title
        title_groups: Dict[str, List[MediaFolder]] = defaultdict(list)

        for folder in folders:
            normalized = self._normalize_title(folder.parsed_title)
            title_groups[normalized].append(folder)

        # Second pass: lookup TMDb for groups and refine
        groups: Dict[int, FolderGroup] = {}
        unmatched: List[MediaFolder] = []
        total = len(folders)

        for i, folder in enumerate(folders):
            if progress_callback:
                progress_callback(i + 1, total, folder.name)

            tmdb_id = None
            canonical_name = None

            if tmdb_lookup and self._tmdb_client:
                if folder.media_type == "movie":
                    tmdb_id = self._tmdb_client.search_movie(
                        folder.parsed_title, folder.parsed_year
                    )
                    if tmdb_id:
                        details = self._tmdb_client.get_movie_details(tmdb_id)
                        if details:
                            title = details.get("title", folder.parsed_title)
                            year = details.get("year", folder.parsed_year)
                            canonical_name = f"{title} ({year})" if year else title
                else:  # TV
                    tmdb_id = self._tmdb_client.search_tv(folder.parsed_title)
                    if tmdb_id:
                        # For TV, we'd need show details - use parsed title for now
                        canonical_name = folder.parsed_title

            if tmdb_id:
                folder.tmdb_id = tmdb_id
                folder.canonical_name = canonical_name

                if tmdb_id not in groups:
                    groups[tmdb_id] = FolderGroup(
                        tmdb_id=tmdb_id,
                        canonical_name=canonical_name or folder.parsed_title,
                        media_type=folder.media_type,
                    )
                groups[tmdb_id].add(folder)
            else:
                unmatched.append(folder)

        # Handle unmatched folders - group by normalized title
        title_groups_remaining: Dict[str, List[MediaFolder]] = defaultdict(list)
        for folder in unmatched:
            normalized = self._normalize_title(folder.parsed_title)
            title_groups_remaining[normalized].append(folder)

        # Create groups for title matches (use negative IDs for non-TMDb)
        fake_id = -1
        for normalized_title, folder_list in title_groups_remaining.items():
            if len(folder_list) > 1:
                # Multiple folders with same normalized title
                canonical = folder_list[0].parsed_title
                if folder_list[0].parsed_year:
                    canonical = f"{canonical} ({folder_list[0].parsed_year})"

                group = FolderGroup(
                    tmdb_id=fake_id,
                    canonical_name=canonical,
                    media_type=folder_list[0].media_type,
                )
                for folder in folder_list:
                    folder.tmdb_id = fake_id
                    folder.canonical_name = canonical
                    group.add(folder)
                groups[fake_id] = group
                fake_id -= 1

        # Return only groups with duplicates
        return [g for g in groups.values() if g.has_duplicates]

    def _parse_folder_name(self, name: str) -> Tuple[str, Optional[int]]:
        """Parse folder name to extract title and year.

        Args:
            name: Folder name

        Returns:
            Tuple of (title, year) where year may be None
        """
        year = None
        year_match = None

        # Find last valid year in name
        for match in self.YEAR_PATTERN.finditer(name):
            potential_year = int(match.group(1))
            if 1888 <= potential_year <= datetime.now().year + 2:
                year = potential_year
                year_match = match

        # Extract title
        if year_match:
            title = name[: year_match.start()].strip()
            title = title.rstrip("([{-_. ")
        else:
            title = name

        # Replace dots/underscores with spaces
        title = title.replace(".", " ").replace("_", " ")

        # Remove region codes
        title = self.REGION_PATTERN.sub("", title).strip()

        # Clean quality tags
        title = self.CLEAN_PATTERN.sub("", title)

        # Normalize whitespace
        title = " ".join(title.split())

        return title.strip(), year

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison.

        Removes dashes, apostrophes, and normalizes spacing.
        """
        normalized = title.lower()
        # Remove dashes and apostrophes
        normalized = re.sub(r"[\-\'\'\"]", "", normalized)
        # Normalize spaces
        normalized = " ".join(normalized.split())
        return normalized

    def _get_folder_stats(
        self, folder: Path, recursive: bool = False
    ) -> Tuple[int, int]:
        """Get file count and total size for a folder.

        Args:
            folder: Folder path
            recursive: Whether to count files in subdirectories

        Returns:
            Tuple of (file_count, total_size_bytes)
        """
        file_count = 0
        total_size = 0

        try:
            if recursive:
                for f in folder.rglob("*"):
                    if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                        file_count += 1
                        try:
                            total_size += f.stat().st_size
                        except OSError:
                            pass
            else:
                for f in folder.iterdir():
                    if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS:
                        file_count += 1
                        try:
                            total_size += f.stat().st_size
                        except OSError:
                            pass
        except OSError:
            pass

        return file_count, total_size
