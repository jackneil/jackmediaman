"""Tests for linker stage."""

import os
from datetime import datetime
from pathlib import Path

import pytest

from jackmediaman.pipeline.stages.linker import LinkerStage
from jackmediaman.pipeline.context import (
    ActionMode,
    FileMapping,
    IdentifiedMedia,
    ProcessContext,
)
from jackmediaman.pipeline.base import StageResult
from jackmediaman.models.media import MediaType, Movie
from jackmediaman.models.quality import Quality, Resolution


def make_movie(
    tmp_path: Path,
    name: str = "movie.mkv",
    title: str = "Test",
    year: int = 2024,
) -> Movie:
    """Create a Movie object with all required fields."""
    path = tmp_path / name
    path.write_text("video content")
    stat = path.stat()
    return Movie(
        path=path,
        filename=path.name,
        size_bytes=stat.st_size,
        quality=Quality(resolution=Resolution.FHD),
        created_at=datetime.fromtimestamp(stat.st_ctime),
        is_symlink=False,
        symlink_target=None,
        title=title,
        year=year,
    )


def make_file_mapping(
    tmp_path: Path,
    src_name: str = "src.mkv",
    dst_subpath: str = "library/dst.mkv",
    create_dirs: bool = True,
) -> tuple:
    """Create a source file and FileMapping."""
    src_dir = tmp_path / "downloads"
    src_dir.mkdir(exist_ok=True)
    src = src_dir / src_name
    src.write_text("video content")

    dst = tmp_path / dst_subpath
    movie = make_movie(tmp_path / "temp", name=src_name)

    identified = IdentifiedMedia(
        source_path=src,
        media_type=MediaType.MOVIE,
        media_item=movie,
    )

    dirs_to_create = [dst.parent] if create_dirs else []
    mapping = FileMapping(
        source=src,
        destination=dst,
        media_item=movie,
        identified=identified,
        create_directories=dirs_to_create,
    )
    return src, dst, mapping


class TestLinkerStage:
    """Tests for LinkerStage."""

    def test_init(self):
        """Can create linker stage."""
        stage = LinkerStage()
        assert stage.name == "linker"
        assert stage.default_action == ActionMode.SYMLINK

    def test_init_with_action(self):
        """Can specify action mode."""
        stage = LinkerStage(action=ActionMode.MOVE)
        assert stage.default_action == ActionMode.MOVE

    def test_validate_with_mappings(self, tmp_path):
        """Validate passes with file mappings."""
        (tmp_path / "temp").mkdir()
        _, _, mapping = make_file_mapping(tmp_path)

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.file_mappings = [mapping]

        stage = LinkerStage()
        assert stage.validate(ctx) is True

    def test_validate_no_mappings(self, tmp_path):
        """Validate fails with no mappings."""
        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)

        stage = LinkerStage()
        assert stage.validate(ctx) is False


class TestCopyAction:
    """Tests for copy action mode."""

    def test_copy_file(self, tmp_path):
        """Copy creates new file in destination."""
        (tmp_path / "temp").mkdir()
        src, dst, mapping = make_file_mapping(tmp_path)

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.COPY)
        ctx.file_mappings = [mapping]

        stage = LinkerStage(action=ActionMode.COPY)
        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert src.exists()  # Original should still exist
        assert dst.exists()  # Copy should exist
        assert dst.read_text() == "video content"

    def test_copy_creates_directories(self, tmp_path):
        """Copy creates destination directories."""
        (tmp_path / "temp").mkdir()
        src, dst, mapping = make_file_mapping(
            tmp_path, dst_subpath="Movies/Test (2024)/Test (2024).mkv"
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.COPY)
        ctx.file_mappings = [mapping]

        stage = LinkerStage(action=ActionMode.COPY)
        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert dst.exists()


class TestMoveAction:
    """Tests for move action mode."""

    def test_move_file(self, tmp_path):
        """Move relocates file to destination."""
        (tmp_path / "temp").mkdir()
        src, dst, mapping = make_file_mapping(tmp_path)

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.MOVE)
        ctx.file_mappings = [mapping]

        stage = LinkerStage(action=ActionMode.MOVE)
        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert not src.exists()  # Original should be gone
        assert dst.exists()  # Destination should exist
        assert dst.read_text() == "video content"


class TestSymlinkAction:
    """Tests for symlink action mode."""

    def test_symlink_file(self, tmp_path):
        """Symlink creates link to original file."""
        (tmp_path / "temp").mkdir()
        src, dst, mapping = make_file_mapping(tmp_path)

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.file_mappings = [mapping]

        stage = LinkerStage(action=ActionMode.SYMLINK)
        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert src.exists()  # Original should still exist
        assert dst.exists()  # Symlink should exist
        assert dst.is_symlink()  # Should be a symlink
        assert dst.read_text() == "video content"  # Should resolve correctly


class TestHardlinkAction:
    """Tests for hardlink action mode."""

    def test_hardlink_file(self, tmp_path):
        """Hardlink creates hard link to original file."""
        (tmp_path / "temp").mkdir()
        src, dst, mapping = make_file_mapping(tmp_path)

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.HARDLINK)
        ctx.file_mappings = [mapping]

        stage = LinkerStage(action=ActionMode.HARDLINK)
        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert src.exists()  # Original should still exist
        assert dst.exists()  # Hardlink should exist
        assert not dst.is_symlink()  # Should NOT be a symlink
        assert dst.read_text() == "video content"

        # Verify same inode (hardlink)
        assert os.stat(src).st_ino == os.stat(dst).st_ino


class TestKeeplinkAction:
    """Tests for keeplink action mode."""

    def test_keeplink_file(self, tmp_path):
        """Keeplink moves file and leaves symlink at original location."""
        (tmp_path / "temp").mkdir()
        src, dst, mapping = make_file_mapping(tmp_path)
        original_location = src

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.KEEPLINK)
        ctx.file_mappings = [mapping]

        stage = LinkerStage(action=ActionMode.KEEPLINK)
        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert dst.exists()  # File should be at destination
        assert not dst.is_symlink()  # Destination is actual file
        assert dst.read_text() == "video content"

        # Original location should now be a symlink
        assert original_location.exists()
        assert original_location.is_symlink()
        # Symlink should point to the destination
        assert original_location.read_text() == "video content"


class TestDryRun:
    """Tests for dry run mode."""

    def test_dry_run_no_changes(self, tmp_path):
        """Dry run doesn't make any changes."""
        (tmp_path / "temp").mkdir()
        src, dst, mapping = make_file_mapping(tmp_path)

        ctx = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.MOVE,
            dry_run=True,
        )
        ctx.file_mappings = [mapping]

        stage = LinkerStage(action=ActionMode.MOVE)
        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert src.exists()  # Original should still exist
        assert not dst.exists()  # Destination should NOT be created


class TestErrorHandling:
    """Tests for error handling in linker."""

    def test_missing_source_file(self, tmp_path):
        """Handle missing source file gracefully."""
        (tmp_path / "temp").mkdir()
        movie = make_movie(tmp_path / "temp")

        # Create mapping with non-existent source
        src = tmp_path / "nonexistent.mkv"
        dst = tmp_path / "dst.mkv"

        identified = IdentifiedMedia(
            source_path=src,
            media_type=MediaType.MOVIE,
            media_item=movie,
        )
        mapping = FileMapping(
            source=src,
            destination=dst,
            media_item=movie,
            identified=identified,
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.COPY)
        ctx.file_mappings = [mapping]

        stage = LinkerStage(action=ActionMode.COPY)
        output = stage.execute(ctx)

        # Should report failure
        assert output.result == StageResult.FAILED
        assert len(ctx.errors) > 0

    def test_destination_already_exists(self, tmp_path):
        """Handle existing destination file."""
        (tmp_path / "temp").mkdir()
        src, dst, mapping = make_file_mapping(tmp_path)

        # Create existing file at destination
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text("existing video")

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.COPY)
        ctx.file_mappings = [mapping]

        stage = LinkerStage(action=ActionMode.COPY)
        output = stage.execute(ctx)

        # Should report failure
        assert output.result == StageResult.FAILED

    def test_tracks_completed_operations(self, tmp_path):
        """Completed operations are tracked for rollback."""
        (tmp_path / "temp").mkdir()
        src, dst, mapping = make_file_mapping(tmp_path)

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.COPY)
        ctx.file_mappings = [mapping]

        stage = LinkerStage(action=ActionMode.COPY)
        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert len(ctx.completed_operations) == 1
        assert ctx.completed_operations[0].success is True


class TestMultipleFiles:
    """Tests for processing multiple files."""

    def test_process_multiple_files(self, tmp_path):
        """Process multiple files in one batch."""
        (tmp_path / "temp").mkdir()
        downloads = tmp_path / "downloads"
        downloads.mkdir()

        mappings = []
        for i in range(3):
            src = downloads / f"movie{i}.mkv"
            src.write_text(f"video {i}")
            dst = tmp_path / "library" / f"Movie {i}" / f"Movie {i}.mkv"

            movie = make_movie(tmp_path / "temp", name=f"movie{i}.mkv", title=f"Movie {i}")
            identified = IdentifiedMedia(
                source_path=src,
                media_type=MediaType.MOVIE,
                media_item=movie,
            )
            mappings.append(
                FileMapping(
                    source=src,
                    destination=dst,
                    media_item=movie,
                    identified=identified,
                    create_directories=[dst.parent],
                )
            )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.file_mappings = mappings

        stage = LinkerStage(action=ActionMode.SYMLINK)
        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert output.items_processed == 3
        assert len(ctx.completed_operations) == 3

        # Verify all files exist
        for mapping in mappings:
            assert mapping.destination.exists()
