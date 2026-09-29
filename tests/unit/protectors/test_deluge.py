"""Tests for Deluge protector."""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from jackmediaman.protectors.deluge import DelugeProtector, DelugeRPC
from jackmediaman.models.media import Movie
from jackmediaman.models.quality import Quality, Resolution
from jackmediaman.core.exceptions import DelugeConnectionError


class TestDelugeRPC:
    """Tests for DelugeRPC class."""

    def test_init_default_values(self):
        """RPC client initializes with defaults."""
        rpc = DelugeRPC()
        assert rpc.host == "127.0.0.1"
        assert rpc.port == 58846
        assert rpc.username == ""
        assert rpc.password == ""

    def test_init_custom_values(self):
        """RPC client accepts custom values."""
        rpc = DelugeRPC(
            host="192.168.1.100",
            port=12345,
            username="admin",
            password="secret",
        )
        assert rpc.host == "192.168.1.100"
        assert rpc.port == 12345
        assert rpc.username == "admin"
        assert rpc.password == "secret"

    def test_disconnect_when_not_connected(self):
        """Disconnect is safe when not connected."""
        rpc = DelugeRPC()
        rpc.disconnect()  # Should not raise

    @patch("socket.create_connection")
    def test_connect_failure(self, mock_socket):
        """Connect handles socket errors."""
        mock_socket.side_effect = OSError("Connection refused")

        rpc = DelugeRPC()
        with pytest.raises(DelugeConnectionError):
            rpc.connect()


class TestDelugeProtector:
    """Tests for DelugeProtector class."""

    @pytest.fixture
    def mock_rpc(self):
        """Create a mock RPC client."""
        rpc = MagicMock()
        rpc.connect = MagicMock()
        rpc.disconnect = MagicMock()
        rpc.get_seeding_files = MagicMock(return_value=set())
        return rpc

    @pytest.fixture
    def protector(self, mock_rpc, mock_settings):
        """Create a Deluge protector with mock RPC."""
        protector = DelugeProtector()
        protector.rpc = mock_rpc
        return protector

    @pytest.fixture
    def sample_movie(self, tmp_path):
        """Create a sample movie for testing."""
        quality = Quality(resolution=Resolution.FHD)
        path = tmp_path / "movie.mkv"
        path.write_bytes(b"0" * 100)

        return Movie(
            path=path,
            filename=path.name,
            size_bytes=100,
            quality=quality,
            title="Test Movie",
            year=2020,
        )

    def test_connect_success(self, protector, mock_rpc):
        """Connect returns True on success."""
        result = protector.connect()
        assert result is True
        assert protector._connected is True
        mock_rpc.connect.assert_called_once()
        mock_rpc.get_seeding_files.assert_called_once()

    def test_connect_failure(self, protector, mock_rpc):
        """Connect returns False on failure."""
        mock_rpc.connect.side_effect = DelugeConnectionError("Failed")

        result = protector.connect()
        assert result is False
        assert protector._connected is False

    def test_disconnect(self, protector, mock_rpc):
        """Disconnect calls RPC disconnect."""
        protector._connected = True
        protector.disconnect()

        assert protector._connected is False
        mock_rpc.disconnect.assert_called_once()

    def test_check_not_connected(self, protector, sample_movie):
        """Check returns False when not connected."""
        protector._seeding_files = None
        assert protector.check(sample_movie) is False

    def test_check_file_not_seeding(self, protector, sample_movie):
        """Check returns False for non-seeding file."""
        protector._seeding_files = set()
        assert protector.check(sample_movie) is False

    def test_check_file_is_seeding(self, protector, sample_movie):
        """Check returns True for seeding file."""
        protector._seeding_files = {sample_movie.path.resolve()}
        assert protector.check(sample_movie) is True

    def test_check_symlink_target_is_seeding(self, tmp_path, protector):
        """Check returns True if symlink target is seeding."""
        quality = Quality(resolution=Resolution.FHD)

        # Create source file
        source = tmp_path / "source.mkv"
        source.write_bytes(b"0" * 100)

        # Create symlink
        symlink = tmp_path / "symlink.mkv"
        symlink.symlink_to(source)

        movie = Movie(
            path=symlink,
            filename=symlink.name,
            size_bytes=100,
            quality=quality,
            title="Test",
            year=2020,
            is_symlink=True,
            symlink_target=source,
        )

        protector._seeding_files = {source.resolve()}
        assert protector.check(movie) is True

    def test_get_reason(self, protector, sample_movie):
        """Get reason returns seeding message."""
        reason = protector.get_reason(sample_movie)
        assert "seeding" in reason.lower()
        assert "Deluge" in reason

    def test_protect_connects_if_needed(self, protector, mock_rpc, sample_movie):
        """Protect connects if not already connected."""
        protector._connected = False

        protector.protect([sample_movie])

        mock_rpc.connect.assert_called()

    def test_protect_marks_seeding_files(self, protector, sample_movie):
        """Protect marks seeding files as protected."""
        protector._connected = True
        protector._seeding_files = {sample_movie.path.resolve()}

        count = protector.protect([sample_movie])

        assert count == 1
        assert sample_movie.is_protected is True
        assert sample_movie.protection_reason is not None

    def test_protect_returns_count(self, protector, sample_movie):
        """Protect returns count of protected items."""
        protector._connected = True
        protector._seeding_files = set()

        count = protector.protect([sample_movie])
        assert count == 0

    def test_protect_connection_failure(self, protector, mock_rpc, sample_movie):
        """Protect returns 0 if connection fails."""
        protector._connected = False
        mock_rpc.connect.side_effect = DelugeConnectionError("Failed")

        count = protector.protect([sample_movie])
        assert count == 0

    def test_protector_attributes(self, protector):
        """Protector has expected attributes."""
        assert protector.name == "deluge"
        assert "Deluge" in protector.description


class TestDelugeProtectorMultipleFiles:
    """Tests for protecting multiple files."""

    @pytest.fixture
    def protector(self, mock_settings):
        """Create a Deluge protector."""
        protector = DelugeProtector()
        protector._connected = True
        protector._seeding_files = set()
        return protector

    def test_protect_multiple_files(self, protector, tmp_path):
        """Protect handles multiple files."""
        quality = Quality(resolution=Resolution.FHD)
        movies = []

        for i in range(5):
            path = tmp_path / f"movie{i}.mkv"
            path.write_bytes(b"0" * 100)
            movies.append(Movie(
                path=path,
                filename=path.name,
                size_bytes=100,
                quality=quality,
                title=f"Movie {i}",
                year=2020,
            ))

        # Mark 2 as seeding
        protector._seeding_files = {
            movies[1].path.resolve(),
            movies[3].path.resolve(),
        }

        count = protector.protect(movies)

        assert count == 2
        assert movies[0].is_protected is False
        assert movies[1].is_protected is True
        assert movies[2].is_protected is False
        assert movies[3].is_protected is True
        assert movies[4].is_protected is False

    def test_protect_empty_list(self, protector):
        """Protect handles empty list."""
        count = protector.protect([])
        assert count == 0
