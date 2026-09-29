"""SQLite cache for ffprobe metadata results."""

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from jackmediaman.core.ffprobe import MediaMetadata


class MetadataCache:
    """SQLite-backed cache for ffprobe results.

    Stores metadata keyed by file path, with invalidation based on
    file hash, size, and modification time.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS metadata (
        path_hash TEXT PRIMARY KEY,
        file_path TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        file_mtime REAL NOT NULL,
        width INTEGER NOT NULL,
        height INTEGER NOT NULL,
        video_codec TEXT,
        video_profile TEXT,
        color_transfer TEXT,
        color_primaries TEXT,
        audio_codec TEXT,
        audio_channels INTEGER,
        duration_seconds REAL,
        bit_rate INTEGER,
        probed_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_file_hash ON metadata(file_hash);
    CREATE INDEX IF NOT EXISTS idx_probed_at ON metadata(probed_at);
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize cache with optional custom database path.

        Args:
            db_path: Path to SQLite database. Defaults to ~/.jackmediaman/cache/metadata.db
        """
        if db_path is None:
            db_path = Path.home() / ".jackmediaman" / "cache" / "metadata.db"

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

    def _path_hash(self, path: Path) -> str:
        """Generate stable hash from absolute path."""
        return hashlib.sha256(str(path.resolve()).encode()).hexdigest()[:32]

    def get(self, path: Path) -> Optional[MediaMetadata]:
        """Get cached metadata if valid.

        Args:
            path: Path to media file

        Returns:
            MediaMetadata if cached and valid, None otherwise
        """
        if not path.exists():
            return None

        path_hash = self._path_hash(path)
        stat = path.stat()

        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM metadata WHERE path_hash = ?",
                (path_hash,),
            ).fetchone()

            if row is None:
                return None

            # Validate cache entry
            if not self._is_valid(row, stat):
                # Remove stale entry
                conn.execute("DELETE FROM metadata WHERE path_hash = ?", (path_hash,))
                return None

            return MediaMetadata(
                width=row["width"],
                height=row["height"],
                video_codec=row["video_codec"],
                video_profile=row["video_profile"],
                color_transfer=row["color_transfer"],
                color_primaries=row["color_primaries"],
                audio_codec=row["audio_codec"],
                audio_channels=row["audio_channels"],
                duration_seconds=row["duration_seconds"],
                bit_rate=row["bit_rate"],
                file_hash=row["file_hash"],
            )

    def _is_valid(self, row: sqlite3.Row, stat) -> bool:
        """Check if cache entry is still valid."""
        # Check file size matches
        if row["file_size"] != stat.st_size:
            return False

        # Check mtime matches (within 1 second tolerance)
        if abs(row["file_mtime"] - stat.st_mtime) > 1.0:
            return False

        return True

    def set(self, path: Path, metadata: MediaMetadata) -> None:
        """Cache metadata for a file.

        Args:
            path: Path to media file
            metadata: Extracted metadata to cache
        """
        if not path.exists():
            return

        path_hash = self._path_hash(path)
        stat = path.stat()
        now = datetime.now().isoformat()

        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO metadata (
                    path_hash, file_path, file_hash, file_size, file_mtime,
                    width, height, video_codec, video_profile,
                    color_transfer, color_primaries,
                    audio_codec, audio_channels,
                    duration_seconds, bit_rate, probed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    path_hash,
                    str(path.resolve()),
                    metadata.file_hash,
                    stat.st_size,
                    stat.st_mtime,
                    metadata.width,
                    metadata.height,
                    metadata.video_codec,
                    metadata.video_profile,
                    metadata.color_transfer,
                    metadata.color_primaries,
                    metadata.audio_codec,
                    metadata.audio_channels,
                    metadata.duration_seconds,
                    metadata.bit_rate,
                    now,
                ),
            )

    def clear(self) -> int:
        """Clear all cached metadata.

        Returns:
            Number of entries cleared
        """
        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM metadata")
            return cursor.rowcount

    def stats(self) -> dict:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        with self._connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM metadata").fetchone()[0]

            oldest = conn.execute(
                "SELECT MIN(probed_at) FROM metadata"
            ).fetchone()[0]

            newest = conn.execute(
                "SELECT MAX(probed_at) FROM metadata"
            ).fetchone()[0]

        # Get database file size
        db_size = self._db_path.stat().st_size if self._db_path.exists() else 0

        return {
            "entries": count,
            "db_size_bytes": db_size,
            "db_size_mb": round(db_size / (1024 * 1024), 2),
            "oldest_entry": oldest,
            "newest_entry": newest,
            "db_path": str(self._db_path),
        }

    def remove(self, path: Path) -> bool:
        """Remove a specific file from cache.

        Args:
            path: Path to remove from cache

        Returns:
            True if entry was removed, False if not found
        """
        path_hash = self._path_hash(path)

        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM metadata WHERE path_hash = ?",
                (path_hash,),
            )
            return cursor.rowcount > 0

    def cleanup_stale(self) -> int:
        """Remove entries for files that no longer exist.

        Returns:
            Number of stale entries removed
        """
        removed = 0

        with self._connection() as conn:
            rows = conn.execute("SELECT path_hash, file_path FROM metadata").fetchall()

            for row in rows:
                if not Path(row["file_path"]).exists():
                    conn.execute(
                        "DELETE FROM metadata WHERE path_hash = ?",
                        (row["path_hash"],),
                    )
                    removed += 1

        return removed
