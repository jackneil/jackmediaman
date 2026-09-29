"""Tests for TV scanner."""

import pytest
from jackmediaman.scanners.tv import TVScanner


class TestSeasonFolderPattern:
    """Tests for season folder pattern matching."""

    def test_season_space_number(self):
        """Match 'Season 05' format."""
        scanner = TVScanner()
        assert scanner._parse_season_number('Season 05') == 5
        assert scanner._parse_season_number('Season 1') == 1
        assert scanner._parse_season_number('Season 12') == 12

    def test_season_period_number(self):
        """Match 'Season.05' format (period instead of space)."""
        scanner = TVScanner()
        assert scanner._parse_season_number('Season.05') == 5
        assert scanner._parse_season_number('Season.1') == 1
        assert scanner._parse_season_number('Season.12') == 12

    def test_season_no_separator(self):
        """Match 'Season05' format (no separator)."""
        scanner = TVScanner()
        assert scanner._parse_season_number('Season05') == 5
        assert scanner._parse_season_number('Season1') == 1
        assert scanner._parse_season_number('Season12') == 12

    def test_season_multiple_periods(self):
        """Match 'Season...05' format (multiple periods)."""
        scanner = TVScanner()
        assert scanner._parse_season_number('Season...05') == 5
        assert scanner._parse_season_number('Season..1') == 1

    def test_case_insensitive(self):
        """Match case-insensitive season formats."""
        scanner = TVScanner()
        assert scanner._parse_season_number('SEASON 05') == 5
        assert scanner._parse_season_number('season.05') == 5
        assert scanner._parse_season_number('SeAsOn 1') == 1

    def test_just_number(self):
        """Match folders that are just numbers."""
        scanner = TVScanner()
        assert scanner._parse_season_number('01') == 1
        assert scanner._parse_season_number('5') == 5
        assert scanner._parse_season_number('12') == 12

    def test_non_season_folders(self):
        """Non-season folders return None."""
        scanner = TVScanner()
        assert scanner._parse_season_number('Specials') is None
        assert scanner._parse_season_number('Extras') is None
        assert scanner._parse_season_number('Behind the Scenes') is None
