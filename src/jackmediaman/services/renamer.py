"""Renamer service for standardizing media filenames."""

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from jackmediaman.models.media import MediaItem, Movie, Episode
from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger
from jackmediaman.core.tmdb_cache import TMDbCache
from jackmediaman.core.utils import sanitize_filename, get_resolution_tag
from jackmediaman.matchers.tmdb import TMDbClient

logger = get_logger("services.renamer")


@dataclass
class RenameResult:
    """Result of a single file rename operation."""

    item: MediaItem
    old_path: Path
    new_path: Path
    success: bool
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None


@dataclass
class RenameSummary:
    """Summary of all rename operations."""

    total_files: int
    renamed: int
    skipped: int
    failed: int
    results: List[RenameResult]


class TMDbTVClient(TMDbClient):
    """Extended TMDb client with TV show support."""

    def search_tv(self, name: str) -> Optional[int]:
        """
        Search for a TV show and return its TMDb ID.

        Args:
            name: Show name to search for

        Returns:
            TMDb TV show ID if found, None otherwise
        """
        if not self.api_key:
            return None

        cache_key = f"tv_search:{name}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            # Empty dict means cached "no result"
            return cached.get("id") if cached else None

        self._rate_limit()

        try:
            import httpx
            response = httpx.get(
                f"{self.BASE_URL}/search/tv",
                params={"api_key": self.api_key, "query": name},
                timeout=10.0,
            )
            response.raise_for_status()
            results = response.json().get("results", [])

            if results:
                show_id = results[0]["id"]
                self._set_cache(
                    cache_key,
                    TMDbCache.TYPE_TV_SEARCH,
                    name,
                    {"id": show_id},
                )
                return show_id

            self._set_cache(cache_key, TMDbCache.TYPE_TV_SEARCH, name, None)
            return None

        except Exception:
            return None

    def get_episode_title(
        self, show_id: int, season: int, episode: int
    ) -> Optional[str]:
        """
        Get episode title from TMDb.

        Uses season-based fetching for efficiency: when an episode title
        isn't cached, fetches all episodes for that season in one API call.

        Args:
            show_id: TMDb TV show ID
            season: Season number
            episode: Episode number

        Returns:
            Episode title if found, None otherwise
        """
        if not self.api_key:
            return None

        # Check episode cache first
        cache_key = f"episode:{show_id}:s{season}e{episode}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            # Empty dict means cached "no result"
            return cached.get("title") if cached else None

        # Fetch whole season (caches all episodes)
        season_eps = self.get_season_episodes(show_id, season)
        return season_eps.get(episode)

    def get_season_episodes(self, show_id: int, season: int) -> dict:
        """Fetch all episode titles for a season in one API call.

        This is more efficient than fetching individual episodes when
        processing multiple episodes from the same season.

        Args:
            show_id: TMDb TV show ID
            season: Season number

        Returns:
            Dict mapping episode_number -> episode_title
        """
        if not self.api_key:
            return {}

        cache_key = f"season:{show_id}:s{season}"
        query_display = f"Season {season} (show:{show_id})"
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached if cached else {}

        self._rate_limit()

        try:
            import httpx
            response = httpx.get(
                f"{self.BASE_URL}/tv/{show_id}/season/{season}",
                params={"api_key": self.api_key},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            episodes = {}
            for ep in data.get("episodes", []):
                ep_num = ep.get("episode_number")
                title = ep.get("name")
                if ep_num is not None and title:
                    episodes[ep_num] = title
                    # Also cache individual episode for compatibility
                    ep_cache_key = f"episode:{show_id}:s{season}e{ep_num}"
                    ep_query = f"S{season:02d}E{ep_num:02d} (show:{show_id})"
                    self._set_cache(
                        ep_cache_key,
                        TMDbCache.TYPE_EPISODE_TITLE,
                        ep_query,
                        {"title": title},
                    )

            self._set_cache(
                cache_key,
                TMDbCache.TYPE_SEASON_EPISODES,
                query_display,
                episodes if episodes else None,
            )
            return episodes

        except Exception:
            return {}

    def get_movie_details(self, movie_id: int) -> Optional[dict]:
        """
        Get movie details from TMDb.

        Args:
            movie_id: TMDb movie ID

        Returns:
            Movie details dict with title and year
        """
        if not self.api_key:
            return None

        cache_key = f"movie_details:{movie_id}"
        query_display = f"movie:{movie_id}"
        cached = self._get_cached(cache_key)
        if cached is not None:
            # Empty dict means cached "no result"
            return cached if cached else None

        self._rate_limit()

        try:
            import httpx
            response = httpx.get(
                f"{self.BASE_URL}/movie/{movie_id}",
                params={"api_key": self.api_key},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            result = {
                "title": data.get("title"),
                "year": data.get("release_date", "")[:4] if data.get("release_date") else None,
            }
            self._set_cache(
                cache_key,
                TMDbCache.TYPE_MOVIE_DETAILS,
                query_display,
                result,
            )
            return result

        except Exception:
            return None


class RenameService:
    """Service for renaming media files to standardized format."""

    # Target formats:
    # TV: Show Name - S01E01 - Episode Title.ext
    # Movie: Movie Name (Year).ext

    def __init__(self, tmdb_client: Optional[TMDbTVClient] = None):
        """
        Initialize the rename service.

        Args:
            tmdb_client: Optional TMDb client for lookups
        """
        self.settings = get_settings()
        self.tmdb_client = tmdb_client or TMDbTVClient()
        self._show_id_cache: dict = {}
        self._plex_service: Optional["PlexService"] = None

    def _get_plex_service(self) -> Optional["PlexService"]:
        """Lazy-load Plex service only if configured."""
        if self._plex_service is None:
            try:
                from jackmediaman.services.plex import PlexService

                service = PlexService()
                if service.is_configured:
                    self._plex_service = service
            except ImportError:
                pass
        return self._plex_service

    def _notify_plex_rename(self, old_path: Path, new_path: Path) -> None:
        """Notify Plex about a rename (both old and new locations)."""
        plex = self._get_plex_service()
        if not plex:
            return

        # Use the service's notify_rename method which handles both paths
        plex.notify_rename(old_path, new_path)

    def generate_new_name(self, item: MediaItem) -> Optional[str]:
        """
        Generate a new standardized filename for a media item.

        Args:
            item: Media item to rename

        Returns:
            New filename (without path), or None if can't generate
        """
        if isinstance(item, Episode):
            return self._generate_episode_name(item)
        elif isinstance(item, Movie):
            return self._generate_movie_name(item)
        return None

    def _generate_episode_name(self, episode: Episode) -> Optional[str]:
        """Generate standardized name for TV episode.

        Format: Show Name - S01E01 - Episode Title [1080p].ext
        """
        # Get extension from original filename
        ext = episode.path.suffix

        # Build episode code (S01E01 or S01E01-E03 for multi-episode)
        if len(episode.episode_numbers) == 1:
            ep_code = f"S{episode.season_number:02d}E{episode.episode_numbers[0]:02d}"
        else:
            # Multi-episode: S01E01-E03
            eps = episode.episode_numbers
            ep_code = f"S{episode.season_number:02d}E{eps[0]:02d}-E{eps[-1]:02d}"

        # Try to get episode title from TMDb
        episode_title = None
        if self.tmdb_client.api_key and len(episode.episode_numbers) == 1:
            show_id = self._get_show_id(episode.series_name)
            if show_id:
                episode_title = self.tmdb_client.get_episode_title(
                    show_id, episode.season_number, episode.episode_numbers[0]
                )

        # Build final name
        series_name = sanitize_filename(episode.series_name)
        if episode_title:
            episode_title = sanitize_filename(episode_title)
            base_name = f"{series_name} - {ep_code} - {episode_title}"
        else:
            base_name = f"{series_name} - {ep_code}"

        # Add resolution tag if available
        resolution_tag = self._get_resolution_tag(episode)
        if resolution_tag:
            base_name = f"{base_name} [{resolution_tag}]"

        return f"{base_name}{ext}"

    def _generate_movie_name(self, movie: Movie) -> Optional[str]:
        """Generate standardized name for movie.

        Format: Movie Name (Year) [2160p].ext
        """
        ext = movie.path.suffix

        title = movie.title
        year = movie.year

        # Try to get canonical info from TMDb
        if self.tmdb_client.api_key:
            tmdb_id = movie.tmdb_id
            if not tmdb_id:
                tmdb_id = self.tmdb_client.search_movie(movie.title, movie.year)

            if tmdb_id:
                details = self.tmdb_client.get_movie_details(tmdb_id)
                if details:
                    title = details.get("title") or title
                    year = details.get("year") or year

        # Build final name
        title = sanitize_filename(title)
        if year:
            base_name = f"{title} ({year})"
        else:
            base_name = title

        # Add resolution tag if available
        resolution_tag = self._get_resolution_tag(movie)
        if resolution_tag:
            base_name = f"{base_name} [{resolution_tag}]"

        return f"{base_name}{ext}"

    def _get_resolution_tag(self, item: MediaItem) -> Optional[str]:
        """Get resolution tag for filename.

        Args:
            item: Media item with quality info

        Returns:
            Resolution string like '2160p', '1080p', etc. or None if unknown
        """
        return get_resolution_tag(item)

    def _get_show_id(self, series_name: str) -> Optional[int]:
        """Get TMDb show ID, using cache."""
        if series_name in self._show_id_cache:
            return self._show_id_cache[series_name]

        show_id = self.tmdb_client.search_tv(series_name)
        self._show_id_cache[series_name] = show_id
        return show_id

    def _find_associated_files(self, video_path: Path) -> List[Path]:
        """Find subtitle and other sidecar files associated with a video file.

        Finds files that match the video's base name, such as:
        - Movie.srt (no language code)
        - Movie.en.srt (language code)
        - Movie.en.forced.srt (language + type)
        - Movie.en.sdh.srt (language + type)
        - Movie.jpg / Movie.png (artwork matching video name)

        Note: poster.jpg is NOT renamed as it's a generic name that doesn't
        need to match the video filename for Plex compatibility.

        Args:
            video_path: Path to the video file

        Returns:
            List of associated file paths
        """
        stem = video_path.stem  # e.g., "Movie" from "Movie.mkv"
        parent = video_path.parent
        associated = []

        # Extensions to check for associated files
        # .srt = subtitles, .jpg/.png = artwork that matches video name
        extensions = [".srt", ".jpg", ".png"]

        for ext in extensions:
            for file in parent.glob(f"{stem}*{ext}"):
                file_stem = file.stem  # e.g., "Movie.en" or "Movie"
                # Verify it's actually associated (not just starts with same letters)
                # Valid: "Movie" or "Movie.en" (starts with stem + ".")
                # Skip generic poster.jpg (doesn't match video name pattern)
                if file.name.lower() == "poster.jpg" or file.name.lower() == "poster.png":
                    continue
                if file_stem == stem or file_stem.startswith(f"{stem}."):
                    associated.append(file)

        return associated

    def preview_rename(self, item: MediaItem) -> Optional[tuple]:
        """
        Preview a rename without executing it.

        Args:
            item: Media item to preview

        Returns:
            Tuple of (old_name, new_name) or None if no change
        """
        new_name = self.generate_new_name(item)
        if not new_name:
            return None

        old_name = item.filename
        if old_name == new_name:
            return None

        return (old_name, new_name)

    def rename(self, item: MediaItem, dry_run: bool = True) -> RenameResult:
        """
        Rename a single media file and its associated subtitle files.

        Args:
            item: Media item to rename
            dry_run: If True, don't actually rename

        Returns:
            RenameResult with details of the operation
        """
        old_path = item.path
        new_name = self.generate_new_name(item)

        if not new_name:
            return RenameResult(
                item=item,
                old_path=old_path,
                new_path=old_path,
                success=False,
                skipped=True,
                skip_reason="Could not generate new name",
            )

        new_path = old_path.parent / new_name

        # Skip if name unchanged
        if old_path.name == new_name:
            return RenameResult(
                item=item,
                old_path=old_path,
                new_path=new_path,
                success=True,
                skipped=True,
                skip_reason="Already named correctly",
            )

        # Check if target already exists
        if new_path.exists() and new_path != old_path:
            return RenameResult(
                item=item,
                old_path=old_path,
                new_path=new_path,
                success=False,
                error=f"Target file already exists: {new_path.name}",
            )

        # Find associated files BEFORE renaming (so we can find them by old name)
        associated_files = self._find_associated_files(old_path)

        if dry_run:
            return RenameResult(
                item=item,
                old_path=old_path,
                new_path=new_path,
                success=True,
            )

        # Actually perform the rename
        try:
            # Query DB for symlinks pointing to this file BEFORE rename
            symlinks_to_update = []
            try:
                from jackmediaman.core.operations_db import get_operations_db
                ops_db = get_operations_db()
                symlinks_to_update = ops_db.get_symlinks_for_file(old_path)
            except Exception as db_err:
                logger.debug(f"Could not query operations DB: {db_err}")

            # Perform the rename
            shutil.move(str(old_path), str(new_path))

            # Update symlinks that were pointing to the old path
            updated_symlinks = 0
            for symlink_path in symlinks_to_update:
                if symlink_path.is_symlink():
                    try:
                        # Remove old symlink
                        symlink_path.unlink()
                        # Create new symlink pointing to renamed file
                        try:
                            rel_target = os.path.relpath(new_path, symlink_path.parent)
                            os.symlink(rel_target, symlink_path)
                        except ValueError:
                            # Different drives on Windows, use absolute
                            os.symlink(str(new_path), str(symlink_path))
                        updated_symlinks += 1
                        logger.info(f"Updated symlink: {symlink_path.name} -> {new_path.name}")
                    except OSError as e:
                        logger.warning(f"Failed to update symlink {symlink_path}: {e}")

            if updated_symlinks > 0:
                logger.info(f"Updated {updated_symlinks} symlink(s) for renamed file")

            # Log to operations database
            try:
                ops_db = get_operations_db()
                ops_db.log_operation(
                    op_type="rename",
                    source=old_path,
                    dest=new_path,
                    success=True,
                )
                ops_db.update_media_file_path(old_path, new_path)
                # Update symlink targets in DB
                for symlink_path in symlinks_to_update:
                    ops_db.update_symlink_target(symlink_path, new_path)
            except Exception as db_err:
                logger.debug(f"Failed to log rename operation to DB: {db_err}")

            # Rename associated subtitle files
            for assoc_path in associated_files:
                # Calculate new name: Movie.en.srt → New Movie (2024).en.srt
                # suffix is everything after the video's stem (e.g., ".en.srt")
                suffix = assoc_path.name[len(old_path.stem):]
                new_assoc_name = new_path.stem + suffix
                new_assoc_path = new_path.parent / new_assoc_name
                try:
                    shutil.move(str(assoc_path), str(new_assoc_path))
                except OSError:
                    # Don't fail the whole operation if a subtitle rename fails
                    pass

            # Notify Plex about the rename (scans both old and new locations)
            self._notify_plex_rename(old_path, new_path)

            return RenameResult(
                item=item,
                old_path=old_path,
                new_path=new_path,
                success=True,
            )
        except OSError as e:
            return RenameResult(
                item=item,
                old_path=old_path,
                new_path=new_path,
                success=False,
                error=str(e),
            )

    def rename_items(
        self,
        items: List[MediaItem],
        dry_run: bool = True,
        progress_callback: Optional[callable] = None,
    ) -> RenameSummary:
        """
        Rename multiple media files.

        Args:
            items: List of media items to rename
            dry_run: If True, don't actually rename
            progress_callback: Optional callback(current, total, filename)

        Returns:
            RenameSummary with results of all operations
        """
        results = []
        renamed = 0
        skipped = 0
        failed = 0

        for i, item in enumerate(items):
            if progress_callback:
                progress_callback(i + 1, len(items), item.filename)

            result = self.rename(item, dry_run=dry_run)
            results.append(result)

            if result.skipped:
                skipped += 1
            elif result.success:
                renamed += 1
            else:
                failed += 1

        return RenameSummary(
            total_files=len(items),
            renamed=renamed,
            skipped=skipped,
            failed=failed,
            results=results,
        )
