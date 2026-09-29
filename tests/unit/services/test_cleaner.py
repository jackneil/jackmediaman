"""Tests for cleanup service."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from jackmediaman.services.cleaner import (
    CleanupService,
    CleanupResult,
    CleanupSummary,
)
from jackmediaman.models.media import Movie
from jackmediaman.models.duplicates import DuplicateGroup
from jackmediaman.models.quality import Quality, Resolution


class TestCleanupResult:
    """Tests for CleanupResult dataclass."""

    def test_successful_result(self, tmp_path, sample_movie):
        """Create successful cleanup result."""
        result = CleanupResult(
            item=sample_movie,
            destination=tmp_path / "trash" / "movie.mkv",
            success=True,
        )
        assert result.success is True
        assert result.error is None

    def test_failed_result(self, tmp_path, sample_movie):
        """Create failed cleanup result."""
        result = CleanupResult(
            item=sample_movie,
            destination=tmp_path / "trash" / "movie.mkv",
            success=False,
            error="Permission denied",
        )
        assert result.success is False
        assert result.error == "Permission denied"


class TestCleanupSummary:
    """Tests for CleanupSummary dataclass."""

    def test_total_gb_freed(self, tmp_path, sample_movie):
        """Calculates total GB freed."""
        result = CleanupResult(
            item=sample_movie,
            destination=tmp_path / "trash",
            success=True,
        )
        summary = CleanupSummary(
            total_groups=1,
            total_files_removed=1,
            total_bytes_freed=2 * 1024 * 1024 * 1024,  # 2 GB
            results=[result],
        )
        assert summary.total_gb_freed == 2.0


class TestCleanupService:
    """Tests for CleanupService class."""

    @pytest.fixture
    def cleaner(self, tmp_path):
        """Create cleanup service with temp trash dir."""
        return CleanupService(trash_dir=tmp_path / "trash")

    def test_prepare_trash(self, cleaner):
        """Prepare trash creates directory."""
        assert not cleaner.trash_dir.exists()
        cleaner.prepare_trash()
        assert cleaner.trash_dir.exists()

    def test_get_trash_path(self, cleaner, sample_movie):
        """Get trash path includes timestamp."""
        trash_path = cleaner.get_trash_path(sample_movie)
        assert cleaner.trash_dir in trash_path.parents or trash_path.parent == cleaner.trash_dir
        assert sample_movie.filename in trash_path.name

    def test_move_to_trash_dry_run(self, cleaner, tmp_path, sample_movie):
        """Dry run doesn't actually move file."""
        # Create the actual file
        sample_movie.path.write_bytes(b"0" * 100)

        result = cleaner.move_to_trash(sample_movie, dry_run=True)

        assert result.success is True
        assert sample_movie.path.exists()  # File still exists
        assert not result.destination.exists()

    @patch("shutil.move")
    def test_move_to_trash_actual(self, mock_move, cleaner, tmp_path, sample_movie):
        """Actual move calls shutil.move."""
        # Create the actual file
        sample_movie.path.write_bytes(b"0" * 100)

        result = cleaner.move_to_trash(sample_movie, dry_run=False)

        assert result.success is True
        mock_move.assert_called_once()

    @patch("shutil.move")
    def test_move_to_trash_error(self, mock_move, cleaner, tmp_path, sample_movie):
        """Move handles errors gracefully."""
        import shutil
        mock_move.side_effect = shutil.Error("Permission denied")

        sample_movie.path.write_bytes(b"0" * 100)
        result = cleaner.move_to_trash(sample_movie, dry_run=False)

        assert result.success is False
        assert "Permission denied" in result.error


class TestCleanupServiceGroups:
    """Tests for cleaning up duplicate groups."""

    @pytest.fixture
    def cleaner(self, tmp_path):
        return CleanupService(trash_dir=tmp_path / "trash")

    def test_cleanup_group_dry_run(self, cleaner, movie_duplicate_group):
        """Cleanup group returns results for removable items."""
        results = cleaner.cleanup_group(movie_duplicate_group, dry_run=True)

        # Should have results for removable items only
        assert len(results) == len(movie_duplicate_group.removable_items)
        assert all(r.success for r in results)

    def test_cleanup_groups_summary(self, cleaner, movie_duplicate_group):
        """Cleanup groups returns summary."""
        summary = cleaner.cleanup_groups([movie_duplicate_group], dry_run=True)

        assert isinstance(summary, CleanupSummary)
        assert summary.total_groups == 1
        assert summary.total_files_removed >= 0

    def test_cleanup_groups_progress_callback(self, cleaner, movie_duplicate_group):
        """Cleanup groups calls progress callback."""
        callback = MagicMock()

        cleaner.cleanup_groups(
            [movie_duplicate_group],
            dry_run=True,
            progress_callback=callback,
        )

        callback.assert_called()


class TestCleanupServiceRestore:
    """Tests for restoring files from trash."""

    @pytest.fixture
    def cleaner(self, tmp_path):
        return CleanupService(trash_dir=tmp_path / "trash")

    def test_restore_from_trash(self, cleaner, tmp_path):
        """Restore moves file back to original location."""
        # Set up trash file
        cleaner.prepare_trash()
        trash_file = cleaner.trash_dir / "20231201_120000_movie.mkv"
        trash_file.write_bytes(b"0" * 100)

        # Restore
        original = tmp_path / "Movies" / "movie.mkv"
        result = cleaner.restore_from_trash(trash_file, original)

        assert result is True
        assert original.exists()
        assert not trash_file.exists()

    def test_restore_creates_parent_dir(self, cleaner, tmp_path):
        """Restore creates parent directory if needed."""
        cleaner.prepare_trash()
        trash_file = cleaner.trash_dir / "movie.mkv"
        trash_file.write_bytes(b"0" * 100)

        original = tmp_path / "new_dir" / "subdir" / "movie.mkv"
        result = cleaner.restore_from_trash(trash_file, original)

        assert result is True
        assert original.parent.exists()


class TestCleanupServiceTrashListing:
    """Tests for listing trash contents."""

    @pytest.fixture
    def cleaner(self, tmp_path):
        return CleanupService(trash_dir=tmp_path / "trash")

    def test_list_trash_empty(self, cleaner):
        """List trash when empty or nonexistent."""
        files = cleaner.list_trash()
        assert files == []

    def test_list_trash_with_files(self, cleaner):
        """List trash with timestamped files."""
        cleaner.prepare_trash()
        (cleaner.trash_dir / "20231201_120000_movie1.mkv").write_bytes(b"0")
        (cleaner.trash_dir / "20231202_130000_movie2.mkv").write_bytes(b"0")

        files = cleaner.list_trash()

        assert len(files) == 2
        # Should be sorted by timestamp descending (newest first)
        assert "movie2" in files[0][0].name
        assert "movie1" in files[1][0].name

    def test_list_trash_returns_timestamps(self, cleaner):
        """List trash includes parsed timestamps."""
        cleaner.prepare_trash()
        (cleaner.trash_dir / "20231201_120000_movie.mkv").write_bytes(b"0")

        files = cleaner.list_trash()

        assert len(files) == 1
        path, timestamp = files[0]
        assert isinstance(timestamp, datetime)
        assert timestamp.year == 2023
        assert timestamp.month == 12
        assert timestamp.day == 1


class TestCleanupServiceEmptyTrash:
    """Tests for emptying trash."""

    @pytest.fixture
    def cleaner(self, tmp_path):
        return CleanupService(trash_dir=tmp_path / "trash")

    def test_empty_trash_all(self, cleaner):
        """Empty trash deletes all files."""
        cleaner.prepare_trash()
        (cleaner.trash_dir / "movie1.mkv").write_bytes(b"0")
        (cleaner.trash_dir / "movie2.mkv").write_bytes(b"0")

        deleted = cleaner.empty_trash()

        assert deleted == 2
        assert len(list(cleaner.trash_dir.iterdir())) == 0

    def test_empty_trash_nonexistent(self, cleaner):
        """Empty trash when directory doesn't exist."""
        deleted = cleaner.empty_trash()
        assert deleted == 0

    def test_empty_trash_older_than(self, cleaner, tmp_path):
        """Empty trash only removes files older than specified days."""
        import os
        cleaner.prepare_trash()

        # Create old file
        old_file = cleaner.trash_dir / "old_movie.mkv"
        old_file.write_bytes(b"0")
        # Set mtime to 30 days ago
        old_time = datetime.now().timestamp() - (30 * 86400)
        os.utime(old_file, (old_time, old_time))

        # Create new file
        new_file = cleaner.trash_dir / "new_movie.mkv"
        new_file.write_bytes(b"0")

        deleted = cleaner.empty_trash(older_than_days=7)

        assert deleted == 1
        assert not old_file.exists()
        assert new_file.exists()
