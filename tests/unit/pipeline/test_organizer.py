"""Tests for organizer stage."""

from datetime import datetime
from pathlib import Path

import pytest

from jackmediaman.pipeline.stages.organizer import OrganizerStage
from jackmediaman.pipeline.context import (
    ActionMode,
    IdentifiedMedia,
    ProcessContext,
)
from jackmediaman.pipeline.base import StageResult
from jackmediaman.models.media import Episode, MediaType, Movie
from jackmediaman.models.quality import Quality, Resolution


def make_movie(
    tmp_path: Path,
    name: str = "movie.mkv",
    title: str = "Test",
    year: int = 2024,
    quality: Quality = None,
) -> Movie:
    """Create a Movie object with all required fields."""
    path = tmp_path / name
    path.write_text("video content")
    stat = path.stat()
    return Movie(
        path=path,
        filename=path.name,
        size_bytes=stat.st_size,
        quality=quality or Quality(resolution=Resolution.FHD),
        created_at=datetime.fromtimestamp(stat.st_ctime),
        is_symlink=False,
        symlink_target=None,
        title=title,
        year=year,
    )


def make_episode(
    tmp_path: Path,
    name: str = "episode.mkv",
    series_name: str = "Show",
    season: int = 1,
    episodes: list = None,
    quality: Quality = None,
) -> Episode:
    """Create an Episode object with all required fields."""
    path = tmp_path / name
    path.write_text("video content")
    stat = path.stat()
    return Episode(
        path=path,
        filename=path.name,
        size_bytes=stat.st_size,
        quality=quality or Quality(resolution=Resolution.FHD),
        created_at=datetime.fromtimestamp(stat.st_ctime),
        is_symlink=False,
        symlink_target=None,
        series_name=series_name,
        season_number=season,
        episode_numbers=episodes or [1],
    )


class TestOrganizerStage:
    """Tests for OrganizerStage."""

    def test_init(self, tmp_path):
        """Can create organizer with default paths."""
        stage = OrganizerStage()
        assert stage.name == "organizer"
        assert stage.movies_dir is not None
        assert stage.tv_dir is not None

    def test_init_custom_paths(self, tmp_path):
        """Can create organizer with custom paths."""
        movies = tmp_path / "Movies"
        tv = tmp_path / "TV"
        stage = OrganizerStage(movies_dir=movies, tv_dir=tv)
        assert stage.movies_dir == movies
        assert stage.tv_dir == tv

    def test_validate_with_media(self, tmp_path):
        """Validate passes with identified media."""
        movie = make_movie(tmp_path)
        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.identified_media = [
            IdentifiedMedia(
                source_path=movie.path,
                media_type=MediaType.MOVIE,
                media_item=movie,
            )
        ]

        stage = OrganizerStage()
        assert stage.validate(ctx) is True

    def test_validate_no_media(self, tmp_path):
        """Validate fails with no identified media."""
        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)

        stage = OrganizerStage()
        assert stage.validate(ctx) is False


class TestMovieOrganization:
    """Tests for movie destination path calculation."""

    @pytest.fixture
    def stage(self, tmp_path):
        return OrganizerStage(
            movies_dir=tmp_path / "Movies",
            tv_dir=tmp_path / "TV",
        )

    def test_organize_movie_basic(self, stage, tmp_path):
        """Calculate movie destination path."""
        movie = make_movie(tmp_path, title="The Matrix", year=1999)
        identified = IdentifiedMedia(
            source_path=movie.path,
            media_type=MediaType.MOVIE,
            media_item=movie,
            canonical_title="The Matrix",
            canonical_year=1999,
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.identified_media = [identified]

        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert len(ctx.file_mappings) == 1

        mapping = ctx.file_mappings[0]
        assert "The Matrix (1999)" in str(mapping.destination)
        assert mapping.destination.suffix == ".mkv"

    def test_organize_movie_with_resolution(self, stage, tmp_path):
        """Movie with resolution tag."""
        quality = Quality(resolution=Resolution.FHD, resolution_raw="1080p")
        movie = make_movie(tmp_path, title="The Matrix", year=1999, quality=quality)
        identified = IdentifiedMedia(
            source_path=movie.path,
            media_type=MediaType.MOVIE,
            media_item=movie,
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.identified_media = [identified]

        output = stage.execute(ctx)

        mapping = ctx.file_mappings[0]
        assert "[1080p]" in str(mapping.destination)

    def test_organize_movie_no_year(self, stage, tmp_path):
        """Movie without year in name."""
        movie = make_movie(tmp_path, title="Some Movie", year=None)
        identified = IdentifiedMedia(
            source_path=movie.path,
            media_type=MediaType.MOVIE,
            media_item=movie,
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.identified_media = [identified]

        output = stage.execute(ctx)

        mapping = ctx.file_mappings[0]
        # Should still work but without year
        assert "Some Movie" in str(mapping.destination)
        assert "()" not in str(mapping.destination)

    def test_organize_movie_special_chars(self, stage, tmp_path):
        """Movie title with special characters is sanitized."""
        movie = make_movie(tmp_path, title="Mission: Impossible", year=1996)
        identified = IdentifiedMedia(
            source_path=movie.path,
            media_type=MediaType.MOVIE,
            media_item=movie,
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.identified_media = [identified]

        stage.execute(ctx)

        mapping = ctx.file_mappings[0]
        # Colon should be replaced
        assert ":" not in str(mapping.destination)
        assert "Mission - Impossible" in str(mapping.destination)


class TestTVOrganization:
    """Tests for TV episode destination path calculation."""

    @pytest.fixture
    def stage(self, tmp_path):
        return OrganizerStage(
            movies_dir=tmp_path / "Movies",
            tv_dir=tmp_path / "TV",
        )

    def test_organize_episode_basic(self, stage, tmp_path):
        """Calculate TV episode destination path."""
        episode = make_episode(
            tmp_path,
            series_name="Breaking Bad",
            season=1,
            episodes=[1],
        )
        identified = IdentifiedMedia(
            source_path=episode.path,
            media_type=MediaType.EPISODE,
            media_item=episode,
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.identified_media = [identified]

        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        mapping = ctx.file_mappings[0]

        # Check path structure
        assert "Breaking Bad" in str(mapping.destination)
        assert "Season 01" in str(mapping.destination)
        assert "S01E01" in str(mapping.destination)

    def test_organize_multi_episode(self, stage, tmp_path):
        """Multi-episode file."""
        episode = make_episode(
            tmp_path,
            series_name="Show Name",
            season=2,
            episodes=[5, 6, 7],
        )
        identified = IdentifiedMedia(
            source_path=episode.path,
            media_type=MediaType.EPISODE,
            media_item=episode,
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.identified_media = [identified]

        stage.execute(ctx)

        mapping = ctx.file_mappings[0]
        assert "S02E05-E07" in str(mapping.destination)

    def test_organize_episode_with_resolution(self, stage, tmp_path):
        """Episode with resolution tag."""
        quality = Quality(resolution=Resolution.HD, resolution_raw="720p")
        episode = make_episode(
            tmp_path,
            series_name="The Office",
            season=4,
            episodes=[12],
            quality=quality,
        )
        identified = IdentifiedMedia(
            source_path=episode.path,
            media_type=MediaType.EPISODE,
            media_item=episode,
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.identified_media = [identified]

        stage.execute(ctx)

        mapping = ctx.file_mappings[0]
        assert "[720p]" in str(mapping.destination)

    def test_organize_directories_created(self, stage, tmp_path):
        """Verify directories to create are specified."""
        episode = make_episode(
            tmp_path,
            series_name="New Show",
            season=1,
            episodes=[1],
        )
        identified = IdentifiedMedia(
            source_path=episode.path,
            media_type=MediaType.EPISODE,
            media_item=episode,
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.identified_media = [identified]

        stage.execute(ctx)

        mapping = ctx.file_mappings[0]
        # Should have show folder and season folder
        assert len(mapping.create_directories) == 2


class TestMixedMedia:
    """Tests for processing mixed media types."""

    def test_organize_mixed_content(self, tmp_path):
        """Process both movies and TV shows."""
        stage = OrganizerStage(
            movies_dir=tmp_path / "Movies",
            tv_dir=tmp_path / "TV",
        )

        movie = make_movie(tmp_path, name="film.mkv", title="Film", year=2024)
        episode = make_episode(
            tmp_path,
            name="show.mkv",
            series_name="Show",
            season=1,
            episodes=[1],
        )

        ctx = ProcessContext(source_path=tmp_path, action=ActionMode.SYMLINK)
        ctx.identified_media = [
            IdentifiedMedia(
                source_path=movie.path,
                media_type=MediaType.MOVIE,
                media_item=movie,
            ),
            IdentifiedMedia(
                source_path=episode.path,
                media_type=MediaType.EPISODE,
                media_item=episode,
            ),
        ]

        output = stage.execute(ctx)

        assert output.result == StageResult.SUCCESS
        assert len(ctx.file_mappings) == 2

        # Verify destinations are in correct directories
        movie_mapping = next(m for m in ctx.file_mappings if "Film" in str(m.destination))
        tv_mapping = next(m for m in ctx.file_mappings if "Show" in str(m.destination))

        assert "Movies" in str(movie_mapping.destination)
        assert "TV" in str(tv_mapping.destination)
