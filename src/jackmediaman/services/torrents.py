"""Torrent service for managing Deluge torrents."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger

logger = get_logger("torrents")


@dataclass
class TorrentInfo:
    """Information about a torrent."""

    torrent_id: str
    name: str
    progress: float  # 0.0 to 1.0
    state: str  # "Downloading", "Seeding", "Paused", etc.
    save_path: Path
    total_size: int  # bytes

    @property
    def is_completed(self) -> bool:
        """Check if torrent is 100% complete."""
        return self.progress >= 1.0

    @property
    def size_gb(self) -> float:
        """Get size in GB."""
        return self.total_size / (1024 * 1024 * 1024)

    @property
    def progress_percent(self) -> int:
        """Get progress as percentage."""
        return int(self.progress * 100)


@dataclass
class MoveResult:
    """Result of a torrent move operation."""

    torrent: TorrentInfo
    destination: Path
    success: bool
    error: Optional[str] = None


class TorrentService:
    """Service for managing Deluge torrents using deluge-client."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        download_path: Optional[Path] = None,
        completed_path: Optional[Path] = None,
    ):
        """Initialize the torrent service."""
        settings = get_settings()
        self.host = host or settings.deluge_host
        self.port = port or settings.deluge_port
        self.username = username or settings.deluge_username or ""
        self.password = password or settings.deluge_password or ""
        self.download_path = download_path or Path.home() / "torrents" / "downloading"
        self.completed_path = completed_path or Path.home() / "torrents" / "completed"
        self._torrents: List[TorrentInfo] = []
        self._connected = False

    def connect(self) -> bool:
        """Connect to Deluge daemon and fetch torrents.

        Returns:
            True if connected successfully, False otherwise
        """
        try:
            from jackmediaman.services.deluge_client import create_deluge_client

            client = create_deluge_client(
                self.host, self.port, self.username, self.password
            )
            client.connect()

            result = client.call(
                "core.get_torrents_status",
                {},
                ["name", "progress", "state", "save_path", "total_size"],
            )

            self._parse_torrents(result)
            self._connected = True
            client.disconnect()
            return True

        except Exception:
            return False

    def _parse_torrents(self, raw_torrents: Dict[bytes, Dict[bytes, Any]]) -> None:
        """Parse raw torrent data from Deluge."""
        self._torrents = []

        for torrent_id, info in raw_torrents.items():
            # Handle bytes
            tid = torrent_id.decode("utf-8") if isinstance(torrent_id, bytes) else torrent_id

            name = info.get(b"name", info.get("name", b"Unknown"))
            if isinstance(name, bytes):
                name = name.decode("utf-8")

            state = info.get(b"state", info.get("state", b"Unknown"))
            if isinstance(state, bytes):
                state = state.decode("utf-8")

            save_path = info.get(b"save_path", info.get("save_path", b""))
            if isinstance(save_path, bytes):
                save_path = save_path.decode("utf-8")

            progress = info.get(b"progress", info.get("progress", 0.0))
            total_size = info.get(b"total_size", info.get("total_size", 0))

            self._torrents.append(
                TorrentInfo(
                    torrent_id=tid,
                    name=name,
                    progress=progress / 100.0,  # Deluge returns 0-100
                    state=state,
                    save_path=Path(save_path),
                    total_size=total_size,
                )
            )

        # Sort by name
        self._torrents.sort(key=lambda t: t.name.lower())

    def disconnect(self) -> None:
        """Disconnect from Deluge daemon."""
        self._connected = False

    def get_torrents(self) -> List[TorrentInfo]:
        """Get all torrents from Deluge."""
        return self._torrents

    def needs_move(self, torrent: TorrentInfo) -> bool:
        """Check if a torrent needs to be moved to completed folder."""
        if not torrent.is_completed:
            return False

        # Check if save_path is in the downloading folder
        try:
            torrent.save_path.relative_to(self.download_path)
            return True
        except ValueError:
            return False

    def get_torrents_needing_move(self) -> List[TorrentInfo]:
        """Get all torrents that need to be moved."""
        return [t for t in self._torrents if self.needs_move(t)]

    def move_torrent(
        self,
        torrent: TorrentInfo,
        dry_run: bool = True,
    ) -> MoveResult:
        """Move a torrent to the completed folder."""
        if dry_run:
            return MoveResult(
                torrent=torrent,
                destination=self.completed_path,
                success=True,
            )

        try:
            from jackmediaman.services.deluge_client import create_deluge_client

            client = create_deluge_client(
                self.host, self.port, self.username, self.password
            )
            client.connect()

            client.call(
                "core.move_storage", [torrent.torrent_id], str(self.completed_path)
            )

            client.disconnect()

            return MoveResult(
                torrent=torrent,
                destination=self.completed_path,
                success=True,
            )

        except Exception as e:
            return MoveResult(
                torrent=torrent,
                destination=self.completed_path,
                success=False,
                error=str(e),
            )

    def move_completed(
        self,
        dry_run: bool = True,
    ) -> List[MoveResult]:
        """Move all completed torrents to the completed folder."""
        torrents = self.get_torrents_needing_move()
        results = []

        for torrent in torrents:
            result = self.move_torrent(torrent, dry_run=dry_run)
            results.append(result)

        return results
