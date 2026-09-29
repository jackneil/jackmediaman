"""Tests for DuplicateGroup model."""

import pytest
from pathlib import Path

from jackmediaman.models.duplicates import DuplicateGroup
from jackmediaman.models.media import Movie
from jackmediaman.models.quality import Quality, Resolution


class TestDuplicateGroup:
    """Tests for DuplicateGroup class."""

    def test_has_duplicates_with_multiple_items(self, movie_duplicate_group):
        """Group with multiple items has duplicates."""
        assert movie_duplicate_group.has_duplicates is True

    def test_has_duplicates_single_item(self, sample_movie):
        """Group with single item has no duplicates."""
        group = DuplicateGroup(identity_key="test", items=[sample_movie])
        assert group.has_duplicates is False

    def test_has_duplicates_empty_group(self):
        """Empty group has no duplicates."""
        group = DuplicateGroup(identity_key="test", items=[])
        assert group.has_duplicates is False

    def test_count_returns_item_count(self, movie_duplicate_group):
        """count property returns number of items."""
        assert movie_duplicate_group.count == 3

    def test_count_empty_group(self):
        """count is 0 for empty group."""
        group = DuplicateGroup(identity_key="test")
        assert group.count == 0

    def test_best_quality_returns_highest_score(self, movie_duplicate_group):
        """best_quality returns item with highest quality score."""
        best = movie_duplicate_group.best_quality
        assert best is not None
        assert best.quality.resolution == Resolution.UHD

    def test_best_quality_empty_group(self):
        """best_quality returns None for empty group."""
        group = DuplicateGroup(identity_key="test")
        assert group.best_quality is None

    def test_protected_items_returns_protected(self, movie_duplicate_group):
        """protected_items returns only protected items."""
        # Mark one item as protected
        movie_duplicate_group.items[1].is_protected = True
        movie_duplicate_group.items[1].protection_reason = "Test"

        protected = movie_duplicate_group.protected_items
        assert len(protected) == 1
        assert protected[0] == movie_duplicate_group.items[1]

    def test_protected_items_empty_when_none_protected(self, movie_duplicate_group):
        """protected_items is empty when no items protected."""
        protected = movie_duplicate_group.protected_items
        assert len(protected) == 0

    def test_removable_items_excludes_best(self, movie_duplicate_group):
        """removable_items excludes the best quality item."""
        best = movie_duplicate_group.best_quality
        removable = movie_duplicate_group.removable_items
        assert best not in removable

    def test_removable_items_excludes_protected(self, movie_duplicate_group):
        """removable_items excludes protected items."""
        # Mark the lowest quality item as protected
        movie_duplicate_group.items[2].is_protected = True

        removable = movie_duplicate_group.removable_items
        assert movie_duplicate_group.items[2] not in removable
        # Should only have the middle quality item
        assert len(removable) == 1

    def test_removable_items_empty_group(self):
        """removable_items is empty for empty group."""
        group = DuplicateGroup(identity_key="test")
        assert len(group.removable_items) == 0

    def test_removable_size_bytes(self, movie_duplicate_group):
        """removable_size_bytes sums sizes correctly."""
        removable = movie_duplicate_group.removable_items
        expected_size = sum(item.size_bytes for item in removable)
        assert movie_duplicate_group.removable_size_bytes == expected_size

    def test_removable_size_bytes_empty_group(self):
        """removable_size_bytes is 0 for empty group."""
        group = DuplicateGroup(identity_key="test")
        assert group.removable_size_bytes == 0

    def test_display_name_from_first_item(self, movie_duplicate_group):
        """display_name returns first item's display name."""
        first_item_display = movie_duplicate_group.items[0].display_name
        assert movie_duplicate_group.display_name == first_item_display

    def test_display_name_empty_group(self):
        """display_name returns identity_key for empty group."""
        group = DuplicateGroup(identity_key="test:key")
        assert group.display_name == "test:key"

    def test_add_item(self, sample_movie):
        """add() adds items to group."""
        group = DuplicateGroup(identity_key="test")
        group.add(sample_movie)
        assert group.count == 1
        assert sample_movie in group.items

    def test_add_item_no_duplicates(self, sample_movie):
        """add() doesn't add duplicate items."""
        group = DuplicateGroup(identity_key="test")
        group.add(sample_movie)
        group.add(sample_movie)  # Add same item again
        assert group.count == 1

    def test_sort_by_quality(self, movie_duplicate_group):
        """sort_by_quality orders highest first."""
        # Shuffle the items first
        movie_duplicate_group.items.reverse()
        movie_duplicate_group.sort_by_quality()

        scores = [item.quality.score for item in movie_duplicate_group.items]
        assert scores == sorted(scores, reverse=True)

    def test_sort_by_quality_empty_group(self):
        """sort_by_quality doesn't fail on empty group."""
        group = DuplicateGroup(identity_key="test")
        group.sort_by_quality()  # Should not raise
        assert group.count == 0


class TestDuplicateGroupGetAction:
    """Tests for get_action method."""

    def test_get_action_keep(self, movie_duplicate_group):
        """get_action returns KEEP for best item."""
        best = movie_duplicate_group.best_quality
        assert movie_duplicate_group.get_action(best) == "KEEP"

    def test_get_action_remove(self, movie_duplicate_group):
        """get_action returns REMOVE for non-protected lower quality."""
        # Get the worst quality item
        worst = min(movie_duplicate_group.items, key=lambda x: x.quality.score)
        assert movie_duplicate_group.get_action(worst) == "REMOVE"

    def test_get_action_protected(self, movie_duplicate_group):
        """get_action returns PROTECTED for protected items."""
        # Mark a non-best item as protected
        item = movie_duplicate_group.items[2]
        item.is_protected = True
        assert movie_duplicate_group.get_action(item) == "PROTECTED"

    def test_get_action_protected_even_if_best(self, movie_duplicate_group):
        """Protected best item still returns KEEP (not PROTECTED)."""
        best = movie_duplicate_group.best_quality
        best.is_protected = True
        # Best quality item is KEEP regardless of protection
        assert movie_duplicate_group.get_action(best) == "KEEP"


class TestBestQualityProtectionPreference:
    """Tests for best_quality preferring protected files on ties."""

    def test_same_quality_protected_wins(self, tmp_path, quality_1080p_webdl):
        """When quality is equal, protected file is preferred."""
        movies_dir = tmp_path / "Movies" / "Inception (2010)"
        movies_dir.mkdir(parents=True, exist_ok=True)

        # Create two files with same quality
        path_a = movies_dir / "Inception.2010.1080p.WEB-DL.mkv"
        path_b = movies_dir / "Inception.2010.1080p.WEB-DL.copy.mkv"
        path_a.write_bytes(b"0" * 200)
        path_b.write_bytes(b"0" * 200)

        movie_a = Movie(
            path=path_a,
            filename=path_a.name,
            size_bytes=200,
            quality=quality_1080p_webdl,
            title="Inception",
            year=2010,
            is_protected=False,
        )
        movie_b = Movie(
            path=path_b,
            filename=path_b.name,
            size_bytes=200,
            quality=quality_1080p_webdl,
            title="Inception",
            year=2010,
            is_protected=True,
            protection_reason="Seeding",
        )

        group = DuplicateGroup(identity_key="movie:title:inception:2010")
        group.add(movie_a)  # Add unprotected first
        group.add(movie_b)  # Add protected second

        # Protected should win despite being added second
        assert group.best_quality == movie_b
        assert group.best_quality.is_protected is True

    def test_higher_quality_beats_protected(
        self, tmp_path, quality_1080p_webdl, quality_720p_hdtv
    ):
        """Higher quality unprotected beats lower quality protected."""
        movies_dir = tmp_path / "Movies" / "Inception (2010)"
        movies_dir.mkdir(parents=True, exist_ok=True)

        path_1080 = movies_dir / "Inception.2010.1080p.WEB-DL.mkv"
        path_720 = movies_dir / "Inception.2010.720p.HDTV.mkv"
        path_1080.write_bytes(b"0" * 200)
        path_720.write_bytes(b"0" * 100)

        movie_1080 = Movie(
            path=path_1080,
            filename=path_1080.name,
            size_bytes=200,
            quality=quality_1080p_webdl,
            title="Inception",
            year=2010,
            is_protected=False,
        )
        movie_720_protected = Movie(
            path=path_720,
            filename=path_720.name,
            size_bytes=100,
            quality=quality_720p_hdtv,
            title="Inception",
            year=2010,
            is_protected=True,
            protection_reason="Seeding",
        )

        group = DuplicateGroup(identity_key="movie:title:inception:2010")
        group.add(movie_720_protected)  # Add protected first
        group.add(movie_1080)  # Add higher quality second

        # Higher quality should win even though unprotected
        assert group.best_quality == movie_1080
        assert group.best_quality.quality.resolution == Resolution.FHD

    def test_no_protected_highest_quality_wins(self, movie_duplicate_group):
        """When no files are protected, highest quality wins."""
        # movie_duplicate_group has no protected items by default
        best = movie_duplicate_group.best_quality
        assert best is not None
        assert best.quality.resolution == Resolution.UHD
        assert best.is_protected is False

    def test_unprotected_becomes_remove_when_protected_same_quality(
        self, tmp_path, quality_1080p_webdl
    ):
        """Unprotected copy should be REMOVE when protected copy has same quality."""
        movies_dir = tmp_path / "Movies" / "Inception (2010)"
        movies_dir.mkdir(parents=True, exist_ok=True)

        path_unprotected = movies_dir / "Inception.2010.1080p.copy.mkv"
        path_protected = movies_dir / "Inception.2010.1080p.symlink.mkv"
        path_unprotected.write_bytes(b"0" * 200)
        path_protected.write_bytes(b"0" * 200)

        movie_unprotected = Movie(
            path=path_unprotected,
            filename=path_unprotected.name,
            size_bytes=200,
            quality=quality_1080p_webdl,
            title="Inception",
            year=2010,
            is_protected=False,
        )
        movie_protected = Movie(
            path=path_protected,
            filename=path_protected.name,
            size_bytes=200,
            quality=quality_1080p_webdl,
            title="Inception",
            year=2010,
            is_protected=True,
            protection_reason="Seeding",
        )

        group = DuplicateGroup(identity_key="movie:title:inception:2010")
        group.add(movie_unprotected)
        group.add(movie_protected)

        # Protected file should be KEEP, unprotected should be REMOVE
        assert group.get_action(movie_protected) == "KEEP"
        assert group.get_action(movie_unprotected) == "REMOVE"
