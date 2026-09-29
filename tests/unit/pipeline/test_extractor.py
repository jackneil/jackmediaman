"""Tests for extractor stage."""

from pathlib import Path

import pytest

from jackmediaman.pipeline.stages.extractor import ExtractorStage
from jackmediaman.pipeline.context import ActionMode, ProcessContext
from jackmediaman.pipeline.base import StageResult


class TestExtractorStage:
    """Tests for ExtractorStage."""

    def test_init(self):
        """Can create extractor stage."""
        stage = ExtractorStage()
        assert stage.name == "extractor"

    def test_validate_with_archive(self, tmp_path):
        """Validate passes for path with archives."""
        source = tmp_path / "torrent"
        source.mkdir()
        # Create an archive file
        (source / "movie.rar").touch()
        ctx = ProcessContext(source_path=source, action=ActionMode.SYMLINK)

        stage = ExtractorStage()
        assert stage.validate(ctx) is True

    def test_validate_without_archives(self, tmp_path):
        """Validate fails when no archives present."""
        source = tmp_path / "torrent"
        source.mkdir()
        # Only video file, no archives
        (source / "movie.mkv").touch()
        ctx = ProcessContext(source_path=source, action=ActionMode.SYMLINK)

        stage = ExtractorStage()
        # Should return False since no archives to extract
        assert stage.validate(ctx) is False

    def test_validate_with_skip_flag(self, tmp_path):
        """Validate fails when skip_extraction is True."""
        source = tmp_path / "torrent"
        source.mkdir()
        ctx = ProcessContext(
            source_path=source,
            action=ActionMode.SYMLINK,
            skip_extraction=True,
        )

        stage = ExtractorStage()
        assert stage.validate(ctx) is False

    def test_is_sample_file(self, tmp_path):
        """Sample file detection (based on filename only)."""
        stage = ExtractorStage()

        # Sample files should be detected (checks filename, not path)
        assert stage._is_sample_file(Path("sample.mkv")) is True
        assert stage._is_sample_file(Path("SAMPLE.mkv")) is True
        assert stage._is_sample_file(Path("movie-sample.mkv")) is True
        assert stage._is_sample_file(Path("proof.mkv")) is True
        assert stage._is_sample_file(Path("video-proof.mkv")) is True

        # Regular files should not be detected as samples
        assert stage._is_sample_file(Path("movie.mkv")) is False
        assert stage._is_sample_file(Path("The.Matrix.1999.mkv")) is False

    def test_find_archives_rar(self, tmp_path):
        """Find RAR archives in directory."""
        # Create mock RAR file
        rar_file = tmp_path / "movie.rar"
        rar_file.touch()

        stage = ExtractorStage()
        archives = stage._find_archives(tmp_path)

        assert len(archives) == 1
        assert archives[0] == rar_file

    def test_find_archives_multipart_rar(self, tmp_path):
        """Only find main RAR when multipart exists."""
        # Create multipart RAR files
        (tmp_path / "movie.rar").touch()
        (tmp_path / "movie.r00").touch()
        (tmp_path / "movie.r01").touch()
        (tmp_path / "movie.r02").touch()

        stage = ExtractorStage()
        archives = stage._find_archives(tmp_path)

        # Should only return the main .rar file
        assert len(archives) == 1
        assert archives[0].suffix == ".rar"

    def test_find_archives_zip(self, tmp_path):
        """Find ZIP archives in directory."""
        zip_file = tmp_path / "movie.zip"
        zip_file.touch()

        stage = ExtractorStage()
        archives = stage._find_archives(tmp_path)

        assert len(archives) == 1
        assert archives[0] == zip_file

    def test_find_archives_7z(self, tmp_path):
        """Find 7z archives in directory."""
        archive = tmp_path / "movie.7z"
        archive.touch()

        stage = ExtractorStage()
        archives = stage._find_archives(tmp_path)

        assert len(archives) == 1
        assert archives[0] == archive

    def test_find_archives_nested(self, tmp_path):
        """Find archives in nested directories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        rar_file = subdir / "movie.rar"
        rar_file.touch()

        stage = ExtractorStage()
        archives = stage._find_archives(tmp_path)

        assert len(archives) == 1
        assert archives[0] == rar_file

    def test_execute_no_archives(self, tmp_path):
        """Execute with no archives returns video files."""
        # Create video file directly
        video = tmp_path / "Movie.2024.1080p.mkv"
        video.write_text("video content")

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        stage = ExtractorStage()

        output = stage.execute(ctx)

        # Should find the video file even without extraction
        assert output.result == StageResult.SUCCESS
        assert len(ctx.extracted_files) == 1
        assert ctx.extracted_files[0] == video

    def test_execute_single_file(self, tmp_path):
        """Execute with single video file."""
        video = tmp_path / "movie.mkv"
        video.write_text("video content")

        ctx = ProcessContext(source_path=video, action=ActionMode.SYMLINK)
        stage = ExtractorStage()

        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert len(ctx.extracted_files) == 1

    def test_find_video_files(self, tmp_path):
        """Find video files in directory."""
        stage = ExtractorStage()

        # Create various files
        (tmp_path / "movie.mkv").touch()
        (tmp_path / "movie.mp4").touch()
        (tmp_path / "movie.avi").touch()
        (tmp_path / "readme.txt").touch()
        (tmp_path / "poster.jpg").touch()

        videos = stage._find_video_files(tmp_path)

        assert len(videos) == 3
        extensions = {v.suffix for v in videos}
        assert extensions == {".mkv", ".mp4", ".avi"}

    def test_find_video_files_excludes_samples(self, tmp_path):
        """Sample videos are excluded from results."""
        stage = ExtractorStage()

        (tmp_path / "movie.mkv").touch()
        sample_dir = tmp_path / "Sample"
        sample_dir.mkdir()
        (sample_dir / "sample.mkv").touch()

        videos = stage._find_video_files(tmp_path)

        assert len(videos) == 1
        assert videos[0].name == "movie.mkv"

    def test_extract_zip(self, tmp_path):
        """Extract ZIP archive."""
        import zipfile

        # Create a ZIP file with a video
        zip_path = tmp_path / "archive.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("video.mkv", "video content")

        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        stage = ExtractorStage()
        files = stage._extract_zip(zip_path, extract_dir)

        assert len(files) == 1
        assert files[0].name == "video.mkv"
        assert (extract_dir / "video.mkv").exists()
