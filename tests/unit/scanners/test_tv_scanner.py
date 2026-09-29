"""Tests for TV scanner."""

import pytest
from pathlib import Path

from jackmediaman.scanners.tv import TVScanner, VIDEO_EXTENSIONS
from jackmediaman.models.media import Episode
from jackmediaman.models.quality import Resolution


class TestTVScanner:
    """Tests for TVScanner class."""

    @pytest.fixture
    def scanner(self):
        """Create a TV scanner."""
        return TVScanner()

    def test_scan_finds_episodes(self, scanner, tmp_tv_library):
        """Scanner finds all video files in TV library."""
        episodes = list(scanner.scan(tmp_tv_library))
        assert len(episodes) >= 3  # At least BB S01E01 x2, S01E02, Office S01E01

    def test_scan_returns_episode_objects(self, scanner, tmp_tv_library):
        """Scanner returns Episode objects."""
        episodes = list(scanner.scan(tmp_tv_library))
        assert all(isinstance(ep, Episode) for ep in episodes)

    def test_scan_skips_non_video_files(self, scanner, tmp_path):
        """Scanner skips non-video files."""
        tv_dir = tmp_path / "TV Shows" / "Show" / "Season 1"
        tv_dir.mkdir(parents=True)
        (tv_dir / "Show.S01E01.txt").write_text("not a video")
        (tv_dir / "Show.S01E01.nfo").write_text("info file")
        (tv_dir / "Show.S01E01.srt").write_text("subtitles")

        episodes = list(scanner.scan(tmp_path / "TV Shows"))
        assert len(episodes) == 0

    def test_scan_includes_all_video_extensions(self, scanner, tmp_path):
        """Scanner includes all video extensions."""
        tv_dir = tmp_path / "TV Shows" / "Show" / "Season 1"
        tv_dir.mkdir(parents=True)

        for ext in [".mkv", ".mp4", ".avi"]:
            (tv_dir / f"Show.S01E01{ext}").write_bytes(b"0" * 100)

        episodes = list(scanner.scan(tmp_path / "TV Shows"))
        assert len(episodes) == 3

    def test_scan_nonexistent_directory(self, scanner, tmp_path):
        """Scanning nonexistent directory yields nothing."""
        episodes = list(scanner.scan(tmp_path / "nonexistent"))
        assert len(episodes) == 0

    def test_scan_extracts_series_name(self, scanner, tmp_tv_library):
        """Scanner extracts series name from folder."""
        episodes = list(scanner.scan(tmp_tv_library))
        series_names = set(ep.series_name for ep in episodes)
        assert "Breaking Bad" in series_names

    def test_scan_extracts_season_number(self, scanner, tmp_tv_library):
        """Scanner extracts season number from folder."""
        episodes = list(scanner.scan(tmp_tv_library))
        bb_episodes = [ep for ep in episodes if ep.series_name == "Breaking Bad"]
        assert all(ep.season_number == 1 for ep in bb_episodes)

    def test_scan_parses_quality(self, scanner, tmp_tv_library):
        """Scanner parses quality from filename."""
        episodes = list(scanner.scan(tmp_tv_library))
        # Find a 1080p episode
        ep_1080 = next((e for e in episodes if "1080p" in e.filename), None)
        if ep_1080:
            assert ep_1080.quality.resolution == Resolution.FHD


class TestTVScannerSeasonParsing:
    """Tests for season folder parsing."""

    @pytest.fixture
    def scanner(self):
        return TVScanner()

    def test_parse_season_standard(self, scanner):
        """Parses 'Season X' format."""
        assert scanner._parse_season_number("Season 1") == 1
        assert scanner._parse_season_number("Season 12") == 12
        assert scanner._parse_season_number("Season 5") == 5

    def test_parse_season_lowercase(self, scanner):
        """Parses lowercase 'season x' format."""
        assert scanner._parse_season_number("season 1") == 1
        assert scanner._parse_season_number("season 10") == 10

    def test_parse_season_no_space(self, scanner):
        """Parses 'SeasonX' format."""
        assert scanner._parse_season_number("Season1") == 1
        assert scanner._parse_season_number("season5") == 5

    def test_parse_season_numeric(self, scanner):
        """Parses numeric-only season folders."""
        assert scanner._parse_season_number("01") == 1
        assert scanner._parse_season_number("12") == 12
        assert scanner._parse_season_number("1") == 1

    def test_parse_season_invalid(self, scanner):
        """Returns None for invalid season folders."""
        assert scanner._parse_season_number("Specials") is None
        assert scanner._parse_season_number("Extras") is None
        assert scanner._parse_season_number("Featurettes") is None


class TestTVScannerEpisodeParsing:
    """Tests for episode number parsing."""

    @pytest.fixture
    def scanner(self):
        return TVScanner()

    def test_parse_episode_standard(self, scanner):
        """Parses S01E01 format."""
        assert scanner._parse_episode_numbers("Show.S01E01.mkv") == [1]
        assert scanner._parse_episode_numbers("Show.S12E99.mkv") == [99]

    def test_parse_episode_lowercase(self, scanner):
        """Parses s01e01 format."""
        assert scanner._parse_episode_numbers("Show.s01e01.mkv") == [1]

    def test_parse_episode_multi_standard(self, scanner):
        """Parses S01E01E02E03 format."""
        result = scanner._parse_episode_numbers("Show.S01E01E02E03.mkv")
        assert result == [1, 2, 3]

    def test_parse_episode_multi_lowercase(self, scanner):
        """Parses s01e01e02 format."""
        result = scanner._parse_episode_numbers("Show.s01e01e02.mkv")
        assert result == [1, 2]

    def test_parse_episode_range(self, scanner):
        """Parses episode range S01E01-03 format."""
        result = scanner._parse_episode_numbers("Show.S01E01-03.mkv")
        assert result == [1, 2, 3]

    def test_parse_episode_alt_format(self, scanner):
        """Parses 1x01 format."""
        assert scanner._parse_episode_numbers("Show.1x01.mkv") == [1]
        assert scanner._parse_episode_numbers("Show.12x99.mkv") == [99]

    def test_parse_episode_with_quality(self, scanner):
        """Parses episode from filename with quality tags."""
        assert scanner._parse_episode_numbers("Show.S01E05.1080p.BluRay.mkv") == [5]

    def test_parse_episode_no_match(self, scanner):
        """Returns empty list for no match."""
        assert scanner._parse_episode_numbers("random_file.mkv") == []

    def test_parse_episode_from_filename(self, scanner):
        """Parses both season and episode from filename."""
        season, episodes = scanner._parse_episode_from_filename("Show.S02E05.mkv")
        assert season == 2
        assert episodes == [5]

    def test_parse_episode_from_filename_range(self, scanner):
        """Parses season and episode range from filename."""
        season, episodes = scanner._parse_episode_from_filename("Show.S01E01-03.mkv")
        assert season == 1
        assert episodes == [1, 2, 3]


class TestTVScannerMultipleShows:
    """Tests for scanning multiple shows."""

    @pytest.fixture
    def scanner(self):
        return TVScanner()

    def test_multiple_shows(self, scanner, tmp_tv_library):
        """Scanner handles multiple shows."""
        episodes = list(scanner.scan(tmp_tv_library))
        series_names = set(ep.series_name for ep in episodes)
        assert len(series_names) >= 2  # Breaking Bad and The Office

    def test_multiple_seasons(self, scanner, tmp_path):
        """Scanner handles multiple seasons."""
        tv_dir = tmp_path / "TV Shows" / "Show"
        for season in [1, 2, 3]:
            season_dir = tv_dir / f"Season {season}"
            season_dir.mkdir(parents=True)
            (season_dir / f"Show.S{season:02d}E01.mkv").write_bytes(b"0" * 100)

        episodes = list(scanner.scan(tmp_path / "TV Shows"))
        seasons = set(ep.season_number for ep in episodes)
        assert seasons == {1, 2, 3}

    def test_symlink_detection(self, scanner, tmp_path):
        """Scanner detects symlinks."""
        tv_dir = tmp_path / "TV Shows" / "Show" / "Season 1"
        tv_dir.mkdir(parents=True)

        # Create target file
        target = tmp_path / "torrents" / "show.mkv"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"0" * 100)

        # Create symlink
        symlink = tv_dir / "Show.S01E01.mkv"
        symlink.symlink_to(target)

        episodes = list(scanner.scan(tmp_path / "TV Shows"))
        assert len(episodes) == 1
        assert episodes[0].is_symlink is True
        assert episodes[0].symlink_target is not None
