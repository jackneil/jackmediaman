"""Status and health check API endpoints."""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from jackmediaman import __version__

router = APIRouter()


class ServiceStatus(BaseModel):
    """Status of an external service."""

    name: str
    configured: bool
    status: str  # 'ok', 'error', 'not_configured'
    detail: Optional[str] = None


class PathStatus(BaseModel):
    """Status of a media path."""

    name: str
    path: str
    exists: bool


class DashboardData(BaseModel):
    """Full dashboard data."""

    version: str
    services: list[ServiceStatus]
    paths: list[PathStatus]
    torrents: Optional[dict] = None
    library: Optional[dict] = None


class HealthResponse(BaseModel):
    """Simple health check response."""

    status: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Simple health check endpoint."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/status", response_model=DashboardData)
async def get_status():
    """Get full dashboard status data."""
    from jackmediaman.core.config import get_settings

    settings = get_settings()

    # Check services
    services = []

    # TMDb
    if settings.tmdb_api_key:
        services.append(ServiceStatus(
            name="TMDb",
            configured=True,
            status="ok",
            detail=f"Key: {settings.tmdb_api_key[:8]}...",
        ))
    else:
        services.append(ServiceStatus(
            name="TMDb",
            configured=False,
            status="not_configured",
        ))

    # Deluge
    if settings.deluge_username:
        services.append(ServiceStatus(
            name="Deluge",
            configured=True,
            status="ok",
            detail=f"{settings.deluge_host}:{settings.deluge_port}",
        ))
    else:
        services.append(ServiceStatus(
            name="Deluge",
            configured=False,
            status="not_configured",
        ))

    # OpenSubtitles - check both providers
    com_configured = bool(settings.opensubtitles_com_api_key)
    org_configured = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)

    if com_configured or org_configured:
        parts = []
        if com_configured:
            parts.append(".com")
        if org_configured:
            parts.append(f".org ({settings.opensubtitles_org_username})")
        services.append(ServiceStatus(
            name="OpenSubtitles",
            configured=True,
            status="ok",
            detail=" + ".join(parts),
        ))
    else:
        services.append(ServiceStatus(
            name="OpenSubtitles",
            configured=False,
            status="not_configured",
        ))

    # Check paths
    paths = [
        PathStatus(name="TV Shows", path=str(settings.tv_dir), exists=settings.tv_dir.exists()),
        PathStatus(name="Movies", path=str(settings.movies_dir), exists=settings.movies_dir.exists()),
        PathStatus(name="Trash", path=str(settings.trash_dir), exists=settings.trash_dir.exists()),
        PathStatus(name="Torrents", path=str(settings.torrent_dir), exists=settings.torrent_dir.exists()),
    ]

    return DashboardData(
        version=__version__,
        services=services,
        paths=paths,
    )


@router.get("/services/{service}/test")
async def test_service(service: str):
    """Test connection to a specific service."""
    from jackmediaman.core.config import get_settings

    settings = get_settings()

    if service == "tmdb":
        if not settings.tmdb_api_key:
            return {"service": "tmdb", "status": "error", "message": "Not configured"}

        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.themoviedb.org/3/configuration",
                    params={"api_key": settings.tmdb_api_key},
                    timeout=10.0,
                )
            if response.status_code == 200:
                return {"service": "tmdb", "status": "ok", "message": "API key valid"}
            elif response.status_code == 401:
                return {"service": "tmdb", "status": "error", "message": "Invalid API key"}
            else:
                return {"service": "tmdb", "status": "error", "message": f"HTTP {response.status_code}"}
        except Exception as e:
            return {"service": "tmdb", "status": "error", "message": str(e)}

    elif service == "deluge":
        if not settings.deluge_username:
            return {"service": "deluge", "status": "error", "message": "Not configured"}

        try:
            from jackmediaman.protectors.deluge import DelugeProtector
            protector = DelugeProtector()
            if protector.connect():
                protector.disconnect()
                return {"service": "deluge", "status": "ok", "message": "Connected successfully"}
            else:
                return {"service": "deluge", "status": "error", "message": "Failed to connect"}
        except Exception as e:
            return {"service": "deluge", "status": "error", "message": str(e)}

    elif service == "opensubtitles":
        com_configured = bool(settings.opensubtitles_com_api_key)
        org_configured = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)

        if not com_configured and not org_configured:
            return {"service": "opensubtitles", "status": "error", "message": "Not configured"}

        results = []

        # Test .com if configured
        if com_configured:
            try:
                from jackmediaman.services.subtitles import OpenSubtitlesComClient
                client = OpenSubtitlesComClient(api_key=settings.opensubtitles_com_api_key)
                if client.validate_credentials():
                    results.append(".com: OK")
                else:
                    results.append(".com: invalid")
            except Exception as e:
                results.append(f".com: {str(e)[:20]}")

        # Test .org if configured
        if org_configured:
            try:
                from jackmediaman.services.subtitles import OpenSubtitlesOrgClient
                client = OpenSubtitlesOrgClient(
                    username=settings.opensubtitles_org_username,
                    password=settings.opensubtitles_org_password,
                )
                if client.validate_credentials():
                    results.append(".org: OK")
                else:
                    results.append(".org: login failed")
            except Exception as e:
                results.append(f".org: {str(e)[:20]}")

        return {"service": "opensubtitles", "status": "ok", "message": ", ".join(results)}

    return {"service": service, "status": "error", "message": "Unknown service"}
