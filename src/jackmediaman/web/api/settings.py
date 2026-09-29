"""Settings API endpoints."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class SettingValue(BaseModel):
    """A single setting value."""

    key: str
    value: Any
    type: str  # 'string', 'path', 'boolean', 'integer'
    description: Optional[str] = None


class SettingsGroup(BaseModel):
    """A group of related settings."""

    name: str
    description: str
    settings: list[SettingValue]


class SettingsUpdateRequest(BaseModel):
    """Request to update settings."""

    settings: dict[str, Any]


class SettingsResponse(BaseModel):
    """Response containing all settings."""

    groups: list[SettingsGroup]


# Define settings groups and their metadata
SETTINGS_METADATA = {
    "paths": {
        "name": "Media Paths",
        "description": "Directories for media library",
        "settings": {
            "tv_dir": {"type": "path", "description": "TV shows directory"},
            "movies_dir": {"type": "path", "description": "Movies directory"},
            "trash_dir": {"type": "path", "description": "Trash directory for deleted files"},
            "torrent_dir": {"type": "path", "description": "Torrent download directory"},
        },
    },
    "tmdb": {
        "name": "TMDb",
        "description": "The Movie Database API settings",
        "settings": {
            "tmdb_api_key": {"type": "string", "description": "TMDb API key"},
        },
    },
    "deluge": {
        "name": "Deluge",
        "description": "Deluge daemon connection settings",
        "settings": {
            "deluge_host": {"type": "string", "description": "Deluge daemon host"},
            "deluge_port": {"type": "integer", "description": "Deluge daemon port"},
            "deluge_username": {"type": "string", "description": "Deluge username"},
            "deluge_password": {"type": "string", "description": "Deluge password"},
        },
    },
    "opensubtitles": {
        "name": "OpenSubtitles",
        "description": "OpenSubtitles API settings",
        "settings": {
            "opensubtitles_com_api_key": {"type": "string", "description": ".com API key"},
            "opensubtitles_org_username": {"type": "string", "description": ".org username"},
            "opensubtitles_org_password": {"type": "string", "description": ".org password"},
            "subtitle_languages": {"type": "string", "description": "Preferred subtitle languages (comma-separated)"},
        },
    },
    "processing": {
        "name": "Processing",
        "description": "Media processing options",
        "settings": {
            "ffprobe_enabled": {"type": "boolean", "description": "Enable FFprobe for quality detection"},
        },
    },
}


def get_current_settings() -> dict:
    """Get current settings values."""
    from jackmediaman.core.config import get_settings

    settings = get_settings()
    return {
        "tv_dir": str(settings.tv_dir),
        "movies_dir": str(settings.movies_dir),
        "trash_dir": str(settings.trash_dir),
        "torrent_dir": str(settings.torrent_dir),
        "tmdb_api_key": settings.tmdb_api_key or "",
        "deluge_host": settings.deluge_host,
        "deluge_port": settings.deluge_port,
        "deluge_username": settings.deluge_username or "",
        "deluge_password": "********" if settings.deluge_password else "",
        "opensubtitles_com_api_key": settings.opensubtitles_com_api_key or "",
        "opensubtitles_org_username": settings.opensubtitles_org_username or "",
        "opensubtitles_org_password": "********" if settings.opensubtitles_org_password else "",
        "subtitle_languages": settings.subtitle_languages,
        "ffprobe_enabled": settings.ffprobe_enabled,
    }


@router.get("/", response_model=SettingsResponse)
async def get_all_settings():
    """Get all settings grouped by category."""
    current_values = get_current_settings()
    groups = []

    for group_key, group_meta in SETTINGS_METADATA.items():
        settings_list = []
        for setting_key, setting_meta in group_meta["settings"].items():
            value = current_values.get(setting_key, "")
            settings_list.append(SettingValue(
                key=setting_key,
                value=value,
                type=setting_meta["type"],
                description=setting_meta.get("description"),
            ))

        groups.append(SettingsGroup(
            name=group_meta["name"],
            description=group_meta["description"],
            settings=settings_list,
        ))

    return SettingsResponse(groups=groups)


@router.get("/{group}", response_model=SettingsGroup)
async def get_settings_group(group: str):
    """Get settings for a specific group."""
    if group not in SETTINGS_METADATA:
        raise HTTPException(status_code=404, detail=f"Settings group '{group}' not found")

    current_values = get_current_settings()
    group_meta = SETTINGS_METADATA[group]

    settings_list = []
    for setting_key, setting_meta in group_meta["settings"].items():
        value = current_values.get(setting_key, "")
        settings_list.append(SettingValue(
            key=setting_key,
            value=value,
            type=setting_meta["type"],
            description=setting_meta.get("description"),
        ))

    return SettingsGroup(
        name=group_meta["name"],
        description=group_meta["description"],
        settings=settings_list,
    )


@router.put("/")
async def update_settings(request: SettingsUpdateRequest):
    """Update multiple settings at once."""
    from jackmediaman.core.settings_manager import SettingsManager

    manager = SettingsManager()
    updated = []

    for key, value in request.settings.items():
        # Skip password if it's masked
        if key == "deluge_password" and value == "********":
            continue

        try:
            manager.update_setting(key, str(value))
            updated.append(key)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to update '{key}': {str(e)}"
            )

    return {"status": "ok", "updated": updated}


@router.post("/test/{service}")
async def test_service_connection(service: str):
    """Test connection to a service."""
    # Reuse the status endpoint logic
    from .status import test_service
    return await test_service(service)
