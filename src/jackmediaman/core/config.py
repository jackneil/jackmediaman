"""Configuration management using TOML config file."""

import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import tomli_w
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Use tomllib (Python 3.11+) or tomli (backport)
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


# =============================================================================
# Config Paths
# =============================================================================

def get_config_dir() -> Path:
    """Get the config directory path (~/.jackmediaman/)."""
    return Path.home() / ".jackmediaman"


def get_config_path() -> Path:
    """Get the config file path (~/.jackmediaman/config.toml)."""
    return get_config_dir() / "config.toml"


def get_old_env_path() -> Path:
    """Get the old .env file path for migration."""
    return Path.home() / ".jackmediaman.env"


# =============================================================================
# TOML Config Loading
# =============================================================================

def _flatten_toml(data: dict, prefix: str = "") -> dict[str, Any]:
    """Flatten nested TOML dict to flat dict with underscore-separated keys.

    Example: {"paths": {"tv_dir": "~/tv"}} -> {"paths_tv_dir": "~/tv"}
    """
    result = {}
    for key, value in data.items():
        full_key = f"{prefix}_{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_toml(value, full_key))
        else:
            result.update({full_key: value})
    return result


def _load_toml_config() -> dict[str, Any]:
    """Load config from ~/.jackmediaman/config.toml.

    Returns a flattened dict suitable for pydantic-settings.
    """
    config_path = get_config_path()
    if not config_path.exists():
        return {}

    try:
        data = tomllib.loads(config_path.read_text())
        # Flatten and map TOML sections to flat field names
        flat = _flatten_toml(data)

        # Map TOML keys to Settings field names
        key_mapping = {
            # paths section
            "paths_tv_dir": "tv_dir",
            "paths_movies_dir": "movies_dir",
            "paths_trash_dir": "trash_dir",
            "paths_torrent_dir": "torrent_dir",
            # deluge section
            "deluge_host": "deluge_host",
            "deluge_port": "deluge_port",
            "deluge_username": "deluge_username",
            "deluge_password": "deluge_password",
            # tmdb section
            "tmdb_api_key": "tmdb_api_key",
            # opensubtitles section
            "opensubtitles_com_api_key": "opensubtitles_com_api_key",
            "opensubtitles_com_username": "opensubtitles_com_username",
            "opensubtitles_com_password": "opensubtitles_com_password",
            "opensubtitles_org_username": "opensubtitles_org_username",
            "opensubtitles_org_password": "opensubtitles_org_password",
            "opensubtitles_languages": "subtitle_languages",
            "opensubtitles_jwt_token": "opensubtitles_com_jwt_token",
            "opensubtitles_jwt_expires": "opensubtitles_com_jwt_expires",
            # plex section
            "plex_url": "plex_url",
            "plex_token": "plex_api_token",
            "plex_notify_enabled": "plex_notify_enabled",
            # processing section
            "processing_default_action": "process_default_action",
            "processing_cleanup_archives": "process_cleanup_archives",
            "processing_extract_dir": "process_extract_dir",
            # cache section
            "cache_dir": "cache_dir",
            "cache_ttl": "cache_ttl",
            "cache_ffprobe_enabled": "ffprobe_enabled",
            "cache_ffprobe_workers": "ffprobe_workers",
            "cache_ffprobe_timeout": "ffprobe_timeout",
            "cache_ffprobe_path": "ffprobe_path",
            # web section
            "web_port": "web_port",
        }

        result = {}
        for toml_key, value in flat.items():
            field_name = key_mapping.get(toml_key, toml_key)
            result[field_name] = value

        return result
    except Exception:
        return {}


def _migrate_env_to_toml() -> bool:
    """Migrate old ~/.jackmediaman.env to new config.toml format.

    Returns True if migration was performed.
    """
    old_path = get_old_env_path()
    new_path = get_config_path()

    if not old_path.exists() or new_path.exists():
        return False

    # Parse old .env file
    old_values: dict[str, str] = {}
    for line in old_path.read_text().splitlines():
        line = line.strip()
        if line and "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            # Remove JMM_ prefix if present
            key = key.strip()
            if key.startswith("JMM_"):
                key = key[4:]
            old_values[key.lower()] = value.strip()

    # Build TOML structure
    config = _build_toml_config(old_values)

    # Ensure config directory exists
    get_config_dir().mkdir(parents=True, exist_ok=True)

    # Write new config
    _write_toml_config(config)

    # Backup old file
    old_path.rename(old_path.with_suffix(".env.backup"))

    return True


def _build_toml_config(values: dict[str, str]) -> dict[str, Any]:
    """Build a TOML config dict from flat values."""
    # Start with defaults
    config: dict[str, Any] = {
        "paths": {
            "tv_dir": values.get("tv_dir", "~/media/TV Shows"),
            "movies_dir": values.get("movies_dir", "~/media/Movies"),
            "trash_dir": values.get("trash_dir", "~/.jackmediaman/trash"),
            "torrent_dir": values.get("torrent_dir", "~/torrents/completed"),
        },
        "deluge": {
            "host": values.get("deluge_host", "127.0.0.1"),
            "port": int(values.get("deluge_port", "58846")),
            "username": values.get("deluge_username", ""),
            "password": values.get("deluge_password", ""),
        },
        "tmdb": {
            "api_key": values.get("tmdb_api_key", ""),
        },
        "opensubtitles": {
            "com_api_key": values.get("opensubtitles_com_api_key", ""),
            "com_username": values.get("opensubtitles_com_username", ""),
            "com_password": values.get("opensubtitles_com_password", ""),
            "org_username": values.get("opensubtitles_org_username", ""),
            "org_password": values.get("opensubtitles_org_password", ""),
            "languages": values.get("subtitle_languages", "en"),
        },
        "plex": {
            "url": values.get("plex_url", "http://localhost:32400"),
            "token": values.get("plex_api_token", ""),
            "notify_enabled": values.get("plex_notify_enabled", "true").lower() == "true",
        },
        "processing": {
            "default_action": values.get("process_default_action", "symlink"),
            "cleanup_archives": values.get("process_cleanup_archives", "false").lower() == "true",
        },
        "cache": {
            "dir": values.get("cache_dir", "~/.jackmediaman/cache"),
            "ttl": int(values.get("cache_ttl", "86400")),
            "ffprobe_enabled": values.get("ffprobe_enabled", "true").lower() == "true",
            "ffprobe_workers": int(values.get("ffprobe_workers", "4")),
            "ffprobe_timeout": int(values.get("ffprobe_timeout", "30")),
        },
        "web": {
            "port": int(values.get("web_port", "8080")),
        },
    }
    return config


# =============================================================================
# TOML Config Writing (with comments)
# =============================================================================

def _escape_toml_string(value: str) -> str:
    """Escape a string value for TOML format.

    Handles: backslashes, quotes, and removes control characters.
    """
    if not value:
        return ""
    # Remove control characters (0x00-0x1F except tab/newline)
    value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', value)
    # Escape backslashes first, then quotes
    value = value.replace('\\', '\\\\')
    value = value.replace('"', '\\"')
    return value


def _write_toml_config(config: dict[str, Any]) -> None:
    """Write config to TOML file with comments."""
    config_path = get_config_path()
    get_config_dir().mkdir(parents=True, exist_ok=True)

    # Build TOML string with comments
    lines = [
        "# JackMediaMan Configuration",
        f"# {config_path}",
        "",
        "# =============================================================================",
        "# Media Library Paths",
        "# =============================================================================",
        "# These paths should point to your Plex/Jellyfin/Emby library folders.",
        "# Use ~ for home directory (e.g., ~/media expands to /home/user/media)",
        "",
        "[paths]",
        f'tv_dir = "{_escape_toml_string(str(config["paths"]["tv_dir"]))}"',
        f'movies_dir = "{_escape_toml_string(str(config["paths"]["movies_dir"]))}"',
        f'trash_dir = "{_escape_toml_string(str(config["paths"]["trash_dir"]))}"',
        f'torrent_dir = "{_escape_toml_string(str(config["paths"]["torrent_dir"]))}"',
        "",
        "# =============================================================================",
        "# Deluge Daemon Connection",
        "# =============================================================================",
        "# Used for seeding protection - prevents deletion of files still being seeded.",
        "# For localhost: username/password are optional (uses ~/.config/deluge/auth)",
        "# For remote daemon: username and password are required",
        "",
        "[deluge]",
        f'host = "{_escape_toml_string(str(config["deluge"]["host"]))}"',
        f'port = {config["deluge"]["port"]}',
        f'username = "{_escape_toml_string(str(config["deluge"]["username"]))}"',
        f'password = "{_escape_toml_string(str(config["deluge"]["password"]))}"',
        "",
        "# =============================================================================",
        "# TMDb API (The Movie Database)",
        "# =============================================================================",
        "# Used for accurate movie/TV identification and metadata.",
        "# Get a FREE API key at: https://www.themoviedb.org/settings/api",
        "# (Create account -> Settings -> API -> Create -> Developer)",
        "",
        "[tmdb]",
        f'api_key = "{_escape_toml_string(str(config["tmdb"]["api_key"] or ""))}"',
        "",
        "# =============================================================================",
        "# OpenSubtitles",
        "# =============================================================================",
        "# Used for automatic subtitle downloads.",
        "# .com: Get a FREE API key at: https://www.opensubtitles.com/en/consumers",
        "# .org: Requires VIP account (username/password only)",
        "",
        "[opensubtitles]",
        f'com_api_key = "{_escape_toml_string(str(config["opensubtitles"].get("com_api_key") or ""))}"',
        f'com_username = "{_escape_toml_string(str(config["opensubtitles"].get("com_username") or ""))}"',
        f'com_password = "{_escape_toml_string(str(config["opensubtitles"].get("com_password") or ""))}"',
        f'org_username = "{_escape_toml_string(str(config["opensubtitles"].get("org_username") or ""))}"',
        f'org_password = "{_escape_toml_string(str(config["opensubtitles"].get("org_password") or ""))}"',
        f'languages = "{_escape_toml_string(str(config["opensubtitles"].get("languages") or "en"))}"',
        "",
        "# =============================================================================",
        "# Plex Integration",
        "# =============================================================================",
        "# Notifies Plex when media is added/changed for instant library updates.",
        "# Token can be auto-discovered from Plex - run: jmm setup plex",
        "# Or get manually: https://support.plex.tv/articles/204059436/",
        "",
        "[plex]",
        f'url = "{_escape_toml_string(str(config["plex"]["url"]))}"',
        f'token = "{_escape_toml_string(str(config["plex"]["token"]))}"',
        f'notify_enabled = {str(config["plex"]["notify_enabled"]).lower()}',
        "",
        "# =============================================================================",
        "# Processing Options",
        "# =============================================================================",
        "# Controls how files are handled when processing torrents",
        "# default_action: move, copy, hardlink, symlink, keeplink",
        "# - symlink: Creates symlink in library, original stays for seeding (recommended)",
        "# - keeplink: Moves to library, leaves symlink at original location",
        "",
        "[processing]",
        f'default_action = "{_escape_toml_string(str(config["processing"]["default_action"]))}"',
        f'cleanup_archives = {str(config["processing"]["cleanup_archives"]).lower()}',
        "",
        "# =============================================================================",
        "# Cache & Performance",
        "# =============================================================================",
        "",
        "[cache]",
        f'dir = "{_escape_toml_string(str(config["cache"]["dir"]))}"',
        f'ttl = {config["cache"]["ttl"]}',
        f'ffprobe_enabled = {str(config["cache"]["ffprobe_enabled"]).lower()}',
        f'ffprobe_workers = {config["cache"]["ffprobe_workers"]}',
        f'ffprobe_timeout = {config["cache"]["ffprobe_timeout"]}',
        "",
        "# =============================================================================",
        "# Web UI",
        "# =============================================================================",
        "# Optional web interface - start with: jmm --web",
        "",
        "[web]",
        f'port = {config["web"]["port"]}',
        "",
    ]

    config_path.write_text("\n".join(lines))


# =============================================================================
# Settings Class
# =============================================================================

class Settings(BaseSettings):
    """Application settings loaded from TOML config and environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="JMM_",  # Env vars still override config file
        extra="ignore",
    )

    # Media library paths
    tv_dir: Path = Field(
        default=Path.home() / "media" / "TV Shows",
        description="Path to TV Shows library",
    )
    movies_dir: Path = Field(
        default=Path.home() / "media" / "Movies",
        description="Path to Movies library",
    )
    trash_dir: Path = Field(
        default=Path.home() / ".jackmediaman" / "trash",
        description="Path to trash directory for removed duplicates",
    )

    # Torrent settings
    torrent_dir: Path = Field(
        default=Path.home() / "torrents" / "completed",
        description="Path to completed torrents directory",
    )

    # Deluge daemon settings
    deluge_host: str = Field(default="127.0.0.1", description="Deluge daemon host")
    deluge_port: int = Field(default=58846, description="Deluge daemon port")
    deluge_username: str = Field(default="", description="Deluge daemon username")
    deluge_password: str = Field(default="", description="Deluge daemon password")

    # TMDb API settings
    tmdb_api_key: Optional[str] = Field(default=None, description="TMDb API key")

    # OpenSubtitles settings
    # .com provider (API key required, username/password optional for downloads)
    opensubtitles_com_api_key: Optional[str] = Field(
        default=None, description="OpenSubtitles.com API key"
    )
    opensubtitles_com_username: Optional[str] = Field(
        default=None, description="OpenSubtitles.com username (optional, enables downloads)"
    )
    opensubtitles_com_password: Optional[str] = Field(
        default=None, description="OpenSubtitles.com password (optional, enables downloads)"
    )
    opensubtitles_com_jwt_token: Optional[str] = Field(
        default=None, description="Cached JWT token for OpenSubtitles.com (auto-managed)"
    )
    opensubtitles_com_jwt_expires: Optional[int] = Field(
        default=None, description="JWT token expiration timestamp (auto-managed)"
    )
    # .org provider (username/password)
    opensubtitles_org_username: Optional[str] = Field(
        default=None, description="OpenSubtitles.org username"
    )
    opensubtitles_org_password: Optional[str] = Field(
        default=None, description="OpenSubtitles.org password"
    )
    subtitle_languages: str = Field(
        default="en",
        description="Comma-separated list of preferred subtitle languages (e.g., 'en,es,fr')",
    )

    # Cache settings
    cache_dir: Path = Field(
        default=Path.home() / ".jackmediaman" / "cache",
        description="Path to cache directory",
    )
    cache_ttl: int = Field(
        default=86400, description="Cache TTL in seconds (default 24 hours)"
    )

    # FFprobe settings for metadata extraction
    ffprobe_enabled: bool = Field(
        default=True,
        description="Enable ffprobe-based metadata extraction for accurate quality detection",
    )
    ffprobe_workers: int = Field(
        default=4,
        ge=1,
        le=16,
        description="Number of parallel ffprobe workers for batch operations",
    )
    ffprobe_timeout: float = Field(
        default=30.0,
        ge=1.0,
        le=120.0,
        description="Timeout in seconds for each ffprobe operation",
    )
    ffprobe_path: Optional[Path] = Field(
        default=None,
        description="Path to ffprobe executable (auto-detected if not set)",
    )

    # Process command settings
    process_default_action: str = Field(
        default="symlink",
        description="Default action mode for process command (move, copy, hardlink, symlink, keeplink)",
    )
    process_extract_dir: Optional[Path] = Field(
        default=None,
        description="Directory for archive extraction (uses temp if not set)",
    )
    process_cleanup_archives: bool = Field(
        default=False,
        description="Delete archives after successful extraction",
    )

    # Plex settings
    plex_url: Optional[str] = Field(
        default=None,
        description="Plex server URL (e.g., http://localhost:32400)",
    )
    plex_api_token: Optional[str] = Field(
        default=None,
        description="Plex API authentication token",
    )
    plex_notify_enabled: bool = Field(
        default=True,
        description="Enable Plex library notifications when files change",
    )

    # Web UI settings
    web_port: int = Field(
        default=8080,
        ge=1024,
        le=65535,
        description="Default port for web UI (jmm --web)",
    )

    @field_validator(
        "tv_dir",
        "movies_dir",
        "trash_dir",
        "torrent_dir",
        "cache_dir",
        "process_extract_dir",
        "ffprobe_path",
        mode="before",
    )
    @classmethod
    def expand_path(cls, v):
        """Expand ~ to home directory in path settings."""
        if v is None:
            return v
        if isinstance(v, str):
            return Path(v).expanduser()
        if isinstance(v, Path):
            return v.expanduser()
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.

    Priority (highest to lowest):
    1. Environment variables (JMM_* prefix)
    2. TOML config file (~/.jackmediaman/config.toml)
    3. Default values
    """
    # Check for and perform migration from old .env format
    if _migrate_env_to_toml():
        from rich.console import Console
        console = Console()
        console.print(
            "[yellow]Migrated configuration from ~/.jackmediaman.env to "
            "~/.jackmediaman/config.toml[/]"
        )

    # Load TOML config
    toml_values = _load_toml_config()

    # Create settings with TOML values as defaults (env vars still override)
    return Settings(**toml_values)


def reload_settings() -> Settings:
    """Clear cached settings and reload from config file."""
    get_settings.cache_clear()
    return get_settings()


def save_setting(key: str, value: Any) -> None:
    """Save a single setting to config.toml.

    Args:
        key: The setting key (e.g., "tmdb_api_key" or "JMM_TMDB_API_KEY")
        value: The value to save
    """
    # Normalize key (remove JMM_ prefix if present)
    if key.startswith("JMM_"):
        key = key[4:].lower()
    else:
        key = key.lower()

    # Load existing config or create new
    config_path = get_config_path()
    if config_path.exists():
        config = tomllib.loads(config_path.read_text())
    else:
        config = _build_toml_config({})

    # Map key to TOML section
    key_to_section = {
        "tv_dir": ("paths", "tv_dir"),
        "movies_dir": ("paths", "movies_dir"),
        "trash_dir": ("paths", "trash_dir"),
        "torrent_dir": ("paths", "torrent_dir"),
        "deluge_host": ("deluge", "host"),
        "deluge_port": ("deluge", "port"),
        "deluge_username": ("deluge", "username"),
        "deluge_password": ("deluge", "password"),
        "tmdb_api_key": ("tmdb", "api_key"),
        "opensubtitles_com_api_key": ("opensubtitles", "com_api_key"),
        "opensubtitles_com_username": ("opensubtitles", "com_username"),
        "opensubtitles_com_password": ("opensubtitles", "com_password"),
        "opensubtitles_org_username": ("opensubtitles", "org_username"),
        "opensubtitles_org_password": ("opensubtitles", "org_password"),
        "subtitle_languages": ("opensubtitles", "languages"),
        "plex_url": ("plex", "url"),
        "plex_api_token": ("plex", "token"),
        "plex_notify_enabled": ("plex", "notify_enabled"),
        "process_default_action": ("processing", "default_action"),
        "process_cleanup_archives": ("processing", "cleanup_archives"),
        "cache_dir": ("cache", "dir"),
        "cache_ttl": ("cache", "ttl"),
        "ffprobe_enabled": ("cache", "ffprobe_enabled"),
        "ffprobe_workers": ("cache", "ffprobe_workers"),
        "ffprobe_timeout": ("cache", "ffprobe_timeout"),
        "ffprobe_path": ("cache", "ffprobe_path"),
        "web_port": ("web", "port"),
    }

    if key in key_to_section:
        section, toml_key = key_to_section[key]
        if section not in config:
            config[section] = {}
        config[section][toml_key] = value

    # Write back
    _write_toml_config(config)

    # Clear cache so next get_settings() picks up changes
    get_settings.cache_clear()
