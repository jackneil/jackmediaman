"""Settings manager for unified configuration editing."""

from pathlib import Path
from typing import Any, Optional

from .config import (
    Settings,
    get_settings,
    reload_settings,
    get_config_path,
    save_setting,
    _build_toml_config,
    _write_toml_config,
)


# Settings groups for organized display
SETTINGS_GROUPS = [
    {
        "name": "paths",
        "label": "Paths",
        "icon": "📁",
        "fields": [
            {"key": "tv_dir", "label": "TV Directory", "type": "path"},
            {"key": "movies_dir", "label": "Movies Directory", "type": "path"},
            {"key": "trash_dir", "label": "Trash Directory", "type": "path"},
            {"key": "torrent_dir", "label": "Torrent Directory", "type": "path"},
        ],
    },
    {
        "name": "deluge",
        "label": "Deluge",
        "icon": "↓",
        "fields": [
            {"key": "deluge_host", "label": "Host", "type": "text"},
            {"key": "deluge_port", "label": "Port", "type": "integer", "min": 1024, "max": 65535},
            {"key": "deluge_username", "label": "Username", "type": "text"},
            {"key": "deluge_password", "label": "Password", "type": "password"},
        ],
    },
    {
        "name": "tmdb",
        "label": "TMDb",
        "icon": "🎬",
        "fields": [
            {"key": "tmdb_api_key", "label": "API Key", "type": "password"},
        ],
    },
    {
        "name": "opensubtitles",
        "label": "OpenSubtitles",
        "icon": "☰",
        "fields": [
            {"key": "opensubtitles_com_api_key", "label": ".com API Key", "type": "password"},
            {"key": "opensubtitles_org_username", "label": ".org Username", "type": "text"},
            {"key": "opensubtitles_org_password", "label": ".org Password", "type": "password"},
            {"key": "subtitle_languages", "label": "Languages", "type": "text"},
        ],
    },
    {
        "name": "plex",
        "label": "Plex",
        "icon": "▣",
        "fields": [
            {"key": "plex_url", "label": "Server URL", "type": "text"},
            {"key": "plex_api_token", "label": "API Token", "type": "password"},
            {"key": "plex_notify_enabled", "label": "Enable Notifications", "type": "boolean"},
        ],
    },
    {
        "name": "processing",
        "label": "Processing",
        "icon": "⚙",
        "fields": [
            {
                "key": "process_default_action",
                "label": "Default Action",
                "type": "select",
                "choices": ["move", "copy", "hardlink", "symlink", "keeplink"],
            },
            {"key": "process_extract_dir", "label": "Extract Directory", "type": "path"},
            {"key": "process_cleanup_archives", "label": "Cleanup Archives", "type": "boolean"},
        ],
    },
    {
        "name": "performance",
        "label": "Performance",
        "icon": "◎",
        "fields": [
            {"key": "ffprobe_enabled", "label": "Enable FFprobe", "type": "boolean"},
            {"key": "ffprobe_workers", "label": "FFprobe Workers", "type": "integer", "min": 1, "max": 16},
            {"key": "ffprobe_timeout", "label": "FFprobe Timeout (s)", "type": "float", "min": 1, "max": 120},
            {"key": "cache_dir", "label": "Cache Directory", "type": "path"},
            {"key": "cache_ttl", "label": "Cache TTL (s)", "type": "integer", "min": 0},
        ],
    },
    {
        "name": "web",
        "label": "Web UI",
        "icon": "🌐",
        "fields": [
            {"key": "web_port", "label": "Port", "type": "integer", "min": 1024, "max": 65535},
        ],
    },
]


class SettingsManager:
    """Manages settings I/O and validation for the unified settings editor."""

    def __init__(self) -> None:
        """Initialize the settings manager."""
        self._config_file = get_config_path()

    def load_all_settings(self) -> dict[str, Any]:
        """Load all current settings from the Settings instance.

        Returns:
            Dictionary mapping setting keys to their current values.
        """
        settings = get_settings()
        result = {}

        for group in SETTINGS_GROUPS:
            for field in group["fields"]:
                key = field["key"]
                value = getattr(settings, key, None)
                # Convert Path to string for display
                if isinstance(value, Path):
                    value = str(value)
                result[key] = value

        return result

    def save_all_settings(self, settings_dict: dict[str, Any]) -> None:
        """Save all settings to ~/.jackmediaman/config.toml.

        Args:
            settings_dict: Dictionary mapping setting keys to their new values.
        """
        # Get current settings
        settings = get_settings()

        # Build merged values dict - start with current settings
        merged = {}
        for group in SETTINGS_GROUPS:
            for field in group["fields"]:
                key = field["key"]
                # Get current value
                current = getattr(settings, key, None)
                if isinstance(current, Path):
                    current = str(current)
                merged[key] = current

        # Override with new values
        for key, value in settings_dict.items():
            # Convert empty strings to None for optional fields
            if value == "":
                value = None
            merged[key] = value

        # Build TOML config structure and write once
        config = _build_toml_config(merged)
        _write_toml_config(config)

        # Reload settings cache
        reload_settings()

    def validate_field(self, key: str, value: Any) -> list[str]:
        """Validate a single field and return warnings.

        Args:
            key: The setting key.
            value: The value to validate.

        Returns:
            List of warning messages (empty if valid).
        """
        warnings = []

        # Get field definition
        field_def = self._get_field_def(key)
        if not field_def:
            return warnings

        field_type = field_def.get("type")

        # Path validation
        if field_type == "path" and value:
            try:
                path = Path(value).expanduser()
                if not path.parent.exists():
                    warnings.append(f"Parent directory doesn't exist: {path.parent}")
            except Exception as e:
                warnings.append(f"Invalid path: {e}")

        # Integer validation
        if field_type == "integer" and value is not None:
            try:
                int_val = int(value)
                min_val = field_def.get("min")
                max_val = field_def.get("max")
                if min_val is not None and int_val < min_val:
                    warnings.append(f"Value should be at least {min_val}")
                if max_val is not None and int_val > max_val:
                    warnings.append(f"Value should be at most {max_val}")
            except ValueError:
                warnings.append("Value must be an integer")

        # Float validation
        if field_type == "float" and value is not None:
            try:
                float_val = float(value)
                min_val = field_def.get("min")
                max_val = field_def.get("max")
                if min_val is not None and float_val < min_val:
                    warnings.append(f"Value should be at least {min_val}")
                if max_val is not None and float_val > max_val:
                    warnings.append(f"Value should be at most {max_val}")
            except ValueError:
                warnings.append("Value must be a number")

        return warnings

    def validate_all(self, settings_dict: dict[str, Any]) -> dict[str, list[str]]:
        """Validate all settings and return warnings per field.

        Args:
            settings_dict: Dictionary of all settings.

        Returns:
            Dictionary mapping field keys to their warnings.
        """
        all_warnings = {}
        for key, value in settings_dict.items():
            warnings = self.validate_field(key, value)
            if warnings:
                all_warnings[key] = warnings
        return all_warnings

    def _get_field_def(self, key: str) -> Optional[dict]:
        """Get field definition by key."""
        for group in SETTINGS_GROUPS:
            for field in group["fields"]:
                if field["key"] == key:
                    return field
        return None

    def get_groups(self) -> list[dict]:
        """Get all settings groups for display."""
        return SETTINGS_GROUPS
