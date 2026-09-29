"""Tests for pipeline context and data models."""

from datetime import datetime
from pathlib import Path

import pytest

from jackmediaman.pipeline.context import (
    ActionMode,
    FileMapping,
    IdentifiedMedia,
    LinkOperation,
    ProcessContext,
    StageError,
)
from jackmediaman.models.media import MediaType, Movie
from jackmediaman.models.quality import Quality, Resolution


def make_movie(tmp_path: Path, name: str = "movie.mkv", title: str = "Test", year: int = 2024) -> Movie:
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


class TestActionMode:
    """Tests for ActionMode enum."""

    def test_all_action_modes_exist(self):
        """Verify all expected action modes are defined."""
        assert ActionMode.MOVE == "move"
        assert ActionMode.COPY == "copy"
        assert ActionMode.HARDLINK == "hardlink"
        assert ActionMode.SYMLINK == "symlink"
        assert ActionMode.KEEPLINK == "keeplink"

    def test_action_mode_from_string(self):
        """Can create ActionMode from string value."""
        assert ActionMode("move") == ActionMode.MOVE
        assert ActionMode("keeplink") == ActionMode.KEEPLINK


class TestProcessContext:
    """Tests for ProcessContext dataclass."""

    def test_create_minimal_context(self, tmp_path):
        """Create context with only required fields."""
        ctx = ProcessContext(
            source_path=tmp_path / "test",
            action=ActionMode.SYMLINK,
        )
        assert ctx.source_path == tmp_path / "test"
        assert ctx.action == ActionMode.SYMLINK
        assert ctx.dry_run is False
        assert ctx.extracted_files == []
        assert ctx.identified_media == []
        assert ctx.file_mappings == []
        assert ctx.completed_operations == []
        assert ctx.errors == []

    def test_create_context_with_options(self, tmp_path):
        """Create context with all options specified."""
        ctx = ProcessContext(
            source_path=tmp_path / "torrent",
            action=ActionMode.KEEPLINK,
            dry_run=True,
            skip_extraction=True,
            skip_tmdb=True,
            skip_subtitles=True,
            skip_artwork=True,
            work_dir=tmp_path / "work",
        )
        assert ctx.dry_run is True
        assert ctx.skip_extraction is True
        assert ctx.skip_tmdb is True
        assert ctx.skip_subtitles is True
        assert ctx.skip_artwork is True
        assert ctx.work_dir == tmp_path / "work"

    def test_add_error(self, tmp_path):
        """Can add errors to context."""
        ctx = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
        )
        ctx.add_error("extractor", "Failed to extract", tmp_path / "file.rar")

        assert len(ctx.errors) == 1
        assert ctx.errors[0].stage == "extractor"
        assert ctx.errors[0].error == "Failed to extract"
        assert ctx.errors[0].path == tmp_path / "file.rar"

    def test_add_error_without_path(self, tmp_path):
        """Can add errors without a path."""
        ctx = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
        )
        ctx.add_error("identifier", "TMDb lookup failed")

        assert len(ctx.errors) == 1
        assert ctx.errors[0].path is None

    def test_video_files_from_extracted(self, tmp_path):
        """video_files property returns extracted_files if set."""
        video = tmp_path / "video.mkv"
        video.write_text("video")

        ctx = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
        )
        ctx.extracted_files = [video]

        assert ctx.video_files == [video]

    def test_video_files_from_source_file(self, tmp_path):
        """video_files property returns source if it's a file."""
        video = tmp_path / "video.mkv"
        video.write_text("video")

        ctx = ProcessContext(
            source_path=video,
            action=ActionMode.SYMLINK,
        )

        assert ctx.video_files == [video]

    def test_video_files_from_source_dir(self, tmp_path):
        """video_files property scans directory for videos."""
        (tmp_path / "movie.mkv").write_text("video")
        (tmp_path / "movie.mp4").write_text("video")
        (tmp_path / "readme.txt").write_text("text")

        ctx = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
        )

        video_files = ctx.video_files
        assert len(video_files) == 2
        extensions = {f.suffix for f in video_files}
        assert extensions == {".mkv", ".mp4"}


class TestStageError:
    """Tests for StageError dataclass."""

    def test_create_stage_error(self, tmp_path):
        """Create a stage error with all fields."""
        error = StageError(
            stage="linker",
            error="Permission denied",
            path=tmp_path / "movie.mkv",
        )
        assert error.stage == "linker"
        assert error.error == "Permission denied"
        assert error.path == tmp_path / "movie.mkv"
        assert error.recoverable is True


class TestIdentifiedMedia:
    """Tests for IdentifiedMedia dataclass."""

    def test_create_identified_movie(self, tmp_path):
        """Create identified media for a movie."""
        movie = make_movie(tmp_path, title="The Matrix", year=1999)
        identified = IdentifiedMedia(
            source_path=tmp_path / "movie.mkv",
            media_type=MediaType.MOVIE,
            media_item=movie,
            tmdb_id=603,
            canonical_title="The Matrix",
            canonical_year=1999,
            confidence=0.95,
        )
        assert identified.media_type == MediaType.MOVIE
        assert identified.tmdb_id == 603
        assert identified.confidence == 0.95


class TestFileMapping:
    """Tests for FileMapping dataclass."""

    def test_create_file_mapping(self, tmp_path):
        """Create a file mapping."""
        movie = make_movie(tmp_path)
        identified = IdentifiedMedia(
            source_path=movie.path,
            media_type=MediaType.MOVIE,
            media_item=movie,
        )
        mapping = FileMapping(
            source=tmp_path / "downloads" / "movie.mkv",
            destination=tmp_path / "library" / "Test (2024)" / "Test (2024).mkv",
            media_item=movie,
            identified=identified,
            create_directories=[tmp_path / "library" / "Test (2024)"],
        )
        assert mapping.source.name == "movie.mkv"
        assert "Test (2024)" in str(mapping.destination)
        assert len(mapping.create_directories) == 1


class TestLinkOperation:
    """Tests for LinkOperation dataclass."""

    def test_create_link_operation(self, tmp_path):
        """Create a link operation record."""
        op = LinkOperation(
            source=tmp_path / "src.mkv",
            destination=tmp_path / "dst.mkv",
            action=ActionMode.SYMLINK,
            success=True,
        )
        assert op.success is True
        assert op.original_link is None
        assert op.error is None

    def test_link_operation_with_keeplink(self, tmp_path):
        """Track symlink for keeplink operation."""
        op = LinkOperation(
            source=tmp_path / "src.mkv",
            destination=tmp_path / "dst.mkv",
            action=ActionMode.KEEPLINK,
            success=True,
            original_link=tmp_path / "src.mkv",
        )
        assert op.original_link == tmp_path / "src.mkv"

    def test_link_operation_with_error(self, tmp_path):
        """Track error for failed operation."""
        op = LinkOperation(
            source=tmp_path / "src.mkv",
            destination=tmp_path / "dst.mkv",
            action=ActionMode.MOVE,
            success=False,
            error="Permission denied",
        )
        assert op.success is False
        assert op.error == "Permission denied"
