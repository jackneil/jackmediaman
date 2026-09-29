"""Tests for operations database."""

from pathlib import Path

import pytest

from jackmediaman.core.operations_db import OperationsDB


class TestOperationsDB:
    """Tests for OperationsDB class."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_operations.db"
        return OperationsDB(db_path)

    def test_log_symlink_basic(self, db):
        """Log a basic symlink without size."""
        symlink_id = db.log_symlink(
            symlink_path=Path("/torrents/show.mkv"),
            target_path=Path("/media/show.mkv"),
        )
        assert symlink_id > 0

    def test_log_symlink_with_target_size(self, db):
        """Log a symlink with target file size."""
        symlink_id = db.log_symlink(
            symlink_path=Path("/torrents/show.mkv"),
            target_path=Path("/media/show.mkv"),
            target_size=1234567890,
        )
        assert symlink_id > 0

        # Verify size was stored
        size = db.get_symlink_target_size(Path("/torrents/show.mkv"))
        assert size == 1234567890

    def test_get_symlink_target_size_returns_none_if_not_stored(self, db):
        """get_symlink_target_size returns None if size wasnt stored."""
        db.log_symlink(
            symlink_path=Path("/torrents/show.mkv"),
            target_path=Path("/media/show.mkv"),
            target_size=None,
        )
        size = db.get_symlink_target_size(Path("/torrents/show.mkv"))
        assert size is None

    def test_get_symlink_target_size_returns_none_if_not_found(self, db):
        """get_symlink_target_size returns None if symlink not in DB."""
        size = db.get_symlink_target_size(Path("/nonexistent/path.mkv"))
        assert size is None

    def test_upsert_preserves_size(self, db):
        """Upserting a symlink preserves existing size if new size is None."""
        # First insert with size
        db.log_symlink(
            symlink_path=Path("/torrents/show.mkv"),
            target_path=Path("/media/show.mkv"),
            target_size=1000,
        )

        # Upsert without size
        db.log_symlink(
            symlink_path=Path("/torrents/show.mkv"),
            target_path=Path("/media/new_show.mkv"),
            target_size=None,
        )

        # Size should be preserved
        size = db.get_symlink_target_size(Path("/torrents/show.mkv"))
        assert size == 1000

    def test_upsert_updates_size(self, db):
        """Upserting a symlink can update the size."""
        # First insert with size
        db.log_symlink(
            symlink_path=Path("/torrents/show.mkv"),
            target_path=Path("/media/show.mkv"),
            target_size=1000,
        )

        # Upsert with new size
        db.log_symlink(
            symlink_path=Path("/torrents/show.mkv"),
            target_path=Path("/media/show.mkv"),
            target_size=2000,
        )

        # Size should be updated
        size = db.get_symlink_target_size(Path("/torrents/show.mkv"))
        assert size == 2000

    def test_get_symlink_info_includes_size(self, db):
        """get_symlink_info includes target_size."""
        db.log_symlink(
            symlink_path=Path("/torrents/show.mkv"),
            target_path=Path("/media/show.mkv"),
            target_size=5555555555,
        )

        info = db.get_symlink_info(Path("/torrents/show.mkv"))
        assert info is not None
        assert info["target_size"] == 5555555555

    def test_get_symlink_info_returns_none_if_not_found(self, db):
        """get_symlink_info returns None if symlink not in DB."""
        info = db.get_symlink_info(Path("/nonexistent/path.mkv"))
        assert info is None


class TestOperationsDBMigration:
    """Tests for database migration (adding target_size column)."""

    def test_migration_adds_target_size_column(self, tmp_path):
        """Schema migration adds target_size column to existing DB."""
        import sqlite3

        db_path = tmp_path / "legacy.db"

        # Create a database WITHOUT target_size column (simulating old schema)
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE symlinks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symlink_path TEXT NOT NULL UNIQUE,
                target_path TEXT NOT NULL,
                created_at TEXT NOT NULL,
                operation_id INTEGER,
                is_valid INTEGER NOT NULL DEFAULT 1
            )
        """)
        # Insert a row
        cursor.execute(
            "INSERT INTO symlinks (symlink_path, target_path, created_at) VALUES (?, ?, ?)",
            ("/test/symlink.mkv", "/test/target.mkv", "2024-01-01"),
        )
        conn.commit()
        conn.close()

        # Now open with OperationsDB - should migrate
        db = OperationsDB(db_path)

        # Verify the column was added and data preserved
        info = db.get_symlink_info(Path("/test/symlink.mkv"))
        assert info is not None
        assert info["symlink_path"] == "/test/symlink.mkv"
        assert info["target_size"] is None  # New column, no value yet

        # Should be able to update with size
        db.log_symlink(
            symlink_path=Path("/test/symlink.mkv"),
            target_path=Path("/test/target.mkv"),
            target_size=9999,
        )

        size = db.get_symlink_target_size(Path("/test/symlink.mkv"))
        assert size == 9999


class TestOperationsDBFileOperations:
    """Tests for logging file operations."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a temporary database for testing."""
        db_path = tmp_path / "test_operations.db"
        return OperationsDB(db_path)

    def test_log_operation(self, db):
        """Log a file operation."""
        op_id = db.log_operation(
            op_type="move",
            source=Path("/source/file.mkv"),
            dest=Path("/dest/file.mkv"),
            success=True,
        )
        assert op_id > 0

    def test_log_operation_with_error(self, db):
        """Log a failed operation with error."""
        op_id = db.log_operation(
            op_type="move",
            source=Path("/source/file.mkv"),
            dest=Path("/dest/file.mkv"),
            success=False,
            error="Permission denied",
        )
        assert op_id > 0

    def test_get_file_history(self, db):
        """Get operation history for a file."""
        # Log some operations
        db.log_operation(
            op_type="rename",
            source=Path("/media/file.mkv"),
            dest=Path("/media/renamed.mkv"),
        )
        db.log_operation(
            op_type="move",
            source=Path("/media/renamed.mkv"),
            dest=Path("/media/TV/renamed.mkv"),
        )

        history = db.get_file_history(Path("/media/renamed.mkv"))
        assert len(history) == 2
