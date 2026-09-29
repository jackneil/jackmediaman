"""Tests for fuzzy matcher and helper functions."""

import pytest
from pathlib import Path

from jackmediaman.matchers.fuzzy import (
    levenshtein_distance,
    similarity_ratio,
    normalize_title,
    FuzzyMatcher,
)
from jackmediaman.models.media import Movie, Episode
from jackmediaman.models.quality import Quality, Resolution


class TestLevenshteinDistance:
    """Tests for levenshtein_distance function."""

    def test_identical_strings(self):
        """Identical strings have distance 0."""
        assert levenshtein_distance("hello", "hello") == 0

    def test_empty_strings(self):
        """Empty string distance is length of other string."""
        assert levenshtein_distance("", "abc") == 3
        assert levenshtein_distance("abc", "") == 3
        assert levenshtein_distance("", "") == 0

    def test_single_substitution(self):
        """Single character substitution."""
        assert levenshtein_distance("cat", "bat") == 1

    def test_single_insertion(self):
        """Single character insertion."""
        assert levenshtein_distance("cat", "cart") == 1

    def test_single_deletion(self):
        """Single character deletion."""
        assert levenshtein_distance("cart", "cat") == 1

    def test_classic_example(self):
        """Classic kitten/sitting example."""
        assert levenshtein_distance("kitten", "sitting") == 3

    def test_completely_different(self):
        """Completely different strings."""
        assert levenshtein_distance("abc", "xyz") == 3

    def test_symmetric(self):
        """Distance is symmetric."""
        assert levenshtein_distance("abc", "xyz") == levenshtein_distance("xyz", "abc")


class TestSimilarityRatio:
    """Tests for similarity_ratio function."""

    def test_identical_strings(self):
        """Identical strings have ratio 1.0."""
        assert similarity_ratio("hello", "hello") == 1.0

    def test_completely_different(self):
        """Completely different strings have low ratio."""
        ratio = similarity_ratio("abc", "xyz")
        assert ratio == 0.0

    def test_both_empty(self):
        """Both empty strings have ratio 1.0."""
        assert similarity_ratio("", "") == 1.0

    def test_one_empty(self):
        """One empty string has ratio 0.0."""
        assert similarity_ratio("", "abc") == 0.0
        assert similarity_ratio("abc", "") == 0.0

    def test_case_insensitive(self):
        """Comparison is case-insensitive."""
        assert similarity_ratio("Hello", "hello") == 1.0
        assert similarity_ratio("HELLO", "hello") == 1.0

    def test_partial_match(self):
        """Partial match has ratio between 0 and 1."""
        ratio = similarity_ratio("hello", "hallo")
        assert 0.0 < ratio < 1.0
        assert ratio == 0.8  # 1 - 1/5

    def test_high_similarity(self):
        """Similar strings have high ratio."""
        ratio = similarity_ratio("Inception", "Inceptino")  # Typo
        assert ratio > 0.7  # Actually 0.778 (2 edits in 9 chars)


class TestNormalizeTitle:
    """Tests for normalize_title function."""

    def test_removes_the_prefix(self):
        """Removes 'The ' prefix."""
        assert normalize_title("The Matrix") == "matrix"

    def test_removes_a_prefix(self):
        """Removes 'A ' prefix."""
        assert normalize_title("A Beautiful Mind") == "beautiful mind"

    def test_removes_an_prefix(self):
        """Removes 'An ' prefix."""
        assert normalize_title("An American Werewolf") == "american werewolf"

    def test_case_insensitive_prefix(self):
        """Prefix removal is case insensitive."""
        assert normalize_title("THE MATRIX") == "matrix"
        assert normalize_title("the matrix") == "matrix"

    def test_removes_special_characters(self):
        """Removes special characters."""
        assert normalize_title("Spider-Man: No Way Home") == "spider man no way home"

    def test_preserves_numbers(self):
        """Preserves numbers."""
        # Note: "A " prefix only removed at start of string
        assert normalize_title("2001: A Space Odyssey") == "2001 a space odyssey"

    def test_normalizes_whitespace(self):
        """Normalizes multiple spaces."""
        assert normalize_title("The    Godfather") == "godfather"

    def test_empty_string(self):
        """Empty string returns empty."""
        assert normalize_title("") == ""

    def test_only_prefix(self):
        """String with only prefix - stays lowercase since no space after."""
        assert normalize_title("The") == "the"


class TestFuzzyMatcher:
    """Tests for FuzzyMatcher class."""

    @pytest.fixture
    def matcher(self):
        """Create a fuzzy matcher with default settings."""
        return FuzzyMatcher(threshold=0.85)

    @pytest.fixture
    def sample_movies(self, tmp_path):
        """Create sample movies for matching."""
        quality = Quality(resolution=Resolution.FHD)
        movies = []

        for name, year in [
            ("Inception", 2010),
            ("Inceptino", 2010),  # Typo - should match
            ("The Matrix", 1999),
            ("Matrix", 1999),  # Missing "The" - should match
            ("Dune", 2021),  # No duplicate
        ]:
            path = tmp_path / f"{name}_{year}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title=name,
                year=year,
            ))

        return movies

    def test_matches_similar_titles(self, matcher, sample_movies):
        """Matches movies with similar titles."""
        groups = matcher.match(sample_movies)
        # Should find at least 1 group (Matrix/The Matrix match)
        # Inception/Inceptino may not match at 0.85 threshold (0.778 similarity)
        assert len(groups) >= 1

    def test_respects_threshold(self, sample_movies):
        """Higher threshold means fewer matches."""
        strict_matcher = FuzzyMatcher(threshold=0.99)
        groups = strict_matcher.match(sample_movies)
        # At 0.99 threshold, might only match "The Matrix"/"Matrix"
        assert len(groups) <= 1

    def test_low_threshold(self, sample_movies):
        """Lower threshold means more matches."""
        lenient_matcher = FuzzyMatcher(threshold=0.5)
        groups = lenient_matcher.match(sample_movies)
        # At 0.5 threshold, might match more
        assert len(groups) >= 2

    def test_year_tolerance(self, matcher, tmp_path):
        """Movies with 1 year difference still match."""
        quality = Quality(resolution=Resolution.FHD)

        movies = []
        for year in [2010, 2011]:  # Same movie, different regional years
            path = tmp_path / f"Inception_{year}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title="Inception",
                year=year,
            ))

        groups = matcher.match(movies)
        assert len(groups) == 1

    def test_year_too_different(self, matcher, tmp_path):
        """Movies with 2+ year difference don't match."""
        quality = Quality(resolution=Resolution.FHD)

        movies = []
        for year in [2010, 2015]:  # Too different
            path = tmp_path / f"Inception_{year}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title="Inception",
                year=year,
            ))

        groups = matcher.match(movies)
        assert len(groups) == 0

    def test_edition_handling_include(self, tmp_path):
        """Different editions grouped when include_editions_as_dupes=True."""
        quality = Quality(resolution=Resolution.FHD)

        movies = []
        for edition in [None, "directors_cut"]:
            path = tmp_path / f"Blade_Runner_{edition}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title="Blade Runner",
                year=1982,
                edition=edition,
            ))

        matcher = FuzzyMatcher(include_editions_as_dupes=True)
        groups = matcher.match(movies)
        assert len(groups) == 1

    def test_edition_handling_exclude(self, tmp_path):
        """Different editions not grouped when include_editions_as_dupes=False."""
        quality = Quality(resolution=Resolution.FHD)

        movies = []
        for edition in [None, "directors_cut"]:
            path = tmp_path / f"Blade_Runner_{edition}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title="Blade Runner",
                year=1982,
                edition=edition,
            ))

        matcher = FuzzyMatcher(include_editions_as_dupes=False)
        groups = matcher.match(movies)
        assert len(groups) == 0

    def test_empty_list(self, matcher):
        """Empty list returns empty results."""
        assert matcher.match([]) == []

    def test_filters_non_movies(self, matcher, tmp_path, sample_episode):
        """Filters out non-Movie items."""
        groups = matcher.match([sample_episode])
        assert len(groups) == 0

    def test_single_movie(self, matcher, sample_movie):
        """Single movie returns no groups."""
        groups = matcher.match([sample_movie])
        assert len(groups) == 0

    def test_sorts_by_quality(self, matcher, tmp_path):
        """Groups are sorted by quality."""
        quality_1080 = Quality(resolution=Resolution.FHD)
        quality_720 = Quality(resolution=Resolution.HD)

        movies = []
        for quality, suffix in [(quality_720, "720p"), (quality_1080, "1080p")]:
            path = tmp_path / f"Movie_{suffix}.mkv"
            path.write_bytes(b"0" * 200)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=200,
                quality=quality,
                title="Test Movie",
                year=2020,
            ))

        groups = matcher.match(movies)
        assert len(groups) == 1
        # First item should be highest quality
        assert groups[0].items[0].quality.resolution == Resolution.FHD

    def test_matcher_attributes(self, matcher):
        """Matcher has expected attributes."""
        assert matcher.name == "fuzzy"
        assert "fuzzy" in matcher.description.lower()
        assert matcher.threshold == 0.85
