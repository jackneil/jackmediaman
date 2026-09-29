"""Identifier stage for media type detection and metadata extraction."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from jackmediaman.core.logging import get_logger
from jackmediaman.core.operations_db import get_operations_db
from jackmediaman.models.media import Episode, MediaType, Movie
from jackmediaman.models.quality import QualityParser
from jackmediaman.pipeline.context import IdentifiedMedia, ProcessContext
from jackmediaman.pipeline.base import StageOutput, StageResult
from jackmediaman.matchers.fuzzy import normalize_title, similarity_ratio

logger = get_logger("pipeline.identifier")


class IdentifierStage:
    """Identify media files (movie vs TV, metadata extraction)."""

    name = "identifier"

    # High-confidence TV patterns
    TV_PATTERNS = [
        # S01E01 format (most common), with optional range
        re.compile(r"[Ss](\d{1,2})[Ee](\d{1,3})(?:-[Ee]?(\d{1,3}))?"),
        # Multi-episode: S01E01E02E03
        re.compile(r"[Ss](\d{1,2})((?:[Ee]\d{1,3})+)"),
        # 1x01 format
        re.compile(r"(\d{1,2})[xX](\d{1,3})(?:-(\d{1,3}))?"),
        # Season X Episode Y format
        re.compile(r"[Ss]eason\s*(\d+)\s*[Ee]pisode\s*(\d+)", re.IGNORECASE),
    ]

    # Year pattern for movies
    YEAR_PATTERN = re.compile(r"[\(\[\{]?(\d{4})[\)\]\}]?")

    # Quality/source markers to strip from title
    CLEAN_PATTERN = re.compile(
        r"\b("
        r"2160p|4k|1080p|1080i|720p|480p|576p|"
        r"bluray|blu-ray|bdrip|brrip|remux|"
        r"web-dl|webdl|webrip|hdtv|hdrip|dvdrip|dvd|"
        r"x264|x265|h264|h265|hevc|avc|xvid|"
        r"aac|ac3|dts|dd5\.1|truehd|atmos|"
        r"hdr|hdr10|dolby[\s.]?vision|dv|"
        r"proper|repack|internal|limited"
        r")\b",
        re.IGNORECASE,
    )

    # Release group pattern
    GROUP_PATTERN = re.compile(r"-([A-Za-z0-9]+)$")

    def __init__(
        self,
        use_tmdb: bool = True,
        quality_parser: Optional[QualityParser] = None,
    ):
        """
        Initialize the identifier stage.

        Args:
            use_tmdb: Whether to use TMDb for metadata lookup
            quality_parser: Optional quality parser
        """
        self.use_tmdb = use_tmdb
        self.quality_parser = quality_parser or QualityParser()
        self._tmdb_client = None

    def validate(self, context: ProcessContext) -> bool:
        """Check if identification should run."""
        return len(context.video_files) > 0

    def execute(self, context: ProcessContext) -> StageOutput:
        """
        Identify media type and metadata for each file.

        1. Parse filename for TV patterns (S01E01, etc.)
        2. If no TV pattern, assume movie
        3. Extract title/year for movies, show/season/episode for TV
        4. Optionally lookup TMDb for accurate metadata
        5. Parse quality from filename
        """
        # Lazy load TMDb client
        if self.use_tmdb and not context.skip_tmdb and self._tmdb_client is None:
            try:
                from jackmediaman.services.renamer import TMDbTVClient

                self._tmdb_client = TMDbTVClient()
            except Exception:
                self._tmdb_client = None

        identified = []
        failed = []

        db = get_operations_db()

        for video_file in context.video_files:
            try:
                media = self._identify_file(video_file, context)
                identified.append(media)

                # Log identification result
                if media.media_type == MediaType.episode:
                    ep = media.media_item
                    db.log_activity(
                        "INFO",
                        "identification",
                        f"Identified TV: {media.canonical_title} S{ep.season:02d}E{ep.episode:02d}",
                        source_path=str(video_file),
                        details=json.dumps({
                            "type": "tv",
                            "title": media.canonical_title,
                            "season": ep.season,
                            "episode": ep.episode,
                            "method": media.identification_method,
                            "tmdb_id": media.tmdb_id,
                        }),
                        session_id=context.session_id,
                    )
                else:
                    movie = media.media_item
                    db.log_activity(
                        "INFO",
                        "identification",
                        f"Identified Movie: {media.canonical_title} ({media.canonical_year or 'unknown'})",
                        source_path=str(video_file),
                        details=json.dumps({
                            "type": "movie",
                            "title": media.canonical_title,
                            "year": media.canonical_year,
                            "method": media.identification_method,
                            "tmdb_id": media.tmdb_id,
                        }),
                        session_id=context.session_id,
                    )

            except Exception as e:
                failed.append((video_file, str(e)))
                context.add_error(
                    stage=self.name,
                    error=f"Failed to identify {video_file.name}: {e}",
                    path=video_file,
                )
                db.log_activity(
                    "ERROR",
                    "identification",
                    f"Failed to identify: {video_file.name} - {e}",
                    source_path=str(video_file),
                    session_id=context.session_id,
                )

        context.identified_media = identified

        if not identified:
            return StageOutput(
                result=StageResult.FAILED,
                message="No media files could be identified",
                items_failed=len(failed),
            )

        return StageOutput(
            result=StageResult.SUCCESS if not failed else StageResult.PARTIAL,
            message=f"Identified {len(identified)} media files",
            items_processed=len(identified),
            items_failed=len(failed),
        )

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        """No rollback needed for identification."""
        return True

    def _identify_file(
        self, path: Path, context: ProcessContext
    ) -> IdentifiedMedia:
        """Identify a single media file."""
        filename = path.name

        # First check: look for TV patterns
        tv_info = self._extract_tv_info(filename)
        if tv_info:
            return self._create_tv_identified(path, tv_info, context)

        # No TV pattern: treat as movie
        movie_info = self._extract_movie_info(filename, path)
        return self._create_movie_identified(path, movie_info, context)

    def _extract_tv_info(self, filename: str) -> Optional[dict]:
        """Extract TV show info from filename."""
        # Try multi-episode pattern first (S01E01E02E03)
        multi_match = self.TV_PATTERNS[1].search(filename)
        if multi_match:
            season = int(multi_match.group(1))
            ep_part = multi_match.group(2)
            episodes = [int(e) for e in re.findall(r"[Ee](\d{1,3})", ep_part)]
            if len(episodes) >= 2:
                title = self._extract_title_before_match(filename, multi_match)
                return {
                    "title": title,
                    "season": season,
                    "episodes": episodes,
                }

        # Try standard patterns
        for pattern in [self.TV_PATTERNS[0], self.TV_PATTERNS[2], self.TV_PATTERNS[3]]:
            match = pattern.search(filename)
            if match:
                groups = match.groups()
                season = int(groups[0])
                episodes = [int(groups[1])]

                # Check for range (S01E01-03)
                if len(groups) >= 3 and groups[2]:
                    end_ep = int(groups[2])
                    if end_ep > episodes[0]:
                        episodes = list(range(episodes[0], end_ep + 1))

                title = self._extract_title_before_match(filename, match)
                return {
                    "title": title,
                    "season": season,
                    "episodes": episodes,
                }

        return None

    def _extract_movie_info(self, filename: str, path: Path) -> dict:
        """Extract movie info from filename."""
        # Remove extension
        name = path.stem

        # Remove release group
        name = self.GROUP_PATTERN.sub("", name)

        # Find year
        year = None
        year_match = None
        for match in self.YEAR_PATTERN.finditer(name):
            potential_year = int(match.group(1))
            if 1888 <= potential_year <= datetime.now().year + 2:
                year = potential_year
                year_match = match

        # Extract title
        if year_match:
            title = name[: year_match.start()]
        else:
            title = name

        # Clean title
        title = self._clean_title(title)

        return {
            "title": title,
            "year": year,
        }

    def _extract_title_before_match(self, filename: str, match: re.Match) -> str:
        """Extract and clean title from before the regex match."""
        title = filename[: match.start()]
        return self._clean_title(title)

    def _clean_title(self, title: str) -> str:
        """Clean quality tags and scene cruft from title."""
        # Replace dots/underscores with spaces
        cleaned = title.replace(".", " ").replace("_", " ")
        # Remove quality tags
        cleaned = self.CLEAN_PATTERN.sub(" ", cleaned)
        # Normalize whitespace
        cleaned = " ".join(cleaned.split())
        # Strip punctuation
        cleaned = cleaned.strip(".-_()[] ")
        return cleaned

    def _create_tv_identified(
        self,
        path: Path,
        tv_info: dict,
        context: ProcessContext,
    ) -> IdentifiedMedia:
        """Create IdentifiedMedia for TV episode."""
        title = tv_info["title"]
        season = tv_info["season"]
        episodes = tv_info["episodes"]

        # Try TMDb lookup for canonical title
        tmdb_id = None
        canonical_title = title
        if self._tmdb_client and self._tmdb_client.api_key:
            try:
                tmdb_id = self._tmdb_client.search_tv(title)
                if tmdb_id:
                    canonical_title = title  # Could enhance with TMDb data
            except Exception:
                pass

        # Create Episode model
        quality = self.quality_parser.parse(path.name)
        stat = path.stat()
        is_symlink = path.is_symlink()

        episode = Episode(
            path=path,
            filename=path.name,
            size_bytes=stat.st_size,
            quality=quality,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            is_symlink=is_symlink,
            symlink_target=path.resolve() if is_symlink else None,
            series_name=canonical_title,
            season_number=season,
            episode_numbers=episodes,
        )

        return IdentifiedMedia(
            source_path=path,
            media_type=MediaType.EPISODE,
            media_item=episode,
            confidence=0.9 if tmdb_id else 0.7,
            identification_method="tmdb" if tmdb_id else "filename",
            tmdb_id=tmdb_id,
            canonical_title=canonical_title,
        )

    def _create_movie_identified(
        self,
        path: Path,
        movie_info: dict,
        context: ProcessContext,
    ) -> IdentifiedMedia:
        """Create IdentifiedMedia for movie."""
        title = movie_info["title"]
        year = movie_info["year"]

        # Try TMDb lookup
        tmdb_id = None
        canonical_title = title
        canonical_year = year
        if self._tmdb_client and self._tmdb_client.api_key:
            try:
                # Search movie
                movie_id = self._tmdb_client.search_movie(title, year)
                if movie_id:
                    tmdb_id = movie_id
                    # Get canonical info
                    details = self._tmdb_client.get_movie_details(movie_id)
                    if details:
                        canonical_title = details.get("title") or title
                        canonical_year = details.get("year") or year
                        if canonical_year:
                            canonical_year = int(canonical_year)
            except Exception:
                pass

        # Create Movie model
        quality = self.quality_parser.parse(path.name)
        stat = path.stat()
        is_symlink = path.is_symlink()

        movie = Movie(
            path=path,
            filename=path.name,
            size_bytes=stat.st_size,
            quality=quality,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            is_symlink=is_symlink,
            symlink_target=path.resolve() if is_symlink else None,
            title=canonical_title,
            year=canonical_year,
            tmdb_id=tmdb_id,
        )

        return IdentifiedMedia(
            source_path=path,
            media_type=MediaType.MOVIE,
            media_item=movie,
            confidence=0.95 if tmdb_id else 0.6,
            identification_method="tmdb" if tmdb_id else "filename",
            tmdb_id=tmdb_id,
            canonical_title=canonical_title,
            canonical_year=canonical_year,
        )
