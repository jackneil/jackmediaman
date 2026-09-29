"""Tests for media models (Movie, Episode, MediaItem)."""

import pytest
from pathlib import Path
from datetime import datetime

from jackmediaman.models.media import Movie, Episode, MediaType
from jackmediaman.models.quality import Quality, Resolution


class TestMovie:
    """Tests for Movie class."""

    def test_movie_identity_key_with_tmdb_id(self, sample_movie):
        """TMDb ID takes precedence for identity key."""
        sample_movie.tmdb_id = 27205
        assert sample_movie.identity_key == "movie:tmdb:27205"

    def test_movie_identity_key_without_tmdb_id(self, sample_movie):
        """Without TMDb ID, use normalized title:year."""
        sample_movie.tmdb_id = None
        assert "movie:title:inception:2010" == sample_movie.identity_key

    def test_movie_identity_key_special_characters(self, tmp_path, quality_unknown):
        """Special characters are stripped from identity key."""
        movie = Movie(
            path=tmp_path / "movie.mkv",
            filename="movie.mkv",
            size_bytes=100,
            quality=quality_unknown,
            title="Spider-Man: No Way Home",
            year=2021,
        )
        # Should not contain special characters in title part
        key = movie.identity_key
        assert "movie:title:" in key
        assert ":" not in key.split("movie:title:")[1].split(":")[0]

    def test_movie_identity_key_without_year(self, tmp_path, quality_unknown):
        """Identity key works without year."""
        movie = Movie(
            path=tmp_path / "movie.mkv",
            filename="movie.mkv",
            size_bytes=100,
            quality=quality_unknown,
            title="Test Movie",
            year=None,
        )
        assert "unknown" in movie.identity_key

    def test_movie_display_name_with_year(self, sample_movie):
        """Display name includes year when available."""
        assert sample_movie.display_name == "Inception (2010)"

    def test_movie_display_name_without_year(self, sample_movie):
        """Display name omits year when not available."""
        sample_movie.year = None
        assert sample_movie.display_name == "Inception"

    def test_movie_media_type(self, sample_movie):
        """Movie returns correct media type."""
        assert sample_movie.media_type == MediaType.MOVIE

    def test_movie_size_mb(self, sample_movie):
        """Size MB conversion works correctly."""
        sample_movie.size_bytes = 1024 * 1024  # 1 MB
        assert sample_movie.size_mb == 1.0

    def test_movie_size_gb(self, sample_movie):
        """Size GB conversion works correctly."""
        sample_movie.size_bytes = 1024 * 1024 * 1024  # 1 GB
        assert sample_movie.size_gb == 1.0


class TestEpisode:
    """Tests for Episode class."""

    def test_episode_identity_key_single_episode(self, sample_episode):
        """Single episode identity key format."""
        assert sample_episode.identity_key == "tv:breaking_bad:s01e01"

    def test_episode_identity_key_multi_episode(self, sample_episode):
        """Multi-episode identity key format."""
        sample_episode.episode_numbers = [1, 2, 3]
        assert sample_episode.identity_key == "tv:breaking_bad:s01e01-02-03"

    def test_episode_identity_key_special_characters(self, tmp_path, quality_unknown):
        """Special characters are stripped from identity key."""
        episode = Episode(
            path=tmp_path / "ep.mkv",
            filename="ep.mkv",
            size_bytes=100,
            quality=quality_unknown,
            series_name="Marvel's Agents of S.H.I.E.L.D.",
            season_number=1,
            episode_numbers=[1],
        )
        key = episode.identity_key
        assert key.startswith("tv:")
        # Should be normalized
        assert "marvel" in key.lower()

    def test_episode_display_name_single(self, sample_episode):
        """Single episode display name."""
        assert sample_episode.display_name == "Breaking Bad S01E01"

    def test_episode_display_name_multi(self, sample_episode):
        """Multi-episode display name."""
        sample_episode.episode_numbers = [1, 2]
        display = sample_episode.display_name
        assert "Breaking Bad" in display
        assert "S01" in display

    def test_episode_media_type(self, sample_episode):
        """Episode returns correct media type."""
        assert sample_episode.media_type == MediaType.EPISODE

    def test_episode_number_property(self, sample_episode):
        """episode_number returns first episode."""
        sample_episode.episode_numbers = [5, 6, 7]
        assert sample_episode.episode_number == 5

    def test_episode_number_empty(self, sample_episode):
        """episode_number returns 0 for empty list."""
        sample_episode.episode_numbers = []
        assert sample_episode.episode_number == 0


class TestMediaItemEquality:
    """Tests for MediaItem equality and hashing."""

    def test_movies_equal_by_path(self, sample_movie, quality_720p_hdtv):
        """Two movies with same path are equal."""
        other = Movie(
            path=sample_movie.path,
            filename=sample_movie.filename,
            size_bytes=999,  # Different size
            quality=quality_720p_hdtv,  # Different quality
            title="Different Title",
        )
        assert sample_movie == other

    def test_movies_not_equal_different_path(self, tmp_path, quality_1080p_webdl):
        """Two movies with different paths are not equal."""
        movie1 = Movie(
            path=tmp_path / "movie1.mkv",
            filename="movie1.mkv",
            size_bytes=100,
            quality=quality_1080p_webdl,
            title="Movie",
        )
        movie2 = Movie(
            path=tmp_path / "movie2.mkv",
            filename="movie2.mkv",
            size_bytes=100,
            quality=quality_1080p_webdl,
            title="Movie",
        )
        assert movie1 != movie2

    def test_movies_hashable(self, sample_movie):
        """Movies can be used in sets/dicts."""
        movie_set = {sample_movie}
        assert sample_movie in movie_set
        assert len(movie_set) == 1

    def test_movie_hash_based_on_path(self, sample_movie, quality_720p_hdtv):
        """Hash is based on path."""
        other = Movie(
            path=sample_movie.path,
            filename=sample_movie.filename,
            size_bytes=999,
            quality=quality_720p_hdtv,
            title="Different",
        )
        assert hash(sample_movie) == hash(other)


class TestMediaItemProtection:
    """Tests for MediaItem protection attributes."""

    def test_default_not_protected(self, sample_movie):
        """Items are not protected by default."""
        assert sample_movie.is_protected is False
        assert sample_movie.protection_reason is None

    def test_mark_as_protected(self, sample_movie):
        """Can mark item as protected."""
        sample_movie.is_protected = True
        sample_movie.protection_reason = "Active torrent"
        assert sample_movie.is_protected is True
        assert sample_movie.protection_reason == "Active torrent"

    def test_symlink_tracking(self, sample_movie, tmp_path):
        """Can track symlink status."""
        sample_movie.is_symlink = True
        sample_movie.symlink_target = tmp_path / "torrents" / "file.mkv"
        assert sample_movie.is_symlink is True
        assert sample_movie.symlink_target == tmp_path / "torrents" / "file.mkv"
