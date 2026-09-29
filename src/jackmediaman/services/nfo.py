"""NFO service for generating Kodi-compatible XML metadata files."""

import re
from html import escape
from pathlib import Path
from typing import Callable, List, Optional

from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger
from jackmediaman.models.nfo import (
    NFOType,
    NFOMovieMetadata,
    NFOTVShowMetadata,
    NFOEpisodeMetadata,
    NFOResult,
    NFOScanResult,
    NFOBatchResult,
)
from jackmediaman.services.tmdb import TMDbService

logger = get_logger("nfo")


class NFOService:
    """Generate Kodi-compatible NFO metadata files."""

    def __init__(self, tmdb_service: Optional[TMDbService] = None):
        """Initialize the NFO service.

        Args:
            tmdb_service: Optional TMDbService instance
        """
        self._tmdb = tmdb_service
        self._settings = get_settings()

    @property
    def tmdb(self) -> TMDbService:
        """Lazy-load TMDb service."""
        if self._tmdb is None:
            self._tmdb = TMDbService()
        return self._tmdb

    def generate_movie_nfo(
        self,
        folder: Path,
        title: str,
        year: Optional[int] = None,
        tmdb_id: Optional[int] = None,
        overwrite: bool = False,
    ) -> NFOResult:
        """Generate movie.nfo in a movie folder.

        Args:
            folder: Path to the movie folder
            title: Movie title (for TMDb search if no tmdb_id)
            year: Movie year (for TMDb search)
            tmdb_id: Optional TMDb ID (skips search if provided)
            overwrite: Whether to overwrite existing NFO

        Returns:
            NFOResult with operation details
        """
        nfo_path = folder / "movie.nfo"

        # Check if NFO already exists
        if nfo_path.exists() and not overwrite:
            return NFOResult(
                path=nfo_path,
                success=False,
                skipped=True,
                reason="exists",
                nfo_type=NFOType.MOVIE,
            )

        # Get TMDb ID if not provided
        if not tmdb_id:
            tmdb_id = self.tmdb.search_movie(title, year)

        if not tmdb_id:
            return NFOResult(
                path=nfo_path,
                success=False,
                reason="not_found",
                nfo_type=NFOType.MOVIE,
            )

        # Get full metadata (cached)
        metadata = self.tmdb.get_movie_details(tmdb_id)

        if not metadata:
            return NFOResult(
                path=nfo_path,
                success=False,
                reason="api_error",
                nfo_type=NFOType.MOVIE,
            )

        # Generate XML
        xml = self._generate_movie_xml(metadata)

        # Write file
        try:
            folder.mkdir(parents=True, exist_ok=True)
            nfo_path.write_text(xml, encoding="utf-8")
            return NFOResult(
                path=nfo_path,
                success=True,
                nfo_type=NFOType.MOVIE,
            )
        except OSError as e:
            return NFOResult(
                path=nfo_path,
                success=False,
                reason=f"write_error: {e}",
                nfo_type=NFOType.MOVIE,
            )

    def generate_show_nfo(
        self,
        folder: Path,
        show_name: str,
        tmdb_id: Optional[int] = None,
        overwrite: bool = False,
    ) -> NFOResult:
        """Generate tvshow.nfo in a TV show folder.

        Args:
            folder: Path to the TV show folder
            show_name: Show name (for TMDb search if no tmdb_id)
            tmdb_id: Optional TMDb ID (skips search if provided)
            overwrite: Whether to overwrite existing NFO

        Returns:
            NFOResult with operation details
        """
        nfo_path = folder / "tvshow.nfo"

        if nfo_path.exists() and not overwrite:
            return NFOResult(
                path=nfo_path,
                success=False,
                skipped=True,
                reason="exists",
                nfo_type=NFOType.TVSHOW,
            )

        # Get TMDb ID if not provided
        if not tmdb_id:
            tmdb_id = self.tmdb.search_tv(show_name)

        if not tmdb_id:
            return NFOResult(
                path=nfo_path,
                success=False,
                reason="not_found",
                nfo_type=NFOType.TVSHOW,
            )

        # Get full metadata
        metadata = self.tmdb.get_tv_details(tmdb_id)

        if not metadata:
            return NFOResult(
                path=nfo_path,
                success=False,
                reason="api_error",
                nfo_type=NFOType.TVSHOW,
            )

        # Generate XML
        xml = self._generate_tvshow_xml(metadata)

        try:
            folder.mkdir(parents=True, exist_ok=True)
            nfo_path.write_text(xml, encoding="utf-8")
            return NFOResult(
                path=nfo_path,
                success=True,
                nfo_type=NFOType.TVSHOW,
            )
        except OSError as e:
            return NFOResult(
                path=nfo_path,
                success=False,
                reason=f"write_error: {e}",
                nfo_type=NFOType.TVSHOW,
            )

    def generate_episode_nfo(
        self,
        video_file: Path,
        show_name: str,
        season: int,
        episode: int,
        tmdb_id: Optional[int] = None,
        overwrite: bool = False,
    ) -> NFOResult:
        """Generate episode NFO alongside a video file.

        Args:
            video_file: Path to the video file
            show_name: Show name (for TMDb search if no tmdb_id)
            season: Season number
            episode: Episode number
            tmdb_id: Optional TMDb show ID
            overwrite: Whether to overwrite existing NFO

        Returns:
            NFOResult with operation details
        """
        # NFO has same name as video but .nfo extension
        nfo_path = video_file.with_suffix(".nfo")

        if nfo_path.exists() and not overwrite:
            return NFOResult(
                path=nfo_path,
                success=False,
                skipped=True,
                reason="exists",
                nfo_type=NFOType.EPISODE,
            )

        # Get TMDb ID if not provided
        if not tmdb_id:
            tmdb_id = self.tmdb.search_tv(show_name)

        if not tmdb_id:
            return NFOResult(
                path=nfo_path,
                success=False,
                reason="not_found",
                nfo_type=NFOType.EPISODE,
            )

        # Get episode details
        metadata = self.tmdb.get_episode_details(tmdb_id, season, episode)

        if not metadata:
            return NFOResult(
                path=nfo_path,
                success=False,
                reason="api_error",
                nfo_type=NFOType.EPISODE,
            )

        # Add show title to metadata for context
        metadata.show_title = show_name

        # Generate XML
        xml = self._generate_episode_xml(metadata)

        try:
            nfo_path.write_text(xml, encoding="utf-8")
            return NFOResult(
                path=nfo_path,
                success=True,
                nfo_type=NFOType.EPISODE,
            )
        except OSError as e:
            return NFOResult(
                path=nfo_path,
                success=False,
                reason=f"write_error: {e}",
                nfo_type=NFOType.EPISODE,
            )

    def scan_movies_library(self) -> List[NFOScanResult]:
        """Scan movies library for NFO status.

        Returns:
            List of NFOScanResult for each movie
        """
        results = []
        movies_dir = self._settings.movies_dir

        if not movies_dir.exists():
            return results

        for item in movies_dir.iterdir():
            if item.is_dir():
                nfo_path = item / "movie.nfo"
                title, year = self._parse_movie_name(item.name)
                results.append(
                    NFOScanResult(
                        path=item,
                        media_type=NFOType.MOVIE,
                        title=f"{title} ({year})" if year else title,
                        has_nfo=nfo_path.exists(),
                        nfo_path=nfo_path if nfo_path.exists() else None,
                    )
                )

        return results

    def scan_tv_library(self) -> List[NFOScanResult]:
        """Scan TV library for NFO status.

        Returns:
            List of NFOScanResult for each show
        """
        results = []
        tv_dir = self._settings.tv_dir

        if not tv_dir.exists():
            return results

        for show_folder in tv_dir.iterdir():
            if show_folder.is_dir():
                nfo_path = show_folder / "tvshow.nfo"
                results.append(
                    NFOScanResult(
                        path=show_folder,
                        media_type=NFOType.TVSHOW,
                        title=show_folder.name,
                        has_nfo=nfo_path.exists(),
                        nfo_path=nfo_path if nfo_path.exists() else None,
                    )
                )

        return results

    def scan_library(
        self,
        media_type: str = "both",
    ) -> List[NFOScanResult]:
        """Scan library for NFO status.

        Args:
            media_type: "movies", "tv", or "both"

        Returns:
            List of NFOScanResult for all media
        """
        results = []

        if media_type in ("movies", "both"):
            results.extend(self.scan_movies_library())

        if media_type in ("tv", "both"):
            results.extend(self.scan_tv_library())

        return results

    def generate_for_movies_library(
        self,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> NFOBatchResult:
        """Generate NFO files for all movies.

        Args:
            overwrite: Whether to overwrite existing NFOs
            progress_callback: Optional callback(current, total, name)

        Returns:
            NFOBatchResult with operation summary
        """
        batch = NFOBatchResult()
        movies_dir = self._settings.movies_dir

        if not movies_dir.exists():
            return batch

        # Find all movie folders
        movie_folders = [d for d in movies_dir.iterdir() if d.is_dir()]

        for i, folder in enumerate(movie_folders):
            if progress_callback:
                progress_callback(i + 1, len(movie_folders), folder.name)

            title, year = self._parse_movie_name(folder.name)
            result = self.generate_movie_nfo(
                folder=folder,
                title=title,
                year=year,
                overwrite=overwrite,
            )
            batch.add(result)

        return batch

    def generate_for_tv_library(
        self,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> NFOBatchResult:
        """Generate NFO files for all TV shows.

        Args:
            overwrite: Whether to overwrite existing NFOs
            progress_callback: Optional callback(current, total, name)

        Returns:
            NFOBatchResult with operation summary
        """
        batch = NFOBatchResult()
        tv_dir = self._settings.tv_dir

        if not tv_dir.exists():
            return batch

        show_folders = [d for d in tv_dir.iterdir() if d.is_dir()]

        for i, show_folder in enumerate(show_folders):
            if progress_callback:
                progress_callback(i + 1, len(show_folders), show_folder.name)

            # Generate tvshow.nfo
            result = self.generate_show_nfo(
                folder=show_folder,
                show_name=show_folder.name,
                overwrite=overwrite,
            )
            batch.add(result)

        return batch

    def generate_for_library(
        self,
        media_type: str = "both",
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> NFOBatchResult:
        """Generate NFO files for entire library.

        Args:
            media_type: "movies", "tv", or "both"
            overwrite: Whether to overwrite existing NFOs
            progress_callback: Optional callback(current, total, name)

        Returns:
            NFOBatchResult with operation summary
        """
        batch = NFOBatchResult()

        if media_type in ("movies", "both"):
            movie_batch = self.generate_for_movies_library(overwrite, progress_callback)
            batch.total += movie_batch.total
            batch.generated += movie_batch.generated
            batch.skipped += movie_batch.skipped
            batch.failed += movie_batch.failed
            batch.results.extend(movie_batch.results)

        if media_type in ("tv", "both"):
            tv_batch = self.generate_for_tv_library(overwrite, progress_callback)
            batch.total += tv_batch.total
            batch.generated += tv_batch.generated
            batch.skipped += tv_batch.skipped
            batch.failed += tv_batch.failed
            batch.results.extend(tv_batch.results)

        return batch

    def _generate_movie_xml(self, metadata: NFOMovieMetadata) -> str:
        """Generate movie.nfo XML content.

        Args:
            metadata: Movie metadata

        Returns:
            XML string
        """
        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            "<movie>",
            f"    <title>{escape(metadata.title)}</title>",
        ]

        if metadata.year:
            lines.append(f"    <year>{metadata.year}</year>")
        if metadata.tmdb_id:
            lines.append(f"    <tmdbid>{metadata.tmdb_id}</tmdbid>")
        if metadata.imdb_id:
            lines.append(f"    <imdbid>{metadata.imdb_id}</imdbid>")
        if metadata.tagline:
            lines.append(f"    <tagline>{escape(metadata.tagline)}</tagline>")
        if metadata.plot:
            lines.append(f"    <plot>{escape(metadata.plot)}</plot>")
        if metadata.rating is not None:
            lines.append(f"    <rating>{metadata.rating:.1f}</rating>")
        if metadata.runtime:
            lines.append(f"    <runtime>{metadata.runtime}</runtime>")
        for genre in metadata.genres:
            lines.append(f"    <genre>{escape(genre)}</genre>")
        if metadata.director:
            lines.append(f"    <director>{escape(metadata.director)}</director>")
        if metadata.studio:
            lines.append(f"    <studio>{escape(metadata.studio)}</studio>")

        lines.append("</movie>")
        return "\n".join(lines)

    def _generate_tvshow_xml(self, metadata: NFOTVShowMetadata) -> str:
        """Generate tvshow.nfo XML content.

        Args:
            metadata: TV show metadata

        Returns:
            XML string
        """
        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            "<tvshow>",
            f"    <title>{escape(metadata.title)}</title>",
        ]

        if metadata.year:
            lines.append(f"    <year>{metadata.year}</year>")
        if metadata.tmdb_id:
            lines.append(f"    <tmdbid>{metadata.tmdb_id}</tmdbid>")
        if metadata.tvdb_id:
            lines.append(f"    <tvdbid>{metadata.tvdb_id}</tvdbid>")
        if metadata.imdb_id:
            lines.append(f"    <imdbid>{metadata.imdb_id}</imdbid>")
        if metadata.plot:
            lines.append(f"    <plot>{escape(metadata.plot)}</plot>")
        if metadata.rating is not None:
            lines.append(f"    <rating>{metadata.rating:.1f}</rating>")
        for genre in metadata.genres:
            lines.append(f"    <genre>{escape(genre)}</genre>")
        if metadata.studio:
            lines.append(f"    <studio>{escape(metadata.studio)}</studio>")
        if metadata.status:
            lines.append(f"    <status>{escape(metadata.status)}</status>")

        lines.append("</tvshow>")
        return "\n".join(lines)

    def _generate_episode_xml(self, metadata: NFOEpisodeMetadata) -> str:
        """Generate episode NFO XML content.

        Args:
            metadata: Episode metadata

        Returns:
            XML string
        """
        lines = [
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            "<episodedetails>",
            f"    <title>{escape(metadata.title)}</title>",
            f"    <season>{metadata.season}</season>",
            f"    <episode>{metadata.episode}</episode>",
        ]

        if metadata.show_title:
            lines.append(f"    <showtitle>{escape(metadata.show_title)}</showtitle>")
        if metadata.aired:
            lines.append(f"    <aired>{metadata.aired.isoformat()}</aired>")
        if metadata.plot:
            lines.append(f"    <plot>{escape(metadata.plot)}</plot>")
        if metadata.rating is not None:
            lines.append(f"    <rating>{metadata.rating:.1f}</rating>")
        if metadata.runtime:
            lines.append(f"    <runtime>{metadata.runtime}</runtime>")
        if metadata.director:
            lines.append(f"    <director>{escape(metadata.director)}</director>")
        if metadata.tmdb_id:
            lines.append(f"    <tmdbid>{metadata.tmdb_id}</tmdbid>")

        lines.append("</episodedetails>")
        return "\n".join(lines)

    def _parse_movie_name(self, folder_name: str) -> tuple:
        """Parse movie title and year from folder name.

        Args:
            folder_name: Movie folder name (e.g., "Movie Name (2024)")

        Returns:
            Tuple of (title, year) where year may be None
        """
        # Match "Movie Name (2024)" or "Movie Name [2024]"
        match = re.match(r"^(.+?)\s*[\(\[](\d{4})[\)\]]", folder_name)
        if match:
            return match.group(1).strip(), int(match.group(2))

        return folder_name, None

    def get_nfo_stats(self) -> dict:
        """Get statistics about NFO coverage in the library.

        Returns:
            Dict with stats for movies and TV shows
        """
        stats = {
            "movies": {"total": 0, "with_nfo": 0, "missing_nfo": 0},
            "tv": {"total": 0, "with_nfo": 0, "missing_nfo": 0},
        }

        # Movies
        if self._settings.movies_dir.exists():
            for item in self._settings.movies_dir.iterdir():
                if item.is_dir():
                    stats["movies"]["total"] += 1
                    if (item / "movie.nfo").exists():
                        stats["movies"]["with_nfo"] += 1
                    else:
                        stats["movies"]["missing_nfo"] += 1

        # TV Shows
        if self._settings.tv_dir.exists():
            for show_folder in self._settings.tv_dir.iterdir():
                if show_folder.is_dir():
                    stats["tv"]["total"] += 1
                    if (show_folder / "tvshow.nfo").exists():
                        stats["tv"]["with_nfo"] += 1
                    else:
                        stats["tv"]["missing_nfo"] += 1

        return stats
