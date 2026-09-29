"""TMDb service for fetching full metadata."""

import time
from datetime import date
from typing import Dict, List, Optional

import httpx

from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger
from jackmediaman.core.tmdb_cache import TMDbCache
from jackmediaman.models.nfo import (
    NFOMovieMetadata,
    NFOTVShowMetadata,
    NFOEpisodeMetadata,
)

logger = get_logger("tmdb")


class TMDbService:
    """Fetch full metadata from TMDb API for NFO generation."""

    API_BASE_URL = "https://api.themoviedb.org/3"
    RATE_LIMIT_DELAY = 0.35  # seconds between API requests

    def __init__(
        self,
        api_key: Optional[str] = None,
        cache: Optional[TMDbCache] = None,
    ):
        """Initialize the TMDb service.

        Args:
            api_key: TMDb API key (falls back to settings)
            cache: Optional TMDbCache instance
        """
        settings = get_settings()
        self.api_key = api_key or settings.tmdb_api_key
        self._cache = cache if cache is not None else TMDbCache()
        self.last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between API requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _api_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
    ) -> Optional[dict]:
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

        params = {"query": title}
        if year:
            params["year"] = year

        data = self._api_request("/search/movie", params)
        if not data:
            return None

        results = data.get("results", [])
        if results:
            movie_id = results[0]["id"]
            self._cache.set(
                cache_key,
                TMDbCache.TYPE_MOVIE_SEARCH,
                f"{title} ({year})",
                {"id": movie_id},
            )
            return movie_id

        self._cache.set(
            cache_key,
            TMDbCache.TYPE_MOVIE_SEARCH,
            f"{title} ({year})",
            None,
        )
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

        data = self._api_request("/search/tv", {"query": name})
        if not data:
            return None

        results = data.get("results", [])
        if results:
            show_id = results[0]["id"]
            self._cache.set(
                cache_key,
                TMDbCache.TYPE_TV_SEARCH,
                name,
                {"id": show_id},
            )
            return show_id

        self._cache.set(cache_key, TMDbCache.TYPE_TV_SEARCH, name, None)
        return None

    def get_movie_details(self, tmdb_id: int) -> Optional[NFOMovieMetadata]:
        """Get full movie details from TMDb.

        Args:
            tmdb_id: TMDb movie ID

        Returns:
            NFOMovieMetadata if found, None otherwise
        """
        cache_key = f"movie_full:{tmdb_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            if cached:  # Not empty dict (cached "not found")
                return NFOMovieMetadata(**cached)
            return None

        # Fetch with credits and external IDs in one request
        data = self._api_request(
            f"/movie/{tmdb_id}",
            params={"append_to_response": "credits,external_ids"},
        )

        if not data:
            self._cache.set(
                cache_key,
                TMDbCache.TYPE_MOVIE_FULL,
                f"Movie {tmdb_id}",
                None,
            )
            return None

        # Extract year from release date
        year = None
        release_date = data.get("release_date")
        if release_date and len(release_date) >= 4:
            try:
                year = int(release_date[:4])
            except ValueError:
                pass

        # Extract director from credits
        director = self._get_director(data.get("credits", {}))

        # Extract studio (first production company)
        studio = None
        production_companies = data.get("production_companies", [])
        if production_companies:
            studio = production_companies[0].get("name")

        # Extract IMDb ID from external IDs
        imdb_id = data.get("external_ids", {}).get("imdb_id")

        # Build metadata object
        metadata = NFOMovieMetadata(
            title=data.get("title", "Unknown"),
            year=year,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            plot=data.get("overview"),
            rating=data.get("vote_average"),
            runtime=data.get("runtime"),
            genres=[g["name"] for g in data.get("genres", [])],
            director=director,
            studio=studio,
            tagline=data.get("tagline"),
        )

        # Cache the result
        self._cache.set(
            cache_key,
            TMDbCache.TYPE_MOVIE_FULL,
            f"{metadata.title} ({year})",
            {
                "title": metadata.title,
                "year": metadata.year,
                "tmdb_id": metadata.tmdb_id,
                "imdb_id": metadata.imdb_id,
                "plot": metadata.plot,
                "rating": metadata.rating,
                "runtime": metadata.runtime,
                "genres": metadata.genres,
                "director": metadata.director,
                "studio": metadata.studio,
                "tagline": metadata.tagline,
            },
        )

        return metadata

    def get_tv_details(self, tmdb_id: int) -> Optional[NFOTVShowMetadata]:
        """Get full TV show details from TMDb.

        Args:
            tmdb_id: TMDb TV show ID

        Returns:
            NFOTVShowMetadata if found, None otherwise
        """
        cache_key = f"tv_full:{tmdb_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            if cached:
                return NFOTVShowMetadata(**cached)
            return None

        # Fetch with external IDs
        data = self._api_request(
            f"/tv/{tmdb_id}",
            params={"append_to_response": "external_ids"},
        )

        if not data:
            self._cache.set(cache_key, TMDbCache.TYPE_TV_FULL, f"TV {tmdb_id}", None)
            return None

        # Extract year from first air date
        year = None
        first_air = data.get("first_air_date")
        if first_air and len(first_air) >= 4:
            try:
                year = int(first_air[:4])
            except ValueError:
                pass

        # Extract external IDs
        external_ids = data.get("external_ids", {})
        imdb_id = external_ids.get("imdb_id")
        tvdb_id = external_ids.get("tvdb_id")

        # Extract studio (first network)
        studio = None
        networks = data.get("networks", [])
        if networks:
            studio = networks[0].get("name")

        metadata = NFOTVShowMetadata(
            title=data.get("name", "Unknown"),
            year=year,
            tmdb_id=tmdb_id,
            imdb_id=imdb_id,
            tvdb_id=tvdb_id,
            plot=data.get("overview"),
            rating=data.get("vote_average"),
            genres=[g["name"] for g in data.get("genres", [])],
            studio=studio,
            status=data.get("status"),
        )

        # Cache
        self._cache.set(
            cache_key,
            TMDbCache.TYPE_TV_FULL,
            f"{metadata.title} ({year})",
            {
                "title": metadata.title,
                "year": metadata.year,
                "tmdb_id": metadata.tmdb_id,
                "imdb_id": metadata.imdb_id,
                "tvdb_id": metadata.tvdb_id,
                "plot": metadata.plot,
                "rating": metadata.rating,
                "genres": metadata.genres,
                "studio": metadata.studio,
                "status": metadata.status,
            },
        )

        return metadata

    def get_episode_details(
        self,
        tmdb_id: int,
        season: int,
        episode: int,
    ) -> Optional[NFOEpisodeMetadata]:
        """Get episode details from TMDb.

        Args:
            tmdb_id: TMDb TV show ID
            season: Season number
            episode: Episode number

        Returns:
            NFOEpisodeMetadata if found, None otherwise
        """
        cache_key = f"episode_full:{tmdb_id}:s{season}e{episode}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            if cached:
                # Convert aired string back to date if present
                if cached.get("aired"):
                    try:
                        cached["aired"] = date.fromisoformat(cached["aired"])
                    except ValueError:
                        cached["aired"] = None
                return NFOEpisodeMetadata(**cached)
            return None

        # Fetch episode data
        data = self._api_request(
            f"/tv/{tmdb_id}/season/{season}/episode/{episode}",
            params={"append_to_response": "credits"},
        )

        if not data:
            self._cache.set(
                cache_key,
                TMDbCache.TYPE_EPISODE_FULL,
                f"TV {tmdb_id} S{season:02d}E{episode:02d}",
                None,
            )
            return None

        # Parse air date
        aired = None
        air_date = data.get("air_date")
        if air_date:
            try:
                aired = date.fromisoformat(air_date)
            except ValueError:
                pass

        # Get director from crew
        director = None
        credits = data.get("credits", {})
        crew = credits.get("crew", [])
        for person in crew:
            if person.get("job") == "Director":
                director = person.get("name")
                break

        metadata = NFOEpisodeMetadata(
            title=data.get("name", f"Episode {episode}"),
            season=season,
            episode=episode,
            aired=aired,
            plot=data.get("overview"),
            rating=data.get("vote_average"),
            runtime=data.get("runtime"),
            director=director,
            tmdb_id=tmdb_id,
        )

        # Cache (convert date to string for JSON serialization)
        self._cache.set(
            cache_key,
            TMDbCache.TYPE_EPISODE_FULL,
            f"S{season:02d}E{episode:02d}: {metadata.title}",
            {
                "title": metadata.title,
                "season": metadata.season,
                "episode": metadata.episode,
                "aired": metadata.aired.isoformat() if metadata.aired else None,
                "plot": metadata.plot,
                "rating": metadata.rating,
                "runtime": metadata.runtime,
                "director": metadata.director,
                "tmdb_id": metadata.tmdb_id,
            },
        )

        return metadata

    def _get_director(self, credits: dict) -> Optional[str]:
        """Extract director name from credits.

        Args:
            credits: Credits dict from TMDb API

        Returns:
            Director name if found, None otherwise
        """
        crew = credits.get("crew", [])
        for person in crew:
            if person.get("job") == "Director":
                return person.get("name")
        return None
