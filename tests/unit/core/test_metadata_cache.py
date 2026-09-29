"""Tests for metadata cache."""

import time
from pathlib import Path

import pytest

from jackmediaman.core.ffprobe import MediaMetadata
from jackmediaman.core.metadata_cache import MetadataCache


class TestMetadataCacheInit:
    """Tests for MetadataCache initialization."""

    def test_creates_db_file(self, tmp_path):
        """Creates database file on init."""
        db_path = tmp_path / "cache" / "metadata.db"
        cache = MetadataCache(db_path)

        assert db_path.exists()

    def test_creates_parent_directories(self, tmp_path):
        """Creates parent directories if needed."""
        db_path = tmp_path / "nested" / "dir" / "metadata.db"
        cache = MetadataCache(db_path)

        assert db_path.parent.exists()

    def test_default_path(self):
        """Uses default path in home directory."""
        cache = MetadataCache()
        assert ".jackmediaman" in str(cache._db_path)
        assert "metadata.db" in str(cache._db_path)


class TestMetadataCacheGetSet:
    """Tests for get and set operations."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return MetadataCache(tmp_path / "test.db")

    @pytest.fixture
    def sample_metadata(self):
        """Create sample metadata."""
        return MediaMetadata(
            width=1920,
            height=1080,
            video_codec="x264",
            video_profile="High",
            color_transfer=None,
            color_primaries=None,
            audio_codec="AAC",
            audio_channels=2,
            duration_seconds=3600.0,
            bit_rate=5000000,
            file_hash="abc123def456",
        )

    def test_get_nonexistent(self, cache, tmp_path):
        """Returns None for uncached file."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        result = cache.get(video_file)
        assert result is None

    def test_get_file_not_exists(self, cache, tmp_path):
        """Returns None when file doesn't exist."""
        result = cache.get(tmp_path / "nonexistent.mkv")
        assert result is None

    def test_set_and_get(self, cache, tmp_path, sample_metadata):
        """Can set and retrieve metadata."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        cache.set(video_file, sample_metadata)
        result = cache.get(video_file)

        assert result is not None
        assert result.width == 1920
        assert result.height == 1080
        assert result.video_codec == "x264"
        assert result.audio_codec == "AAC"
        assert result.duration_seconds == 3600.0

    def test_set_nonexistent_file(self, cache, tmp_path, sample_metadata):
        """Set does nothing for nonexistent file."""
        # Should not raise error
        cache.set(tmp_path / "nonexistent.mkv", sample_metadata)

    def test_update_existing(self, cache, tmp_path, sample_metadata):
        """Can update existing cache entry."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        cache.set(video_file, sample_metadata)

        # Update with different metadata
        updated = MediaMetadata(
            width=3840,
            height=2160,
            video_codec="x265",
            file_hash="new_hash",
        )
        cache.set(video_file, updated)

        result = cache.get(video_file)
        assert result.width == 3840
        assert result.video_codec == "x265"


class TestMetadataCacheInvalidation:
    """Tests for cache invalidation."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return MetadataCache(tmp_path / "test.db")

    @pytest.fixture
    def sample_metadata(self):
        """Create sample metadata."""
        return MediaMetadata(
            width=1920,
            height=1080,
            video_codec="x264",
            file_hash="abc123",
        )

    def test_invalidate_on_size_change(self, cache, tmp_path, sample_metadata):
        """Invalidates cache when file size changes."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        cache.set(video_file, sample_metadata)

        # Change file size
        video_file.write_bytes(b"0" * 2000)

        result = cache.get(video_file)
        assert result is None  # Cache invalidated

    def test_invalidate_on_mtime_change(self, cache, tmp_path, sample_metadata):
        """Invalidates cache when modification time changes."""
        import os

        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        cache.set(video_file, sample_metadata)

        # Modify the file's mtime to be significantly different
        # Use os.utime to set a future mtime (2 seconds in the future)
        stat = video_file.stat()
        os.utime(video_file, (stat.st_atime, stat.st_mtime + 2.0))

        result = cache.get(video_file)
        assert result is None  # Cache invalidated

    def test_valid_within_mtime_tolerance(self, cache, tmp_path, sample_metadata):
        """Cache stays valid within mtime tolerance."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        cache.set(video_file, sample_metadata)

        # Reading immediately should still be valid
        result = cache.get(video_file)
        assert result is not None


class TestMetadataCacheClear:
    """Tests for cache clearing."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return MetadataCache(tmp_path / "test.db")

    def test_clear_empty_cache(self, cache):
        """Clearing empty cache returns 0."""
        cleared = cache.clear()
        assert cleared == 0

    def test_clear_with_entries(self, cache, tmp_path):
        """Clears all entries and returns count."""
        # Add some entries
        for i in range(3):
            video_file = tmp_path / f"video{i}.mkv"
            video_file.write_bytes(b"0" * 1000)
            metadata = MediaMetadata(
                width=1920, height=1080, video_codec="x264", file_hash=f"hash{i}"
            )
            cache.set(video_file, metadata)

        cleared = cache.clear()

        assert cleared == 3

        # Verify entries are gone
        stats = cache.stats()
        assert stats["entries"] == 0


class TestMetadataCacheStats:
    """Tests for cache statistics."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return MetadataCache(tmp_path / "test.db")

    def test_stats_empty_cache(self, cache):
        """Returns stats for empty cache."""
        stats = cache.stats()

        assert stats["entries"] == 0
        assert stats["oldest_entry"] is None
        assert stats["newest_entry"] is None
        assert "db_path" in stats
        assert "db_size_mb" in stats

    def test_stats_with_entries(self, cache, tmp_path):
        """Returns stats for populated cache."""
        # Add some entries
        for i in range(5):
            video_file = tmp_path / f"video{i}.mkv"
            video_file.write_bytes(b"0" * 1000)
            metadata = MediaMetadata(
                width=1920, height=1080, video_codec="x264", file_hash=f"hash{i}"
            )
            cache.set(video_file, metadata)
            time.sleep(0.01)  # Small delay for timestamp ordering

        stats = cache.stats()

        assert stats["entries"] == 5
        assert stats["oldest_entry"] is not None
        assert stats["newest_entry"] is not None
        assert stats["db_size_bytes"] > 0


class TestMetadataCacheRemove:
    """Tests for removing specific entries."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return MetadataCache(tmp_path / "test.db")

    def test_remove_nonexistent(self, cache, tmp_path):
        """Removing nonexistent entry returns False."""
        result = cache.remove(tmp_path / "nonexistent.mkv")
        assert result is False

    def test_remove_existing(self, cache, tmp_path):
        """Removing existing entry returns True."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)
        metadata = MediaMetadata(
            width=1920, height=1080, video_codec="x264", file_hash="testhash"
        )
        cache.set(video_file, metadata)

        result = cache.remove(video_file)

        assert result is True

        # Verify entry is gone
        assert cache.get(video_file) is None


class TestMetadataCacheCleanupStale:
    """Tests for stale entry cleanup."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return MetadataCache(tmp_path / "test.db")

    def test_cleanup_no_stale(self, cache, tmp_path):
        """No cleanup needed when all files exist."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)
        metadata = MediaMetadata(
            width=1920, height=1080, video_codec="x264", file_hash="testhash"
        )
        cache.set(video_file, metadata)

        removed = cache.cleanup_stale()

        assert removed == 0
        assert cache.stats()["entries"] == 1

    def test_cleanup_removes_deleted_files(self, cache, tmp_path):
        """Removes entries for deleted files."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)
        metadata = MediaMetadata(
            width=1920, height=1080, video_codec="x264", file_hash="testhash"
        )
        cache.set(video_file, metadata)

        # Delete the file
        video_file.unlink()

        removed = cache.cleanup_stale()

        assert removed == 1
        assert cache.stats()["entries"] == 0

    def test_cleanup_mixed_entries(self, cache, tmp_path):
        """Removes only stale entries, keeps valid ones."""
        # Create files
        valid_file = tmp_path / "valid.mkv"
        stale_file = tmp_path / "stale.mkv"
        valid_file.write_bytes(b"0" * 1000)
        stale_file.write_bytes(b"0" * 1000)

        # Cache both
        metadata_valid = MediaMetadata(
            width=1920, height=1080, video_codec="x264", file_hash="hash_valid"
        )
        metadata_stale = MediaMetadata(
            width=1920, height=1080, video_codec="x264", file_hash="hash_stale"
        )
        cache.set(valid_file, metadata_valid)
        cache.set(stale_file, metadata_stale)

        # Delete one file
        stale_file.unlink()

        removed = cache.cleanup_stale()

        assert removed == 1
        assert cache.stats()["entries"] == 1
        assert cache.get(valid_file) is not None


class TestMetadataCachePathHashing:
    """Tests for path hash consistency."""

    @pytest.fixture
    def cache(self, tmp_path):
        """Create cache with test database."""
        return MetadataCache(tmp_path / "test.db")

    def test_same_path_same_hash(self, cache, tmp_path):
        """Same path produces same hash."""
        path = tmp_path / "video.mkv"
        hash1 = cache._path_hash(path)
        hash2 = cache._path_hash(path)
        assert hash1 == hash2

    def test_different_paths_different_hash(self, cache, tmp_path):
        """Different paths produce different hashes."""
        path1 = tmp_path / "video1.mkv"
        path2 = tmp_path / "video2.mkv"
        hash1 = cache._path_hash(path1)
        hash2 = cache._path_hash(path2)
        assert hash1 != hash2

    def test_hash_length(self, cache, tmp_path):
        """Hash is truncated to 32 characters."""
        path = tmp_path / "video.mkv"
        hash_result = cache._path_hash(path)
        assert len(hash_result) == 32
