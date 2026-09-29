"""Status commands for checking library and configuration."""

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from rich.table import Table

from jackmediaman.core.config import get_settings
from jackmediaman.protectors.deluge import DelugeProtector
from jackmediaman.services.cleaner import CleanupService

app = typer.Typer(help="Check status of library and configuration")
console = Console()


@dataclass
class ServiceStatus:
    """Status of an external service."""

    name: str
    configured: bool
    status_text: str
    detail: Optional[str] = None
    setup_hint: Optional[str] = None
    impact: Optional[str] = None  # What's affected if not configured


def _check_tmdb_status() -> ServiceStatus:
    """Check TMDb API status by testing connection."""
    settings = get_settings()
    impact = "No episode titles, basic matching"

    if not settings.tmdb_api_key:
        return ServiceStatus(
            name="TMDb API",
            configured=False,
            status_text="Not configured",
            setup_hint="jmm setup tmdb",
            impact=impact,
        )

    # Actually test the API
    try:
        import httpx
        response = httpx.get(
            "https://api.themoviedb.org/3/configuration",
            params={"api_key": settings.tmdb_api_key},
            timeout=5.0,
        )
        if response.status_code == 200:
            return ServiceStatus(
                name="TMDb API",
                configured=True,
                status_text="Connected",
                detail=f"Key: {settings.tmdb_api_key}",
                impact=impact,
            )
        elif response.status_code == 401:
            return ServiceStatus(
                name="TMDb API",
                configured=False,
                status_text="Invalid key",
                detail="API key rejected",
                setup_hint="jmm setup tmdb",
                impact=impact,
            )
        else:
            return ServiceStatus(
                name="TMDb API",
                configured=False,
                status_text=f"HTTP {response.status_code}",
                detail="Unexpected response",
                impact=impact,
            )
    except httpx.ConnectError:
        return ServiceStatus(
            name="TMDb API",
            configured=False,
            status_text="Connection failed",
            detail="Cannot reach api.themoviedb.org",
            impact=impact,
        )
    except httpx.TimeoutException:
        return ServiceStatus(
            name="TMDb API",
            configured=False,
            status_text="Timeout",
            detail="API not responding",
            impact=impact,
        )
    except Exception as e:
        return ServiceStatus(
            name="TMDb API",
            configured=False,
            status_text="Error",
            detail=str(e),
            impact=impact,
        )


def _check_deluge_status() -> ServiceStatus:
    """Check Deluge daemon status by attempting connection."""
    settings = get_settings()
    impact = "No seeding protection"

    # Try actual connection (quick test)
    try:
        protector = DelugeProtector()
        if protector.connect():
            protector.disconnect()
            return ServiceStatus(
                name="Deluge Daemon",
                configured=True,
                status_text="Connected",
                detail=f"{settings.deluge_host}:{settings.deluge_port}",
                impact=impact,
            )
    except Exception:
        pass

    # Connection failed - show as not connected
    return ServiceStatus(
        name="Deluge Daemon",
        configured=False,
        status_text="Not connected",
        detail=f"{settings.deluge_host}:{settings.deluge_port}",
        setup_hint="jmm setup deluge",
        impact=impact,
    )


def _check_opensubtitles_status() -> ServiceStatus:
    """Check OpenSubtitles status - checks both .org and .com providers."""
    settings = get_settings()
    impact = "No subtitle downloads"

    com_configured = bool(settings.opensubtitles_com_api_key)
    org_configured = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)

    if not com_configured and not org_configured:
        return ServiceStatus(
            name="OpenSubtitles",
            configured=False,
            status_text="Not configured",
            setup_hint="jmm setup opensubtitles",
            impact=impact,
        )

    # Build status from configured providers
    parts = []
    detail_parts = []

    # Check .com API key
    if com_configured:
        try:
            import httpx
            response = httpx.get(
                "https://api.opensubtitles.com/api/v1/infos/languages",
                headers={
                    "Api-Key": settings.opensubtitles_com_api_key,
                    "User-Agent": "JackMediaMan v0.3.0",
                },
                timeout=5.0,
                follow_redirects=True,
            )
            if response.status_code == 200:
                parts.append(".com")
                detail_parts.append(".com: OK")
            else:
                detail_parts.append(f".com: HTTP {response.status_code}")
        except Exception as e:
            detail_parts.append(f".com: {str(e)[:20]}")

    # For .org, just show configured (XML-RPC validation is slower)
    if org_configured:
        parts.append(".org")
        detail_parts.append(f".org: {settings.opensubtitles_org_username}")

    if parts:
        return ServiceStatus(
            name="OpenSubtitles",
            configured=True,
            status_text=" + ".join(parts),
            detail=", ".join(detail_parts),
            impact=impact,
        )
    else:
        return ServiceStatus(
            name="OpenSubtitles",
            configured=False,
            status_text="Configuration error",
            detail=", ".join(detail_parts),
            setup_hint="jmm setup opensubtitles",
            impact=impact,
        )


def _check_plex_status() -> ServiceStatus:
    """Check Plex server status by attempting connection."""
    impact = "No library notifications"

    try:
        from jackmediaman.services.plex import PlexService

        plex = PlexService()
        if plex.is_configured:
            libraries = plex.get_libraries()
            if libraries:
                lib_count = len(libraries)
                return ServiceStatus(
                    name="Plex Server",
                    configured=True,
                    status_text="Connected",
                    detail=f"{plex.url} ({lib_count} libraries)",
                    impact=impact,
                )
            else:
                # Configured but not responding
                return ServiceStatus(
                    name="Plex Server",
                    configured=False,
                    status_text="No response",
                    detail=plex.url,
                    impact=impact,
                )
    except Exception:
        pass

    return ServiceStatus(
        name="Plex Server",
        configured=False,
        status_text="Not configured",
        setup_hint="jmm setup plex",
        impact=impact,
    )


def _check_ffprobe_status() -> ServiceStatus:
    """Check FFprobe availability."""
    settings = get_settings()
    impact = "No quality detection"

    if not settings.ffprobe_enabled:
        return ServiceStatus(
            name="FFprobe",
            configured=False,
            status_text="Disabled",
            detail="Enable in config to detect video quality",
            impact=impact,
        )

    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path:
        return ServiceStatus(
            name="FFprobe",
            configured=True,
            status_text="Installed",
            detail=ffprobe_path,
            impact=impact,
        )

    return ServiceStatus(
        name="FFprobe",
        configured=False,
        status_text="Not installed",
        detail="Install ffmpeg package",
        impact=impact,
    )


@app.command("config")
def show_config() -> None:
    """Show current configuration and service status."""
    settings = get_settings()

    console.print()

    # Services section
    console.print(Panel("[bold]External Services[/]", border_style="cyan"))
    console.print()

    services_table = Table(show_header=True, box=None, expand=True)
    services_table.add_column("Service", style="cyan", width=14, no_wrap=True)
    services_table.add_column("Status", width=14, no_wrap=True)
    services_table.add_column("If Missing", style="dim", width=26)
    services_table.add_column("Details", style="dim", overflow="fold")

    # Check all services (with loading spinner)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Checking services...", total=None)
        services = [
            _check_tmdb_status(),
            _check_deluge_status(),
            _check_opensubtitles_status(),
            _check_plex_status(),
            _check_ffprobe_status(),
        ]

    for svc in services:
        if svc.configured:
            status = f"[green]{svc.status_text}[/]"
            impact = "[dim]-[/]"
            detail = svc.detail or ""
        else:
            status = f"[yellow]{svc.status_text}[/]"
            impact = svc.impact or ""
            detail = f"Run `{svc.setup_hint}`" if svc.setup_hint else (svc.detail or "")

        services_table.add_row(svc.name, status, impact, detail)

    console.print(services_table)
    console.print()

    # Directories section
    console.print(Panel("[bold]Media Directories[/]", border_style="cyan"))
    console.print()

    def get_dir_stats(path: Path, count_type: str = "files") -> str:
        """Get directory statistics."""
        if not path.exists():
            return "[red]Not found[/]"

        try:
            if count_type == "shows":
                # Count subdirectories (each is a show)
                count = sum(1 for d in path.iterdir() if d.is_dir())
                return f"[green]{count} shows[/]"
            elif count_type == "movies":
                # Count subdirectories (each is a movie folder)
                count = sum(1 for d in path.iterdir() if d.is_dir())
                return f"[green]{count} movies[/]"
            else:
                # Count files (non-recursive for performance)
                count = sum(1 for f in path.iterdir() if f.is_file())
                return f"[green]{count} files[/]"
        except PermissionError:
            return "[yellow]No access[/]"

    dirs_table = Table(show_header=True, box=None)
    dirs_table.add_column("Directory", style="cyan", width=18)
    dirs_table.add_column("Path", style="white")
    dirs_table.add_column("Contents", width=14)

    dirs_table.add_row("TV Shows", str(settings.tv_dir), get_dir_stats(settings.tv_dir, "shows"))
    dirs_table.add_row("Movies", str(settings.movies_dir), get_dir_stats(settings.movies_dir, "movies"))
    dirs_table.add_row("Trash", str(settings.trash_dir), get_dir_stats(settings.trash_dir, "files"))
    dirs_table.add_row("Torrents", str(settings.torrent_dir), get_dir_stats(settings.torrent_dir, "files"))

    console.print(dirs_table)
    console.print()

    # Show setup hint if any services are not configured
    unconfigured = [s for s in services if not s.configured and s.setup_hint]
    if unconfigured:
        console.print("[dim]Tip: Run `jmm setup` to configure services interactively[/]")
        console.print()


@app.command("deluge")
def check_deluge() -> None:
    """Check Deluge daemon connection and seeding status."""
    console.print()
    console.print("[bold]Checking Deluge connection...[/]")

    protector = DelugeProtector()
    if protector.connect():
        console.print("[green]Connected to Deluge daemon[/]")

        seeding_files = protector._seeding_files or set()
        console.print(f"[dim]Found {len(seeding_files)} files currently seeding[/]")

        if seeding_files:
            console.print()
            table = Table(title="Seeding Files (sample)", show_header=False)
            table.add_column("File")

            for i, path in enumerate(sorted(seeding_files)[:10]):
                table.add_row(str(path))

            if len(seeding_files) > 10:
                table.add_row(f"[dim]... and {len(seeding_files) - 10} more[/]")

            console.print(table)

        protector.disconnect()
    else:
        console.print("[red]Failed to connect to Deluge daemon[/]")
        console.print()
        console.print("Run [cyan]jmm setup deluge[/] to configure connection settings")

    console.print()


@app.command("trash")
def check_trash() -> None:
    """Show contents of trash directory."""
    cleaner = CleanupService()
    files = cleaner.list_trash()

    if not files:
        console.print("\n[dim]Trash is empty[/]\n")
        return

    total_size = sum(f.stat().st_size for f, _ in files)
    total_gb = total_size / (1024 * 1024 * 1024)

    console.print()
    console.print(Panel(
        f"[bold]{len(files)} files in trash[/]\n"
        f"[dim]Total size: {total_gb:.2f} GB[/]",
        title="[bold cyan]Trash Contents[/]",
        border_style="cyan",
    ))
    console.print()

    table = Table(show_header=True)
    table.add_column("Date", style="dim")
    table.add_column("File", style="white")
    table.add_column("Size", style="magenta", justify="right")

    for path, timestamp in files[:20]:
        size_mb = path.stat().st_size / (1024 * 1024)
        # Remove timestamp prefix from filename for display
        display_name = "_".join(path.name.split("_")[2:]) if "_" in path.name else path.name
        table.add_row(
            timestamp.strftime("%Y-%m-%d %H:%M"),
            display_name[:50] + "..." if len(display_name) > 50 else display_name,
            f"{size_mb:.1f} MB",
        )

    if len(files) > 20:
        table.add_row("", f"[dim]... and {len(files) - 20} more files[/]", "")

    console.print(table)
    console.print()


@app.command("tmdb")
def check_tmdb() -> None:
    """Check TMDb API connection and status."""
    settings = get_settings()

    console.print()
    console.print("[bold]Checking TMDb API status...[/]")
    console.print()

    if not settings.tmdb_api_key:
        console.print("[yellow]TMDb API key not configured[/]")
        console.print()
        console.print("[dim]Without an API key, the following features are limited:[/]")
        console.print("[dim]  - Rename command won't fetch episode titles[/]")
        console.print("[dim]  - TMDb matcher will fall back to title/year matching[/]")
        console.print()
        console.print("Run [cyan]jmm setup tmdb[/] to configure interactively")
        console.print()
        return

    # Test the API key by making a simple request
    try:
        import httpx
        response = httpx.get(
            "https://api.themoviedb.org/3/configuration",
            params={"api_key": settings.tmdb_api_key},
            timeout=10.0,
        )

        if response.status_code == 200:
            console.print("[green]TMDb API key is valid and working[/]")
            console.print()

            # Show some info about available features
            table = Table(show_header=False, box=None)
            table.add_column("Feature", style="dim")
            table.add_column("Status", style="green")

            table.add_row("Movie lookup", "[green]Available[/]")
            table.add_row("TV show lookup", "[green]Available[/]")
            table.add_row("Episode titles", "[green]Available[/]")
            table.add_row("TMDb-based matching", "[green]Available[/]")

            console.print(table)

        elif response.status_code == 401:
            console.print("[red]TMDb API key is invalid[/]")
            console.print("[dim]Please check your API key in the .env file[/]")

        else:
            console.print(f"[yellow]TMDb API returned status {response.status_code}[/]")

    except httpx.ConnectError:
        console.print("[red]Could not connect to TMDb API[/]")
        console.print("[dim]Check your internet connection[/]")

    except httpx.TimeoutException:
        console.print("[yellow]TMDb API request timed out[/]")

    except Exception as e:
        console.print(f"[red]Error checking TMDb: {e}[/]")

    console.print()


@app.command("empty-trash")
def empty_trash(
    older_than: int = typer.Option(
        None,
        "--older-than",
        "-d",
        help="Only delete files older than N days",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Don't ask for confirmation",
    ),
) -> None:
    """Empty the trash directory."""
    cleaner = CleanupService()
    files = cleaner.list_trash()

    if not files:
        console.print("\n[dim]Trash is already empty[/]\n")
        return

    if not force:
        from jackmediaman.cli.interactive import confirm_action
        if not confirm_action(f"Delete {len(files)} files from trash?", default=False):
            return

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[filename]}[/]"),
        console=console,
    ) as progress:
        task = progress.add_task("Deleting...", total=len(files), filename="")

        def update_progress(current: int, total: int, filename: str) -> None:
            progress.update(task, completed=current, total=total, filename=filename[:50])

        deleted = cleaner.empty_trash(older_than_days=older_than, progress_callback=update_progress)

    console.print(f"\n[green]Deleted {deleted} files from trash[/]\n")


@app.command("opensubtitles")
def check_opensubtitles() -> None:
    """Check OpenSubtitles API connection and status for both providers."""
    settings = get_settings()

    com_configured = bool(settings.opensubtitles_com_api_key)
    org_configured = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)

    console.print()
    console.print("[bold]Checking OpenSubtitles status...[/]")
    console.print()

    if not com_configured and not org_configured:
        console.print("[yellow]No providers configured[/]")
        console.print()
        console.print("Run [cyan]jmm setup opensubtitles[/] to configure")
        console.print()
        return

    # Check .com provider
    if com_configured:
        console.print("[bold cyan]OpenSubtitles.com[/] [dim](API key)[/]")
        try:
            from jackmediaman.services.subtitles import OpenSubtitlesComClient
            client = OpenSubtitlesComClient(api_key=settings.opensubtitles_com_api_key)
            if client.validate_credentials():
                console.print("  [green]API key valid[/]")
            else:
                console.print("  [red]API key invalid[/]")
        except Exception as e:
            console.print(f"  [red]Error: {e}[/]")
        console.print()

    # Check .org provider
    if org_configured:
        console.print("[bold cyan]OpenSubtitles.org[/] [dim](username/password)[/]")
        try:
            from jackmediaman.services.subtitles import OpenSubtitlesOrgClient
            client = OpenSubtitlesOrgClient(
                username=settings.opensubtitles_org_username,
                password=settings.opensubtitles_org_password,
            )
            if client.validate_credentials():
                console.print(f"  [green]Login successful[/] ({settings.opensubtitles_org_username})")
            else:
                console.print("  [red]Login failed[/]")
        except Exception as e:
            console.print(f"  [red]Error: {e}[/]")
        console.print()

    console.print(f"[dim]Preferred languages: {settings.subtitle_languages}[/]")
    console.print()


@app.command("plex")
def check_plex() -> None:
    """Check Plex server connection and list libraries."""
    console.print()
    console.print(Panel("[bold]Plex Server[/]", border_style="cyan"))
    console.print()

    from jackmediaman.services.plex import PlexService

    plex = PlexService()

    if not plex.is_configured:
        console.print("[yellow]Not configured[/]")
        console.print("[dim]Run: jmm setup plex[/]")
        console.print()
        return

    console.print(f"URL: [cyan]{plex.url}[/]")

    libraries = plex.get_libraries()
    if libraries:
        console.print(f"[green]Connected[/] - {len(libraries)} libraries found")
        console.print()
        for lib in libraries:
            console.print(f"  • {lib.title} ({lib.type})")
    else:
        console.print("[yellow]No response from server[/]")

    console.print()
