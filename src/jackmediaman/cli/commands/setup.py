"""Setup command for configuring external services interactively."""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.table import Table

from jackmediaman.core.config import (
    get_config_path,
    get_settings,
    reload_settings,
    save_setting,
    _build_toml_config,
    _write_toml_config,
)

app = typer.Typer(help="Configure external services interactively")
console = Console()


def _show_service_status() -> None:
    """Show current status of all settings."""
    settings = get_settings()

    console.print()
    console.print(Panel("[bold]JackMediaMan Configuration[/]", border_style="cyan"))

    # --- Media Library Paths ---
    console.print()
    console.print("[bold cyan]Media Library Paths[/]  [dim](jmm setup paths)[/]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Setting", style="dim", width=20)
    table.add_column("Value")
    table.add_row("TV Shows", f"[white]{settings.tv_dir}[/]")
    table.add_row("Movies", f"[white]{settings.movies_dir}[/]")
    table.add_row("Torrents", f"[white]{settings.torrent_dir}[/]")
    table.add_row("Trash", f"[white]{settings.trash_dir}[/]")
    console.print(table)

    # --- External Services ---
    console.print()
    console.print("[bold cyan]External Services[/]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Service", style="dim", width=20)
    table.add_column("Status")
    table.add_column("Action", style="dim")

    # TMDb
    if settings.tmdb_api_key:
        table.add_row("TMDb API", "[green]Configured[/]", "jmm setup tmdb")
    else:
        table.add_row("TMDb API", "[yellow]Not set[/]", "jmm setup tmdb")

    # Deluge
    is_localhost = settings.deluge_host in ("127.0.0.1", "localhost", "::1")
    if is_localhost:
        table.add_row(
            "Deluge Daemon",
            f"[green]localhost:{settings.deluge_port}[/] [dim](auto-auth)[/]",
            "jmm setup deluge",
        )
    elif settings.deluge_username or settings.deluge_password:
        table.add_row(
            "Deluge Daemon",
            f"[green]{settings.deluge_host}:{settings.deluge_port}[/]",
            "jmm setup deluge",
        )
    else:
        table.add_row("Deluge Daemon", "[yellow]Not configured[/]", "jmm setup deluge")

    # OpenSubtitles - show both providers
    com_configured = bool(settings.opensubtitles_com_api_key)
    org_configured = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)

    if com_configured or org_configured:
        parts = []
        if com_configured:
            parts.append("[green].com[/]")
        if org_configured:
            parts.append(f"[green].org[/] [dim]({settings.opensubtitles_org_username})[/]")
        table.add_row("OpenSubtitles", " + ".join(parts), "jmm setup opensubtitles")
    else:
        table.add_row("OpenSubtitles", "[yellow]Not set[/]", "jmm setup opensubtitles")

    # Plex - check for auto-discovery
    from jackmediaman.services.plex import PlexService, discover_plex_config

    plex = PlexService()
    if plex.is_configured:
        if "auto-discovered" in plex.config_source:
            plex_status = f"[green]{plex.url}[/] [dim](auto-discovered)[/]"
        else:
            plex_status = f"[green]{plex.url}[/]"
        if not settings.plex_notify_enabled:
            plex_status += " [dim](disabled)[/]"
        table.add_row("Plex", plex_status, "jmm setup plex")
    else:
        # Check if we can auto-discover but it's disabled
        discovered = discover_plex_config()
        if discovered.token:
            table.add_row(
                "Plex",
                f"[yellow]Found locally[/] [dim](enable with PLEX_NOTIFY_ENABLED=true)[/]",
                "jmm setup plex",
            )
        else:
            table.add_row("Plex", "[yellow]Not configured[/]", "jmm setup plex")

    console.print(table)

    # --- Processing Options ---
    console.print()
    console.print("[bold cyan]Processing Options[/]  [dim](jmm setup processing)[/]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Setting", style="dim", width=20)
    table.add_column("Value")
    table.add_row("Default Action", f"[white]{settings.process_default_action}[/]")
    table.add_row("Cleanup Archives", f"[white]{settings.process_cleanup_archives}[/]")
    table.add_row("Subtitle Languages", f"[white]{settings.subtitle_languages}[/]")
    console.print(table)

    # --- Performance ---
    console.print()
    console.print("[bold cyan]Performance[/]  [dim](jmm setup performance)[/]")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Setting", style="dim", width=20)
    table.add_column("Value")
    table.add_row("FFprobe Enabled", f"[white]{settings.ffprobe_enabled}[/]")
    table.add_row("FFprobe Workers", f"[white]{settings.ffprobe_workers}[/]")
    table.add_row("FFprobe Timeout", f"[white]{settings.ffprobe_timeout}s[/]")
    table.add_row("Cache TTL", f"[white]{settings.cache_ttl}s ({settings.cache_ttl // 3600}h)[/]")
    console.print(table)

    console.print()
    console.print(f"[dim]Config file: {get_config_path()}[/]")
    console.print()


@app.command("init")
def setup_init(
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing config"),
    auto: bool = typer.Option(True, "--auto/--no-auto", help="Auto-discover Plex and configure Deluge"),
) -> None:
    """Initialize configuration with auto-discovery.

    Automatically discovers:
    - Plex server (token, URL, library paths)
    - Deluge Execute plugin (configures automatic torrent processing)

    Use --no-auto to skip auto-discovery and only create the config file.
    """
    config_file = get_config_path()

    # Check if config already exists
    if config_file.exists() and not force:
        console.print()
        console.print(f"[yellow]Config file already exists:[/] {config_file}")
        console.print("[dim]Use --force to overwrite[/]")
        console.print()
        return

    # Create config with defaults
    try:
        config = _build_toml_config({})
        _write_toml_config(config)

    except Exception as e:
        console.print(f"[red]Error creating config: {e}[/]")
        return

    console.print()
    console.print(f"[green]Config file created:[/] {config_file}")

    # Run auto-discovery if enabled
    if auto:
        console.print()
        _run_auto_discovery()

    console.print()
    console.print("[bold]Next steps:[/]")
    console.print("  - Run [cyan]jmm setup tmdb[/] to add TMDb API key (optional)")
    console.print("  - Run [cyan]jmm[/] to verify configuration")
    console.print()


def _run_auto_discovery() -> None:
    """Run auto-discovery for Plex and Deluge."""
    from jackmediaman.services.autosetup import AutoSetupService

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Auto-discovering services...", total=None)

        service = AutoSetupService()
        result = service.run()

        progress.update(task, description="[green]Auto-discovery complete[/]")

    # Display Plex results
    if result.plex_discovered:
        console.print()
        console.print(f"[green]Plex discovered[/] at {result.plex_url}")
        console.print(f"  [dim]Source: {result.plex_source}[/]")
        if result.movies_dir:
            console.print(f"  Movies: [cyan]{result.movies_dir}[/]")
        if result.tv_dir:
            console.print(f"  TV: [cyan]{result.tv_dir}[/]")
    else:
        console.print()
        console.print("[dim]Plex not found locally[/]")

    # Display Deluge results
    if result.deluge_configured:
        if result.deluge_already_exists:
            console.print()
            console.print("[dim]Deluge hook already configured[/]")
        else:
            console.print()
            console.print("[green]Deluge Execute plugin configured[/]")
            console.print("  [dim]Completed torrents will be processed automatically[/]")
    elif result.deluge_error:
        console.print()
        console.print(f"[yellow]Deluge setup skipped:[/] {result.deluge_error}")

    # Display any other errors
    for error in result.errors:
        if "Plex" not in error and "Deluge" not in error:
            console.print(f"[yellow]Warning:[/] {error}")

    # Show what was saved
    if result.settings_written:
        console.print()
        console.print(f"[dim]Settings saved: {', '.join(result.settings_written)}[/]")




@app.command("paths")
def setup_paths() -> None:
    """Configure media library paths interactively."""
    from pathlib import Path

    settings = get_settings()

    console.print()
    console.print(Panel(
        "[bold]Media Library Paths[/]\n\n"
        "Configure where JackMediaMan finds and organizes your media files.\n"
        "Press Enter to keep current values.",
        border_style="cyan",
    ))
    console.print()

    # TV Shows directory
    tv_dir = Prompt.ask(
        "  TV Shows directory",
        default=str(settings.tv_dir),
    )

    # Movies directory
    movies_dir = Prompt.ask(
        "  Movies directory",
        default=str(settings.movies_dir),
    )

    # Torrents directory
    torrent_dir = Prompt.ask(
        "  Completed torrents directory",
        default=str(settings.torrent_dir),
    )

    # Trash directory
    trash_dir = Prompt.ask(
        "  Trash directory",
        default=str(settings.trash_dir),
    )

    # Save settings
    save_setting("JMM_TV_DIR", tv_dir)
    save_setting("JMM_MOVIES_DIR", movies_dir)
    save_setting("JMM_TORRENT_DIR", torrent_dir)
    save_setting("JMM_TRASH_DIR", trash_dir)
    reload_settings()

    console.print()
    console.print("[green]Paths saved![/]")
    console.print()


@app.command("processing")
def setup_processing() -> None:
    """Configure processing options interactively."""
    settings = get_settings()

    console.print()
    console.print(Panel(
        "[bold]Processing Options[/]\n\n"
        "Configure how JackMediaMan processes completed torrents.",
        border_style="cyan",
    ))
    console.print()

    # Default action
    console.print("[bold]Default action mode:[/]")
    console.print("  [cyan]move[/]     - Move files to library")
    console.print("  [cyan]copy[/]     - Copy files to library")
    console.print("  [cyan]hardlink[/] - Create hardlinks (same filesystem)")
    console.print("  [cyan]symlink[/]  - Create symlinks (original stays for seeding)")
    console.print("  [cyan]keeplink[/] - Move to library, symlink at original for seeding")
    console.print()

    action = Prompt.ask(
        "  Default action",
        choices=["move", "copy", "hardlink", "symlink", "keeplink"],
        default=settings.process_default_action,
    )

    # Cleanup archives
    console.print()
    cleanup = Prompt.ask(
        "  Delete archives after extraction?",
        choices=["true", "false"],
        default=str(settings.process_cleanup_archives).lower(),
    )

    # Subtitle languages
    console.print()
    languages = Prompt.ask(
        "  Subtitle languages (comma-separated, e.g., en,es,fr)",
        default=settings.subtitle_languages,
    )

    # Save settings
    save_setting("JMM_PROCESS_DEFAULT_ACTION", action)
    save_setting("JMM_PROCESS_CLEANUP_ARCHIVES", cleanup)
    save_setting("JMM_SUBTITLE_LANGUAGES", languages)
    reload_settings()

    console.print()
    console.print("[green]Processing options saved![/]")
    console.print()


@app.command("performance")
def setup_performance() -> None:
    """Configure performance settings interactively."""
    settings = get_settings()

    console.print()
    console.print(Panel(
        "[bold]Performance Settings[/]\n\n"
        "Configure FFprobe and caching behavior.",
        border_style="cyan",
    ))
    console.print()

    # FFprobe enabled
    ffprobe_enabled = Prompt.ask(
        "  Enable FFprobe for accurate quality detection?",
        choices=["true", "false"],
        default=str(settings.ffprobe_enabled).lower(),
    )

    # FFprobe workers
    console.print()
    workers = Prompt.ask(
        "  FFprobe parallel workers (1-16)",
        default=str(settings.ffprobe_workers),
    )
    try:
        workers_int = max(1, min(16, int(workers)))
    except ValueError:
        workers_int = 4

    # FFprobe timeout
    console.print()
    timeout = Prompt.ask(
        "  FFprobe timeout in seconds",
        default=str(int(settings.ffprobe_timeout)),
    )
    try:
        timeout_float = max(1.0, min(120.0, float(timeout)))
    except ValueError:
        timeout_float = 30.0

    # Cache TTL
    console.print()
    console.print("[dim]Cache TTL: How long to keep TMDb/metadata cache (in hours)[/]")
    cache_hours = Prompt.ask(
        "  Cache TTL (hours)",
        default=str(settings.cache_ttl // 3600),
    )
    try:
        cache_ttl = int(cache_hours) * 3600
    except ValueError:
        cache_ttl = 86400

    # Save settings
    save_setting("JMM_FFPROBE_ENABLED", ffprobe_enabled)
    save_setting("JMM_FFPROBE_WORKERS", str(workers_int))
    save_setting("JMM_FFPROBE_TIMEOUT", str(timeout_float))
    save_setting("JMM_CACHE_TTL", str(cache_ttl))
    reload_settings()

    console.print()
    console.print("[green]Performance settings saved![/]")
    console.print()


@app.command("tmdb")
def setup_tmdb() -> None:
    """Configure TMDb API key interactively."""
    console.print()
    console.print(Panel(
        "[bold]TMDb API Configuration[/]\n\n"
        "TMDb (The Movie Database) provides movie and TV show metadata including:\n"
        "  - Accurate movie/show titles\n"
        "  - Episode titles and air dates\n"
        "  - Movie release years\n\n"
        "[dim]This improves the accuracy of the rename and duplicate detection commands.[/]",
        border_style="cyan",
    ))
    console.print()

    console.print("[bold]To get a free API key:[/]")
    console.print("  1. Create an account at [cyan]https://www.themoviedb.org/[/]")
    console.print("  2. Go to Settings > API")
    console.print("  3. Request an API key (choose 'Developer')")
    console.print()

    api_key = Prompt.ask("Enter your TMDb API key", default="")

    if not api_key.strip():
        console.print("[yellow]No API key provided. Setup cancelled.[/]")
        console.print()
        return

    # Validate the API key
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Validating API key...", total=None)

        try:
            import httpx
            response = httpx.get(
                "https://api.themoviedb.org/3/configuration",
                params={"api_key": api_key.strip()},
                timeout=10.0,
            )

            if response.status_code == 200:
                progress.update(task, description="[green]API key validated![/]")
            elif response.status_code == 401:
                progress.update(task, description="[red]Invalid API key[/]")
                console.print()
                console.print("[red]The API key is invalid. Please check and try again.[/]")
                console.print()
                return
            else:
                progress.update(task, description=f"[yellow]Unexpected response: {response.status_code}[/]")

        except httpx.HTTPError as e:
            progress.update(task, description=f"[red]Connection error: {e}[/]")
            console.print()
            console.print("[red]Could not validate API key. Check your internet connection.[/]")
            console.print()
            return

    # Save the API key
    save_setting("JMM_TMDB_API_KEY", api_key.strip())
    reload_settings()

    console.print()
    console.print("[green]TMDb API key saved![/]")
    console.print()


@app.command("deluge")
def setup_deluge() -> None:
    """Configure Deluge daemon connection interactively."""
    settings = get_settings()

    console.print()
    console.print(Panel(
        "[bold]Deluge Daemon Configuration[/]\n\n"
        "Deluge protection prevents removal of files that are actively seeding.\n"
        "JackMediaMan connects to the Deluge daemon to check torrent status.\n\n"
        "[cyan]Localhost (127.0.0.1):[/] No credentials needed - auto-auth from ~/.config/deluge/auth\n"
        "[cyan]Remote host:[/] Username and password required",
        border_style="cyan",
    ))
    console.print()

    console.print("[bold]Deluge daemon settings:[/]")
    console.print()

    # Get host
    host = Prompt.ask(
        "  Host",
        default=settings.deluge_host or "127.0.0.1",
    )

    # Check if localhost
    is_localhost = host in ("127.0.0.1", "localhost", "::1")

    # Get port
    port_str = Prompt.ask(
        "  Port",
        default=str(settings.deluge_port or 58846),
    )
    try:
        port = int(port_str)
    except ValueError:
        console.print("[red]Invalid port number. Using default 58846.[/]")
        port = 58846

    # For localhost, credentials are optional
    if is_localhost:
        console.print()
        console.print("[dim]  Localhost detected - credentials are optional (uses auto-auth)[/]")
        console.print()

    # Get username
    username_prompt = "  Username (optional)" if is_localhost else "  Username"
    username = Prompt.ask(
        username_prompt,
        default=settings.deluge_username or "",
    )

    # Get password
    password_prompt = "  Password (optional)" if is_localhost else "  Password"
    password = Prompt.ask(
        password_prompt,
        default="",
        password=True,
    )

    # If no new password provided but we have an existing one, keep it
    if not password and settings.deluge_password:
        password = settings.deluge_password
        console.print("[dim]  (Using existing password)[/]")

    console.print()

    # Test the connection
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Testing connection...", total=None)

        try:
            # Temporarily update settings for testing
            from jackmediaman.protectors.deluge import DelugeProtector

            # Create protector with test settings
            test_protector = DelugeProtector()
            # Override settings for test
            test_protector._settings = type('Settings', (), {
                'deluge_host': host,
                'deluge_port': port,
                'deluge_username': username,
                'deluge_password': password,
            })()

            if test_protector.connect():
                seeding_count = len(test_protector._seeding_files or set())
                progress.update(task, description=f"[green]Connected! Found {seeding_count} seeding files[/]")
                test_protector.disconnect()
            else:
                progress.update(task, description="[red]Connection failed[/]")
                console.print()
                console.print("[red]Could not connect to Deluge daemon.[/]")
                console.print("[dim]Check that the daemon is running and credentials are correct.[/]")
                console.print()
                return

        except Exception as e:
            progress.update(task, description=f"[red]Error: {e}[/]")
            console.print()
            console.print(f"[red]Connection error: {e}[/]")
            console.print()
            return

    # Save settings
    save_setting("JMM_DELUGE_HOST", host)
    save_setting("JMM_DELUGE_PORT", str(port))
    save_setting("JMM_DELUGE_USERNAME", username)
    if password:
        save_setting("JMM_DELUGE_PASSWORD", password)
    reload_settings()

    console.print()
    console.print("[green]Deluge settings saved![/]")
    console.print()

    # Ask about Execute plugin setup
    setup_hook = Prompt.ask(
        "Configure automatic processing on torrent completion?",
        choices=["y", "n"],
        default="y",
    )

    if setup_hook.lower() == "y":
        _setup_execute_hook(host, port, username, password)


def _setup_execute_hook(host: str, port: int, username: str, password: str) -> None:
    """Set up Deluge Execute plugin hook for automatic torrent processing."""
    from jackmediaman.services.deluge_setup import DelugeExecuteSetup

    settings = get_settings()
    action = settings.process_default_action or "symlink"

    console.print()
    console.print(
        Panel(
            "[bold]Execute Plugin Setup[/]\n\n"
            "This will configure Deluge to automatically process completed torrents.\n"
            "When a torrent finishes, JackMediaMan will:\n"
            "  - Extract any archives (RAR, ZIP, 7z)\n"
            "  - Identify media type and metadata\n"
            "  - Organize files into your library\n\n"
            f"[dim]Default action: {action}[/]",
            border_style="cyan",
        )
    )
    console.print()

    setup = DelugeExecuteSetup(host, port, username, password, action)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Creating hook script...", total=None)
        script_path = setup.create_hook_script()
        progress.update(task, description=f"[green]Created {script_path}[/]")

        task2 = progress.add_task("Configuring Execute plugin...", total=None)
        result = setup.setup_execute_plugin()

        if result.success:
            if result.existing_command:
                progress.update(task2, description="[green]Hook already configured![/]")
            else:
                progress.update(task2, description="[green]Execute plugin configured![/]")
        else:
            progress.update(task2, description=f"[red]Failed: {result.error}[/]")
            console.print()
            console.print(f"[red]Could not configure Execute plugin: {result.error}[/]")
            console.print("[dim]You may need to configure the Execute plugin manually.[/]")
            console.print()
            return

    console.print()
    if result.plugin_enabled:
        console.print(
            "[yellow]Execute plugin was enabled. Restart Deluge to activate.[/]"
        )
    if result.command_added:
        console.print(
            "[yellow]Execute plugin requires Deluge restart to apply changes.[/]"
        )
    console.print()
    console.print("[green]Done! Completed torrents will now be automatically processed.[/]")
    console.print(f"[dim]Hook script: {script_path}[/]")
    console.print(f"[dim]Log file: ~/.jackmediaman/deluge-hook.log[/]")
    console.print()


@app.command("opensubtitles")
def setup_opensubtitles() -> None:
    """Configure OpenSubtitles credentials interactively.

    Supports both OpenSubtitles.org and OpenSubtitles.com as separate providers.
    """
    settings = get_settings()

    console.print()
    console.print(Panel(
        "[bold]OpenSubtitles Configuration[/]\n\n"
        "OpenSubtitles provides automatic subtitle downloads for your media files.\n"
        "You can configure one or both providers:\n\n"
        "[cyan].com[/] - OpenSubtitles.com (free API key, fast search)\n"
        "[cyan].org[/] - OpenSubtitles.org (VIP account, search + download)",
        border_style="cyan",
    ))

    # --- OpenSubtitles.com (API key only) ---
    console.print()
    console.print("[bold cyan]OpenSubtitles.com[/] [dim](API key only)[/]")
    console.print("[dim]Get API key from: https://www.opensubtitles.com/en/consumers[/]")
    console.print()

    api_key = Prompt.ask(
        "  .com API Key",
        default=settings.opensubtitles_com_api_key or "",
    )

    com_valid = False
    if api_key.strip():
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Validating .com API key...", total=None)
            try:
                from jackmediaman.services.subtitles import OpenSubtitlesComClient
                client = OpenSubtitlesComClient(api_key=api_key.strip())
                if client.validate_credentials():
                    progress.update(task, description="[green].com API key valid![/]")
                    com_valid = True
                else:
                    progress.update(task, description="[red].com API key invalid[/]")
            except Exception as e:
                progress.update(task, description=f"[red]Error: {e}[/]")
    else:
        console.print("[dim]  (skipped)[/]")

    # --- OpenSubtitles.org (username/password) ---
    console.print()
    console.print("[bold cyan]OpenSubtitles.org[/] [dim](username/password)[/]")
    console.print("[dim]Required for downloading subtitles[/]")
    console.print()

    username = Prompt.ask(
        "  .org Username",
        default=settings.opensubtitles_org_username or "",
    )

    org_valid = False
    if username.strip():
        password = Prompt.ask(
            "  .org Password",
            password=True,
        )

        if password.strip():
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Validating .org credentials...", total=None)
                try:
                    from jackmediaman.services.subtitles import OpenSubtitlesOrgClient
                    client = OpenSubtitlesOrgClient(
                        username=username.strip(),
                        password=password.strip(),
                    )
                    if client.validate_credentials():
                        progress.update(task, description="[green].org credentials valid![/]")
                        org_valid = True
                    else:
                        progress.update(task, description="[red].org login failed[/]")
                except Exception as e:
                    progress.update(task, description=f"[red]Error: {e}[/]")
        else:
            console.print("[dim]  (skipped - no password)[/]")
    else:
        console.print("[dim]  (skipped)[/]")
        password = ""

    # Check if anything was configured
    if not com_valid and not org_valid:
        console.print()
        console.print("[yellow]No valid credentials configured. Setup cancelled.[/]")
        console.print()
        return

    # Save settings
    if api_key.strip():
        save_setting("JMM_OPENSUBTITLES_COM_API_KEY", api_key.strip())
    if username.strip() and password.strip():
        save_setting("JMM_OPENSUBTITLES_ORG_USERNAME", username.strip())
        save_setting("JMM_OPENSUBTITLES_ORG_PASSWORD", password.strip())

    # Ask about preferred languages
    console.print()
    languages = Prompt.ask(
        "Preferred subtitle languages (comma-separated)",
        default=settings.subtitle_languages or "en",
    )
    save_setting("JMM_SUBTITLE_LANGUAGES", languages.strip())

    reload_settings()

    console.print()
    parts = []
    if com_valid:
        parts.append(".com (API key)")
    if org_valid:
        parts.append(f".org ({username})")
    console.print(f"[green]OpenSubtitles configured:[/] {' + '.join(parts)}")
    console.print("[dim]Settings saved![/]")
    console.print()


@app.command("plex")
def setup_plex() -> None:
    """Configure Plex server connection for library notifications.

    When configured, JackMediaMan will notify Plex to scan specific paths
    after files are added, renamed, or removed. This triggers instant updates
    in your Plex library without waiting for scheduled scans.

    Plex is assumed to run locally (localhost:32400) by default, but remote
    servers are also supported. If Plex is installed locally, the token and
    URL can be auto-discovered from Preferences.xml.
    """
    from rich.prompt import Confirm

    from jackmediaman.services.plex import discover_plex_config

    settings = get_settings()

    console.print()
    console.print(Panel(
        "[bold]Plex Configuration[/]\n\n"
        "JackMediaMan can notify Plex when media is added, renamed, or removed.\n"
        "This triggers a targeted library scan for instant updates.\n\n"
        "[cyan]Localhost (default):[/] http://localhost:32400\n"
        "[cyan]Remote server:[/] Full URL required (e.g., http://192.168.1.100:32400)",
        border_style="cyan",
    ))
    console.print()

    # Check for auto-discovered config
    discovered = discover_plex_config()

    if discovered.token:
        console.print(f"[green]Found Plex config at:[/] {discovered.source}")
        console.print(f"  URL: [cyan]{discovered.url}[/]")
        console.print()

        use_discovered = Confirm.ask("Use auto-discovered config?", default=True)
        if use_discovered:
            url = discovered.url
            token = discovered.token
        else:
            # Manual entry
            current_url = settings.plex_url or "http://localhost:32400"
            url = Prompt.ask("Plex server URL", default=current_url)

            console.print()
            console.print("[bold]To get your Plex API token:[/]")
            console.print("  1. Open Plex in your browser and sign in")
            console.print("  2. Go to any media item and click [cyan]Get Info[/]")
            console.print("  3. Click [cyan]View XML[/] at the bottom")
            console.print("  4. Find [cyan]X-Plex-Token[/] in the URL")
            console.print()
            console.print("  Or visit: [cyan]https://support.plex.tv/articles/204059436/[/]")
            console.print()

            token = Prompt.ask("Plex API token", default="", password=True)

            if not token.strip():
                console.print("[yellow]No API token provided. Setup cancelled.[/]")
                console.print()
                return
    else:
        console.print("[dim]No local Plex installation found.[/]")
        console.print()

        # Get Plex URL
        current_url = settings.plex_url or "http://localhost:32400"
        url = Prompt.ask("Plex server URL", default=current_url)

        # Get API token
        console.print()
        console.print("[bold]To get your Plex API token:[/]")
        console.print("  1. Open Plex in your browser and sign in")
        console.print("  2. Go to any media item and click [cyan]Get Info[/]")
        console.print("  3. Click [cyan]View XML[/] at the bottom")
        console.print("  4. Find [cyan]X-Plex-Token[/] in the URL")
        console.print()
        console.print("  Or visit: [cyan]https://support.plex.tv/articles/204059436/[/]")
        console.print()

        token = Prompt.ask("Plex API token", default="", password=True)

        if not token.strip():
            console.print("[yellow]No API token provided. Setup cancelled.[/]")
            console.print()
            return

    # Test connection and get libraries
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Connecting to Plex...", total=None)

        try:
            from jackmediaman.services.plex import PlexService

            service = PlexService(url=url, token=token.strip())
            libraries = service.get_libraries()

            if not libraries:
                progress.update(task, description="[red]Could not connect to Plex[/]")
                console.print()
                console.print("[red]Could not connect to Plex server.[/]")
                console.print("[dim]Check the URL and token, and ensure Plex is running.[/]")
                console.print()
                return

            progress.update(task, description="[green]Connected to Plex![/]")

        except Exception as e:
            progress.update(task, description=f"[red]Error: {e}[/]")
            console.print()
            console.print(f"[red]Connection error: {e}[/]")
            console.print()
            return

    # Show discovered libraries
    console.print()
    console.print("[bold]Libraries found:[/]")
    for lib in libraries:
        lib_type = "movie" if lib.type == "movie" else "show"
        console.print(f"  [cyan]{lib.title}[/] ({lib_type})")
        for loc in lib.locations:
            console.print(f"    [dim]{loc}[/]")
    console.print()

    # Check if media paths match Plex library locations
    settings = get_settings()
    plex_paths = set()
    for lib in libraries:
        for loc in lib.locations:
            plex_paths.add(str(loc))

    movies_in_plex = any(str(settings.movies_dir).startswith(p) or p.startswith(str(settings.movies_dir)) for p in plex_paths)
    tv_in_plex = any(str(settings.tv_dir).startswith(p) or p.startswith(str(settings.tv_dir)) for p in plex_paths)

    if not movies_in_plex and not tv_in_plex:
        console.print("[yellow]Warning: Your media directories don't appear to match Plex library locations.[/]")
        console.print(f"[dim]Movies: {settings.movies_dir}[/]")
        console.print(f"[dim]TV: {settings.tv_dir}[/]")
        console.print("[dim]Plex notifications may not work unless paths match.[/]")
        console.print()

    # Save settings
    save_setting("JMM_PLEX_URL", url)
    save_setting("JMM_PLEX_API_TOKEN", token.strip())
    save_setting("JMM_PLEX_NOTIFY_ENABLED", "true")
    reload_settings()

    console.print("[green]Plex settings saved![/]")
    console.print()
    console.print("Plex will now be notified when:")
    console.print("  - New media is processed (jmm process)")
    console.print("  - Files are renamed (jmm rename)")
    console.print("  - Duplicates are removed (jmm clean)")
    console.print()


@app.command("shell")
def setup_shell(
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be changed without modifying files"),
) -> None:
    """Configure shell PATH for user-installed JackMediaMan.

    This command adds ~/.local/bin to your PATH so you can run 'jmm' from anywhere.
    Useful for seedbox or user installations where pip installs to ~/.local/bin.
    """
    import os
    from pathlib import Path

    local_bin = Path.home() / ".local" / "bin"

    console.print()
    console.print(Panel(
        "[bold]Shell PATH Configuration[/]\n\n"
        "This will add ~/.local/bin to your PATH so 'jmm' can be run from anywhere.\n"
        "Required for pip install --user installations.",
        border_style="cyan",
    ))
    console.print()

    # Check if already in PATH
    path_dirs = os.environ.get("PATH", "").split(":")
    if str(local_bin) in path_dirs:
        console.print("[green]~/.local/bin is already in your PATH![/]")
        console.print()
        return

    # Detect shell and rc file
    shell = os.environ.get("SHELL", "/bin/bash")
    shell_name = Path(shell).name

    rc_files: dict[str, list[str]] = {
        "bash": [".bashrc", ".bash_profile"],
        "zsh": [".zshrc"],
        "fish": [".config/fish/config.fish"],
    }

    rc_candidates = rc_files.get(shell_name, [".bashrc", ".profile"])

    # Find existing rc file or use first candidate
    rc_file = None
    for candidate in rc_candidates:
        path = Path.home() / candidate
        if path.exists():
            rc_file = path
            break
    if not rc_file:
        rc_file = Path.home() / rc_candidates[0]

    # The line to add
    if shell_name == "fish":
        path_line = 'set -gx PATH "$HOME/.local/bin" $PATH'
    else:
        path_line = 'export PATH="$HOME/.local/bin:$PATH"'

    # Check if already configured in rc file
    if rc_file.exists():
        content = rc_file.read_text()
        if ".local/bin" in content:
            console.print(f"[green]PATH already configured in {rc_file}[/]")
            console.print()
            console.print("To activate, run:")
            console.print(f"  [cyan]source {rc_file}[/]")
            console.print()
            return

    if dry_run:
        console.print(f"[cyan]Would add to {rc_file}:[/]")
        console.print(f"  {path_line}")
        console.print()
        return

    # Add to rc file
    console.print(f"Adding to [cyan]{rc_file}[/]...")
    with open(rc_file, "a") as f:
        f.write(f"\n# JackMediaMan PATH\n{path_line}\n")

    console.print()
    console.print("[green]Shell configured![/]")
    console.print()
    console.print("To activate now, run:")
    console.print(f"  [cyan]source {rc_file}[/]")
    console.print()
    console.print("Or start a new terminal session.")
    console.print()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Configure external services interactively."""
    if ctx.invoked_subcommand is None:
        _show_service_status()
