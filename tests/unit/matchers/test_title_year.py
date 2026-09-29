"""Tests for title/year matcher."""

import pytest
from pathlib import Path

from jackmediaman.matchers.title_year import TitleYearMatcher
from jackmediaman.models.media import Movie, Episode
from jackmediaman.models.quality import Quality, Resolution


class TestTitleYearMatcher:
    """Tests for TitleYearMatcher class."""

    @pytest.fixture
    def matcher(self):
        """Create a title/year matcher."""
        return TitleYearMatcher()

    @pytest.fixture
    def sample_movies(self, tmp_path):
        """Create sample movies for matching."""
        quality_1080 = Quality(resolution=Resolution.FHD, resolution_raw="1080p")
        quality_720 = Quality(resolution=Resolution.HD, resolution_raw="720p")

        movies = []

        # Inception 2010 - two versions (duplicate)
        path1 = tmp_path / "Inception.2010.1080p.mkv"
        path1.write_bytes(b"0" * 800)
        movies.append(Movie(
            path=path1,
            filename=path1.name,
            size_bytes=800,
            quality=quality_1080,
            title="Inception",
            year=2010,
        ))

        path2 = tmp_path / "Inception.2010.720p.mkv"
        path2.write_bytes(b"0" * 500)
        movies.append(Movie(
            path=path2,
            filename=path2.name,
            size_bytes=500,
            quality=quality_720,
            title="Inception",
            year=2010,
        ))

        # The Matrix 1999 - single version (no duplicate)
        path3 = tmp_path / "The.Matrix.1999.1080p.mkv"
        path3.write_bytes(b"0" * 700)
        movies.append(Movie(
            path=path3,
            filename=path3.name,
            size_bytes=700,
            quality=quality_1080,
            title="The Matrix",
            year=1999,
        ))

        return movies

    def test_matches_duplicate_movies(self, matcher, sample_movies):
        """Matcher finds duplicate movies."""
        groups = matcher.match(sample_movies)
        assert len(groups) == 1  # Only Inception has duplicates
        assert groups[0].count == 2

    def test_groups_by_title_and_year(self, matcher, sample_movies):
        """Movies are grouped by title and year."""
        groups = matcher.match(sample_movies)
        group = groups[0]
        # All items should have the same title and year
        titles = set(m.title for m in group.items)
        years = set(m.year for m in group.items)
        assert len(titles) == 1
        assert len(years) == 1

    def test_sorts_by_quality(self, matcher, sample_movies):
        """Groups are sorted by quality."""
        groups = matcher.match(sample_movies)
        group = groups[0]
        # First item should be highest quality (1080p)
        assert group.items[0].quality.resolution == Resolution.FHD

    def test_filters_non_movies(self, matcher, tmp_path):
        """Filters out non-Movie items."""
        quality = Quality(resolution=Resolution.FHD)

        episode = Episode(
            path=tmp_path / "ep.mkv",
            filename="ep.mkv",
            size_bytes=100,
            quality=quality,
            series_name="Test",
            season_number=1,
            episode_numbers=[1],
        )

        movie = Movie(
            path=tmp_path / "movie.mkv",
            filename="movie.mkv",
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
        )

        groups = matcher.match([episode, movie])
        # Should have no groups since only 1 movie
        assert len(groups) == 0

    def test_empty_list(self, matcher):
        """Empty list returns empty results."""
        assert matcher.match([]) == []

    def test_no_duplicates(self, matcher, tmp_path):
        """No groups when no duplicates exist."""
        quality = Quality(resolution=Resolution.FHD)

        movies = []
        for i in range(3):
            path = tmp_path / f"movie_{i}.mkv"
            path.write_bytes(b"0" * 100)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=100,
                quality=quality,
                title=f"Movie {i}",
                year=2020 + i,
            ))

        groups = matcher.match(movies)
        assert len(groups) == 0

    def test_same_title_different_year(self, matcher, tmp_path):
        """Same title but different year are not duplicates."""
        quality = Quality(resolution=Resolution.FHD)

        movies = []
        # Dune 1984 and Dune 2021
        for year in [1984, 2021]:
            path = tmp_path / f"Dune.{year}.mkv"
            path.write_bytes(b"0" * 100)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=100,
                quality=quality,
                title="Dune",
                year=year,
            ))

        groups = matcher.match(movies)
        assert len(groups) == 0


class TestTitleYearMatcherEditions:
    """Tests for edition handling."""

    def test_editions_as_duplicates_default(self, tmp_path):
        """By default, different editions are considered duplicates."""
        matcher = TitleYearMatcher(include_editions_as_dupes=True)
        quality = Quality(resolution=Resolution.FHD)

        movies = []
        for edition in [None, "directors_cut", "extended"]:
            path = tmp_path / f"Movie_{edition}.mkv"
            path.write_bytes(b"0" * 100)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=100,
                quality=quality,
                title="Test Movie",
                year=2020,
                edition=edition,
            ))

        groups = matcher.match(movies)
        assert len(groups) == 1
        assert groups[0].count == 3

    def test_editions_separate(self, tmp_path):
        """With include_editions_as_dupes=False, editions are separate."""
        matcher = TitleYearMatcher(include_editions_as_dupes=False)
        quality = Quality(resolution=Resolution.FHD)

        movies = []
        for edition in [None, "directors_cut"]:
            path = tmp_path / f"Movie_{edition}.mkv"
            path.write_bytes(b"0" * 100)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=100,
                quality=quality,
                title="Test Movie",
                year=2020,
                edition=edition,
            ))

        groups = matcher.match(movies)
        # No groups because each edition is unique
        assert len(groups) == 0

    def test_same_edition_with_separate_setting(self, tmp_path):
        """Same edition still groups when include_editions_as_dupes=False."""
        matcher = TitleYearMatcher(include_editions_as_dupes=False)
        quality_1080 = Quality(resolution=Resolution.FHD)
        quality_720 = Quality(resolution=Resolution.HD)

        movies = []
        for quality in [quality_1080, quality_720]:
            path = tmp_path / f"Movie_{quality.resolution.name}.mkv"
            path.write_bytes(b"0" * 100)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=100,
                quality=quality,
                title="Test Movie",
                year=2020,
                edition="directors_cut",  # Same edition
            ))

        groups = matcher.match(movies)
        assert len(groups) == 1
        assert groups[0].count == 2

    def test_matcher_attributes(self):
        """Matcher has expected attributes."""
        matcher = TitleYearMatcher()
        assert matcher.name == "title_year"
        assert "title" in matcher.description.lower()
        assert matcher.include_editions_as_dupes is True

        matcher2 = TitleYearMatcher(include_editions_as_dupes=False)
        assert matcher2.include_editions_as_dupes is False
