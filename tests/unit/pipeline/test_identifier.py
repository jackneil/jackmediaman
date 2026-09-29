"""Tests for identifier stage."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jackmediaman.pipeline.stages.identifier import IdentifierStage
from jackmediaman.pipeline.context import ActionMode, ProcessContext
from jackmediaman.pipeline.base import StageResult
from jackmediaman.models.media import MediaType


class TestIdentifierStage:
    """Tests for IdentifierStage."""

    def test_init(self):
        """Can create identifier stage."""
        stage = IdentifierStage()
        assert stage.name == "identifier"
        assert stage.use_tmdb is True

    def test_init_without_tmdb(self):
        """Can disable TMDb lookup."""
        stage = IdentifierStage(use_tmdb=False)
        assert stage.use_tmdb is False

    def test_validate_with_files(self, tmp_path):
        """Validate passes when video files exist."""
        video = tmp_path / "movie.mkv"
        video.write_text("video")

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.extracted_files = [video]

        stage = IdentifierStage()
        assert stage.validate(ctx) is True

    def test_validate_no_files(self, tmp_path):
        """Validate fails when no video files."""
        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)

        stage = IdentifierStage()
        assert stage.validate(ctx) is False


class TestTVPatternDetection:
    """Tests for TV show pattern detection."""

    @pytest.fixture
    def stage(self):
        return IdentifierStage(use_tmdb=False)

    def test_detect_s01e01(self, stage):
        """Detect S01E01 pattern."""
        info = stage._extract_tv_info("Show.Name.S01E01.1080p.mkv")
        assert info is not None
        assert info["season"] == 1
        assert info["episodes"] == [1]

        info_lower = stage._extract_tv_info("Show.Name.s01e01.mkv")
        assert info_lower is not None

    def test_detect_multi_episode(self, stage):
        """Detect multi-episode S01E01E02."""
        info = stage._extract_tv_info("Show.Name.S01E01E02.mkv")
        assert info is not None
        assert info["season"] == 1
        assert info["episodes"] == [1, 2]

        info3 = stage._extract_tv_info("Show.S02E05E06E07.mkv")
        assert info3 is not None
        assert info3["season"] == 2
        assert info3["episodes"] == [5, 6, 7]

    def test_detect_1x01(self, stage):
        """Detect 1x01 pattern."""
        info = stage._extract_tv_info("Show.Name.1x01.mkv")
        assert info is not None
        assert info["season"] == 1
        assert info["episodes"] == [1]

        info2 = stage._extract_tv_info("Show.Name.10x12.mkv")
        assert info2 is not None
        assert info2["season"] == 10
        assert info2["episodes"] == [12]

    def test_no_tv_pattern_movie(self, stage):
        """Movies don't have TV patterns."""
        info = stage._extract_tv_info("The.Matrix.1999.1080p.mkv")
        assert info is None

        info2 = stage._extract_tv_info("Movie.2024.BluRay.mkv")
        assert info2 is None


class TestMovieParsing:
    """Tests for movie name parsing."""

    @pytest.fixture
    def stage(self):
        return IdentifierStage(use_tmdb=False)

    def test_parse_movie_with_year(self, stage, tmp_path):
        """Parse movie with year."""
        video = tmp_path / "The.Matrix.1999.1080p.BluRay.x264.mkv"
        video.write_text("video")

        info = stage._extract_movie_info(video.name, video)

        assert info["title"] == "The Matrix"
        assert info["year"] == 1999

    def test_parse_movie_no_year(self, stage, tmp_path):
        """Parse movie without year."""
        video = tmp_path / "Some.Movie.1080p.mkv"
        video.write_text("video")

        info = stage._extract_movie_info(video.name, video)

        assert info["title"] == "Some Movie"
        assert info["year"] is None

    def test_clean_title_quality_tags(self, stage):
        """Quality tags are removed from title."""
        cleaned = stage._clean_title("Movie.2160p.BluRay.x265.HEVC")
        assert "2160p" not in cleaned
        assert "BluRay" not in cleaned
        assert "x265" not in cleaned

    def test_clean_title_dots_to_spaces(self, stage):
        """Dots are converted to spaces."""
        cleaned = stage._clean_title("The.Matrix.Reloaded")
        assert "." not in cleaned


class TestIdentification:
    """Tests for media identification."""

    @pytest.fixture
    def stage(self):
        return IdentifierStage(use_tmdb=False)

    def test_identify_movie(self, stage, tmp_path):
        """Identify a movie file."""
        video = tmp_path / "The.Matrix.1999.1080p.BluRay.mkv"
        video.write_text("video")

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.extracted_files = [video]

        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert len(ctx.identified_media) == 1
        assert ctx.identified_media[0].media_type == MediaType.MOVIE

    def test_identify_tv_episode(self, stage, tmp_path):
        """Identify a TV episode."""
        video = tmp_path / "Breaking.Bad.S01E01.720p.mkv"
        video.write_text("video")

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.extracted_files = [video]

        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert len(ctx.identified_media) == 1
        assert ctx.identified_media[0].media_type == MediaType.EPISODE

    def test_identify_multiple_files(self, stage, tmp_path):
        """Identify multiple files."""
        video1 = tmp_path / "Movie.2020.mkv"
        video2 = tmp_path / "Show.S01E01.mkv"
        video1.write_text("video")
        video2.write_text("video")

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.extracted_files = [video1, video2]

        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert len(ctx.identified_media) == 2

    def test_execute_no_files(self, stage, tmp_path):
        """Execute with no files returns failed."""
        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.extracted_files = []

        output = stage.execute(ctx)

        assert output.result == StageResult.FAILED


class TestTMDbIntegration:
    """Tests for TMDb lookup integration."""

    def test_skip_tmdb_when_flag_set(self, tmp_path):
        """TMDb is not called when skip_tmdb is set."""
        stage = IdentifierStage(use_tmdb=True)

        video = tmp_path / "The.Matrix.1999.mkv"
        video.write_text("video")

        ctx = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
            skip_tmdb=True,
        )
        ctx.extracted_files = [video]

        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        # Media should still be identified, just without TMDb enrichment
        assert len(ctx.identified_media) == 1
        # Confidence should be lower without TMDb
        assert ctx.identified_media[0].confidence < 0.9

    def test_uses_video_files_property(self, tmp_path):
        """Identifier uses video_files property for validation."""
        stage = IdentifierStage(use_tmdb=False)

        # Create video in directory, don't set extracted_files
        video = tmp_path / "movie.mkv"
        video.write_text("video")

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        # Don't set extracted_files - should find from source_path

        # video_files property should find the video
        assert len(ctx.video_files) == 1

        output = stage.execute(ctx)
        assert output.result == StageResult.SUCCESS
