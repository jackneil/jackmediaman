"""Tests for repair commands."""

import os
from pathlib import Path
from unittest.mock import Mock, MagicMock

import pytest

from jackmediaman.cli.commands.repair import (
    find_broken_symlinks,
    find_matching_file,
    fix_symlink,
    extract_resolution_from_filename,
    extract_episode_info,
    _resolution_matches,
    _show_names_match,
    RESOLUTION_TAG_PATTERN,
)


class TestResolutionTagPattern:
    """Tests for the resolution tag regex pattern."""

    def test_matches_1080p(self):
        """Matches [1080p] tag."""
        assert RESOLUTION_TAG_PATTERN.fullmatch(" [1080p]")

    def test_matches_720p(self):
        """Matches [720p] tag."""
        assert RESOLUTION_TAG_PATTERN.fullmatch(" [720p]")

    def test_matches_2160p(self):
        """Matches [2160p] tag."""
        assert RESOLUTION_TAG_PATTERN.fullmatch(" [2160p]")

    def test_matches_4k(self):
        """Matches [4K] tag."""
        assert RESOLUTION_TAG_PATTERN.fullmatch(" [4K]")

    def test_matches_case_insensitive(self):
        """Pattern is case insensitive."""
        assert RESOLUTION_TAG_PATTERN.fullmatch(" [1080P]")
        assert RESOLUTION_TAG_PATTERN.fullmatch(" [4k]")

    def test_matches_960p(self):
        """Matches [960p] tag."""
        assert RESOLUTION_TAG_PATTERN.fullmatch(" [960p]")

    def test_matches_640p(self):
        """Matches [640p] tag."""
        assert RESOLUTION_TAG_PATTERN.fullmatch(" [640p]")

    def test_matches_540p(self):
        """Matches [540p] tag."""
        assert RESOLUTION_TAG_PATTERN.fullmatch(" [540p]")

    def test_no_match_without_brackets(self):
        """Doesn't match without brackets."""
        assert not RESOLUTION_TAG_PATTERN.fullmatch(" 1080p")

    def test_no_match_random_text(self):
        """Doesn't match random text."""
        assert not RESOLUTION_TAG_PATTERN.fullmatch(" [REPACK]")


class TestFindBrokenSymlinks:
    """Tests for finding broken symlinks."""

    def test_no_symlinks(self, tmp_path):
        """Return empty list when no symlinks exist."""
        (tmp_path / "file.mkv").touch()
        broken = find_broken_symlinks(tmp_path)
        assert broken == []

    def test_valid_symlink_not_returned(self, tmp_path):
        """Valid symlinks are not returned."""
        target = tmp_path / "target.mkv"
        target.touch()
        link = tmp_path / "link.mkv"
        os.symlink(str(target), str(link))

        broken = find_broken_symlinks(tmp_path)
        assert broken == []

    def test_broken_symlink_returned(self, tmp_path):
        """Broken symlinks are returned."""
        target = tmp_path / "nonexistent.mkv"
        link = tmp_path / "link.mkv"
        os.symlink(str(target), str(link))

        broken = find_broken_symlinks(tmp_path)

        assert len(broken) == 1
        assert broken[0][0] == link

    def test_multiple_broken_symlinks(self, tmp_path):
        """Multiple broken symlinks are returned."""
        link1 = tmp_path / "link1.mkv"
        link2 = tmp_path / "link2.mkv"
        os.symlink("/nonexistent/path1.mkv", str(link1))
        os.symlink("/nonexistent/path2.mkv", str(link2))

        broken = find_broken_symlinks(tmp_path)

        assert len(broken) == 2

    def test_recursive_search(self, tmp_path):
        """Finds broken symlinks in subdirectories."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        link = subdir / "link.mkv"
        os.symlink("/nonexistent.mkv", str(link))

        broken = find_broken_symlinks(tmp_path, recursive=True)

        assert len(broken) == 1
        assert broken[0][0] == link

    def test_non_recursive_search(self, tmp_path):
        """Non-recursive search only checks top level."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        link = subdir / "link.mkv"
        os.symlink("/nonexistent.mkv", str(link))

        broken = find_broken_symlinks(tmp_path, recursive=False)

        assert broken == []


class TestFindMatchingFile:
    """Tests for finding matching files."""

    def test_exact_match_in_same_directory(self, tmp_path):
        """Find exact match in same directory."""
        target_dir = tmp_path / "media"
        target_dir.mkdir()

        # The actual file
        actual = target_dir / "Show - S01E01 - Title.mkv"
        actual.touch()

        # The broken target (same name)
        broken_target = target_dir / "Show - S01E01 - Title.mkv"

        match = find_matching_file(broken_target, [])

        assert match == actual

    def test_match_with_resolution_tag_added(self, tmp_path):
        """Find file where resolution tag was added."""
        target_dir = tmp_path / "media"
        target_dir.mkdir()

        # Actual file has resolution tag
        actual = target_dir / "Show - S01E01 - Title [1080p].mkv"
        actual.touch()

        # Broken target doesn't have resolution tag
        broken_target = target_dir / "Show - S01E01 - Title.mkv"

        match = find_matching_file(broken_target, [])

        assert match == actual

    def test_no_match_different_name(self, tmp_path):
        """Return None when no matching file exists."""
        target_dir = tmp_path / "media"
        target_dir.mkdir()

        # Different file
        (target_dir / "Other Show.mkv").touch()

        broken_target = target_dir / "Show - S01E01 - Title.mkv"

        match = find_matching_file(broken_target, [])

        assert match is None

    def test_search_in_provided_directories(self, tmp_path):
        """Search in provided directories."""
        # Target directory doesn't exist
        broken_target = tmp_path / "old" / "Show - S01E01.mkv"

        # But file exists in search dir
        search_dir = tmp_path / "media"
        search_dir.mkdir()
        actual = search_dir / "shows" / "Show - S01E01 [1080p].mkv"
        actual.parent.mkdir(parents=True)
        actual.touch()

        match = find_matching_file(broken_target, [search_dir])

        assert match == actual

    def test_strict_mode_same_directory_only(self, tmp_path):
        """Strict mode only matches in same directory."""
        # Target directory
        target_dir = tmp_path / "media" / "Show"
        target_dir.mkdir(parents=True)

        # File in different directory
        other_dir = tmp_path / "media" / "Other"
        other_dir.mkdir()
        (other_dir / "Show - S01E01 [1080p].mkv").touch()

        broken_target = target_dir / "Show - S01E01.mkv"

        match = find_matching_file(broken_target, [tmp_path / "media"], strict=True)

        assert match is None

    def test_ignores_symlinks(self, tmp_path):
        """Matching ignores symlinks."""
        target_dir = tmp_path / "media"
        target_dir.mkdir()

        # Create a symlink (not a real file)
        os.symlink("/nonexistent", str(target_dir / "Show - S01E01 [1080p].mkv"))

        broken_target = target_dir / "Show - S01E01.mkv"

        match = find_matching_file(broken_target, [])

        assert match is None


class TestFixSymlink:
    """Tests for fixing symlinks."""

    def test_fix_broken_symlink(self, tmp_path):
        """Fix a broken symlink."""
        target = tmp_path / "new_target.mkv"
        target.touch()
        link = tmp_path / "link.mkv"
        os.symlink("/nonexistent.mkv", str(link))

        result = fix_symlink(link, target)

        assert result is True
        assert link.is_symlink()
        assert link.exists()  # Now valid

    def test_dry_run_doesnt_modify(self, tmp_path):
        """Dry run doesn't modify symlink."""
        target = tmp_path / "new_target.mkv"
        target.touch()
        link = tmp_path / "link.mkv"
        original_target = "/nonexistent.mkv"
        os.symlink(original_target, str(link))

        result = fix_symlink(link, target, dry_run=True)

        assert result is True
        # Symlink should still point to original
        assert os.readlink(str(link)) == original_target

    def test_creates_relative_symlink(self, tmp_path):
        """Creates relative symlink when possible."""
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        target = subdir / "target.mkv"
        target.touch()
        link = subdir / "link.mkv"
        os.symlink("/nonexistent.mkv", str(link))

        fix_symlink(link, target)

        # Should be a relative symlink
        link_target = os.readlink(str(link))
        assert not link_target.startswith("/")

    def test_handles_missing_symlink(self, tmp_path):
        """Handle case where symlink doesn't exist."""
        link = tmp_path / "nonexistent_link.mkv"
        target = tmp_path / "target.mkv"
        target.touch()

        # This should fail gracefully
        result = fix_symlink(link, target)

        assert result is False


class TestIntegration:
    """Integration tests for repair functionality."""

    def test_find_and_fix_broken_symlink(self, tmp_path):
        """Full workflow: find broken symlink and fix it."""
        # Setup: media file with resolution tag
        media_dir = tmp_path / "media" / "TV" / "Show" / "Season 01"
        media_dir.mkdir(parents=True)
        actual_file = media_dir / "Show - S01E01 - Title [1080p].mkv"
        actual_file.write_bytes(b"video content")

        # Setup: broken symlink pointing to old name without tag
        torrent_dir = tmp_path / "torrents"
        torrent_dir.mkdir()
        broken_link = torrent_dir / "Show.S01E01.mkv"
        old_target = media_dir / "Show - S01E01 - Title.mkv"
        os.symlink(str(old_target), str(broken_link))

        # Step 1: Find broken symlinks
        broken = find_broken_symlinks(torrent_dir)
        assert len(broken) == 1
        assert broken[0][0] == broken_link

        # Step 2: Find matching file
        broken_target = broken[0][1]
        match = find_matching_file(broken_target, [media_dir.parent.parent])
        assert match == actual_file

        # Step 3: Fix the symlink
        result = fix_symlink(broken_link, match)
        assert result is True

        # Verify symlink is now valid
        assert broken_link.exists()
        assert broken_link.is_symlink()
        # And points to the actual file
        assert broken_link.resolve() == actual_file

    def test_multiple_resolutions_prefers_same_directory(self, tmp_path):
        """When multiple matches exist, prefer same directory."""
        target_dir = tmp_path / "media" / "Show"
        target_dir.mkdir(parents=True)

        # File in same directory
        same_dir_file = target_dir / "Show - S01E01 [1080p].mkv"
        same_dir_file.touch()

        # File in different directory
        other_dir = tmp_path / "media" / "Other"
        other_dir.mkdir()
        (other_dir / "Show - S01E01 [720p].mkv").touch()

        broken_target = target_dir / "Show - S01E01.mkv"

        match = find_matching_file(broken_target, [tmp_path / "media"])

        # Should match file in same directory
        assert match == same_dir_file


class TestExtractResolutionFromFilename:
    """Tests for extract_resolution_from_filename helper."""

    def test_extract_1080p(self):
        """Extract 1080p resolution."""
        assert extract_resolution_from_filename("Show - S01E01 [1080p]") == "1080p"

    def test_extract_2160p(self):
        """Extract 2160p resolution."""
        assert extract_resolution_from_filename("Movie (2024) [2160p]") == "2160p"

    def test_extract_720p(self):
        """Extract 720p resolution."""
        assert extract_resolution_from_filename("Title [720p]") == "720p"

    def test_extract_4k(self):
        """Extract 4K resolution."""
        assert extract_resolution_from_filename("Title [4K]") == "4k"

    def test_no_resolution(self):
        """Return None when no resolution tag."""
        assert extract_resolution_from_filename("Show - S01E01") is None

    def test_case_insensitive(self):
        """Resolution extraction is case insensitive."""
        assert extract_resolution_from_filename("Title [1080P]") == "1080p"


class TestResolutionMatches:
    """Tests for _resolution_matches helper."""

    def test_exact_match(self):
        """Exact match works."""
        assert _resolution_matches("1080p", "1080p") is True

    def test_case_insensitive(self):
        """Case insensitive matching."""
        assert _resolution_matches("1080P", "1080p") is True
        assert _resolution_matches("1080p", "1080P") is True

    def test_no_match(self):
        """Different resolutions don't match."""
        assert _resolution_matches("1080p", "720p") is False

    def test_none_resolution(self):
        """None resolution doesn't match."""
        assert _resolution_matches(None, "1080p") is False


class TestFindMatchingFileWithProber:
    """Tests for find_matching_file with prober (ffprobe verification)."""

    def test_single_candidate_no_prober_needed(self, tmp_path):
        """Single candidate doesn't need prober."""
        target_dir = tmp_path / "media"
        target_dir.mkdir()

        # Only one file
        file_1080p = target_dir / "Show - S01E01 [1080p].mkv"
        file_1080p.touch()

        broken_target = target_dir / "Show - S01E01.mkv"

        # Mock prober that would fail if called
        mock_prober = Mock()
        mock_prober.is_available = True

        match = find_matching_file(broken_target, [], prober=mock_prober)

        assert match == file_1080p
        # Prober shouldn't be called for single candidate
        mock_prober.probe_quality.assert_not_called()

    def test_multiple_candidates_uses_filename_resolution_first(self, tmp_path):
        """When broken target has resolution, match by filename first."""
        target_dir = tmp_path / "media"
        target_dir.mkdir()

        # Two files with different resolutions
        file_1080p = target_dir / "Show - S01E01 [1080p].mkv"
        file_1080p.touch()
        file_720p = target_dir / "Show - S01E01 [720p].mkv"
        file_720p.touch()

        # Broken target had 1080p resolution
        broken_target = target_dir / "Show - S01E01 [1080p].mkv"

        # Even without prober, should match by filename
        match = find_matching_file(broken_target, [], prober=None)

        assert match == file_1080p

    def test_multiple_candidates_with_prober_verification(self, tmp_path):
        """When multiple candidates, prober verifies resolution."""
        target_dir = tmp_path / "media"
        target_dir.mkdir()

        # Two files - names suggest different resolutions
        file_1080p = target_dir / "Show - S01E01 [1080p].mkv"
        file_1080p.touch()
        file_720p = target_dir / "Show - S01E01 [720p].mkv"
        file_720p.touch()

        # Broken target without resolution tag
        broken_target = target_dir / "Show - S01E01.mkv"

        # Mock prober that returns quality info
        mock_prober = Mock()
        mock_prober.is_available = True

        # Mock quality objects
        quality_1080p = Mock()
        quality_1080p.resolution_raw = "1080p"
        quality_720p = Mock()
        quality_720p.resolution_raw = "720p"

        # Return different quality for each file
        def probe_quality_side_effect(path):
            if "1080p" in str(path):
                return quality_1080p
            return quality_720p

        mock_prober.probe_quality.side_effect = probe_quality_side_effect

        match = find_matching_file(broken_target, [], prober=mock_prober)

        # Should pick the one where filename resolution matches probed resolution
        assert match == file_1080p

    def test_prober_not_available_falls_back(self, tmp_path):
        """When prober not available, falls back to filename matching."""
        target_dir = tmp_path / "media"
        target_dir.mkdir()

        file_1080p = target_dir / "Show - S01E01 [1080p].mkv"
        file_1080p.touch()
        file_720p = target_dir / "Show - S01E01 [720p].mkv"
        file_720p.touch()

        broken_target = target_dir / "Show - S01E01.mkv"

        # Prober that's not available
        mock_prober = Mock()
        mock_prober.is_available = False

        match = find_matching_file(broken_target, [], prober=mock_prober)

        # Should return first candidate (same directory preference)
        assert match is not None
        assert match in [file_1080p, file_720p]


class TestExtractEpisodeInfo:
    """Tests for extract_episode_info helper."""

    def test_standard_format(self):
        """Parse standard 'Show - S01E02 - Title' format."""
        result = extract_episode_info("Stranger Things - S03E02 - Chapter Two")
        assert result == ("Stranger Things", 3, 2)

    def test_with_parenthetical(self):
        """Parse show name with parenthetical info."""
        result = extract_episode_info("Euphoria (US) - S01E06 - The Next Episode")
        assert result == ("Euphoria (US)", 1, 6)

    def test_numeric_show_name(self):
        """Parse show with numeric name."""
        result = extract_episode_info("1883 - S01E05 - The Fangs of Freedom")
        assert result == ("1883", 1, 5)

    def test_lowercase_episode(self):
        """Parse lowercase s##e## format."""
        result = extract_episode_info("The Office - s02e05 - Halloween")
        assert result == ("The Office", 2, 5)

    def test_no_episode_pattern(self):
        """Return None when no episode pattern found."""
        result = extract_episode_info("Some Random Movie (2024)")
        assert result is None

    def test_resolution_tag_ignored(self):
        """Resolution tag doesn't affect parsing."""
        result = extract_episode_info("Show - S01E01 - Title [1080p]")
        assert result == ("Show", 1, 1)

    def test_double_digit_season_episode(self):
        """Parse double-digit season and episode numbers."""
        result = extract_episode_info("Show - S12E25 - Finale")
        assert result == ("Show", 12, 25)


class TestShowNamesMatch:
    """Tests for _show_names_match helper."""

    def test_exact_match(self):
        """Exact names match."""
        assert _show_names_match("Stranger Things", "Stranger Things") is True

    def test_case_insensitive(self):
        """Case insensitive matching."""
        assert _show_names_match("stranger things", "Stranger Things") is True
        assert _show_names_match("THE OFFICE", "the office") is True

    def test_parenthetical_ignored(self):
        """Parenthetical info is ignored for matching."""
        assert _show_names_match("Euphoria (US)", "Euphoria") is True
        assert _show_names_match("Euphoria", "Euphoria (UK)") is True

    def test_partial_match(self):
        """Partial name match works."""
        assert _show_names_match("The Office", "The Office US") is True
        assert _show_names_match("House", "House MD") is True

    def test_different_shows(self):
        """Different show names don't match."""
        assert _show_names_match("Breaking Bad", "Better Call Saul") is False
        assert _show_names_match("Friends", "Seinfeld") is False

    def test_whitespace_handling(self):
        """Handles extra whitespace."""
        assert _show_names_match("  Stranger Things  ", "Stranger Things") is True


class TestFlexibleMatching:
    """Tests for flexible matching by show name + S##E##."""

    def test_different_episode_title(self, tmp_path):
        """Match files with different episode titles."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Actual file has different episode title
        actual = media_dir / "Stranger Things - S03E02 - The Mall Rats [1080p].mkv"
        actual.touch()

        # Broken target has full episode title
        broken_target = tmp_path / "old" / "Stranger Things - S03E02 - Chapter Two - The Mall Rats.mkv"

        match = find_matching_file(broken_target, [media_dir])

        assert match == actual

    def test_parenthetical_show_name(self, tmp_path):
        """Match show with parenthetical info."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Actual file
        actual = media_dir / "Euphoria (US) - S01E06 - The Next Episode [1080p].mkv"
        actual.touch()

        # Broken target (same show)
        broken_target = tmp_path / "old" / "Euphoria (US) - S01E06 - Episode Six.mkv"

        match = find_matching_file(broken_target, [media_dir])

        assert match == actual

    def test_no_match_different_episode(self, tmp_path):
        """Don't match different episodes."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # File for episode 3
        (media_dir / "Show - S01E03 - Title [1080p].mkv").touch()

        # Looking for episode 2
        broken_target = tmp_path / "old" / "Show - S01E02 - Title.mkv"

        match = find_matching_file(broken_target, [media_dir])

        assert match is None

    def test_no_match_different_show(self, tmp_path):
        """Don't match different shows."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Different show, same episode
        (media_dir / "Other Show - S01E02 - Title [1080p].mkv").touch()

        broken_target = tmp_path / "old" / "My Show - S01E02 - Title.mkv"

        match = find_matching_file(broken_target, [media_dir])

        assert match is None

    def test_flexible_match_in_nested_directory(self, tmp_path):
        """Find match in nested subdirectory."""
        media_dir = tmp_path / "media"
        nested = media_dir / "TV" / "Stranger Things" / "Season 03"
        nested.mkdir(parents=True)

        actual = nested / "Stranger Things - S03E02 - The Mall Rats [1080p].mkv"
        actual.touch()

        broken_target = tmp_path / "old" / "Stranger Things - S03E02 - Different Title.mkv"

        match = find_matching_file(broken_target, [media_dir])

        assert match == actual

    def test_prefers_exact_match_over_flexible(self, tmp_path):
        """Prefer exact prefix match over flexible match."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Exact prefix match (would be found by Strategy 2)
        exact = media_dir / "Show - S01E02 - Title [1080p].mkv"
        exact.touch()

        # Flexible match candidate
        flexible = media_dir / "Show - S01E02 - Different Title [720p].mkv"
        flexible.touch()

        # Broken target matches exact by prefix
        broken_target = media_dir / "Show - S01E02 - Title.mkv"

        match = find_matching_file(broken_target, [media_dir])

        # Should prefer the exact prefix match
        assert match == exact

    def test_match_file_without_episode_title(self, tmp_path):
        """Match when actual file has no episode title but broken target does."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Actual file has NO episode title
        actual = media_dir / "Euphoria (US) - S01E08 [1080p].mkv"
        actual.touch()

        # Broken target HAS episode title
        broken_target = tmp_path / "old" / "Euphoria (US) - S01E08 - And Salt the Earth Behind You.mkv"

        match = find_matching_file(broken_target, [media_dir])

        assert match == actual

    def test_match_960p_resolution(self, tmp_path):
        """Match files with 960p resolution tag."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # File with 960p resolution
        actual = media_dir / "Show - S01E01 - Title [960p].mkv"
        actual.touch()

        # Broken target without resolution
        broken_target = media_dir / "Show - S01E01 - Title.mkv"

        match = find_matching_file(broken_target, [media_dir])

        assert match == actual

    def test_match_640p_resolution(self, tmp_path):
        """Match files with 640p resolution tag."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # File with 640p resolution
        actual = media_dir / "Show - S01E01 - Title [640p].mkv"
        actual.touch()

        # Broken target without resolution
        broken_target = media_dir / "Show - S01E01 - Title.mkv"

        match = find_matching_file(broken_target, [media_dir])

        assert match == actual


class TestSizeVerification:
    """Tests for file size verification in matching."""

    def test_single_candidate_with_matching_size(self, tmp_path):
        """Single candidate with matching size returns that candidate."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Create file with specific size
        actual = media_dir / "Show - S01E01 [1080p].mkv"
        actual.write_bytes(b"x" * 1000)  # 1000 bytes

        broken_target = media_dir / "Show - S01E01.mkv"

        match = find_matching_file(broken_target, [], expected_size=1000)

        assert match == actual

    def test_single_candidate_with_wrong_size_still_matches(self, tmp_path):
        """Single candidate with wrong size still matches (size is filter, not rejection)."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Create file with different size
        actual = media_dir / "Show - S01E01 [1080p].mkv"
        actual.write_bytes(b"x" * 500)  # Different from expected

        broken_target = media_dir / "Show - S01E01.mkv"

        # Even with wrong size, should match if only candidate
        match = find_matching_file(broken_target, [], expected_size=1000)

        assert match == actual

    def test_multiple_candidates_size_filters_to_correct_one(self, tmp_path):
        """When multiple candidates exist, size filters to the correct one."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Create two files with different sizes
        file_1080p = media_dir / "Show - S01E01 [1080p].mkv"
        file_1080p.write_bytes(b"x" * 2000)  # 2000 bytes

        file_720p = media_dir / "Show - S01E01 [720p].mkv"
        file_720p.write_bytes(b"x" * 1000)  # 1000 bytes

        broken_target = media_dir / "Show - S01E01.mkv"

        # Should match the 720p file based on size
        match = find_matching_file(broken_target, [], expected_size=1000)

        assert match == file_720p

    def test_multiple_candidates_size_filters_to_1080p(self, tmp_path):
        """Size verification selects 1080p when size matches."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Create two files with different sizes
        file_1080p = media_dir / "Show - S01E01 [1080p].mkv"
        file_1080p.write_bytes(b"x" * 2000)  # 2000 bytes

        file_720p = media_dir / "Show - S01E01 [720p].mkv"
        file_720p.write_bytes(b"x" * 1000)  # 1000 bytes

        broken_target = media_dir / "Show - S01E01.mkv"

        # Should match the 1080p file based on size
        match = find_matching_file(broken_target, [], expected_size=2000)

        assert match == file_1080p

    def test_no_size_provided_uses_other_methods(self, tmp_path):
        """Without expected_size, falls back to filename/resolution matching."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        file_1080p = media_dir / "Show - S01E01 [1080p].mkv"
        file_1080p.write_bytes(b"x" * 2000)

        file_720p = media_dir / "Show - S01E01 [720p].mkv"
        file_720p.write_bytes(b"x" * 1000)

        # Broken target has 1080p in name
        broken_target = media_dir / "Show - S01E01 [1080p].mkv"

        # Without size, should match by filename resolution
        match = find_matching_file(broken_target, [], expected_size=None)

        assert match == file_1080p

    def test_multiple_size_matches_uses_other_criteria(self, tmp_path):
        """When multiple files match size, use other criteria to decide."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Two files with same size
        file_1080p = media_dir / "Show - S01E01 [1080p].mkv"
        file_1080p.write_bytes(b"x" * 1000)

        file_720p = media_dir / "Show - S01E01 [720p].mkv"
        file_720p.write_bytes(b"x" * 1000)  # Same size!

        # Broken target with resolution tag
        broken_target = media_dir / "Show - S01E01 [1080p].mkv"

        # With matching size but multiple candidates, use filename resolution
        match = find_matching_file(broken_target, [], expected_size=1000)

        assert match == file_1080p

    def test_size_verification_in_search_directories(self, tmp_path):
        """Size verification works when searching in provided directories."""
        target_dir = tmp_path / "torrents"
        target_dir.mkdir()

        media_dir = tmp_path / "media" / "TV" / "Show"
        media_dir.mkdir(parents=True)

        # Files in search directory with different sizes
        correct_file = media_dir / "Show - S01E01 [1080p].mkv"
        correct_file.write_bytes(b"x" * 5000)

        wrong_file = media_dir / "Show - S01E01 [720p].mkv"
        wrong_file.write_bytes(b"x" * 2000)

        # Broken target in different location
        broken_target = target_dir / "Show - S01E01.mkv"

        match = find_matching_file(broken_target, [tmp_path / "media"], expected_size=5000)

        assert match == correct_file

    def test_size_verification_with_flexible_matching(self, tmp_path):
        """Size verification works with flexible episode matching."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        # Files with different episode titles and sizes
        file_a = media_dir / "Show - S01E01 - Episode One [1080p].mkv"
        file_a.write_bytes(b"x" * 3000)

        file_b = media_dir / "Show - S01E01 - Different Title [720p].mkv"
        file_b.write_bytes(b"x" * 1500)

        # Broken target with yet another title
        broken_target = tmp_path / "old" / "Show - S01E01 - Third Title.mkv"

        # Should match based on S01E01 + size
        match = find_matching_file(broken_target, [media_dir], expected_size=3000)

        assert match == file_a


class TestGetFileSizeFromDeluge:
    """Tests for get_file_size_from_deluge helper."""

    @pytest.fixture(autouse=True)
    def reset_deluge_cache(self):
        """Reset Deluge cache before each test."""
        from jackmediaman.cli.commands import repair
        repair._deluge_cache = None
        repair._deluge_connection_failed = False
        yield
        # Clean up after test
        repair._deluge_cache = None
        repair._deluge_connection_failed = False

    def test_returns_none_when_deluge_unavailable(self, monkeypatch):
        """Returns None when Deluge connection fails."""
        from jackmediaman.cli.commands import repair

        # Mock the import to raise - patch at the source module
        def mock_create_client(*args, **kwargs):
            raise ConnectionError("Cannot connect")

        monkeypatch.setattr(
            "jackmediaman.services.deluge_client.create_deluge_client",
            mock_create_client,
        )

        result = repair.get_file_size_from_deluge(Path("/some/path.mkv"))
        assert result is None

    def test_returns_none_when_file_not_in_torrents(self, monkeypatch):
        """Returns None when file path doesn't match any torrent."""
        from jackmediaman.cli.commands import repair

        # Mock client that returns no matching torrents
        mock_client = MagicMock()
        mock_client.call.return_value = {
            b"torrent1": {
                b"save_path": b"/different/path",
                b"files": [
                    {b"path": b"other_file.mkv", b"size": 1000}
                ]
            }
        }

        def mock_create_client(*args, **kwargs):
            return mock_client

        monkeypatch.setattr(
            "jackmediaman.services.deluge_client.create_deluge_client",
            mock_create_client,
        )

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.deluge_host = "localhost"
        mock_settings.deluge_port = 58846
        mock_settings.deluge_username = "user"
        mock_settings.deluge_password = "pass"
        monkeypatch.setattr(repair, "get_settings", lambda: mock_settings)

        result = repair.get_file_size_from_deluge(Path("/torrents/completed/file.mkv"))
        assert result is None

    def test_returns_size_when_file_found(self, monkeypatch):
        """Returns file size when matching torrent file is found."""
        from jackmediaman.cli.commands import repair

        # Mock client that returns matching torrent
        mock_client = MagicMock()
        mock_client.call.return_value = {
            b"torrent1": {
                b"save_path": b"/torrents/completed",
                b"files": [
                    {b"path": b"Show.S01E01.mkv", b"size": 1234567890}
                ]
            }
        }

        def mock_create_client(*args, **kwargs):
            return mock_client

        monkeypatch.setattr(
            "jackmediaman.services.deluge_client.create_deluge_client",
            mock_create_client,
        )

        mock_settings = MagicMock()
        mock_settings.deluge_host = "localhost"
        mock_settings.deluge_port = 58846
        mock_settings.deluge_username = "user"
        mock_settings.deluge_password = "pass"
        monkeypatch.setattr(repair, "get_settings", lambda: mock_settings)

        result = repair.get_file_size_from_deluge(Path("/torrents/completed/Show.S01E01.mkv"))
        assert result == 1234567890

    def test_handles_string_keys_in_response(self, monkeypatch):
        """Handles both bytes and string keys in Deluge response."""
        from jackmediaman.cli.commands import repair

        # Mock client with string keys (some Deluge versions)
        mock_client = MagicMock()
        mock_client.call.return_value = {
            "torrent1": {
                "save_path": "/torrents/completed",
                "files": [
                    {"path": "Show.S01E01.mkv", "size": 9876543210}
                ]
            }
        }

        def mock_create_client(*args, **kwargs):
            return mock_client

        monkeypatch.setattr(
            "jackmediaman.services.deluge_client.create_deluge_client",
            mock_create_client,
        )

        mock_settings = MagicMock()
        mock_settings.deluge_host = "localhost"
        mock_settings.deluge_port = 58846
        mock_settings.deluge_username = "user"
        mock_settings.deluge_password = "pass"
        monkeypatch.setattr(repair, "get_settings", lambda: mock_settings)

        result = repair.get_file_size_from_deluge(Path("/torrents/completed/Show.S01E01.mkv"))
        assert result == 9876543210

    def test_matches_nested_file_in_torrent(self, monkeypatch):
        """Matches files in subdirectories within torrent."""
        from jackmediaman.cli.commands import repair

        mock_client = MagicMock()
        mock_client.call.return_value = {
            b"torrent1": {
                b"save_path": b"/torrents/completed",
                b"files": [
                    {b"path": b"Show.S01/Show.S01E01.mkv", b"size": 5555555555}
                ]
            }
        }

        def mock_create_client(*args, **kwargs):
            return mock_client

        monkeypatch.setattr(
            "jackmediaman.services.deluge_client.create_deluge_client",
            mock_create_client,
        )

        mock_settings = MagicMock()
        mock_settings.deluge_host = "localhost"
        mock_settings.deluge_port = 58846
        mock_settings.deluge_username = "user"
        mock_settings.deluge_password = "pass"
        monkeypatch.setattr(repair, "get_settings", lambda: mock_settings)

        result = repair.get_file_size_from_deluge(
            Path("/torrents/completed/Show.S01/Show.S01E01.mkv")
        )
        assert result == 5555555555


class TestFolderConsolidation:
    """Tests for season folder consolidation helpers."""

    def test_find_season_folder_variants_single(self, tmp_path):
        """Find single variant for each season."""
        from jackmediaman.services.folder_consolidator import FolderConsolidator

        show_dir = tmp_path / "Show"
        show_dir.mkdir()
        (show_dir / "Season 01").mkdir()
        (show_dir / "Season 02").mkdir()

        consolidator = FolderConsolidator(tv_dir=tmp_path)
        variants = consolidator._find_season_variants_for_show(show_dir)

        assert len(variants) == 2
        assert len(variants[1]) == 1
        assert len(variants[2]) == 1

    def test_find_season_folder_variants_multiple(self, tmp_path):
        """Find multiple variants for same season."""
        from jackmediaman.services.folder_consolidator import FolderConsolidator

        show_dir = tmp_path / "Show"
        show_dir.mkdir()
        (show_dir / "Season 01").mkdir()
        (show_dir / "Season.01").mkdir()
        (show_dir / "Season 1").mkdir()

        consolidator = FolderConsolidator(tv_dir=tmp_path)
        variants = consolidator._find_season_variants_for_show(show_dir)

        assert len(variants) == 1  # All map to season 1
        assert len(variants[1]) == 3  # Three variants

    def test_find_season_folder_variants_mixed(self, tmp_path):
        """Find mixed variants across seasons."""
        from jackmediaman.services.folder_consolidator import FolderConsolidator

        show_dir = tmp_path / "Show"
        show_dir.mkdir()
        (show_dir / "Season 01").mkdir()
        (show_dir / "Season.01").mkdir()
        (show_dir / "Season 02").mkdir()
        (show_dir / "Season.02").mkdir()
        (show_dir / "Season 2").mkdir()

        consolidator = FolderConsolidator(tv_dir=tmp_path)
        variants = consolidator._find_season_variants_for_show(show_dir)

        assert len(variants) == 2
        assert len(variants[1]) == 2
        assert len(variants[2]) == 3

    def test_find_season_folder_variants_ignores_non_season(self, tmp_path):
        """Ignores non-season folders."""
        from jackmediaman.services.folder_consolidator import FolderConsolidator

        show_dir = tmp_path / "Show"
        show_dir.mkdir()
        (show_dir / "Season 01").mkdir()
        (show_dir / "Specials").mkdir()
        (show_dir / "Extras").mkdir()

        consolidator = FolderConsolidator(tv_dir=tmp_path)
        variants = consolidator._find_season_variants_for_show(show_dir)

        assert len(variants) == 1
        assert 1 in variants

    def test_get_canonical_season_folder(self, tmp_path):
        """Get canonical season folder name."""
        from jackmediaman.services.folder_consolidator import FolderConsolidator

        show_dir = tmp_path / "Show"
        consolidator = FolderConsolidator(tv_dir=tmp_path)

        assert consolidator._get_canonical_season_folder(show_dir, 1) == show_dir / "Season 01"
        assert consolidator._get_canonical_season_folder(show_dir, 5) == show_dir / "Season 05"
        assert consolidator._get_canonical_season_folder(show_dir, 12) == show_dir / "Season 12"

    def test_season_folder_pattern_variants(self):
        """Test the season folder pattern matches all variants."""
        from jackmediaman.services.folder_consolidator import SEASON_FOLDER_PATTERN

        test_cases = [
            ("Season 01", 1),
            ("Season.01", 1),
            ("Season01", 1),
            ("Season 5", 5),
            ("Season.5", 5),
            ("season 12", 12),
            ("SEASON.12", 12),
        ]

        for folder_name, expected in test_cases:
            match = SEASON_FOLDER_PATTERN.search(folder_name)
            assert match is not None, f"Failed to match: {folder_name}"
            assert int(match.group(1)) == expected, f"Wrong number for: {folder_name}"
