"""Deluge RPC client helper with localhost auth fallback.

Uses deluge-client (synchronous) instead of deluge.ui.client (Twisted) to avoid
reactor issues where connections fail after the first use.
"""

from pathlib import Path
from typing import Optional, Tuple

from deluge_client import DelugeRPCClient

from jackmediaman.core.logging import get_logger

logger = get_logger("deluge")


def get_localclient_auth() -> Optional[Tuple[str, str]]:
    """Read localclient credentials from ~/.config/deluge/auth.

    The Deluge auth file format is: username:password:level
    For localhost connections, we use the 'localclient' user.

    Returns:
        Tuple of (username, password) if found, None otherwise.
    """
    auth_file = Path.home() / ".config" / "deluge" / "auth"
    if not auth_file.exists():
        return None

    try:
        for line in auth_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == "localclient":
                return (parts[0], parts[1])
    except Exception:
        pass

    return None


def create_deluge_client(
    host: str,
    port: int,
    username: str = "",
    password: str = "",
) -> DelugeRPCClient:
    """Create a Deluge RPC client with localhost auth fallback.

    If no credentials are provided and the host is localhost, this will
    automatically read the localclient credentials from ~/.config/deluge/auth.

    Args:
        host: Deluge daemon host
        port: Deluge daemon port
        username: Optional username (falls back to localclient for localhost)
        password: Optional password (falls back to auth file for localhost)

    Returns:
        Configured DelugeRPCClient (not yet connected)
    """
    # If no credentials and localhost, try auth file
    if not username and host in ("127.0.0.1", "localhost"):
        auth = get_localclient_auth()
        if auth:
            username, password = auth

    return DelugeRPCClient(host, port, username, password)
