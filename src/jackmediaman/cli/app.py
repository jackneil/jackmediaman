"""Main CLI application for JackMediaMan."""

import typer
from rich.console import Console
from rich.panel import Panel

from jackmediaman import __version__
from jackmediaman.core.logging import setup_logging

# Initialize logging at startup
setup_logging()
from jackmediaman.cli.commands import duplicates, status, rename, trash, cache, setup, subtitles, artwork, nfo, torrents, process, folders, repair

# Create main app
app = typer.Typer(
    name="jackmediaman",
    help="JackMediaMan - Media library manager for organizing, renaming, and deduplicating your media collection.",
    no_args_is_help=False,
    rich_markup_mode="rich",
)

# Add subcommands
app.add_typer(duplicates.app, name="duplicates", help="Find and clean duplicate media files")
app.add_typer(status.app, name="status", help="Check status of library and configuration")
app.add_typer(rename.app, name="rename", help="Rename media files to standardized format")
app.add_typer(trash.app, name="trash", help="Manage trash directory")
app.add_typer(cache.app, name="cache", help="Manage FFprobe metadata cache")
app.add_typer(setup.app, name="setup", help="Configure external services interactively")
app.add_typer(subtitles.app, name="subtitles", help="Download subtitles for media files")
app.add_typer(artwork.app, name="artwork", help="Download poster artwork from TMDb")
app.add_typer(nfo.app, name="nfo", help="Generate Kodi-compatible NFO metadata files")
app.add_typer(torrents.app, name="torrents", help="Manage Deluge torrents")
app.add_typer(process.app, name="process", help="Process completed torrent downloads")
app.add_typer(folders.app, name="folders", help="Find and consolidate duplicate folders")
app.add_typer(repair.app, name="repair", help="Repair broken symlinks and other issues")

console = Console()


@app.command("version")
def version() -> None:
    """Show version information."""
    console.print(f"\n[bold cyan]JackMediaMan[/] v{__version__}\n")


@app.command("interactive")
def interactive_mode() -> None:
    """Launch interactive menu mode."""
    from jackmediaman.cli.interactive import run_interactive
    run_interactive()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    show_version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Show version and exit",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Launch interactive menu mode",
    ),
    web: bool = typer.Option(
        False,
        "--web",
        help="Start web server (requires jackmediaman[web])",
    ),
    port: int = typer.Option(
        8080,
        "--port",
        "-p",
        help="Port for web server (with --web)",
    ),
) -> None:
    """
    JackMediaMan - Media library manager.

    Run without arguments to show status, or use subcommands:

    \b
    Library Operations:
    • jmm process run <path>  - Process completed torrent downloads
    • jmm duplicates scan     - Find duplicate files in library
    • jmm duplicates clean    - Clean up duplicates (interactive)
    • jmm rename scan         - Rename media files to standard format
    • jmm subtitles scan      - Download missing subtitles
    • jmm artwork scan        - Download missing poster artwork
    • jmm nfo generate        - Generate NFO metadata files

    \b
    Status & Configuration:
    • jmm status config       - Show configuration and service status
    • jmm status deluge       - Check Deluge daemon connection
    • jmm status tmdb         - Check TMDb API status
    • jmm setup init          - Run setup wizard for all services
    • jmm setup deluge        - Configure Deluge connection
    • jmm setup tmdb          - Configure TMDb API key

    \b
    Interactive Mode:
    • jmm -i                  - Launch interactive menu
    • jmm interactive         - Same as above

    \b
    Web Interface:
    • jmm --web               - Start web server at http://localhost:8080
    • jmm --web --port 3000   - Start on custom port
    """
    if show_version:
        version()
        raise typer.Exit()

    if ctx.invoked_subcommand is None:
        if interactive:
            # Launch interactive menu
            from jackmediaman.cli.interactive import run_interactive
            run_interactive()
        elif web:
            # Start web server
            try:
                from jackmediaman.web import start_server
                start_server(port=port)
            except ImportError as e:
                console.print()
                console.print(Panel(
                    f"[bold red]Web dependencies not installed[/]\n\n"
                    f"Error: {e}\n\n"
                    "Install with: [cyan]pip install jackmediaman[web][/]",
                    border_style="red",
                ))
                console.print()
                raise typer.Exit(1)
        else:
            # Default: show status overview
            _show_quick_status()


def _show_quick_status() -> None:
    """Show quick status overview when run without arguments."""
    from jackmediaman.core.config import get_settings

    console.print()
    console.print(Panel(
        f"[bold cyan]JackMediaMan[/] v{__version__}\n"
        "[dim]Media Library Manager[/]",
        border_style="cyan",
    ))
    console.print()

    try:
        settings = get_settings()

        # Quick service status
        console.print("[bold]Service Status:[/]")

        services = []
        if settings.tmdb_api_key:
            services.append("  [green]✓[/] TMDb API configured")
        else:
            services.append("  [dim]○[/] TMDb API not configured")

        # Deluge: localhost can use auto-auth without credentials
        is_localhost = settings.deluge_host in ("127.0.0.1", "localhost", "::1")
        if is_localhost or settings.deluge_username:
            services.append("  [green]✓[/] Deluge configured")
        else:
            services.append("  [dim]○[/] Deluge not configured")

        # OpenSubtitles - check both providers
        com_configured = bool(settings.opensubtitles_com_api_key)
        org_configured = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)
        if com_configured or org_configured:
            services.append("  [green]✓[/] OpenSubtitles configured")
        else:
            services.append("  [dim]○[/] OpenSubtitles not configured")

        # Plex: check if configured
        from jackmediaman.services.plex import PlexService
        plex = PlexService()
        if plex.is_configured:
            services.append("  [green]✓[/] Plex configured")
        else:
            services.append("  [dim]○[/] Plex not configured")

        for svc in services:
            console.print(svc)

        console.print()
        console.print("[bold]Media Paths:[/]")
        console.print(f"  TV:     {settings.tv_dir}" + (" [green]✓[/]" if settings.tv_dir.exists() else " [red]✗[/]"))
        console.print(f"  Movies: {settings.movies_dir}" + (" [green]✓[/]" if settings.movies_dir.exists() else " [red]✗[/]"))

    except Exception as e:
        console.print(f"[yellow]Could not load settings: {e}[/]")

    console.print()
    console.print("[dim]Run [cyan]jmm -i[/] for interactive menu, or [cyan]jmm --help[/] for commands[/]")
    console.print()


if __name__ == "__main__":
    app()
