"""Tests for torrent service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jackmediaman.services.torrents import MoveResult, TorrentInfo, TorrentService


class TestTorrentInfo:
    """Tests for TorrentInfo dataclass."""

    def test_create_torrent_info(self):
        """Create a TorrentInfo instance."""
        info = TorrentInfo(
            torrent_id="abc123",
            name="Test.Torrent.2024",
            progress=0.5,
            state="Downloading",
            save_path=Path("/downloads"),
            total_size=1024 * 1024 * 1024,  # 1 GB
        )
        assert info.torrent_id == "abc123"
        assert info.name == "Test.Torrent.2024"
        assert info.progress == 0.5
        assert info.state == "Downloading"

    def test_is_completed_true(self):
        """Torrent with 100% progress is completed."""
        info = TorrentInfo(
            torrent_id="abc123",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/downloads"),
            total_size=1024,
        )
        assert info.is_completed is True

    def test_is_completed_false(self):
        """Torrent with less than 100% is not completed."""
        info = TorrentInfo(
            torrent_id="abc123",
            name="Test",
            progress=0.99,
            state="Downloading",
            save_path=Path("/downloads"),
            total_size=1024,
        )
        assert info.is_completed is False

    def test_is_completed_at_boundary(self):
        """Torrent at exactly 1.0 is completed."""
        info = TorrentInfo(
            torrent_id="abc123",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/downloads"),
            total_size=1024,
        )
        assert info.is_completed is True

    def test_size_gb(self):
        """Size in GB calculation."""
        info = TorrentInfo(
            torrent_id="abc123",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/downloads"),
            total_size=2 * 1024 * 1024 * 1024,  # 2 GB
        )
        assert info.size_gb == 2.0

    def test_size_gb_fractional(self):
        """Size in GB with fractional value."""
        info = TorrentInfo(
            torrent_id="abc123",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/downloads"),
            total_size=int(1.5 * 1024 * 1024 * 1024),  # 1.5 GB
        )
        assert abs(info.size_gb - 1.5) < 0.01

    def test_progress_percent(self):
        """Progress as percentage."""
        info = TorrentInfo(
            torrent_id="abc123",
            name="Test",
            progress=0.75,
            state="Downloading",
            save_path=Path("/downloads"),
            total_size=1024,
        )
        assert info.progress_percent == 75

    def test_progress_percent_zero(self):
        """Progress percent at 0%."""
        info = TorrentInfo(
            torrent_id="abc123",
            name="Test",
            progress=0.0,
            state="Queued",
            save_path=Path("/downloads"),
            total_size=1024,
        )
        assert info.progress_percent == 0

    def test_progress_percent_100(self):
        """Progress percent at 100%."""
        info = TorrentInfo(
            torrent_id="abc123",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/downloads"),
            total_size=1024,
        )
        assert info.progress_percent == 100


class TestMoveResult:
    """Tests for MoveResult dataclass."""

    def test_create_success_result(self):
        """Create a successful move result."""
        torrent = TorrentInfo(
            torrent_id="abc123",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/downloads"),
            total_size=1024,
        )
        result = MoveResult(
            torrent=torrent,
            destination=Path("/completed"),
            success=True,
        )
        assert result.success is True
        assert result.error is None

    def test_create_failure_result(self):
        """Create a failed move result."""
        torrent = TorrentInfo(
            torrent_id="abc123",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/downloads"),
            total_size=1024,
        )
        result = MoveResult(
            torrent=torrent,
            destination=Path("/completed"),
            success=False,
            error="Permission denied",
        )
        assert result.success is False
        assert result.error == "Permission denied"


class TestTorrentService:
    """Tests for TorrentService class."""

    def test_init_default_settings(self):
        """Initialize with default settings."""
        with patch("jackmediaman.services.torrents.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
            )
            service = TorrentService()

            assert service.host == "127.0.0.1"
            assert service.port == 58846
            assert service.username == ""
            assert service.password == ""

    def test_init_custom_settings(self):
        """Initialize with custom settings."""
        with patch("jackmediaman.services.torrents.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
            )
            service = TorrentService(
                host="192.168.1.100",
                port=12345,
                username="user",
                password="pass",
                download_path=Path("/custom/downloads"),
                completed_path=Path("/custom/completed"),
            )

            assert service.host == "192.168.1.100"
            assert service.port == 12345
            assert service.username == "user"
            assert service.password == "pass"
            assert service.download_path == Path("/custom/downloads")
            assert service.completed_path == Path("/custom/completed")

    def test_disconnect(self):
        """Disconnect sets connected flag."""
        with patch("jackmediaman.services.torrents.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
            )
            service = TorrentService()
            service._connected = True

            service.disconnect()

            assert service._connected is False

    def test_get_torrents_empty(self):
        """Get torrents when none exist."""
        with patch("jackmediaman.services.torrents.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
            )
            service = TorrentService()

            torrents = service.get_torrents()

            assert torrents == []

    def test_get_torrents_after_parse(self):
        """Get torrents after parsing."""
        with patch("jackmediaman.services.torrents.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
            )
            service = TorrentService()

            # Simulate parsed torrents
            service._torrents = [
                TorrentInfo(
                    torrent_id="abc",
                    name="Test1",
                    progress=1.0,
                    state="Seeding",
                    save_path=Path("/downloads"),
                    total_size=1024,
                ),
                TorrentInfo(
                    torrent_id="def",
                    name="Test2",
                    progress=0.5,
                    state="Downloading",
                    save_path=Path("/downloads"),
                    total_size=2048,
                ),
            ]

            torrents = service.get_torrents()

            assert len(torrents) == 2


class TestTorrentServiceParsing:
    """Tests for torrent parsing logic."""

    @pytest.fixture
    def service(self):
        """Create a TorrentService instance."""
        with patch("jackmediaman.services.torrents.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
            )
            return TorrentService()

    def test_parse_torrents_bytes_keys(self, service):
        """Parse torrents with bytes keys (Deluge format)."""
        raw_data = {
            b"abc123": {
                b"name": b"Test.Torrent.2024",
                b"progress": 100.0,
                b"state": b"Seeding",
                b"save_path": b"/downloads",
                b"total_size": 1024,
            }
        }

        service._parse_torrents(raw_data)

        assert len(service._torrents) == 1
        assert service._torrents[0].name == "Test.Torrent.2024"
        assert service._torrents[0].progress == 1.0
        assert service._torrents[0].state == "Seeding"

    def test_parse_torrents_string_keys(self, service):
        """Parse torrents with string keys."""
        raw_data = {
            "abc123": {
                "name": "Test.Torrent.2024",
                "progress": 50.0,
                "state": "Downloading",
                "save_path": "/downloads",
                "total_size": 2048,
            }
        }

        service._parse_torrents(raw_data)

        assert len(service._torrents) == 1
        assert service._torrents[0].progress == 0.5  # Deluge returns 0-100

    def test_parse_torrents_multiple(self, service):
        """Parse multiple torrents."""
        raw_data = {
            b"abc": {
                b"name": b"Torrent A",
                b"progress": 100.0,
                b"state": b"Seeding",
                b"save_path": b"/downloads",
                b"total_size": 1024,
            },
            b"def": {
                b"name": b"Torrent B",
                b"progress": 50.0,
                b"state": b"Downloading",
                b"save_path": b"/downloads",
                b"total_size": 2048,
            },
        }

        service._parse_torrents(raw_data)

        assert len(service._torrents) == 2

    def test_parse_torrents_sorted_by_name(self, service):
        """Torrents are sorted by name."""
        raw_data = {
            b"1": {b"name": b"Zebra", b"progress": 100.0, b"state": b"Seeding", b"save_path": b"/dl", b"total_size": 100},
            b"2": {b"name": b"Alpha", b"progress": 100.0, b"state": b"Seeding", b"save_path": b"/dl", b"total_size": 100},
            b"3": {b"name": b"Beta", b"progress": 100.0, b"state": b"Seeding", b"save_path": b"/dl", b"total_size": 100},
        }

        service._parse_torrents(raw_data)

        names = [t.name for t in service._torrents]
        assert names == ["Alpha", "Beta", "Zebra"]


class TestTorrentServiceNeedsMove:
    """Tests for needs_move logic."""

    @pytest.fixture
    def service(self):
        """Create a TorrentService with specific paths."""
        with patch("jackmediaman.services.torrents.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
            )
            return TorrentService(
                download_path=Path("/torrents/downloading"),
                completed_path=Path("/torrents/completed"),
            )

    def test_needs_move_completed_in_downloading(self, service):
        """Completed torrent in downloading folder needs move."""
        torrent = TorrentInfo(
            torrent_id="abc",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/torrents/downloading"),
            total_size=1024,
        )

        assert service.needs_move(torrent) is True

    def test_needs_move_completed_in_completed(self, service):
        """Completed torrent already in completed folder doesn't need move."""
        torrent = TorrentInfo(
            torrent_id="abc",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/torrents/completed"),
            total_size=1024,
        )

        assert service.needs_move(torrent) is False

    def test_needs_move_incomplete(self, service):
        """Incomplete torrent doesn't need move."""
        torrent = TorrentInfo(
            torrent_id="abc",
            name="Test",
            progress=0.5,
            state="Downloading",
            save_path=Path("/torrents/downloading"),
            total_size=1024,
        )

        assert service.needs_move(torrent) is False

    def test_needs_move_other_location(self, service):
        """Torrent in other location doesn't need move."""
        torrent = TorrentInfo(
            torrent_id="abc",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/other/location"),
            total_size=1024,
        )

        assert service.needs_move(torrent) is False

    def test_get_torrents_needing_move(self, service):
        """Get only torrents that need to be moved."""
        service._torrents = [
            # Completed in downloading - needs move
            TorrentInfo(
                torrent_id="1",
                name="Needs Move",
                progress=1.0,
                state="Seeding",
                save_path=Path("/torrents/downloading"),
                total_size=1024,
            ),
            # Incomplete - doesn't need move
            TorrentInfo(
                torrent_id="2",
                name="Still Downloading",
                progress=0.5,
                state="Downloading",
                save_path=Path("/torrents/downloading"),
                total_size=2048,
            ),
            # Completed but already moved - doesn't need move
            TorrentInfo(
                torrent_id="3",
                name="Already Moved",
                progress=1.0,
                state="Seeding",
                save_path=Path("/torrents/completed"),
                total_size=4096,
            ),
        ]

        needing_move = service.get_torrents_needing_move()

        assert len(needing_move) == 1
        assert needing_move[0].name == "Needs Move"


class TestTorrentServiceDryRun:
    """Tests for dry run functionality."""

    @pytest.fixture
    def service(self):
        """Create a TorrentService instance."""
        with patch("jackmediaman.services.torrents.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
            )
            return TorrentService(
                download_path=Path("/torrents/downloading"),
                completed_path=Path("/torrents/completed"),
            )

    def test_move_torrent_dry_run(self, service):
        """Dry run returns success without actually moving."""
        torrent = TorrentInfo(
            torrent_id="abc",
            name="Test",
            progress=1.0,
            state="Seeding",
            save_path=Path("/torrents/downloading"),
            total_size=1024,
        )

        result = service.move_torrent(torrent, dry_run=True)

        assert result.success is True
        assert result.destination == Path("/torrents/completed")
        assert result.error is None

    def test_move_completed_dry_run(self, service):
        """Dry run for move_completed returns all success."""
        service._torrents = [
            TorrentInfo(
                torrent_id="1",
                name="Test1",
                progress=1.0,
                state="Seeding",
                save_path=Path("/torrents/downloading"),
                total_size=1024,
            ),
            TorrentInfo(
                torrent_id="2",
                name="Test2",
                progress=1.0,
                state="Seeding",
                save_path=Path("/torrents/downloading"),
                total_size=2048,
            ),
        ]

        results = service.move_completed(dry_run=True)

        assert len(results) == 2
        assert all(r.success for r in results)


class TestTorrentServiceConnection:
    """Tests for connection handling (mocked)."""

    def test_connect_import_error(self):
        """Handle missing Deluge library."""
        with patch("jackmediaman.services.torrents.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(
                deluge_host="127.0.0.1",
                deluge_port=58846,
                deluge_username="",
                deluge_password="",
            )
            service = TorrentService()

            # Mock the import to fail
            with patch.dict("sys.modules", {"deluge.ui.client": None}):
                with patch("builtins.__import__", side_effect=ImportError("No module")):
                    result = service.connect()

            assert result is False
