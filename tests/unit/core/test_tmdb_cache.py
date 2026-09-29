"""Tests for TMDb SQLite cache."""

import time
from pathlib import Path

import pytest

from jackmediaman.core.tmdb_cache import TMDbCache


class TestTMDbCacheInit:
    """Tests for TMDbCache initialization."""

    def test_creates_db_file(self, tmp_path):
        """Creates database file on init."""
        db_path = tmp_path / "cache" / "tmdb.db"
        cache = TMDbCache(db_path)

        assert db_path.exists()

    def test_creates_parent_directories(self, tmp_path):
        """Creates parent directories if needed."""
        db_path = tmp_path / "nested" / "dir" / "tmdb.db"
        cache = TMDbCache(db_path)

        assert db_path.parent.exists()

    def test_default_path(self):
        """Uses default path in home directory."""
        cache = TMDbCache()
        assert ".jackmediaman" in str(cache._db_path)
        assert "tmdb.db" in str(cache._db_path)


class TestTMDbCacheGetSet:
    """Tests for get and set operations."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return TMDbCache(tmp_path / "test.db")

    def test_get_nonexistent(self, cache):
        """Returns None for uncached key."""
        result = cache.get("nonexistent:key")
        assert result is None

    def test_set_and_get(self, cache):
        """Can set and retrieve value."""
        cache.set(
            "movie_search:test",
            TMDbCache.TYPE_MOVIE_SEARCH,
            "Test Movie",
            {"id": 12345},
        )
        result = cache.get("movie_search:test")

        assert result is not None
        assert result["id"] == 12345

    def test_set_none_value(self, cache):
        """Can cache 'no result' with None value."""
        cache.set(
            "movie_search:notfound",
            TMDbCache.TYPE_MOVIE_SEARCH,
            "Not Found Movie",
            None,
        )
        result = cache.get("movie_search:notfound")

        # Empty dict indicates "no result" was cached
        assert result == {}

    def test_update_existing(self, cache):
        """Can update existing cache entry."""
        cache.set(
            "movie_search:test",
            TMDbCache.TYPE_MOVIE_SEARCH,
            "Test",
            {"id": 100},
        )
        cache.set(
            "movie_search:test",
            TMDbCache.TYPE_MOVIE_SEARCH,
            "Test",
            {"id": 200},
        )

        result = cache.get("movie_search:test")
        assert result["id"] == 200

    def test_different_cache_types(self, cache):
        """Handles different cache types."""
        cache.set(
            "movie_search:inception",
            TMDbCache.TYPE_MOVIE_SEARCH,
            "Inception",
            {"id": 27205},
        )
        cache.set(
            "tv_search:breaking_bad",
            TMDbCache.TYPE_TV_SEARCH,
            "Breaking Bad",
            {"id": 1396},
        )
        cache.set(
            "episode:1396:s1e1",
            TMDbCache.TYPE_EPISODE_TITLE,
            "S01E01",
            {"title": "Pilot"},
        )
        cache.set(
            "movie_details:27205",
            TMDbCache.TYPE_MOVIE_DETAILS,
            "movie:27205",
            {"title": "Inception", "year": "2010"},
        )

        assert cache.get("movie_search:inception")["id"] == 27205
        assert cache.get("tv_search:breaking_bad")["id"] == 1396
        assert cache.get("episode:1396:s1e1")["title"] == "Pilot"
        assert cache.get("movie_details:27205")["title"] == "Inception"


class TestTMDbCacheNoExpiration:
    """Tests that cache never auto-expires."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return TMDbCache(tmp_path / "test.db")

    def test_no_expiration(self, cache):
        """Cache entries never auto-expire."""
        cache.set(
            "movie_search:test",
            TMDbCache.TYPE_MOVIE_SEARCH,
            "Test",
            {"id": 12345},
        )

        # Sleep briefly (in real scenarios this would be much longer)
        time.sleep(0.01)

        # Entry should still be valid
        result = cache.get("movie_search:test")
        assert result is not None
        assert result["id"] == 12345


class TestTMDbCacheClear:
    """Tests for cache clearing."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return TMDbCache(tmp_path / "test.db")

    def test_clear_empty_cache(self, cache):
        """Clearing empty cache returns 0."""
        cleared = cache.clear()
        assert cleared == 0

    def test_clear_all(self, cache):
        """Clears all entries."""
        for i in range(5):
            cache.set(
                f"test:key{i}",
                TMDbCache.TYPE_MOVIE_SEARCH,
                f"Query {i}",
                {"id": i},
            )

        cleared = cache.clear()

        assert cleared == 5
        assert cache.stats()["entries"] == 0

    def test_clear_by_type(self, cache):
        """Clears only entries of specified type."""
        # Add different types
        cache.set("movie:1", TMDbCache.TYPE_MOVIE_SEARCH, "Movie 1", {"id": 1})
        cache.set("movie:2", TMDbCache.TYPE_MOVIE_SEARCH, "Movie 2", {"id": 2})
        cache.set("tv:1", TMDbCache.TYPE_TV_SEARCH, "TV 1", {"id": 3})
        cache.set("episode:1", TMDbCache.TYPE_EPISODE_TITLE, "Ep 1", {"title": "Pilot"})

        # Clear only movie searches
        cleared = cache.clear(cache_type=TMDbCache.TYPE_MOVIE_SEARCH)

        assert cleared == 2
        stats = cache.stats()
        assert stats["entries"] == 2
        assert stats["movie_searches"] == 0
        assert stats["tv_searches"] == 1
        assert stats["episode_titles"] == 1


class TestTMDbCacheStats:
    """Tests for cache statistics."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return TMDbCache(tmp_path / "test.db")

    def test_stats_empty_cache(self, cache):
        """Returns stats for empty cache."""
        stats = cache.stats()

        assert stats["entries"] == 0
        assert stats["movie_searches"] == 0
        assert stats["tv_searches"] == 0
        assert stats["episode_titles"] == 0
        assert stats["movie_details"] == 0
        assert stats["oldest_entry"] is None
        assert stats["newest_entry"] is None
        assert "db_path" in stats
        assert "db_size_mb" in stats

    def test_stats_with_entries(self, cache):
        """Returns stats for populated cache."""
        cache.set("movie:1", TMDbCache.TYPE_MOVIE_SEARCH, "Movie 1", {"id": 1})
        cache.set("movie:2", TMDbCache.TYPE_MOVIE_SEARCH, "Movie 2", {"id": 2})
        cache.set("tv:1", TMDbCache.TYPE_TV_SEARCH, "TV 1", {"id": 3})
        time.sleep(0.01)  # Small delay for timestamp ordering
        cache.set("episode:1", TMDbCache.TYPE_EPISODE_TITLE, "Ep 1", {"title": "Pilot"})
        cache.set("details:1", TMDbCache.TYPE_MOVIE_DETAILS, "movie:1", {"title": "X"})

        stats = cache.stats()

        assert stats["entries"] == 5
        assert stats["movie_searches"] == 2
        assert stats["tv_searches"] == 1
        assert stats["episode_titles"] == 1
        assert stats["movie_details"] == 1
        assert stats["oldest_entry"] is not None
        assert stats["newest_entry"] is not None
        assert stats["db_size_bytes"] > 0

    def test_stats_by_type(self, cache):
        """by_type dict has correct counts."""
        cache.set("movie:1", TMDbCache.TYPE_MOVIE_SEARCH, "Movie", {"id": 1})
        cache.set("tv:1", TMDbCache.TYPE_TV_SEARCH, "TV", {"id": 2})
        cache.set("tv:2", TMDbCache.TYPE_TV_SEARCH, "TV2", {"id": 3})

        stats = cache.stats()

        assert stats["by_type"][TMDbCache.TYPE_MOVIE_SEARCH] == 1
        assert stats["by_type"][TMDbCache.TYPE_TV_SEARCH] == 2


class TestTMDbCacheRecentEntries:
    """Tests for recent entries retrieval."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return TMDbCache(tmp_path / "test.db")

    def test_get_recent_entries_empty(self, cache):
        """Returns empty list for empty cache."""
        entries = cache.get_recent_entries()
        assert entries == []

    def test_get_recent_entries(self, cache):
        """Returns recent entries in order."""
        for i in range(5):
            cache.set(
                f"test:{i}",
                TMDbCache.TYPE_MOVIE_SEARCH,
                f"Query {i}",
                {"id": i},
            )
            time.sleep(0.01)

        entries = cache.get_recent_entries(limit=3)

        assert len(entries) == 3
        # Most recent should be first
        assert entries[0]["query"] == "Query 4"
        assert entries[1]["query"] == "Query 3"
        assert entries[2]["query"] == "Query 2"

    def test_get_recent_entries_limit(self, cache):
        """Respects limit parameter."""
        for i in range(10):
            cache.set(
                f"test:{i}",
                TMDbCache.TYPE_MOVIE_SEARCH,
                f"Query {i}",
                {"id": i},
            )

        entries = cache.get_recent_entries(limit=5)
        assert len(entries) == 5


class TestTMDbCacheIntegration:
    """Integration tests simulating real usage patterns."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return TMDbCache(tmp_path / "test.db")

    def test_movie_search_workflow(self, cache):
        """Test typical movie search caching workflow."""
        # First search - cache miss
        assert cache.get("movie_search:inception:2010") is None

        # Cache the result
        cache.set(
            "movie_search:inception:2010",
            TMDbCache.TYPE_MOVIE_SEARCH,
            "Inception (2010)",
            {"id": 27205},
        )

        # Second search - cache hit
        result = cache.get("movie_search:inception:2010")
        assert result["id"] == 27205

    def test_tv_show_workflow(self, cache):
        """Test typical TV show lookup workflow."""
        # Search for show
        cache.set(
            "tv_search:breaking bad",
            TMDbCache.TYPE_TV_SEARCH,
            "Breaking Bad",
            {"id": 1396},
        )

        # Cache episode titles
        cache.set(
            "episode:1396:s1e1",
            TMDbCache.TYPE_EPISODE_TITLE,
            "S01E01 (show:1396)",
            {"title": "Pilot"},
        )
        cache.set(
            "episode:1396:s1e2",
            TMDbCache.TYPE_EPISODE_TITLE,
            "S01E02 (show:1396)",
            {"title": "Cat's in the Bag..."},
        )

        # Verify all cached
        assert cache.get("tv_search:breaking bad")["id"] == 1396
        assert cache.get("episode:1396:s1e1")["title"] == "Pilot"
        assert cache.get("episode:1396:s1e2")["title"] == "Cat's in the Bag..."

    def test_no_result_caching(self, cache):
        """Test caching of 'no result' to avoid repeated lookups."""
        # Movie not found
        cache.set(
            "movie_search:nonexistent movie:2099",
            TMDbCache.TYPE_MOVIE_SEARCH,
            "Nonexistent Movie (2099)",
            None,
        )

        # Should return empty dict, not None
        result = cache.get("movie_search:nonexistent movie:2099")
        assert result == {}
        # Empty dict is falsy but not None - can distinguish from cache miss
        assert result is not None
