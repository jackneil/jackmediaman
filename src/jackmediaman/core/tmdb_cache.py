"""SQLite cache for TMDb API results."""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional


class TMDbCache:
    """SQLite-backed cache for TMDb API results.

    Stores API results permanently (no auto-expiration) with manual
    cache management via CLI commands.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS tmdb_cache (
        cache_key TEXT PRIMARY KEY,
        cache_type TEXT NOT NULL,
        query TEXT NOT NULL,
        result_json TEXT,
        cached_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_cache_type ON tmdb_cache(cache_type);
    CREATE INDEX IF NOT EXISTS idx_cached_at ON tmdb_cache(cached_at);
    """

    # Cache type constants
    TYPE_MOVIE_SEARCH = "movie_search"
    TYPE_TV_SEARCH = "tv_search"
    TYPE_EPISODE_TITLE = "episode_title"
    TYPE_MOVIE_DETAILS = "movie_details"
    TYPE_SEASON_EPISODES = "season_episodes"

    # Full metadata cache types (for NFO generation)
    TYPE_MOVIE_FULL = "movie_full"       # Full movie details with credits
    TYPE_TV_FULL = "tv_full"             # Full TV show details
    TYPE_EPISODE_FULL = "episode_full"   # Full episode details

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize cache with optional custom database path.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.jackmediaman/cache/tmdb.db
        """
        if db_path is None:
            db_path = Path.home() / ".jackmediaman" / "cache" / "tmdb.db"

        self._db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """Create database and schema if not exists."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.executescript(self.SCHEMA)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached result (never expires).

        Args:
            cache_key: Unique key for the cached value

        Returns:
            Cached dict if found, None otherwise.
            Note: Returns empty dict {} for cached "no result" entries.
        """
        with self._connection() as conn:
            row = conn.execute(
                "SELECT result_json FROM tmdb_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()

            if row is None:
                return None

            result_json = row["result_json"]
            if result_json is None:
                # Cached "no result" - return empty dict to distinguish from cache miss
                return {}

            return json.loads(result_json)

    def set(
        self,
        cache_key: str,
        cache_type: str,
        query: str,
        value: Optional[Dict[str, Any]],
    ) -> None:
        """Store result in cache.

        Args:
            cache_key: Unique key for the cached value
            cache_type: Type of cache entry (e.g., 'movie_search', 'tv_search')
            query: Original query string for display purposes
            value: Result to cache, or None for "no result"
        """
        now = datetime.now().isoformat()
        result_json = json.dumps(value) if value is not None else None

        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tmdb_cache (
                    cache_key, cache_type, query, result_json, cached_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (cache_key, cache_type, query, result_json, now),
            )

    def stats(self) -> Dict[str, Any]:
        """Return cache statistics with entry counts by type and age info.

        Returns:
            Dictionary with cache statistics
        """
        with self._connection() as conn:
            # Total count
            total = conn.execute("SELECT COUNT(*) FROM tmdb_cache").fetchone()[0]

            # Counts by type
            type_counts = {}
            for row in conn.execute(
                "SELECT cache_type, COUNT(*) as count FROM tmdb_cache GROUP BY cache_type"
            ):
                type_counts[row["cache_type"]] = row["count"]

            # Oldest and newest entries
            oldest = conn.execute(
                "SELECT MIN(cached_at) FROM tmdb_cache"
            ).fetchone()[0]
            newest = conn.execute(
                "SELECT MAX(cached_at) FROM tmdb_cache"
            ).fetchone()[0]

        # Get database file size
        db_size = self._db_path.stat().st_size if self._db_path.exists() else 0

        return {
            "entries": total,
            "by_type": type_counts,
            "movie_searches": type_counts.get(self.TYPE_MOVIE_SEARCH, 0),
            "tv_searches": type_counts.get(self.TYPE_TV_SEARCH, 0),
            "episode_titles": type_counts.get(self.TYPE_EPISODE_TITLE, 0),
            "movie_details": type_counts.get(self.TYPE_MOVIE_DETAILS, 0),
            "movie_full": type_counts.get(self.TYPE_MOVIE_FULL, 0),
            "tv_full": type_counts.get(self.TYPE_TV_FULL, 0),
            "episode_full": type_counts.get(self.TYPE_EPISODE_FULL, 0),
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / (1024 * 1024), 2),
            "oldest_entry": oldest,
            "newest_entry": newest,
            "db_path": str(self._db_path),
        }

    def clear(self, cache_type: Optional[str] = None) -> int:
        """Clear cache entries.

        Args:
            cache_type: If specified, only clear entries of this type.
                       If None, clear all entries.

        Returns:
            Number of entries cleared
        """
        with self._connection() as conn:
            if cache_type:
                cursor = conn.execute(
                    "DELETE FROM tmdb_cache WHERE cache_type = ?",
                    (cache_type,),
                )
            else:
                cursor = conn.execute("DELETE FROM tmdb_cache")
            return cursor.rowcount

    def get_recent_entries(self, limit: int = 10) -> list:
        """Get most recent cache entries for display.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent entries with type, query, and age
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT cache_type, query, cached_at
                FROM tmdb_cache
                ORDER BY cached_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

            return [
                {
                    "type": row["cache_type"],
                    "query": row["query"],
                    "cached_at": row["cached_at"],
                }
                for row in rows
            ]
