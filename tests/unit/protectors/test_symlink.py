"""Tests for symlink protector."""

import pytest
from pathlib import Path
from unittest.mock import patch

from jackmediaman.protectors.symlink import SymlinkProtector
from jackmediaman.models.media import Movie
from jackmediaman.models.quality import Quality, Resolution


class TestSymlinkProtector:
    """Tests for SymlinkProtector class."""

    @pytest.fixture
    def protector(self, tmp_path):
        """Create a symlink protector with test torrent dir."""
        torrent_dir = tmp_path / "torrents"
        torrent_dir.mkdir()
        return SymlinkProtector(torrent_dir=torrent_dir)

    @pytest.fixture
    def sample_movie(self, tmp_path):
        """Create a non-symlink movie."""
        quality = Quality(resolution=Resolution.FHD)
        path = tmp_path / "Movies" / "movie.mkv"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"0" * 100)

        return Movie(
            path=path,
            filename=path.name,
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
            is_symlink=False,
            symlink_target=None,
        )

    @pytest.fixture
    def symlinked_movie_to_torrent(self, tmp_path):
        """Create a movie that is symlinked to torrent directory."""
        quality = Quality(resolution=Resolution.FHD)

        # Create torrent directory and source file
        torrent_dir = tmp_path / "torrents"
        torrent_dir.mkdir(exist_ok=True)
        source = torrent_dir / "movie.mkv"
        source.write_bytes(b"0" * 100)

        # Create symlink in Movies directory
        movies_dir = tmp_path / "Movies"
        movies_dir.mkdir()
        symlink = movies_dir / "movie.mkv"
        symlink.symlink_to(source)

        return Movie(
            path=symlink,
            filename=symlink.name,
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
            is_symlink=True,
            symlink_target=source,
        )

    @pytest.fixture
    def symlinked_movie_elsewhere(self, tmp_path):
        """Create a movie symlinked to non-torrent directory."""
        quality = Quality(resolution=Resolution.FHD)

        # Create source file in different location
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        source = other_dir / "movie.mkv"
        source.write_bytes(b"0" * 100)

        # Create symlink in Movies directory
        movies_dir = tmp_path / "Movies"
        movies_dir.mkdir()
        symlink = movies_dir / "movie.mkv"
        symlink.symlink_to(source)

        return Movie(
            path=symlink,
            filename=symlink.name,
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
            is_symlink=True,
            symlink_target=source,
        )

    def test_check_non_symlink(self, protector, sample_movie):
        """Non-symlink files are not protected."""
        assert protector.check(sample_movie) is False

    def test_check_symlink_to_torrent(self, protector, symlinked_movie_to_torrent, tmp_path):
        """Symlinks to torrent directory are protected."""
        # Create protector with correct torrent dir
        torrent_dir = tmp_path / "torrents"
        protector = SymlinkProtector(torrent_dir=torrent_dir)

        assert protector.check(symlinked_movie_to_torrent) is True

    def test_check_symlink_elsewhere(self, tmp_path, symlinked_movie_elsewhere):
        """Symlinks to non-torrent directories are not protected."""
        # Create protector with different torrent dir
        torrent_dir = tmp_path / "torrents"
        torrent_dir.mkdir(exist_ok=True)
        protector = SymlinkProtector(torrent_dir=torrent_dir)

        assert protector.check(symlinked_movie_elsewhere) is False

    def test_get_reason(self, protector, symlinked_movie_to_torrent):
        """Get reason includes symlink target."""
        reason = protector.get_reason(symlinked_movie_to_torrent)
        assert "Symlink" in reason
        assert "torrent" in reason.lower()

    def test_protect_marks_items(self, tmp_path):
        """Protect method marks items as protected."""
        quality = Quality(resolution=Resolution.FHD)

        # Create torrent directory and source file
        torrent_dir = tmp_path / "torrents"
        torrent_dir.mkdir(exist_ok=True)
        source = torrent_dir / "movie.mkv"
        source.write_bytes(b"0" * 100)

        # Create symlink
        movies_dir = tmp_path / "Movies"
        movies_dir.mkdir()
        symlink = movies_dir / "movie.mkv"
        symlink.symlink_to(source)

        movie = Movie(
            path=symlink,
            filename=symlink.name,
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
            is_symlink=True,
            symlink_target=source,
        )

        protector = SymlinkProtector(torrent_dir=torrent_dir)
        count = protector.protect([movie])

        assert count == 1
        assert movie.is_protected is True
        assert movie.protection_reason is not None

    def test_protect_returns_count(self, protector, sample_movie):
        """Protect returns count of protected items."""
        count = protector.protect([sample_movie])
        assert count == 0

    def test_protector_attributes(self, protector):
        """Protector has expected attributes."""
        assert protector.name == "symlink"
        assert "symlink" in protector.description.lower()


class TestSymlinkProtectorEdgeCases:
    """Edge case tests for SymlinkProtector."""

    def test_broken_symlink(self, tmp_path):
        """Handles broken symlinks gracefully."""
        quality = Quality(resolution=Resolution.FHD)

        # Create symlink to non-existent target
        movies_dir = tmp_path / "Movies"
        movies_dir.mkdir()
        symlink = movies_dir / "movie.mkv"
        symlink.symlink_to(tmp_path / "nonexistent" / "movie.mkv")

        movie = Movie(
            path=symlink,
            filename=symlink.name,
            size_bytes=0,
            quality=quality,
            title="Test",
            year=2020,
            is_symlink=True,
            symlink_target=tmp_path / "nonexistent" / "movie.mkv",
        )

        torrent_dir = tmp_path / "torrents"
        torrent_dir.mkdir()
        protector = SymlinkProtector(torrent_dir=torrent_dir)

        # Should not raise, should return False
        result = protector.check(movie)
        assert result is False

    def test_symlink_target_none(self, tmp_path):
        """Handles None symlink target."""
        quality = Quality(resolution=Resolution.FHD)

        path = tmp_path / "movie.mkv"
        path.write_bytes(b"0" * 100)

        movie = Movie(
            path=path,
            filename=path.name,
            size_bytes=100,
            quality=quality,
            title="Test",
            year=2020,
            is_symlink=True,  # Says symlink but no target
            symlink_target=None,
        )

        protector = SymlinkProtector(torrent_dir=tmp_path / "torrents")
        assert protector.check(movie) is False
