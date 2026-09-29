"""Subtitles command for downloading subtitles via OpenSubtitles."""

from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from jackmediaman.core.config import get_settings
from jackmediaman.services.subtitles import (
    SubtitleService,
    SubtitleResult,
    VIDEO_EXTENSIONS,
    find_placeholder_subtitles,
    subtitle_exists,
)

app = typer.Typer(help="Download subtitles for media files")
console = Console()


class MediaType(str, Enum):
    """Type of media to process."""

    tv = "tv"
    movies = "movies"
    both = "both"


def _check_api_key() -> bool:
    """Check if at least one OpenSubtitles provider is configured.

    Returns True if configured, False otherwise.
    """
    settings = get_settings()

    com_configured = bool(settings.opensubtitles_com_api_key)
    org_configured = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)

    if com_configured or org_configured:
        return True

    console.print()
    console.print("[yellow]No OpenSubtitles providers configured[/]")
    console.print()
    console.print("Run [cyan]jmm setup opensubtitles[/] to configure")
    console.print()
    return False


def _create_progress() -> Progress:
    """Create a progress bar for subtitle downloads with real-time stats."""
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TextColumn("{task.fields[stats]}"),
        TextColumn("[dim]{task.fields[filename]}"),
        console=console,
    )


def _display_results(results: List[SubtitleResult], dry_run: bool = False) -> None:
    """Display subtitle download results in a Rich table."""
    downloaded = [r for r in results if r.success and not r.skipped]
    skipped = [r for r in results if r.skipped]
    failed = [r for r in results if not r.success and not r.skipped]

    # Group downloaded by provider
    by_provider = {"com": [], "org": [], "unknown": []}
    for r in downloaded:
        if r.provider == "com":
            by_provider["com"].append(r)
        elif r.provider == "org":
            by_provider["org"].append(r)
        else:
            by_provider["unknown"].append(r)

    console.print()
    mode_text = "[yellow]DRY RUN - No files downloaded[/]" if dry_run else ""

    # Build summary with provider breakdown
    summary_lines = [
        "[bold]Subtitle Download Results[/]",
        "",
        f"Downloaded: [green]{len(downloaded)}[/]",
    ]

    # Show provider breakdown if any downloads
    if downloaded:
        if by_provider["com"]:
            summary_lines.append(f"  • OpenSubtitles.com: [green]{len(by_provider['com'])}[/]")
        if by_provider["org"]:
            summary_lines.append(f"  • OpenSubtitles.org: [green]{len(by_provider['org'])}[/]")

    summary_lines.extend([
        f"Skipped: [dim]{len(skipped)}[/]",
        f"Not found: [red]{len(failed)}[/]",
    ])

    if mode_text:
        summary_lines.append(mode_text)

    console.print(
        Panel(
            "\n".join(summary_lines),
            title="[bold cyan]Results[/]",
            border_style="cyan",
        )
    )

    # Show downloaded subtitles with provider info
    if downloaded:
        console.print()
        table = Table(title="Downloaded Subtitles", show_header=True)
        table.add_column("Video File", style="cyan")
        table.add_column("Language", style="green")
        table.add_column("Provider", style="magenta")
        table.add_column("Subtitle", style="dim")

        for result in downloaded[:20]:
            provider_display = "com" if result.provider == "com" else "org"
            table.add_row(
                result.video_path.name[:40]
                + ("..." if len(result.video_path.name) > 40 else ""),
                result.language,
                provider_display,
                result.subtitle_path.name if result.subtitle_path else "",
            )

        if len(downloaded) > 20:
            table.add_row(f"[dim]... and {len(downloaded) - 20} more[/]", "", "", "")

        console.print(table)

    # Show failed downloads
    if failed:
        console.print()
        console.print("[bold red]Not Found:[/]")
        for result in failed[:10]:
            error_msg = result.error or "No subtitles found"
            console.print(f"  [red]•[/] {result.video_path.name[:50]}: {error_msg}")

        if len(failed) > 10:
            console.print(f"  [dim]... and {len(failed) - 10} more[/]")

    # Show skipped summary
    if skipped:
        console.print()
        console.print(f"[dim]Skipped {len(skipped)} files (subtitles already exist)[/]")


@app.command("download")
def download(
    path: Optional[Path] = typer.Argument(
        None,
        help="File or directory to download subtitles for",
    ),
    media_type: Optional[MediaType] = typer.Option(
        None,
        "--type",
        "-t",
        help="Media type to process (tv, movies, or both). Use instead of path for library-wide.",
    ),
    language: Optional[str] = typer.Option(
        None,
        "--language",
        "-l",
        help="Subtitle languages (comma-separated, e.g., 'en,es'). Defaults to settings.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-o",
        help="Overwrite existing subtitle files",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be downloaded without actually downloading",
    ),
) -> None:
    """Download subtitles for media files.

    Examples:

        jmm subtitles download /path/to/video.mkv
        jmm subtitles download /path/to/show/
        jmm subtitles download --type tv
        jmm subtitles download --type both -l en,es
    """
    if not _check_api_key():
        raise typer.Exit(1)

    settings = get_settings()

    # Parse languages
    languages = None
    if language:
        languages = [lang.strip() for lang in language.split(",")]

    console.print()
    console.print(
        Panel(
            "[bold]JackMediaMan - Subtitle Downloader[/]\n\n"
            "Download subtitles from OpenSubtitles.com",
            border_style="cyan",
        )
    )

    service = SubtitleService()
    results: List[SubtitleResult] = []

    # Determine what to scan
    if path:
        # Single file or directory
        path = path.resolve()
        if not path.exists():
            console.print(f"\n[red]Path not found: {path}[/]\n")
            raise typer.Exit(1)

        if path.is_file():
            # Single file
            console.print(f"\n[dim]Processing: {path.name}[/]")

            if dry_run:
                # For dry run, just check if subtitle exists
                for lang in languages or [
                    settings.subtitle_languages.split(",")[0].strip()
                ]:
                    subtitle_path = path.with_suffix(f".{lang}.srt")
                    if subtitle_exists(subtitle_path) and not overwrite:
                        results.append(
                            SubtitleResult(
                                video_path=path,
                                subtitle_path=subtitle_path,
                                language=lang,
                                success=True,
                                skipped=True,
                                skip_reason="Subtitle already exists",
                            )
                        )
                    else:
                        results.append(
                            SubtitleResult(
                                video_path=path,
                                language=lang,
                                success=True,
                                skipped=False,
                            )
                        )
            else:
                result = service.download_for_file(path, languages, overwrite)
                results.append(result)
        else:
            # Directory - scan with real-time stats
            video_files = [
                f
                for f in path.rglob("*")
                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
            ]

            # Track stats for real-time display
            stats = {"com": 0, "org": 0, "skipped": 0, "failed": 0}

            def format_stats() -> str:
                return f"[green]com:{stats['com']}[/] [cyan]org:{stats['org']}[/] [red]✗:{stats['failed']}[/]"

            with _create_progress() as progress:
                task = progress.add_task(
                    "Downloading", total=len(video_files), filename="Starting...", stats=""
                )

                for i, video_path in enumerate(video_files):
                    progress.update(
                        task,
                        completed=i,
                        filename=video_path.name[:35],
                        stats=format_stats(),
                    )

                    if dry_run:
                        # Dry run: just check if subtitle exists
                        for lang in languages or [
                            settings.subtitle_languages.split(",")[0].strip()
                        ]:
                            subtitle_path = video_path.with_suffix(f".{lang}.srt")
                            if subtitle_exists(subtitle_path) and not overwrite:
                                results.append(
                                    SubtitleResult(
                                        video_path=video_path,
                                        subtitle_path=subtitle_path,
                                        language=lang,
                                        success=True,
                                        skipped=True,
                                        skip_reason="Subtitle already exists",
                                    )
                                )
                                stats["skipped"] += 1
                            else:
                                results.append(
                                    SubtitleResult(
                                        video_path=video_path,
                                        language=lang,
                                        success=True,
                                        skipped=False,
                                    )
                                )
                    else:
                        # Actually download
                        result = service.download_for_file(video_path, languages, overwrite)
                        results.append(result)

                        # Update stats based on result
                        if result.skipped:
                            stats["skipped"] += 1
                        elif result.success:
                            stats[result.provider or "com"] += 1
                        else:
                            stats["failed"] += 1

                        if service.stop_reason:
                            break

                # Final update
                progress.update(task, completed=len(video_files), stats=format_stats())

    elif media_type:
        # Library-wide scan with real-time stats
        directories = []
        if media_type in (MediaType.tv, MediaType.both):
            if settings.tv_dir.exists():
                directories.append(settings.tv_dir)
        if media_type in (MediaType.movies, MediaType.both):
            if settings.movies_dir.exists():
                directories.append(settings.movies_dir)

        # Scan for all video files
        video_files = []
        for directory in directories:
            video_files.extend(
                [
                    f
                    for f in directory.rglob("*")
                    if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
                ]
            )

        # Track stats for real-time display
        stats = {"com": 0, "org": 0, "skipped": 0, "failed": 0}

        def format_stats() -> str:
            return f"[green]com:{stats['com']}[/] [cyan]org:{stats['org']}[/] [red]✗:{stats['failed']}[/]"

        with _create_progress() as progress:
            task = progress.add_task(
                "Downloading", total=len(video_files), filename="Starting...", stats=""
            )

            for i, video_path in enumerate(video_files):
                progress.update(
                    task,
                    completed=i,
                    filename=video_path.name[:35],
                    stats=format_stats(),
                )

                if dry_run:
                    # Dry run: just check if subtitle exists
                    for lang in languages or [
                        settings.subtitle_languages.split(",")[0].strip()
                    ]:
                        subtitle_path = video_path.with_suffix(f".{lang}.srt")
                        if subtitle_exists(subtitle_path) and not overwrite:
                            results.append(
                                SubtitleResult(
                                    video_path=video_path,
                                    subtitle_path=subtitle_path,
                                    language=lang,
                                    success=True,
                                    skipped=True,
                                    skip_reason="Subtitle already exists",
                                )
                            )
                            stats["skipped"] += 1
                        else:
                            results.append(
                                SubtitleResult(
                                    video_path=video_path,
                                    language=lang,
                                    success=True,
                                    skipped=False,
                                )
                            )
                else:
                    # Actually download
                    result = service.download_for_file(video_path, languages, overwrite)
                    results.append(result)

                    # Update stats based on result
                    if result.skipped:
                        stats["skipped"] += 1
                    elif result.success:
                        stats[result.provider or "com"] += 1
                    else:
                        stats["failed"] += 1

                    if service.stop_reason:
                        break

            # Final update
            progress.update(task, completed=len(video_files), stats=format_stats())
    else:
        # No path or type specified - show help
        console.print()
        console.print("[yellow]Please specify a path or --type option[/]")
        console.print()
        console.print("Examples:")
        console.print("  jmm subtitles download /path/to/video.mkv")
        console.print("  jmm subtitles download /path/to/show/")
        console.print("  jmm subtitles download --type tv")
        console.print("  jmm subtitles download --type both")
        console.print()
        raise typer.Exit(1)

    _display_results(results, dry_run)

    if service.stop_reason:
        console.print()
        console.print(f"[bold yellow]Stopped early:[/] {service.stop_reason}")
    console.print()


@app.command("purge-ads")
def purge_ads(
    media_type: MediaType = typer.Option(
        MediaType.both,
        "--type",
        "-t",
        help="Media type to clean (tv, movies, or both)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="List the ad subtitles without deleting them",
    ),
) -> int:
    """Delete OpenSubtitles ad placeholders saved as .srt files.

    Examples:

        jmm subtitles purge-ads --dry-run
        jmm subtitles purge-ads --type tv
    """
    # Returns the number of ad subtitles found (used by the interactive menu)
    settings = get_settings()

    directories = []
    if media_type in (MediaType.tv, MediaType.both):
        directories.append(settings.tv_dir)
    if media_type in (MediaType.movies, MediaType.both):
        directories.append(settings.movies_dir)

    ads: List[Path] = []
    with console.status("Scanning for ad subtitles..."):
        for directory in directories:
            ads.extend(find_placeholder_subtitles(directory))

    console.print()
    if not ads:
        console.print("[green]No ad subtitles found[/]")
        console.print()
        return 0

    if dry_run:
        for ad in ads:
            console.print(f"  [dim]{ad}[/]")
        console.print()
        console.print(f"[yellow]DRY RUN[/] - would delete {len(ads)} ad subtitles")
        console.print()
        return len(ads)

    deleted = 0
    for ad in ads:
        try:
            ad.unlink()
            deleted += 1
        except OSError as e:
            console.print(f"  [red]Could not delete {ad}: {e}[/]")

    console.print(f"[green]Deleted {deleted} ad subtitles[/]")
    console.print()
    return len(ads)


@app.command("status")
def status() -> None:
    """Show OpenSubtitles configuration status."""
    from jackmediaman.services.subtitles import (
        OpenSubtitlesOrgClient,
        OpenSubtitlesComClient,
    )

    settings = get_settings()

    console.print()
    console.print(Panel("[bold]OpenSubtitles Status[/]", border_style="cyan"))
    console.print()

    # Check what's configured
    has_com = bool(settings.opensubtitles_com_api_key)
    has_org = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)

    if not has_com and not has_org:
        console.print("[yellow]No providers configured[/]")
        console.print()
        console.print("Run [cyan]jmm setup opensubtitles[/] to configure")
        console.print()
        return

    console.print(f"Preferred languages: [cyan]{settings.subtitle_languages}[/]")
    console.print()

    # Show .com status
    console.print("[bold]OpenSubtitles.com:[/]")
    if has_com:
        console.print(f"  [green]✓[/] API key: {settings.opensubtitles_com_api_key[:8]}...")

        console.print("  [dim]Validating...[/]", end=" ")
        try:
            client = OpenSubtitlesComClient()
            if client.validate_credentials():
                console.print("[green]Valid[/]")
            else:
                console.print("[red]Invalid API key[/]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")
    else:
        console.print("  [dim]○ Not configured[/]")

    console.print()

    # Show .org status
    console.print("[bold]OpenSubtitles.org:[/]")
    if has_org:
        console.print(f"  [green]✓[/] Username: {settings.opensubtitles_org_username}")

        console.print("  [dim]Validating...[/]", end=" ")
        try:
            client = OpenSubtitlesOrgClient()
            if client.validate_credentials():
                console.print("[green]Valid[/]")
            else:
                console.print("[red]Invalid credentials[/]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")
    else:
        console.print("  [dim]○ Not configured[/]")

    # Show fallback status
    if has_com and has_org:
        console.print()
        console.print("[green]✓[/] Both providers configured - .com first, .org as fallback")

    console.print()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Download subtitles for media files."""
    if ctx.invoked_subcommand is None:
        # Show help and status
        console.print()
        console.print(
            Panel(
                "[bold]JackMediaMan - Subtitle Downloader[/]\n\n"
                "Download subtitles from OpenSubtitles\n\n"
                "[dim]Commands:[/]\n"
                "  jmm subtitles download <path>  Download for file/directory\n"
                "  jmm subtitles download --type tv  Download for TV library\n"
                "  jmm subtitles purge-ads        Delete ad placeholder subtitles\n"
                "  jmm subtitles status           Check API configuration",
                border_style="cyan",
            )
        )
        console.print()

        # Check if configured (either provider)
        settings = get_settings()
        has_com = bool(settings.opensubtitles_com_api_key)
        has_org = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)

        if not has_com and not has_org:
            console.print("[yellow]OpenSubtitles not configured[/]")
            console.print("Run [cyan]jmm setup opensubtitles[/] to get started")
            console.print()
        else:
            providers = []
            if has_com:
                providers.append(".com")
            if has_org:
                providers.append(".org")
            console.print(f"[green]OpenSubtitles configured[/] ({', '.join(providers)})")
            console.print(f"Languages: [cyan]{settings.subtitle_languages}[/]")
            console.print()
