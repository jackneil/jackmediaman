"""Scanners must skip dangling symlinks instead of crashing (issue #2)."""

import os
from pathlib import Path

import pytest

from jackmediaman.scanners.movies import MovieScanner
from jackmediaman.scanners.tv import TVScanner


def _dangling_link(link: Path, target: Path) -> Path:
    """Create a symlink to a target that does not exist, or skip the test."""
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError) as e:
        pytest.skip(f"cannot create symlinks here: {e}")
    return link


@pytest.fixture
def movie_library(tmp_path):
    movies = tmp_path / "Movies"
    movie_dir = movies / "A Christmas Story (1983)"
    movie_dir.mkdir(parents=True)
    link = _dangling_link(
        movie_dir / "A Christmas Story 1983 1080p BluRay x264-OFT.mkv",
        tmp_path / "torrents" / "gone.mkv",
    )
    return movies, link


@pytest.fixture
def tv_library(tmp_path):
    tv = tmp_path / "TV"
    season = tv / "Show" / "Season 01"
    season.mkdir(parents=True)
    link = _dangling_link(season / "Show S01E01.mkv", tmp_path / "torrents" / "gone.mkv")
    return tv, link


class TestMovieScannerBrokenLinks:
    def test_scan_skips_dangling_symlink(self, movie_library):
        movies, link = movie_library
        scanner = MovieScanner()
        assert list(scanner.scan(movies)) == []
        assert scanner.broken_links == [link]

    def test_scan_with_metadata_skips_dangling_symlink(self, movie_library):
        movies, link = movie_library
        scanner = MovieScanner()
        assert scanner.scan_with_metadata(movies) == []
        assert scanner.broken_links == [link]


class TestTVScannerBrokenLinks:
    def test_scan_skips_dangling_symlink(self, tv_library):
        tv, link = tv_library
        scanner = TVScanner()
        assert list(scanner.scan(tv)) == []
        assert scanner.broken_links == [link]

    def test_scan_with_metadata_skips_dangling_symlink(self, tv_library):
        tv, link = tv_library
        scanner = TVScanner()
        assert scanner.scan_with_metadata(tv) == []
        assert scanner.broken_links == [link]


class TestBrokenLinkWithoutSymlinkPrivilege:
    """Same check where symlinks can't be created: a path whose exists() is False."""

    def test_movie_scan_collects_missing_target(self, tmp_path, monkeypatch):
        movie_dir = tmp_path / "Movies" / "Film (2020)"
        movie_dir.mkdir(parents=True)
        video = movie_dir / "Film.2020.1080p.mkv"
        video.write_bytes(b"x")

        real_exists = Path.exists
        monkeypatch.setattr(Path, "exists", lambda self: self != video and real_exists(self))

        scanner = MovieScanner()
        assert list(scanner.scan(tmp_path / "Movies")) == []
        assert scanner.broken_links == [video]
