"""Artwork service for downloading poster images from TMDb."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

import httpx

from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger
from jackmediaman.core.tmdb_cache import TMDbCache

logger = get_logger("artwork")


@dataclass
class ArtworkResult:
    """Result of an artwork download operation."""

    path: Path  # Where artwork was saved (or would be saved)
    media_path: Path  # The video/folder it's for
    artwork_type: str  # "movie_poster", "show_poster", "season_poster"
    success: bool
    skipped: bool = False
    skip_reason: Optional[str] = None
    error: Optional[str] = None


class ArtworkService:
    """Download and manage poster artwork from TMDb."""

    IMAGE_BASE_URL = "https://image.tmdb.org/t/p"
    API_BASE_URL = "https://api.themoviedb.org/3"
    DEFAULT_SIZE = "w500"  # Good quality, reasonable file size (~50-150KB)
    RATE_LIMIT_DELAY = 0.35  # seconds between API requests

    def __init__(self, api_key: Optional[str] = None, cache: Optional[TMDbCache] = None):
        """Initialize the artwork service.

        Args:
            api_key: TMDb API key (falls back to settings)
            cache: Optional TMDbCache instance for caching API responses
        """
        settings = get_settings()
        self.api_key = api_key or settings.tmdb_api_key
        self._cache = cache if cache is not None else TMDbCache()
        self.last_request_time = 0.0
        self.settings = settings
        logger.debug("ArtworkService initialized")

    def _rate_limit(self) -> None:
        """Enforce rate limiting between API requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _api_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[dict]:
        """Make a TMDb API request.

        Args:
            endpoint: API endpoint (e.g., "/movie/123")
            params: Additional query parameters

        Returns:
            JSON response dict, or None on failure
        """
        if not self.api_key:
            return None

        self._rate_limit()

        request_params = {"api_key": self.api_key}
        if params:
            request_params.update(params)

        try:
            response = httpx.get(
                f"{self.API_BASE_URL}{endpoint}",
                params=request_params,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    def get_movie_poster_url(self, tmdb_id: int, size: str = DEFAULT_SIZE) -> Optional[str]:
        """Get the poster URL for a movie.

        Args:
            tmdb_id: TMDb movie ID
            size: Image size (w500, original, etc.)

        Returns:
            Full image URL, or None if not available
        """
        # Check cache first
        cache_key = f"movie_poster:{tmdb_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            poster_path = cached.get("poster_path") if cached else None
            if poster_path:
                return f"{self.IMAGE_BASE_URL}/{size}{poster_path}"
            return None

        # Fetch from API
        data = self._api_request(f"/movie/{tmdb_id}")
        if not data:
            return None

        poster_path = data.get("poster_path")
        self._cache.set(
            cache_key,
            "movie_poster",
            str(tmdb_id),
            {"poster_path": poster_path} if poster_path else None,
        )

        if poster_path:
            return f"{self.IMAGE_BASE_URL}/{size}{poster_path}"
        return None

    def get_show_poster_url(self, tmdb_id: int, size: str = DEFAULT_SIZE) -> Optional[str]:
        """Get the poster URL for a TV show.

        Args:
            tmdb_id: TMDb TV show ID
            size: Image size

        Returns:
            Full image URL, or None if not available
        """
        cache_key = f"show_poster:{tmdb_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            poster_path = cached.get("poster_path") if cached else None
            if poster_path:
                return f"{self.IMAGE_BASE_URL}/{size}{poster_path}"
            return None

        data = self._api_request(f"/tv/{tmdb_id}")
        if not data:
            return None

        poster_path = data.get("poster_path")
        self._cache.set(
            cache_key,
            "show_poster",
            str(tmdb_id),
            {"poster_path": poster_path} if poster_path else None,
        )

        if poster_path:
            return f"{self.IMAGE_BASE_URL}/{size}{poster_path}"
        return None

    def get_season_poster_url(
        self, tmdb_id: int, season: int, size: str = DEFAULT_SIZE
    ) -> Optional[str]:
        """Get the poster URL for a TV season.

        Args:
            tmdb_id: TMDb TV show ID
            season: Season number
            size: Image size

        Returns:
            Full image URL, or None if not available
        """
        cache_key = f"season_poster:{tmdb_id}:s{season}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            poster_path = cached.get("poster_path") if cached else None
            if poster_path:
                return f"{self.IMAGE_BASE_URL}/{size}{poster_path}"
            return None

        data = self._api_request(f"/tv/{tmdb_id}/season/{season}")
        if not data:
            return None

        poster_path = data.get("poster_path")
        self._cache.set(
            cache_key,
            "season_poster",
            f"{tmdb_id}:S{season:02d}",
            {"poster_path": poster_path} if poster_path else None,
        )

        if poster_path:
            return f"{self.IMAGE_BASE_URL}/{size}{poster_path}"
        return None

    def search_movie(self, title: str, year: Optional[int] = None) -> Optional[int]:
        """Search for a movie and return its TMDb ID.

        Args:
            title: Movie title
            year: Optional release year

        Returns:
            TMDb ID if found, None otherwise
        """
        if not self.api_key:
            return None

        cache_key = f"movie_search:{title}:{year}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached.get("id") if cached else None

        self._rate_limit()

        params = {"query": title}
        if year:
            params["year"] = year

        data = self._api_request("/search/movie", params)
        if not data:
            return None

        results = data.get("results", [])
        if results:
            movie_id = results[0]["id"]
            self._cache.set(cache_key, "movie_search", f"{title} ({year})", {"id": movie_id})
            return movie_id

        self._cache.set(cache_key, "movie_search", f"{title} ({year})", None)
        return None

    def search_tv(self, name: str) -> Optional[int]:
        """Search for a TV show and return its TMDb ID.

        Args:
            name: Show name

        Returns:
            TMDb ID if found, None otherwise
        """
        if not self.api_key:
            return None

        cache_key = f"tv_search:{name}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached.get("id") if cached else None

        self._rate_limit()

        data = self._api_request("/search/tv", {"query": name})
        if not data:
            return None

        results = data.get("results", [])
        if results:
            show_id = results[0]["id"]
            self._cache.set(cache_key, "tv_search", name, {"id": show_id})
            return show_id

        self._cache.set(cache_key, "tv_search", name, None)
        return None

    def download_image(self, url: str, dest_path: Path) -> bool:
        """Download an image to a file.

        Args:
            url: Image URL
            dest_path: Destination file path

        Returns:
            True if successful, False otherwise
        """
        try:
            response = httpx.get(url, timeout=30.0, follow_redirects=True)
            response.raise_for_status()

            # Ensure parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            dest_path.write_bytes(response.content)
            return True
        except (httpx.HTTPError, OSError):
            return False

    def download_movie_poster(
        self,
        movie_path: Path,
        title: str,
        year: Optional[int] = None,
        tmdb_id: Optional[int] = None,
        overwrite: bool = False,
    ) -> ArtworkResult:
        """Download poster for a movie.

        Args:
            movie_path: Path to the movie file
            title: Movie title (for TMDb search if no tmdb_id)
            year: Movie year (for TMDb search)
            tmdb_id: Optional TMDb ID (skips search if provided)
            overwrite: Whether to overwrite existing poster

        Returns:
            ArtworkResult with operation details
        """
        # Determine poster path - in same folder as movie
        movie_folder = movie_path.parent
        poster_path = movie_folder / "poster.jpg"

        # Check if poster already exists
        if poster_path.exists() and not overwrite:
            return ArtworkResult(
                path=poster_path,
                media_path=movie_path,
                artwork_type="movie_poster",
                success=True,
                skipped=True,
                skip_reason="Poster already exists",
            )

        # Get TMDb ID if not provided
        if not tmdb_id:
            tmdb_id = self.search_movie(title, year)

        if not tmdb_id:
            return ArtworkResult(
                path=poster_path,
                media_path=movie_path,
                artwork_type="movie_poster",
                success=False,
                error="Movie not found on TMDb",
            )

        # Get poster URL
        poster_url = self.get_movie_poster_url(tmdb_id)
        if not poster_url:
            # No poster available - keep existing if any
            if poster_path.exists():
                return ArtworkResult(
                    path=poster_path,
                    media_path=movie_path,
                    artwork_type="movie_poster",
                    success=True,
                    skipped=True,
                    skip_reason="No poster on TMDb, keeping existing",
                )
            return ArtworkResult(
                path=poster_path,
                media_path=movie_path,
                artwork_type="movie_poster",
                success=False,
                error="No poster available on TMDb",
            )

        # Download the poster
        if self.download_image(poster_url, poster_path):
            return ArtworkResult(
                path=poster_path,
                media_path=movie_path,
                artwork_type="movie_poster",
                success=True,
            )

        return ArtworkResult(
            path=poster_path,
            media_path=movie_path,
            artwork_type="movie_poster",
            success=False,
            error="Failed to download poster",
        )

    def download_show_artwork(
        self,
        show_folder: Path,
        show_name: str,
        tmdb_id: Optional[int] = None,
        include_seasons: bool = True,
        overwrite: bool = False,
    ) -> List[ArtworkResult]:
        """Download artwork for a TV show (poster + season posters).

        Args:
            show_folder: Path to the show's root folder
            show_name: Show name (for TMDb search if no tmdb_id)
            tmdb_id: Optional TMDb ID (skips search if provided)
            include_seasons: Whether to download season posters
            overwrite: Whether to overwrite existing posters

        Returns:
            List of ArtworkResult for each download attempt
        """
        results = []

        # Get TMDb ID if not provided
        if not tmdb_id:
            tmdb_id = self.search_tv(show_name)

        if not tmdb_id:
            return [
                ArtworkResult(
                    path=show_folder / "poster.jpg",
                    media_path=show_folder,
                    artwork_type="show_poster",
                    success=False,
                    error="Show not found on TMDb",
                )
            ]

        # Download show poster
        show_poster_path = show_folder / "poster.jpg"
        if show_poster_path.exists() and not overwrite:
            results.append(
                ArtworkResult(
                    path=show_poster_path,
                    media_path=show_folder,
                    artwork_type="show_poster",
                    success=True,
                    skipped=True,
                    skip_reason="Poster already exists",
                )
            )
        else:
            poster_url = self.get_show_poster_url(tmdb_id)
            if poster_url:
                if self.download_image(poster_url, show_poster_path):
                    results.append(
                        ArtworkResult(
                            path=show_poster_path,
                            media_path=show_folder,
                            artwork_type="show_poster",
                            success=True,
                        )
                    )
                else:
                    results.append(
                        ArtworkResult(
                            path=show_poster_path,
                            media_path=show_folder,
                            artwork_type="show_poster",
                            success=False,
                            error="Failed to download poster",
                        )
                    )
            else:
                if show_poster_path.exists():
                    results.append(
                        ArtworkResult(
                            path=show_poster_path,
                            media_path=show_folder,
                            artwork_type="show_poster",
                            success=True,
                            skipped=True,
                            skip_reason="No poster on TMDb, keeping existing",
                        )
                    )
                else:
                    results.append(
                        ArtworkResult(
                            path=show_poster_path,
                            media_path=show_folder,
                            artwork_type="show_poster",
                            success=False,
                            error="No poster available on TMDb",
                        )
                    )

        # Download season posters
        if include_seasons:
            # Find season folders
            seasons = self._find_season_numbers(show_folder)
            for season_num in seasons:
                season_poster_path = show_folder / f"season{season_num:02d}-poster.jpg"

                if season_poster_path.exists() and not overwrite:
                    results.append(
                        ArtworkResult(
                            path=season_poster_path,
                            media_path=show_folder,
                            artwork_type="season_poster",
                            success=True,
                            skipped=True,
                            skip_reason=f"Season {season_num} poster already exists",
                        )
                    )
                    continue

                season_url = self.get_season_poster_url(tmdb_id, season_num)
                if season_url:
                    if self.download_image(season_url, season_poster_path):
                        results.append(
                            ArtworkResult(
                                path=season_poster_path,
                                media_path=show_folder,
                                artwork_type="season_poster",
                                success=True,
                            )
                        )
                    else:
                        results.append(
                            ArtworkResult(
                                path=season_poster_path,
                                media_path=show_folder,
                                artwork_type="season_poster",
                                success=False,
                                error=f"Failed to download season {season_num} poster",
                            )
                        )
                else:
                    if season_poster_path.exists():
                        results.append(
                            ArtworkResult(
                                path=season_poster_path,
                                media_path=show_folder,
                                artwork_type="season_poster",
                                success=True,
                                skipped=True,
                                skip_reason=f"No season {season_num} poster on TMDb, keeping existing",
                            )
                        )
                    # Don't report missing season posters as errors - many shows don't have them

        return results

    def _find_season_numbers(self, show_folder: Path) -> List[int]:
        """Find season numbers from season folders.

        Args:
            show_folder: Path to show folder

        Returns:
            List of season numbers found
        """
        import re

        seasons = set()
        for item in show_folder.iterdir():
            if item.is_dir():
                # Match "Season 1", "Season 01", "S1", "S01", etc.
                match = re.match(r"(?:season\s*|s)(\d+)", item.name, re.IGNORECASE)
                if match:
                    seasons.add(int(match.group(1)))
        return sorted(seasons)

    def download_for_movies_library(
        self,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[ArtworkResult]:
        """Download posters for all movies in the library.

        Args:
            overwrite: Whether to overwrite existing posters
            progress_callback: Optional callback(current, total, name)

        Returns:
            List of ArtworkResult for all operations
        """
        results = []
        movies_dir = self.settings.movies_dir

        if not movies_dir.exists():
            return results

        # Find all movie folders (folders containing video files)
        movie_folders = self._find_movie_folders(movies_dir)

        for i, (folder, video_file) in enumerate(movie_folders):
            if progress_callback:
                progress_callback(i + 1, len(movie_folders), folder.name)

            # Parse movie info from folder/file name
            title, year = self._parse_movie_name(folder.name)

            result = self.download_movie_poster(
                movie_path=video_file,
                title=title,
                year=year,
                overwrite=overwrite,
            )
            results.append(result)

        return results

    def download_for_tv_library(
        self,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[ArtworkResult]:
        """Download posters for all TV shows in the library.

        Args:
            overwrite: Whether to overwrite existing posters
            progress_callback: Optional callback(current, total, name)

        Returns:
            List of ArtworkResult for all operations
        """
        results = []
        tv_dir = self.settings.tv_dir

        if not tv_dir.exists():
            return results

        # Find all show folders
        show_folders = [d for d in tv_dir.iterdir() if d.is_dir()]

        for i, show_folder in enumerate(show_folders):
            if progress_callback:
                progress_callback(i + 1, len(show_folders), show_folder.name)

            show_results = self.download_show_artwork(
                show_folder=show_folder,
                show_name=show_folder.name,
                overwrite=overwrite,
            )
            results.extend(show_results)

        return results

    def download_for_library(
        self,
        media_type: str = "both",
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[ArtworkResult]:
        """Download posters for the entire media library.

        Args:
            media_type: "movies", "tv", or "both"
            overwrite: Whether to overwrite existing posters
            progress_callback: Optional callback(current, total, name)

        Returns:
            List of ArtworkResult for all operations
        """
        results = []

        if media_type in ("movies", "both"):
            results.extend(
                self.download_for_movies_library(overwrite, progress_callback)
            )

        if media_type in ("tv", "both"):
            results.extend(
                self.download_for_tv_library(overwrite, progress_callback)
            )

        return results

    def _find_movie_folders(self, movies_dir: Path) -> List[tuple]:
        """Find movie folders containing video files.

        Args:
            movies_dir: Root movies directory

        Returns:
            List of (folder_path, video_file_path) tuples
        """
        video_extensions = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".ts", ".mov"}
        movie_folders = []

        for item in movies_dir.iterdir():
            if item.is_dir():
                # Find video file in folder
                for video in item.iterdir():
                    if video.is_file() and video.suffix.lower() in video_extensions:
                        movie_folders.append((item, video))
                        break  # One video per folder

        return movie_folders

    def _parse_movie_name(self, folder_name: str) -> tuple:
        """Parse movie title and year from folder name.

        Args:
            folder_name: Movie folder name (e.g., "Movie Name (2024)")

        Returns:
            Tuple of (title, year) where year may be None
        """
        import re

        # Match "Movie Name (2024)" or "Movie Name [2024]"
        match = re.match(r"^(.+?)\s*[\(\[](\d{4})[\)\]]", folder_name)
        if match:
            return match.group(1).strip(), int(match.group(2))

        return folder_name, None

    def get_artwork_stats(self) -> Dict[str, Dict[str, int]]:
        """Get statistics about artwork coverage in the library.

        Returns:
            Dict with stats for movies and TV shows
        """
        stats = {
            "movies": {"total": 0, "with_poster": 0, "missing_poster": 0},
            "tv": {"total": 0, "with_poster": 0, "missing_poster": 0, "seasons": 0, "seasons_with_poster": 0},
        }

        # Movies
        if self.settings.movies_dir.exists():
            movie_folders = self._find_movie_folders(self.settings.movies_dir)
            stats["movies"]["total"] = len(movie_folders)
            for folder, _ in movie_folders:
                if (folder / "poster.jpg").exists():
                    stats["movies"]["with_poster"] += 1
                else:
                    stats["movies"]["missing_poster"] += 1

        # TV Shows
        if self.settings.tv_dir.exists():
            for show_folder in self.settings.tv_dir.iterdir():
                if show_folder.is_dir():
                    stats["tv"]["total"] += 1
                    if (show_folder / "poster.jpg").exists():
                        stats["tv"]["with_poster"] += 1
                    else:
                        stats["tv"]["missing_poster"] += 1

                    # Count seasons
                    seasons = self._find_season_numbers(show_folder)
                    stats["tv"]["seasons"] += len(seasons)
                    for season_num in seasons:
                        if (show_folder / f"season{season_num:02d}-poster.jpg").exists():
                            stats["tv"]["seasons_with_poster"] += 1

        return stats
