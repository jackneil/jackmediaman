"""TMDb matcher for movies - uses TMDb API for accurate matching."""

import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from jackmediaman.models.media import MediaItem, Movie
from jackmediaman.models.duplicates import DuplicateGroup
from jackmediaman.core.config import get_settings
from jackmediaman.core.exceptions import TMDbError
from jackmediaman.core.tmdb_cache import TMDbCache


class TMDbClient:
    """Client for TMDb API with rate limiting and SQLite caching."""

    BASE_URL = "https://api.themoviedb.org/3"
    RATE_LIMIT_DELAY = 0.35  # seconds between requests

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache: Optional[TMDbCache] = None,
        cache_dir: Optional[Path] = None,  # Deprecated, kept for compatibility
    ):
        """
        Initialize the TMDb client.

        Args:
            api_key: TMDb API key
            cache: Optional TMDbCache instance (creates default if not provided)
            cache_dir: Deprecated, kept for backward compatibility
        """
        settings = get_settings()
        self.api_key = api_key or settings.tmdb_api_key
        self._cache = cache if cache is not None else TMDbCache()
        self.last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _get_cached(self, cache_key: str) -> Optional[dict]:
        """Get a cached response (never expires)."""
        return self._cache.get(cache_key)

    def _set_cache(
        self,
        cache_key: str,
        cache_type: str,
        query: str,
        value: Optional[dict],
    ) -> None:
        """Store a value in the cache."""
        self._cache.set(cache_key, cache_type, query, value)

    def search_movie(
        self, title: str, year: Optional[int] = None
    ) -> Optional[int]:
        """
        Search for a movie and return its TMDb ID.

        Args:
            title: Movie title to search for
            year: Optional release year to narrow search

        Returns:
            TMDb movie ID if found, None otherwise
        """
        if not self.api_key:
            return None

        cache_key = f"movie_search:{title}:{year}"
        query_display = f"{title} ({year})" if year else title
        cached = self._get_cached(cache_key)
        if cached is not None:
            # Empty dict means cached "no result"
            return cached.get("id") if cached else None

        self._rate_limit()

        params = {
            "api_key": self.api_key,
            "query": title,
        }
        if year:
            params["year"] = year

        try:
            response = httpx.get(
                f"{self.BASE_URL}/search/movie",
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            results = response.json().get("results", [])

            if results:
                movie_id = results[0]["id"]
                self._set_cache(
                    cache_key,
                    TMDbCache.TYPE_MOVIE_SEARCH,
                    query_display,
                    {"id": movie_id},
                )
                return movie_id

            self._set_cache(
                cache_key,
                TMDbCache.TYPE_MOVIE_SEARCH,
                query_display,
                None,
            )
            return None

        except httpx.HTTPError as e:
            raise TMDbError(f"TMDb API error: {e}") from e


class TMDbMatcher:
    """Match movies using TMDb API for accurate identification."""

    name = "tmdb"
    description = "Match movies using TMDb metadata lookup (most accurate)"

    def __init__(
        self,
        api_key: Optional[str] = None,
        include_editions_as_dupes: bool = True,
    ):
        """
        Initialize the matcher.

        Args:
            api_key: TMDb API key (falls back to settings)
            include_editions_as_dupes: If True, different editions are considered duplicates.
        """
        self.client = TMDbClient(api_key=api_key)
        self.include_editions_as_dupes = include_editions_as_dupes

    def match(
        self,
        items: List[MediaItem],
        progress_callback: Optional[callable] = None,
    ) -> List[DuplicateGroup]:
        """
        Group movies that are duplicates based on TMDb ID.

        Args:
            items: List of media items to match
            progress_callback: Optional callback(current, total, filename) for progress
        """
        # Filter to only movies
        movies = [item for item in items if isinstance(item, Movie)]

        if not movies:
            return []

        # Look up TMDb IDs for all movies
        groups: Dict[str, List[Movie]] = defaultdict(list)
        unmatched: List[Movie] = []

        for i, movie in enumerate(movies):
            if progress_callback:
                progress_callback(i + 1, len(movies), movie.filename)

            # Try to get TMDb ID
            tmdb_id = self.client.search_movie(movie.title, movie.year)

            if tmdb_id:
                movie.tmdb_id = tmdb_id
                key = self._get_match_key(movie, tmdb_id)
                groups[key].append(movie)
            else:
                unmatched.append(movie)

        # Create DuplicateGroup objects for groups with duplicates
        result = []
        for key, group_items in groups.items():
            if len(group_items) > 1:
                group = DuplicateGroup(identity_key=key)
                for item in group_items:
                    group.add(item)
                group.sort_by_quality()
                result.append(group)

        return result

    def _get_match_key(self, movie: Movie, tmdb_id: int) -> str:
        """Get the matching key for a movie."""
        base_key = f"movie:tmdb:{tmdb_id}"

        if not self.include_editions_as_dupes and movie.edition:
            return f"{base_key}:{movie.edition}"

        return base_key
