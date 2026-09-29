"""Tests for duplicate finder service."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock

from jackmediaman.services.finder import DuplicateFinder
from jackmediaman.models.media import Movie
from jackmediaman.models.duplicates import DuplicateGroup
from jackmediaman.models.quality import Quality, Resolution


class TestDuplicateFinder:
    """Tests for DuplicateFinder class."""

    @pytest.fixture
    def mock_scanner(self):
        """Create a mock scanner."""
        scanner = MagicMock()
        scanner.scan = MagicMock(return_value=[])
        return scanner

    @pytest.fixture
    def mock_matcher(self):
        """Create a mock matcher."""
        matcher = MagicMock()
        matcher.match = MagicMock(return_value=[])
        return matcher

    @pytest.fixture
    def mock_protector(self):
        """Create a mock protector."""
        protector = MagicMock()
        protector.name = "test_protector"
        protector.protect = MagicMock(return_value=0)
        return protector

    @pytest.fixture
    def finder(self, mock_scanner, mock_matcher):
        """Create a duplicate finder with mocks."""
        return DuplicateFinder(scanner=mock_scanner, matcher=mock_matcher)

    @pytest.fixture
    def finder_with_protector(self, mock_scanner, mock_matcher, mock_protector):
        """Create a duplicate finder with protector."""
        return DuplicateFinder(
            scanner=mock_scanner,
            matcher=mock_matcher,
            protectors=[mock_protector],
        )

    def test_find_calls_scanner(self, finder, mock_scanner, tmp_path):
        """Find method calls scanner with correct path."""
        finder.find(tmp_path)
        mock_scanner.scan.assert_called_once_with(tmp_path)

    def test_find_calls_matcher(self, finder, mock_scanner, mock_matcher, tmp_path):
        """Find method calls matcher with scanned items."""
        quality = Quality(resolution=Resolution.FHD)
        movie = Movie(
            path=tmp_path / "movie.mkv",
            filename="movie.mkv",
            size_bytes=100,
            quality=quality,
            title="Test",
            year=2020,
        )
        mock_scanner.scan.return_value = [movie]

        finder.find(tmp_path)

        mock_matcher.match.assert_called_once()
        call_args = mock_matcher.match.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0] == movie

    def test_find_returns_groups(self, finder, mock_scanner, mock_matcher, tmp_path, movie_duplicate_group):
        """Find method returns groups from matcher."""
        # Scanner must return items for matcher to be called
        mock_scanner.scan.return_value = movie_duplicate_group.items
        mock_matcher.match.return_value = [movie_duplicate_group]

        groups = finder.find(tmp_path)

        assert len(groups) == 1
        assert groups[0] == movie_duplicate_group

    def test_find_empty_scan(self, finder, mock_scanner, mock_matcher, tmp_path):
        """Find returns empty list when scan returns nothing."""
        mock_scanner.scan.return_value = []

        groups = finder.find(tmp_path)

        assert groups == []
        mock_matcher.match.assert_not_called()

    def test_find_calls_protectors(
        self, finder_with_protector, mock_scanner, mock_protector, tmp_path
    ):
        """Find method calls protectors on scanned items."""
        quality = Quality(resolution=Resolution.FHD)
        movie = Movie(
            path=tmp_path / "movie.mkv",
            filename="movie.mkv",
            size_bytes=100,
            quality=quality,
            title="Test",
            year=2020,
        )
        mock_scanner.scan.return_value = [movie]

        finder_with_protector.find(tmp_path)

        mock_protector.protect.assert_called_once()
        call_args = mock_protector.protect.call_args[0][0]
        assert movie in call_args

    def test_find_progress_callback(self, finder, mock_scanner, tmp_path):
        """Find method calls progress callback."""
        callback = MagicMock()
        mock_scanner.scan.return_value = []

        finder.find(tmp_path, progress_callback=callback)

        # Should be called for scan phase
        assert callback.call_count >= 1


class TestDuplicateFinderFindAll:
    """Tests for DuplicateFinder.find_all method."""

    @pytest.fixture
    def mock_scanner(self):
        scanner = MagicMock()
        scanner.scan = MagicMock(return_value=[])
        return scanner

    @pytest.fixture
    def mock_matcher(self):
        matcher = MagicMock()
        matcher.match = MagicMock(return_value=[])
        return matcher

    @pytest.fixture
    def finder(self, mock_scanner, mock_matcher):
        return DuplicateFinder(scanner=mock_scanner, matcher=mock_matcher)

    def test_find_all_scans_multiple_roots(self, finder, mock_scanner, tmp_path):
        """find_all scans all provided roots."""
        root1 = tmp_path / "movies1"
        root2 = tmp_path / "movies2"

        finder.find_all([root1, root2])

        assert mock_scanner.scan.call_count == 2
        mock_scanner.scan.assert_any_call(root1)
        mock_scanner.scan.assert_any_call(root2)

    def test_find_all_combines_items(self, finder, mock_scanner, mock_matcher, tmp_path):
        """find_all combines items from all roots."""
        quality = Quality(resolution=Resolution.FHD)

        movie1 = Movie(
            path=tmp_path / "movie1.mkv",
            filename="movie1.mkv",
            size_bytes=100,
            quality=quality,
            title="Test1",
            year=2020,
        )
        movie2 = Movie(
            path=tmp_path / "movie2.mkv",
            filename="movie2.mkv",
            size_bytes=100,
            quality=quality,
            title="Test2",
            year=2020,
        )

        # Return different movie from each root
        mock_scanner.scan.side_effect = [[movie1], [movie2]]

        finder.find_all([tmp_path / "root1", tmp_path / "root2"])

        # Matcher should receive both movies
        call_args = mock_matcher.match.call_args[0][0]
        assert len(call_args) == 2
        assert movie1 in call_args
        assert movie2 in call_args

    def test_find_all_empty_roots(self, finder, mock_scanner, mock_matcher):
        """find_all returns empty when all roots are empty."""
        mock_scanner.scan.return_value = []

        groups = finder.find_all([Path("/root1"), Path("/root2")])

        assert groups == []
        mock_matcher.match.assert_not_called()
