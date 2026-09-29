"""Central command registry defining all commands, subcommands, and options."""

from typing import Optional

from .definitions import (
    ArgumentDef,
    CommandDef,
    OptionDef,
    OptionType,
    SubcommandDef,
)


# =============================================================================
# DUPLICATES COMMAND
# =============================================================================

DUPLICATES_SCAN = SubcommandDef(
    name="scan",
    description="Scan library for duplicate files",
    icon="⊕",
    category="read-only",
    options=[
        OptionDef(
            name="type",
            cli_flag="--type",
            short_name="-t",
            option_type=OptionType.ENUM,
            description="Type of media to scan",
            default="both",
            choices=["tv", "movies", "both"],
            icon="▤",
        ),
        OptionDef(
            name="matcher",
            cli_flag="--matcher",
            short_name="-m",
            option_type=OptionType.ENUM,
            description="Movie matching strategy",
            default="title_year",
            choices=["title_year", "fuzzy", "tmdb"],
            icon="◎",
        ),
        OptionDef(
            name="protector",
            cli_flag="--protector",
            short_name="-p",
            option_type=OptionType.ENUM,
            description="Seeding protection method",
            default="symlink",
            choices=["symlink", "deluge", "both", "none"],
            icon="◉",
        ),
        OptionDef(
            name="editions_as_dupes",
            cli_flag="--editions-as-dupes/--editions-separate",
            option_type=OptionType.BOOLEAN,
            description="Treat different editions as duplicates",
            default=True,
            icon="▣",
        ),
    ],
)

DUPLICATES_CLEAN = SubcommandDef(
    name="clean",
    description="Remove lower-quality duplicates",
    icon="⊘",
    category="destructive",
    confirm_required=True,
    options=[
        OptionDef(
            name="type",
            cli_flag="--type",
            short_name="-t",
            option_type=OptionType.ENUM,
            description="Type of media to clean",
            default="both",
            choices=["tv", "movies", "both"],
            icon="▤",
        ),
        OptionDef(
            name="matcher",
            cli_flag="--matcher",
            short_name="-m",
            option_type=OptionType.ENUM,
            description="Movie matching strategy",
            default="title_year",
            choices=["title_year", "fuzzy", "tmdb"],
            icon="◎",
        ),
        OptionDef(
            name="protector",
            cli_flag="--protector",
            short_name="-p",
            option_type=OptionType.ENUM,
            description="Seeding protection method",
            default="symlink",
            choices=["symlink", "deluge", "both", "none"],
            icon="◉",
        ),
        OptionDef(
            name="editions_as_dupes",
            cli_flag="--editions-as-dupes/--editions-separate",
            option_type=OptionType.BOOLEAN,
            description="Treat different editions as duplicates",
            default=True,
            icon="▣",
        ),
        OptionDef(
            name="dry_run",
            cli_flag="--dry-run/--execute",
            option_type=OptionType.BOOLEAN,
            description="Preview changes without executing",
            default=True,
            icon="◌",
        ),
        OptionDef(
            name="interactive",
            cli_flag="--interactive/--auto",
            option_type=OptionType.BOOLEAN,
            description="Confirm each group individually",
            default=True,
            icon="☰",
        ),
        OptionDef(
            name="rename",
            cli_flag="--rename/--no-rename",
            option_type=OptionType.BOOLEAN,
            description="Also rename kept files to standard format",
            default=False,
            icon="✎",
        ),
    ],
)

DUPLICATES_CMD = CommandDef(
    name="duplicates",
    description="Find and manage duplicate media files",
    icon="◈",
    order=1,
    subcommands={
        "scan": DUPLICATES_SCAN,
        "clean": DUPLICATES_CLEAN,
    },
)


# =============================================================================
# PROCESS COMMAND
# =============================================================================

PROCESS_RUN = SubcommandDef(
    name="run",
    description="Process a completed torrent download",
    icon="▶",
    category="action",
    arguments=[
        ArgumentDef(
            name="path",
            arg_type=OptionType.PATH,
            description="Path to completed torrent (file or directory)",
            required=True,
            must_exist=True,
            placeholder="/path/to/torrent",
            icon="▢",
        ),
    ],
    options=[
        OptionDef(
            name="action",
            cli_flag="--action",
            short_name="-a",
            option_type=OptionType.ENUM,
            description="How to handle files",
            default="symlink",
            choices=["move", "copy", "hardlink", "symlink", "keeplink"],
            icon="◎",
        ),
        OptionDef(
            name="dry_run",
            cli_flag="--dry-run",
            short_name="-n",
            option_type=OptionType.BOOLEAN,
            description="Preview changes without executing",
            default=False,
            icon="◌",
        ),
        OptionDef(
            name="no_extract",
            cli_flag="--no-extract",
            option_type=OptionType.BOOLEAN,
            description="Skip archive extraction",
            default=False,
            icon="⊘",
        ),
        OptionDef(
            name="no_tmdb",
            cli_flag="--no-tmdb",
            option_type=OptionType.BOOLEAN,
            description="Skip TMDb lookup for metadata",
            default=False,
            icon="⊘",
        ),
        OptionDef(
            name="no_subtitles",
            cli_flag="--no-subtitles",
            option_type=OptionType.BOOLEAN,
            description="Skip automatic subtitle download",
            default=False,
            icon="⊘",
        ),
        OptionDef(
            name="no_artwork",
            cli_flag="--no-artwork",
            option_type=OptionType.BOOLEAN,
            description="Skip automatic artwork download",
            default=False,
            icon="⊘",
        ),
        OptionDef(
            name="no_plex",
            cli_flag="--no-plex",
            option_type=OptionType.BOOLEAN,
            description="Skip Plex library notification",
            default=False,
            icon="⊘",
        ),
    ],
)

PROCESS_CMD = CommandDef(
    name="process",
    description="Process completed torrent downloads",
    icon="▸",
    order=2,
    subcommands={
        "run": PROCESS_RUN,
    },
)


# =============================================================================
# RENAME COMMAND
# =============================================================================

RENAME_PREVIEW = SubcommandDef(
    name="preview",
    description="Preview file renames without changes",
    icon="◎",
    category="read-only",
    options=[
        OptionDef(
            name="type",
            cli_flag="--type",
            short_name="-t",
            option_type=OptionType.ENUM,
            description="Type of media to rename",
            default="both",
            choices=["tv", "movies", "both"],
            icon="▤",
        ),
    ],
)

RENAME_EXECUTE = SubcommandDef(
    name="execute",
    description="Execute file renames",
    icon="▶",
    category="action",
    confirm_required=True,
    options=[
        OptionDef(
            name="type",
            cli_flag="--type",
            short_name="-t",
            option_type=OptionType.ENUM,
            description="Type of media to rename",
            default="both",
            choices=["tv", "movies", "both"],
            icon="▤",
        ),
        OptionDef(
            name="yes",
            cli_flag="--yes",
            short_name="-y",
            option_type=OptionType.BOOLEAN,
            description="Skip confirmation prompt",
            default=False,
            icon="✓",
        ),
    ],
)

RENAME_CMD = CommandDef(
    name="rename",
    description="Rename media files to standardized format",
    icon="✎",
    order=3,
    subcommands={
        "preview": RENAME_PREVIEW,
        "execute": RENAME_EXECUTE,
    },
)


# =============================================================================
# SUBTITLES COMMAND
# =============================================================================

SUBTITLES_DOWNLOAD = SubcommandDef(
    name="download",
    description="Download subtitles for media files",
    icon="⤓",
    category="action",
    arguments=[
        ArgumentDef(
            name="path",
            arg_type=OptionType.PATH,
            description="File or directory to download subtitles for",
            required=False,
            placeholder="/path/to/media",
            icon="▢",
        ),
    ],
    options=[
        OptionDef(
            name="type",
            cli_flag="--type",
            short_name="-t",
            option_type=OptionType.ENUM,
            description="Media type to process (use instead of path)",
            default=None,
            choices=["tv", "movies", "both"],
            icon="▤",
        ),
        OptionDef(
            name="language",
            cli_flag="--language",
            short_name="-l",
            option_type=OptionType.LIST,
            description="Subtitle languages (comma-separated)",
            default="en",
            icon="☰",
        ),
        OptionDef(
            name="overwrite",
            cli_flag="--overwrite",
            short_name="-o",
            option_type=OptionType.BOOLEAN,
            description="Overwrite existing subtitle files",
            default=False,
            icon="⊘",
        ),
        OptionDef(
            name="dry_run",
            cli_flag="--dry-run",
            short_name="-n",
            option_type=OptionType.BOOLEAN,
            description="Preview without downloading",
            default=False,
            icon="◌",
        ),
    ],
)

SUBTITLES_STATUS = SubcommandDef(
    name="status",
    description="Show OpenSubtitles configuration status",
    icon="◉",
    category="read-only",
)

SUBTITLES_CMD = CommandDef(
    name="subtitles",
    description="Download subtitles for media files",
    icon="☰",
    order=4,
    subcommands={
        "download": SUBTITLES_DOWNLOAD,
        "status": SUBTITLES_STATUS,
    },
)


# =============================================================================
# ARTWORK COMMAND
# =============================================================================

ARTWORK_DOWNLOAD = SubcommandDef(
    name="download",
    description="Download poster artwork from TMDb",
    icon="⤓",
    category="action",
    arguments=[
        ArgumentDef(
            name="path",
            arg_type=OptionType.PATH,
            description="Specific folder to download artwork for",
            required=False,
            placeholder="/path/to/media",
            icon="▢",
        ),
    ],
    options=[
        OptionDef(
            name="type",
            cli_flag="--type",
            short_name="-t",
            option_type=OptionType.ENUM,
            description="Media type to process",
            default=None,
            choices=["tv", "movies", "both"],
            icon="▤",
        ),
        OptionDef(
            name="refresh",
            cli_flag="--refresh",
            short_name="-r",
            option_type=OptionType.BOOLEAN,
            description="Re-download even if poster exists",
            default=False,
            icon="◌",
        ),
        OptionDef(
            name="dry_run",
            cli_flag="--dry-run",
            short_name="-n",
            option_type=OptionType.BOOLEAN,
            description="Preview without downloading",
            default=False,
            icon="◌",
        ),
    ],
)

ARTWORK_STATUS = SubcommandDef(
    name="status",
    description="Show artwork coverage statistics",
    icon="◉",
    category="read-only",
)

ARTWORK_CMD = CommandDef(
    name="artwork",
    description="Download poster artwork from TMDb",
    icon="◐",
    order=5,
    subcommands={
        "download": ARTWORK_DOWNLOAD,
        "status": ARTWORK_STATUS,
    },
)


# =============================================================================
# TORRENTS COMMAND
# =============================================================================

TORRENTS_LIST = SubcommandDef(
    name="list",
    description="List all torrents with their status",
    icon="☰",
    category="read-only",
)

TORRENTS_MOVE = SubcommandDef(
    name="move",
    description="Move completed torrents to completed folder",
    icon="▶",
    category="action",
    options=[
        OptionDef(
            name="dry_run",
            cli_flag="--dry-run/--execute",
            option_type=OptionType.BOOLEAN,
            description="Preview without moving",
            default=True,
            icon="◌",
        ),
    ],
)

TORRENTS_CMD = CommandDef(
    name="torrents",
    description="Manage Deluge torrents",
    icon="↓",
    order=6,
    subcommands={
        "list": TORRENTS_LIST,
        "move": TORRENTS_MOVE,
    },
)


# =============================================================================
# STATUS COMMAND
# =============================================================================

STATUS_CONFIG = SubcommandDef(
    name="config",
    description="Show current configuration and service status",
    icon="⚙",
    category="read-only",
)

STATUS_DELUGE = SubcommandDef(
    name="deluge",
    description="Check Deluge daemon connection",
    icon="↓",
    category="read-only",
)

STATUS_TMDB = SubcommandDef(
    name="tmdb",
    description="Check TMDb API connection",
    icon="▢",
    category="read-only",
)

STATUS_OPENSUBTITLES = SubcommandDef(
    name="opensubtitles",
    description="Check OpenSubtitles API connection",
    icon="☰",
    category="read-only",
)

STATUS_TRASH = SubcommandDef(
    name="trash",
    description="Show contents of trash directory",
    icon="␡",
    category="read-only",
)

STATUS_CMD = CommandDef(
    name="status",
    description="Check status of library and configuration",
    icon="◉",
    order=7,
    subcommands={
        "config": STATUS_CONFIG,
        "deluge": STATUS_DELUGE,
        "tmdb": STATUS_TMDB,
        "opensubtitles": STATUS_OPENSUBTITLES,
        "trash": STATUS_TRASH,
    },
)


# =============================================================================
# SETUP COMMAND
# =============================================================================

SETUP_INIT = SubcommandDef(
    name="init",
    description="Initialize configuration with auto-discovery",
    icon="▶",
    category="action",
    options=[
        OptionDef(
            name="force",
            cli_flag="--force",
            short_name="-f",
            option_type=OptionType.BOOLEAN,
            description="Overwrite existing config",
            default=False,
            icon="⚠",
        ),
        OptionDef(
            name="auto",
            cli_flag="--auto/--no-auto",
            option_type=OptionType.BOOLEAN,
            description="Auto-discover Plex and configure Deluge",
            default=True,
            icon="◎",
        ),
    ],
)

SETUP_PATHS = SubcommandDef(
    name="paths",
    description="Configure media library paths",
    icon="▢",
    category="action",
)

SETUP_TMDB = SubcommandDef(
    name="tmdb",
    description="Configure TMDb API key",
    icon="▢",
    category="action",
)

SETUP_DELUGE = SubcommandDef(
    name="deluge",
    description="Configure Deluge daemon connection",
    icon="↓",
    category="action",
)

SETUP_OPENSUBTITLES = SubcommandDef(
    name="opensubtitles",
    description="Configure OpenSubtitles credentials",
    icon="☰",
    category="action",
)

SETUP_PLEX = SubcommandDef(
    name="plex",
    description="Configure Plex server connection",
    icon="▣",
    category="action",
)

SETUP_PROCESSING = SubcommandDef(
    name="processing",
    description="Configure processing options",
    icon="⚙",
    category="action",
)

SETUP_PERFORMANCE = SubcommandDef(
    name="performance",
    description="Configure performance settings",
    icon="◎",
    category="action",
)

SETUP_SHELL = SubcommandDef(
    name="shell",
    description="Configure shell PATH",
    icon="◉",
    category="action",
    options=[
        OptionDef(
            name="dry_run",
            cli_flag="--dry-run",
            option_type=OptionType.BOOLEAN,
            description="Preview without modifying files",
            default=False,
            icon="◌",
        ),
    ],
)

SETUP_CMD = CommandDef(
    name="setup",
    description="Configure external services",
    icon="⚙",
    order=8,
    subcommands={
        "init": SETUP_INIT,
        "paths": SETUP_PATHS,
        "tmdb": SETUP_TMDB,
        "deluge": SETUP_DELUGE,
        "opensubtitles": SETUP_OPENSUBTITLES,
        "plex": SETUP_PLEX,
        "processing": SETUP_PROCESSING,
        "performance": SETUP_PERFORMANCE,
        "shell": SETUP_SHELL,
    },
)


# =============================================================================
# CACHE COMMAND
# =============================================================================

CACHE_STATS = SubcommandDef(
    name="stats",
    description="Show cache statistics",
    icon="◉",
    category="read-only",
)

CACHE_CLEAR = SubcommandDef(
    name="clear",
    description="Clear cache entries",
    icon="⊘",
    category="destructive",
    confirm_required=True,
    options=[
        OptionDef(
            name="type",
            cli_flag="--type",
            short_name="-t",
            option_type=OptionType.ENUM,
            description="Which cache to clear",
            default="all",
            choices=["all", "metadata", "tmdb"],
            icon="◎",
        ),
        OptionDef(
            name="yes",
            cli_flag="--yes",
            short_name="-y",
            option_type=OptionType.BOOLEAN,
            description="Skip confirmation prompt",
            default=False,
            icon="✓",
        ),
    ],
)

CACHE_CLEANUP = SubcommandDef(
    name="cleanup",
    description="Remove stale cache entries",
    icon="⊘",
    category="action",
)

CACHE_CMD = CommandDef(
    name="cache",
    description="Manage metadata cache",
    icon="◎",
    order=9,
    subcommands={
        "stats": CACHE_STATS,
        "clear": CACHE_CLEAR,
        "cleanup": CACHE_CLEANUP,
    },
)


# =============================================================================
# TRASH COMMAND
# =============================================================================

TRASH_LIST = SubcommandDef(
    name="list",
    description="List contents of trash directory",
    icon="☰",
    category="read-only",
)

TRASH_CLEAR = SubcommandDef(
    name="clear",
    description="Permanently delete files from trash",
    icon="⊘",
    category="destructive",
    confirm_required=True,
    options=[
        OptionDef(
            name="days",
            cli_flag="--days",
            short_name="-d",
            option_type=OptionType.INTEGER,
            description="Only delete files older than N days",
            default=None,
            icon="◌",
        ),
        OptionDef(
            name="yes",
            cli_flag="--yes",
            short_name="-y",
            option_type=OptionType.BOOLEAN,
            description="Skip confirmation prompt",
            default=False,
            icon="✓",
        ),
    ],
)

TRASH_RESTORE = SubcommandDef(
    name="restore",
    description="Restore a file from trash",
    icon="↩",
    category="action",
    arguments=[
        ArgumentDef(
            name="file_number",
            arg_type=OptionType.INTEGER,
            description="File number from 'jmm trash list'",
            required=True,
            placeholder="1",
            icon="◎",
        ),
    ],
)

TRASH_CMD = CommandDef(
    name="trash",
    description="Manage trash directory",
    icon="␡",
    order=10,
    subcommands={
        "list": TRASH_LIST,
        "clear": TRASH_CLEAR,
        "restore": TRASH_RESTORE,
    },
)


# =============================================================================
# COMMAND REGISTRY
# =============================================================================

COMMANDS: dict[str, CommandDef] = {
    "duplicates": DUPLICATES_CMD,
    "process": PROCESS_CMD,
    "rename": RENAME_CMD,
    "subtitles": SUBTITLES_CMD,
    "artwork": ARTWORK_CMD,
    "torrents": TORRENTS_CMD,
    "status": STATUS_CMD,
    "setup": SETUP_CMD,
    "cache": CACHE_CMD,
    "trash": TRASH_CMD,
}


def get_command(name: str) -> Optional[CommandDef]:
    """Get command by name."""
    return COMMANDS.get(name)


def get_subcommand(cmd_name: str, sub_name: str) -> Optional[SubcommandDef]:
    """Get subcommand by command and subcommand name."""
    cmd = COMMANDS.get(cmd_name)
    if cmd:
        return cmd.get_subcommand(sub_name)
    return None


def list_commands() -> list[CommandDef]:
    """List all commands sorted by order."""
    return sorted(COMMANDS.values(), key=lambda c: c.order)
