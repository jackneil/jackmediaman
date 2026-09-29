"""SQLite database for tracking file operations and symlink relationships."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from jackmediaman.core.logging import get_logger

logger = get_logger("core.operations_db")

# Default database location
DEFAULT_DB_PATH = Path.home() / ".jackmediaman" / "operations.db"


class OperationsDB:
    """Track file operations and symlink relationships in SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the operations database.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.jackmediaman/operations.db
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), timeout=30.0)
            self._conn.row_factory = sqlite3.Row
            # Allow concurrent readers + one writer, and wait on a busy lock
            # instead of immediately failing — Deluge fires Execute hooks in
            # parallel when many torrents complete at once.
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=30000")
        return self._conn

    def _init_schema(self) -> None:
        """Initialize database schema."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # File operations table - tracks all moves, renames, copies, etc.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS file_operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                source_path TEXT NOT NULL,
                dest_path TEXT,
                success INTEGER NOT NULL DEFAULT 1,
                error TEXT,
                metadata TEXT
            )
        """)

        # Symlinks table - tracks symlink → target relationships
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS symlinks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symlink_path TEXT NOT NULL UNIQUE,
                target_path TEXT NOT NULL,
                target_size INTEGER,
                created_at TEXT NOT NULL,
                operation_id INTEGER,
                is_valid INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (operation_id) REFERENCES file_operations(id)
            )
        """)

        # Migration: Add target_size column if it doesn't exist (for existing DBs)
        cursor.execute("PRAGMA table_info(symlinks)")
        columns = [row[1] for row in cursor.fetchall()]
        if "target_size" not in columns:
            cursor.execute("ALTER TABLE symlinks ADD COLUMN target_size INTEGER")

        # Media files table - tracks current location of media files
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                current_path TEXT NOT NULL UNIQUE,
                original_path TEXT,
                media_type TEXT,
                tmdb_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # Activity log table - tracks processing events for easy querying
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                level TEXT NOT NULL,
                category TEXT NOT NULL,
                source_path TEXT,
                message TEXT NOT NULL,
                details TEXT,
                traceback TEXT,
                session_id TEXT
            )
        """)

        # Create indexes for common queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_operations_source
            ON file_operations(source_path)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_operations_dest
            ON file_operations(dest_path)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_symlinks_target
            ON symlinks(target_path)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_media_files_path
            ON media_files(current_path)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_timestamp
            ON activity_log(timestamp)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_session
            ON activity_log(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_activity_source
            ON activity_log(source_path)
        """)

        conn.commit()
        logger.debug(f"Database initialized at {self.db_path}")

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def log_operation(
        self,
        op_type: str,
        source: Path,
        dest: Optional[Path] = None,
        success: bool = True,
        error: Optional[str] = None,
        metadata: Optional[str] = None,
    ) -> int:
        """
        Log a file operation.

        Args:
            op_type: Operation type (move, copy, rename, keeplink, symlink, delete, trash)
            source: Source file path
            dest: Destination path (if applicable)
            success: Whether operation succeeded
            error: Error message if failed
            metadata: Optional JSON metadata

        Returns:
            Operation ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO file_operations (timestamp, operation_type, source_path, dest_path, success, error, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                op_type,
                str(source),
                str(dest) if dest else None,
                1 if success else 0,
                error,
                metadata,
            ),
        )
        conn.commit()

        op_id = cursor.lastrowid
        logger.debug(f"Logged operation {op_id}: {op_type} {source} -> {dest}")
        return op_id

    def log_symlink(
        self,
        symlink_path: Path,
        target_path: Path,
        operation_id: Optional[int] = None,
        target_size: Optional[int] = None,
    ) -> int:
        """
        Log a symlink creation.

        Args:
            symlink_path: Path where symlink is created
            target_path: Path the symlink points to
            operation_id: Optional related operation ID
            target_size: Size of target file in bytes (for verification during repair)

        Returns:
            Symlink record ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Upsert - update if exists, insert if not
        cursor.execute(
            """
            INSERT INTO symlinks (symlink_path, target_path, target_size, created_at, operation_id, is_valid)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(symlink_path) DO UPDATE SET
                target_path = excluded.target_path,
                target_size = COALESCE(excluded.target_size, symlinks.target_size),
                operation_id = excluded.operation_id,
                is_valid = 1
            """,
            (
                str(symlink_path),
                str(target_path),
                target_size,
                datetime.now().isoformat(),
                operation_id,
            ),
        )
        conn.commit()

        symlink_id = cursor.lastrowid
        logger.debug(f"Logged symlink: {symlink_path} -> {target_path} (size={target_size})")
        return symlink_id

    def get_symlinks_for_file(self, file_path: Path) -> List[Path]:
        """
        Get all symlinks that point to a file.

        Args:
            file_path: Path to the target file

        Returns:
            List of symlink paths
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT symlink_path FROM symlinks
            WHERE target_path = ? AND is_valid = 1
            """,
            (str(file_path),),
        )

        return [Path(row["symlink_path"]) for row in cursor.fetchall()]

    def update_symlink_target(
        self,
        symlink_path: Path,
        new_target: Path,
    ) -> bool:
        """
        Update the target of a symlink record.

        Args:
            symlink_path: Path to the symlink
            new_target: New target path

        Returns:
            True if record was updated
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE symlinks
            SET target_path = ?, is_valid = 1
            WHERE symlink_path = ?
            """,
            (str(new_target), str(symlink_path)),
        )
        conn.commit()

        updated = cursor.rowcount > 0
        if updated:
            logger.debug(f"Updated symlink target: {symlink_path} -> {new_target}")
        return updated

    def get_symlink_target_size(self, symlink_path: Path) -> Optional[int]:
        """
        Get the stored target size for a symlink.

        Args:
            symlink_path: Path to the symlink

        Returns:
            Target file size in bytes, or None if not stored
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT target_size FROM symlinks WHERE symlink_path = ?",
            (str(symlink_path),),
        )
        row = cursor.fetchone()
        return row["target_size"] if row else None

    def get_symlink_info(self, symlink_path: Path) -> Optional[dict]:
        """
        Get full info for a symlink.

        Args:
            symlink_path: Path to the symlink

        Returns:
            Dict with symlink info or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM symlinks WHERE symlink_path = ?",
            (str(symlink_path),),
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def mark_symlink_invalid(self, symlink_path: Path) -> bool:
        """Mark a symlink as invalid/broken."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE symlinks SET is_valid = 0 WHERE symlink_path = ?
            """,
            (str(symlink_path),),
        )
        conn.commit()
        return cursor.rowcount > 0

    def find_broken_symlinks(self) -> List[Tuple[Path, Path]]:
        """
        Find symlinks marked as broken or with missing targets.

        Returns:
            List of (symlink_path, target_path) tuples
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT symlink_path, target_path FROM symlinks
            WHERE is_valid = 0 OR NOT EXISTS (
                SELECT 1 FROM media_files WHERE current_path = symlinks.target_path
            )
        """)

        return [(Path(row["symlink_path"]), Path(row["target_path"])) for row in cursor.fetchall()]

    def log_media_file(
        self,
        current_path: Path,
        original_path: Optional[Path] = None,
        media_type: Optional[str] = None,
        tmdb_id: Optional[int] = None,
    ) -> int:
        """
        Log or update a media file record.

        Args:
            current_path: Current file path
            original_path: Original path before any moves
            media_type: Type of media (movie, episode)
            tmdb_id: TMDb ID if known

        Returns:
            Media file record ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        cursor.execute(
            """
            INSERT INTO media_files (current_path, original_path, media_type, tmdb_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(current_path) DO UPDATE SET
                media_type = COALESCE(excluded.media_type, media_files.media_type),
                tmdb_id = COALESCE(excluded.tmdb_id, media_files.tmdb_id),
                updated_at = excluded.updated_at
            """,
            (
                str(current_path),
                str(original_path) if original_path else None,
                media_type,
                tmdb_id,
                now,
                now,
            ),
        )
        conn.commit()

        return cursor.lastrowid

    def update_media_file_path(self, old_path: Path, new_path: Path) -> bool:
        """
        Update a media file's current path after a rename/move.

        Args:
            old_path: Previous path
            new_path: New path

        Returns:
            True if record was updated
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE media_files
            SET current_path = ?, updated_at = ?
            WHERE current_path = ?
            """,
            (str(new_path), datetime.now().isoformat(), str(old_path)),
        )
        conn.commit()

        updated = cursor.rowcount > 0
        if updated:
            logger.debug(f"Updated media file path: {old_path} -> {new_path}")
        return updated

    def get_file_history(self, file_path: Path) -> List[dict]:
        """
        Get operation history for a file.

        Args:
            file_path: Path to search for

        Returns:
            List of operation records
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM file_operations
            WHERE source_path = ? OR dest_path = ?
            ORDER BY timestamp DESC
            """,
            (str(file_path), str(file_path)),
        )

        return [dict(row) for row in cursor.fetchall()]

    def get_all_symlinks(self) -> List[Tuple[Path, Path, bool]]:
        """
        Get all tracked symlinks.

        Returns:
            List of (symlink_path, target_path, is_valid) tuples
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT symlink_path, target_path, is_valid FROM symlinks
            ORDER BY created_at DESC
        """)

        return [
            (Path(row["symlink_path"]), Path(row["target_path"]), bool(row["is_valid"]))
            for row in cursor.fetchall()
        ]

    def get_stats(self) -> dict:
        """Get database statistics."""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        cursor.execute("SELECT COUNT(*) as count FROM file_operations")
        stats["total_operations"] = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM symlinks")
        stats["total_symlinks"] = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM symlinks WHERE is_valid = 1")
        stats["valid_symlinks"] = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM media_files")
        stats["tracked_files"] = cursor.fetchone()["count"]

        cursor.execute("""
            SELECT operation_type, COUNT(*) as count
            FROM file_operations
            GROUP BY operation_type
        """)
        stats["operations_by_type"] = {row["operation_type"]: row["count"] for row in cursor.fetchall()}

        return stats

    # =========================================================================
    # Activity Log Methods
    # =========================================================================

    def log_activity(
        self,
        level: str,
        category: str,
        message: str,
        source_path: Optional[str] = None,
        details: Optional[str] = None,
        traceback_str: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> int:
        """
        Log a processing activity event.

        Args:
            level: Log level (INFO, WARNING, ERROR, DEBUG)
            category: Event category (process, stage, identification, etc.)
            message: Human-readable message
            source_path: Path being processed (torrent/file)
            details: JSON string with extra data
            traceback_str: Full traceback for errors
            session_id: Groups related log entries

        Returns:
            Activity log ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO activity_log (timestamp, level, category, source_path, message, details, traceback, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(),
                level,
                category,
                source_path,
                message,
                details,
                traceback_str,
                session_id,
            ),
        )
        conn.commit()

        log_id = cursor.lastrowid
        # Also log to file logger
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"[{category}] {message}")
        return log_id

    def get_recent_activity(
        self,
        limit: int = 100,
        category: Optional[str] = None,
        level: Optional[str] = None,
    ) -> List[dict]:
        """
        Get recent activity log entries.

        Args:
            limit: Maximum entries to return
            category: Filter by category
            level: Filter by level (INFO, WARNING, ERROR)

        Returns:
            List of activity log entries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM activity_log WHERE 1=1"
        params = []

        if category:
            query += " AND category = ?"
            params.append(category)
        if level:
            query += " AND level = ?"
            params.append(level)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_activity_for_file(self, source_path: str) -> List[dict]:
        """
        Get all activity log entries for a specific file/path.

        Args:
            source_path: Path to search for

        Returns:
            List of activity log entries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM activity_log
            WHERE source_path = ? OR source_path LIKE ?
            ORDER BY timestamp DESC
            """,
            (source_path, f"%{source_path}%"),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_session_activity(self, session_id: str) -> List[dict]:
        """
        Get all activity log entries for a processing session.

        Args:
            session_id: Session ID to search for

        Returns:
            List of activity log entries in chronological order
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM activity_log
            WHERE session_id = ?
            ORDER BY timestamp ASC
            """,
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


# Singleton instance
_db_instance: Optional[OperationsDB] = None


def get_operations_db(db_path: Optional[Path] = None) -> OperationsDB:
    """Get the singleton operations database instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = OperationsDB(db_path)
    return _db_instance
