"""Deluge Execute plugin setup using deluge-client."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ExecuteSetupResult:
    """Result of Execute plugin setup operation."""

    success: bool
    plugin_enabled: bool  # True if plugin was enabled during setup
    command_added: bool  # True if command was added during setup
    existing_command: bool  # True if hook already existed
    error: Optional[str] = None
    requires_restart: bool = True  # Execute plugin changes require restart


class DelugeExecuteSetup:
    """Configure Deluge Execute plugin to call JackMediaMan on torrent completion.

    Uses deluge-client for synchronous RPC communication.
    """

    HOOK_SCRIPT_PATH = Path.home() / ".jackmediaman" / "deluge-hook.sh"
    COMMAND_EVENT = "complete"  # Deluge event name for torrent completion

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        action: str = "symlink",
    ):
        """Initialize Deluge Execute setup.

        Args:
            host: Deluge daemon host
            port: Deluge daemon port
            username: Deluge username
            password: Deluge password
            action: Default action mode for jmm process (symlink, move, etc.)
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.action = action

    def create_hook_script(self) -> Path:
        """Create the wrapper script that Deluge will execute.

        Returns:
            Path to the created script
        """
        self.HOOK_SCRIPT_PATH.parent.mkdir(parents=True, exist_ok=True)

        script_content = f'''#!/bin/bash
# JackMediaMan Deluge hook script - Auto-generated
# Execute plugin passes: torrent_id, torrent_name, torrent_path

TORRENT_ID="$1"
TORRENT_NAME="$2"
TORRENT_PATH="$3"

LOG_FILE="$HOME/.jackmediaman/deluge-hook.log"
echo "$(date): Processing $TORRENT_NAME at $TORRENT_PATH" >> "$LOG_FILE"

FULL_PATH="$TORRENT_PATH/$TORRENT_NAME"
if [ -e "$FULL_PATH" ]; then
    jmm process run "$FULL_PATH" --action {self.action} 2>&1 >> "$LOG_FILE"
else
    echo "$(date): Path not found: $FULL_PATH" >> "$LOG_FILE"
fi
'''
        self.HOOK_SCRIPT_PATH.write_text(script_content)
        self.HOOK_SCRIPT_PATH.chmod(0o755)  # Make executable
        return self.HOOK_SCRIPT_PATH

    def setup_execute_plugin(self) -> ExecuteSetupResult:
        """Configure Execute plugin via deluge-client.

        Returns:
            ExecuteSetupResult with status of the operation
        """
        try:
            from jackmediaman.services.deluge_client import create_deluge_client

            client = create_deluge_client(
                self.host, self.port, self.username, self.password
            )
            client.connect()

            result = ExecuteSetupResult(
                success=False,
                plugin_enabled=False,
                command_added=False,
                existing_command=False,
            )

            # Step 1: Check/enable Execute plugin
            plugins = client.call("core.get_enabled_plugins")
            plugin_names = [
                p.decode() if isinstance(p, bytes) else p for p in plugins
            ]

            if "Execute" not in plugin_names:
                client.call("core.enable_plugin", "Execute")
                result.plugin_enabled = True

            # Step 2: Get existing commands
            # Commands are returned as tuple of tuples: ((id, event, path), ...)
            commands = client.call("execute.get_commands")

            # Check if our hook already exists
            script_path = str(self.HOOK_SCRIPT_PATH)
            for cmd in commands:
                # Each cmd is (command_id, event, command_path)
                if len(cmd) >= 3:
                    cmd_path = cmd[2]
                    if isinstance(cmd_path, bytes):
                        cmd_path = cmd_path.decode()
                    if cmd_path == script_path:
                        result.existing_command = True
                        result.success = True
                        client.disconnect()
                        return result

            # Step 3: Add our command
            client.call("execute.add_command", self.COMMAND_EVENT, script_path)
            result.command_added = True
            result.success = True

            client.disconnect()
            return result

        except ImportError as e:
            return ExecuteSetupResult(
                success=False,
                plugin_enabled=False,
                command_added=False,
                existing_command=False,
                error=f"deluge-client not installed: {e}",
            )
        except Exception as e:
            return ExecuteSetupResult(
                success=False,
                plugin_enabled=False,
                command_added=False,
                existing_command=False,
                error=str(e),
            )

    def remove_hook(self) -> ExecuteSetupResult:
        """Remove the JackMediaMan hook from Deluge Execute plugin.

        Returns:
            ExecuteSetupResult with status of the operation
        """
        try:
            from jackmediaman.services.deluge_client import create_deluge_client

            client = create_deluge_client(
                self.host, self.port, self.username, self.password
            )
            client.connect()

            # Get existing commands
            # Commands are returned as tuple of tuples: ((id, event, path), ...)
            commands = client.call("execute.get_commands")

            # Find and remove our hook
            script_path = str(self.HOOK_SCRIPT_PATH)
            for cmd in commands:
                # Each cmd is (command_id, event, command_path)
                if len(cmd) >= 3:
                    cmd_id = cmd[0]
                    cmd_path = cmd[2]
                    if isinstance(cmd_path, bytes):
                        cmd_path = cmd_path.decode()
                    if cmd_path == script_path:
                        # Decode cmd_id if bytes
                        if isinstance(cmd_id, bytes):
                            cmd_id = cmd_id.decode()
                        client.call("execute.remove_command", cmd_id)
                        client.disconnect()
                        return ExecuteSetupResult(
                            success=True,
                            plugin_enabled=False,
                            command_added=False,
                            existing_command=False,
                        )

            # Hook not found
            client.disconnect()
            return ExecuteSetupResult(
                success=False,
                plugin_enabled=False,
                command_added=False,
                existing_command=False,
                error="Hook not found in Deluge configuration",
            )

        except ImportError as e:
            return ExecuteSetupResult(
                success=False,
                plugin_enabled=False,
                command_added=False,
                existing_command=False,
                error=f"deluge-client not installed: {e}",
            )
        except Exception as e:
            return ExecuteSetupResult(
                success=False,
                plugin_enabled=False,
                command_added=False,
                existing_command=False,
                error=str(e),
            )
