"""Tests for TV episode matcher."""

import pytest
from pathlib import Path

from jackmediaman.matchers.tv import TVMatcher
from jackmediaman.models.media import Episode, Movie
from jackmediaman.models.quality import Quality, Resolution


class TestTVMatcher:
    """Tests for TVMatcher class."""

    @pytest.fixture
    def matcher(self):
        """Create a TV matcher."""
        return TVMatcher()

    @pytest.fixture
    def sample_episodes(self, tmp_path):
        """Create sample episodes for matching."""
        quality_1080 = Quality(resolution=Resolution.FHD, resolution_raw="1080p")
        quality_720 = Quality(resolution=Resolution.HD, resolution_raw="720p")

        episodes = []

        # Breaking Bad S01E01 - two versions (duplicate)
        path1 = tmp_path / "bb_s01e01_1080p.mkv"
        path1.write_bytes(b"0" * 600)
        episodes.append(Episode(
            path=path1,
            filename=path1.name,
            size_bytes=600,
            quality=quality_1080,
            series_name="Breaking Bad",
            season_number=1,
            episode_numbers=[1],
        ))

        path2 = tmp_path / "bb_s01e01_720p.mkv"
        path2.write_bytes(b"0" * 400)
        episodes.append(Episode(
            path=path2,
            filename=path2.name,
            size_bytes=400,
            quality=quality_720,
            series_name="Breaking Bad",
            season_number=1,
            episode_numbers=[1],
        ))

        # Breaking Bad S01E02 - single version (no duplicate)
        path3 = tmp_path / "bb_s01e02_1080p.mkv"
        path3.write_bytes(b"0" * 550)
        episodes.append(Episode(
            path=path3,
            filename=path3.name,
            size_bytes=550,
            quality=quality_1080,
            series_name="Breaking Bad",
            season_number=1,
            episode_numbers=[2],
        ))

        return episodes

    def test_matches_duplicate_episodes(self, matcher, sample_episodes):
        """Matcher finds duplicate episodes."""
        groups = matcher.match(sample_episodes)
        assert len(groups) == 1  # Only S01E01 has duplicates
        assert groups[0].count == 2

    def test_groups_by_identity_key(self, matcher, sample_episodes):
        """Episodes are grouped by identity key."""
        groups = matcher.match(sample_episodes)
        group = groups[0]
        # All items should have the same identity key
        keys = set(ep.identity_key for ep in group.items)
        assert len(keys) == 1

    def test_sorts_by_quality(self, matcher, sample_episodes):
        """Groups are sorted by quality."""
        groups = matcher.match(sample_episodes)
        group = groups[0]
        # First item should be highest quality (1080p)
        assert group.items[0].quality.resolution == Resolution.FHD

    def test_filters_non_episodes(self, matcher, tmp_path):
        """Filters out non-Episode items."""
        quality = Quality(resolution=Resolution.FHD)

        movie = Movie(
            path=tmp_path / "movie.mkv",
            filename="movie.mkv",
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
        )

        episode = Episode(
            path=tmp_path / "ep.mkv",
            filename="ep.mkv",
            size_bytes=100,
            quality=quality,
            series_name="Test",
            season_number=1,
            episode_numbers=[1],
        )

        groups = matcher.match([movie, episode])
        # Should have no groups since only 1 episode
        assert len(groups) == 0

    def test_empty_list(self, matcher):
        """Empty list returns empty results."""
        assert matcher.match([]) == []

    def test_no_duplicates(self, matcher, tmp_path):
        """No groups when no duplicates exist."""
        quality = Quality(resolution=Resolution.FHD)

        episodes = []
        for i in range(3):
            path = tmp_path / f"ep_{i}.mkv"
            path.write_bytes(b"0" * 100)
            episodes.append(Episode(
                path=path,
                filename=path.name,
                size_bytes=100,
                quality=quality,
                series_name="Test",
                season_number=1,
                episode_numbers=[i + 1],  # Different episodes
            ))

        groups = matcher.match(episodes)
        assert len(groups) == 0

    def test_multiple_shows(self, matcher, tmp_path):
        """Correctly groups different shows separately."""
        quality = Quality(resolution=Resolution.FHD)

        episodes = []

        # Two shows, each with duplicate S01E01
        for show in ["Breaking Bad", "The Office"]:
            for version in ["v1", "v2"]:
                path = tmp_path / f"{show}_{version}.mkv"
                path.write_bytes(b"0" * 100)
                episodes.append(Episode(
                    path=path,
                    filename=path.name,
                    size_bytes=100,
                    quality=quality,
                    series_name=show,
                    season_number=1,
                    episode_numbers=[1],
                ))

        groups = matcher.match(episodes)
        assert len(groups) == 2  # One group per show

    def test_different_seasons_not_duplicates(self, matcher, tmp_path):
        """Same episode number in different seasons are not duplicates."""
        quality = Quality(resolution=Resolution.FHD)

        episodes = []
        for season in [1, 2]:
            path = tmp_path / f"ep_s{season}e01.mkv"
            path.write_bytes(b"0" * 100)
            episodes.append(Episode(
                path=path,
                filename=path.name,
                size_bytes=100,
                quality=quality,
                series_name="Test",
                season_number=season,
                episode_numbers=[1],
            ))

        groups = matcher.match(episodes)
        assert len(groups) == 0  # Different seasons = not duplicates

    def test_matcher_attributes(self, matcher):
        """Matcher has expected attributes."""
        assert matcher.name == "tv"
        assert "episode" in matcher.description.lower()
