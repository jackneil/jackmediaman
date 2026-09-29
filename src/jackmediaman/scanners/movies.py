"""Movie scanner for movie files."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Dict, Iterator, List, Optional, Tuple

from jackmediaman.models.media import Movie
from jackmediaman.models.quality import Quality, QualityParser

if TYPE_CHECKING:
    from jackmediaman.services.metadata_prober import MetadataProber

# Video file extensions to scan
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".ts", ".mov"}

# Edition patterns
EDITION_PATTERNS = {
    "directors_cut": [r"director'?s?[\s._-]?cut", r"\bdc\b"],
    "extended": [r"extended[\s._-]?(?:cut|edition)?", r"\bext\b"],
    "unrated": [r"unrated", r"uncensored"],
    "theatrical": [r"theatrical[\s._-]?(?:cut|edition)?"],
    "remastered": [r"remaster(?:ed)?", r"restored"],
    "special": [r"special[\s._-]?edition"],
    "criterion": [r"criterion"],
    "imax": [r"imax"],
    "3d": [r"\b3d\b"],
}


class MovieScanner:
    """Scan movie library for movie files."""

    # Pattern for year in folder/filename
    YEAR_PATTERN = re.compile(r"[\(\[\{]?(\d{4})[\)\]\}]?")

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

    def __init__(
        self,
        quality_parser: Optional[QualityParser] = None,
        metadata_prober: Optional[MetadataProber] = None,
    ):
        """Initialize the movie scanner.

        Args:
            quality_parser: Parser for extracting quality from filenames
            metadata_prober: Optional prober for accurate metadata via ffprobe
        """
        self.quality_parser = quality_parser or QualityParser()
        self._metadata_prober = metadata_prober

    def scan(self, root: Path) -> Iterator[Movie]:
        """Scan movie library: root/MovieName (Year)/movie.file."""
        if not root.exists():
            return

        for movie_dir in sorted(root.iterdir()):
            if not movie_dir.is_dir():
                continue

            title, year = self._parse_movie_folder(movie_dir.name)

            for file_path in sorted(movie_dir.iterdir()):
                if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue

                # Skip sample files
                if "sample" in file_path.name.lower():
                    continue

                # Skip very small files (likely samples)
                if file_path.stat().st_size < 100 * 1024 * 1024:  # 100MB
                    continue

                yield self._create_movie(file_path, title, year)

    def scan_with_metadata(
        self,
        root: Path,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Movie]:
        """Scan movie library with accurate metadata from ffprobe.

        This method collects all files first, then batch probes them
        for more efficient processing.

        Args:
            root: Root directory of movie library
            progress_callback: Optional callback(current, total, filename)

        Returns:
            List of Movie objects with accurate quality info
        """
        if not root.exists():
            return []

        # First pass: collect all movie data without quality
        movie_data: List[Tuple[Path, str, Optional[int]]] = []

        for movie_dir in sorted(root.iterdir()):
            if not movie_dir.is_dir():
                continue

            title, year = self._parse_movie_folder(movie_dir.name)

            for file_path in sorted(movie_dir.iterdir()):
                if file_path.suffix.lower() not in VIDEO_EXTENSIONS:
                    continue

                if "sample" in file_path.name.lower():
                    continue

                if file_path.stat().st_size < 100 * 1024 * 1024:
                    continue

                movie_data.append((file_path, title, year))

        if not movie_data:
            return []

        # Second pass: batch probe for quality if prober available
        paths = [data[0] for data in movie_data]
        qualities: Dict[Path, Optional[Quality]] = {}

        if self._metadata_prober and self._metadata_prober.is_available:
            qualities = self._metadata_prober.probe_batch_quality(paths, progress_callback)
        else:
            # Fall back to filename parsing
            for i, path in enumerate(paths):
                qualities[path] = self.quality_parser.parse(path.name)
                if progress_callback:
                    progress_callback(i + 1, len(paths), path.name)

        # Create movies with quality
        movies = []
        for path, title, year in movie_data:
            quality = qualities.get(path) or self.quality_parser.parse(path.name)
            movies.append(self._create_movie(path, title, year, quality))

        return movies

    def _parse_movie_folder(self, name: str) -> Tuple[str, Optional[int]]:
        """Parse movie title and year from folder name."""
        # Find year (usually at the end in parentheses)
        year = None
        year_match = None

        # Look for year pattern
        for match in self.YEAR_PATTERN.finditer(name):
            potential_year = int(match.group(1))
            # Valid movie years (1888 = first movie)
            if 1888 <= potential_year <= datetime.now().year + 2:
                year = potential_year
                year_match = match

        # Extract title
        if year_match:
            title = name[: year_match.start()].strip()
            # Also strip trailing punctuation
            title = title.rstrip("([{-_. ")
        else:
            title = name

        # Replace dots/underscores with spaces
        title = title.replace(".", " ").replace("_", " ")

        # Clean up title
        title = self._clean_title(title)

        return title, year

    def _clean_title(self, title: str) -> str:
        """Clean quality tags and other cruft from title."""
        # Remove quality tags
        cleaned = self.CLEAN_PATTERN.sub(" ", title)
        # Normalize whitespace
        cleaned = " ".join(cleaned.split())
        # Strip trailing/leading punctuation
        cleaned = cleaned.strip(".-_()[] ")
        return cleaned

    def _detect_edition(self, filename: str) -> Optional[str]:
        """Detect special edition from filename."""
        filename_lower = filename.lower()
        for edition, patterns in EDITION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower):
                    return edition
        return None

    def _create_movie(
        self,
        path: Path,
        title: str,
        year: Optional[int],
        quality: Optional[Quality] = None,
    ) -> Movie:
        """Create a Movie object from file path.

        Args:
            path: Path to movie file
            title: Parsed movie title
            year: Parsed release year
            quality: Optional pre-computed quality (falls back to filename parsing)
        """
        stat = path.stat()
        is_symlink = path.is_symlink()

        return Movie(
            path=path,
            filename=path.name,
            size_bytes=stat.st_size,
            quality=quality or self.quality_parser.parse(path.name),
            created_at=datetime.fromtimestamp(stat.st_ctime),
            is_symlink=is_symlink,
            symlink_target=path.resolve() if is_symlink else None,
            title=title,
            year=year,
            edition=self._detect_edition(path.name),
        )
