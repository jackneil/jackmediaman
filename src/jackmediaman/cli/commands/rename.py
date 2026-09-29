"""Rename command for standardizing media filenames."""

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
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    MofNCompleteColumn,
)
from rich.prompt import Prompt
from rich.table import Table

from jackmediaman.core.config import get_settings, reload_settings, save_setting
from jackmediaman.models.media import MediaItem, Movie, Episode
from jackmediaman.scanners.tv import TVScanner
from jackmediaman.scanners.movies import MovieScanner
from jackmediaman.services.renamer import RenameService, RenameResult
from jackmediaman.services.metadata_prober import get_metadata_prober
from jackmediaman.cli.interactive import show_menu, confirm_action

app = typer.Typer(help="Rename media files to standardized format")
console = Console()


class MediaType(str, Enum):
    """Type of media to rename."""
    tv = "tv"
    movies = "movies"
    both = "both"


def _check_tmdb_api_key(media_type: MediaType) -> bool:
    """Check if TMDB API key is configured, prompt if not.

    Returns True if we can proceed, False if user aborted.
    """
    settings = get_settings()

    if settings.tmdb_api_key:
        return True

    # Only critical for TV (episodes need titles)
    if media_type == MediaType.movies:
        console.print("[yellow]Note: TMDB not configured - using parsed title/year[/]")
        return True

    console.print()
    console.print("[yellow]TMDB API key not configured[/]")
    console.print("[dim]Episode titles require TMDB API access[/]")
    console.print()

    api_key = Prompt.ask(
        "Enter your TMDB API key (get one at [cyan]themoviedb.org[/])",
        default="",
    )

    if not api_key.strip():
        console.print("[red]No API key provided. Aborting.[/]")
        raise typer.Exit(1)

    # Save to env file
    save_setting("JMM_TMDB_API_KEY", api_key.strip())
    reload_settings()

    console.print("[green]API key saved![/]")
    console.print()
    return True


def _create_progress() -> Progress:
    """Create a progress bar with time estimates."""
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        TextColumn("[dim]{task.fields[filename]}"),
        console=console,
    )


def _display_preview(results: List[RenameResult], dry_run: bool = True) -> None:
    """Display rename preview in a Rich table."""
    # Filter to only items that would change
    changes = [r for r in results if not r.skipped]
    skipped = [r for r in results if r.skipped]

    if not changes:
        console.print("\n[green]No files need renaming![/]\n")
        if skipped:
            console.print(f"[dim]{len(skipped)} files already named correctly[/]")
        return

    console.print()
    mode_text = "[yellow]DRY RUN - No files will be changed[/]" if dry_run else "[green]EXECUTE MODE[/]"
    console.print(Panel(
        f"[bold]Rename Preview[/]\n"
        f"Files to rename: [cyan]{len(changes)}[/]\n"
        f"Files skipped: [dim]{len(skipped)}[/]\n\n"
        f"{mode_text}",
        title="[bold cyan]Rename Results[/]",
        border_style="cyan",
    ))
    console.print()

    # Build table
    table = Table(
        title="Files to Rename",
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("#", style="dim", width=4)
    table.add_column("Current Name", style="red", no_wrap=False)
    table.add_column("New Name", style="green", no_wrap=False)
    table.add_column("Status", style="yellow")

    for i, result in enumerate(changes, 1):
        if result.error:
            status = f"[red]ERROR: {result.error}[/]"
        elif result.success:
            status = "[green]OK[/]" if not dry_run else "[dim]WILL RENAME[/]"
        else:
            status = "[red]FAILED[/]"

        old_name = result.old_path.name
        new_name = result.new_path.name

        # Truncate long names
        if len(old_name) > 50:
            old_name = old_name[:47] + "..."
        if len(new_name) > 50:
            new_name = new_name[:47] + "..."

        table.add_row(str(i), old_name, new_name, status)

    console.print(table)

    # Show skipped items summary
    if skipped:
        console.print(f"\n[dim]Skipped {len(skipped)} files (already named correctly)[/]")


def _scan_media(media_type: MediaType) -> List[MediaItem]:
    """Scan media directories and return items with accurate metadata."""
    settings = get_settings()
    items: List[MediaItem] = []

    # Initialize metadata prober for accurate quality detection (resolution from ffprobe)
    prober = None
    if settings.ffprobe_enabled:
        prober = get_metadata_prober(
            cache_enabled=True,
            max_workers=settings.ffprobe_workers,
        )
        if not prober.is_available:
            console.print("[yellow]Warning: ffprobe not found, using filename-only quality detection[/]")
            prober = None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[filename]}[/]"),
        console=console,
    ) as progress:
        # Scan TV Shows
        if media_type in (MediaType.tv, MediaType.both):
            task = progress.add_task("Scanning TV Shows...", total=None, filename="")
            scanner = TVScanner(metadata_prober=prober)
            if prober:
                # Use scan_with_metadata for accurate resolution detection
                tv_items = scanner.scan_with_metadata(
                    settings.tv_dir,
                    progress_callback=lambda c, t, f: progress.update(
                        task, completed=c, total=t, filename=f[:60]
                    ),
                )
            else:
                tv_items = list(scanner.scan(settings.tv_dir))
            items.extend(tv_items)
            progress.update(task, description=f"[green]TV Shows: {len(tv_items)} files[/]", filename="")

        # Scan Movies
        if media_type in (MediaType.movies, MediaType.both):
            task = progress.add_task("Scanning Movies...", total=None, filename="")
            scanner = MovieScanner(metadata_prober=prober)
            if prober:
                movie_items = scanner.scan_with_metadata(
                    settings.movies_dir,
                    progress_callback=lambda c, t, f: progress.update(
                        task, completed=c, total=t, filename=f[:60]
                    ),
                )
            else:
                movie_items = list(scanner.scan(settings.movies_dir))
            items.extend(movie_items)
            progress.update(task, description=f"[green]Movies: {len(movie_items)} files[/]", filename="")

    return items


@app.command("preview")
def preview(
    media_type: MediaType = typer.Option(
        MediaType.both,
        "--type", "-t",
        help="Type of media to rename",
    ),
) -> None:
    """Preview file renames without making changes."""
    console.print()
    console.print(Panel(
        "[bold]JackMediaMan - Media Renamer[/]\n\n"
        "Preview standardized filenames for your media library.",
        border_style="cyan",
    ))

    # Check TMDB API key (prompts if missing for TV)
    _check_tmdb_api_key(media_type)

    # Scan media
    items = _scan_media(media_type)

    if not items:
        console.print("\n[yellow]No media files found[/]\n")
        return

    # Generate rename previews
    service = RenameService()

    with _create_progress() as progress:
        task = progress.add_task("Processing", total=len(items), filename="")

        def update_progress(current, total, filename):
            progress.update(task, completed=current, filename=filename[:40])

        summary = service.rename_items(items, dry_run=True, progress_callback=update_progress)

    _display_preview(summary.results, dry_run=True)


@app.command("execute")
def execute(
    media_type: MediaType = typer.Option(
        MediaType.both,
        "--type", "-t",
        help="Type of media to rename",
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Execute file renames."""
    console.print()
    console.print(Panel(
        "[bold]JackMediaMan - Media Renamer[/]\n\n"
        "Rename media files to standardized format.",
        border_style="cyan",
    ))

    # Check TMDB API key (prompts if missing for TV)
    _check_tmdb_api_key(media_type)

    # Scan media
    items = _scan_media(media_type)

    if not items:
        console.print("\n[yellow]No media files found[/]\n")
        return

    # Generate rename previews first
    service = RenameService()

    with _create_progress() as progress:
        task = progress.add_task("Processing", total=len(items), filename="")

        def update_progress(current, total, filename):
            progress.update(task, completed=current, filename=filename[:40])

        preview_summary = service.rename_items(items, dry_run=True, progress_callback=update_progress)

    _display_preview(preview_summary.results, dry_run=True)

    # Check if there are any changes to make
    changes = [r for r in preview_summary.results if not r.skipped and r.success]
    if not changes:
        return

    # Confirm execution
    if not yes:
        console.print()
        if not confirm_action(f"Rename {len(changes)} files?", default=False):
            console.print("[yellow]Cancelled[/]")
            return

    # Execute renames
    console.print()
    with _create_progress() as progress:
        task = progress.add_task("Renaming", total=len(items), filename="")

        def update_progress(current, total, filename):
            progress.update(task, completed=current, filename=filename[:40])

        summary = service.rename_items(items, dry_run=False, progress_callback=update_progress)

    console.print()
    console.print(Panel(
        f"[bold green]Rename Complete[/]\n\n"
        f"Files renamed: [green]{summary.renamed}[/]\n"
        f"Files skipped: [dim]{summary.skipped}[/]\n"
        f"Errors: [red]{summary.failed}[/]",
        border_style="green",
    ))

    # Show errors if any
    errors = [r for r in summary.results if r.error]
    if errors:
        console.print("\n[bold red]Errors:[/]")
        for r in errors:
            console.print(f"  [red]•[/] {r.old_path.name}: {r.error}")


def _run_interactive_rename() -> None:
    """Run interactive rename mode."""
    console.print()
    console.print(Panel(
        "[bold]JackMediaMan - Media Renamer[/]\n\n"
        "Rename media files to standardized format.\n"
        "[dim]TV: Show Name - S01E01 - Episode Title.ext[/]\n"
        "[dim]Movie: Movie Name (Year).ext[/]",
        border_style="cyan",
    ))

    # Select media type
    media_choice = show_menu(
        "What would you like to rename?",
        [
            ("TV Shows", "Rename TV show episodes"),
            ("Movies", "Rename movie files"),
            ("Both", "Rename all media files"),
        ],
        default=3,
    )
    media_type = [MediaType.tv, MediaType.movies, MediaType.both][media_choice - 1]

    # Check TMDB API key (prompts if missing for TV)
    _check_tmdb_api_key(media_type)

    # Scan media
    items = _scan_media(media_type)

    if not items:
        console.print("\n[yellow]No media files found[/]\n")
        return

    # Generate rename previews
    service = RenameService()

    with _create_progress() as progress:
        task = progress.add_task("Processing", total=len(items), filename="")

        def update_progress(current, total, filename):
            progress.update(task, completed=current, filename=filename[:40])

        preview_summary = service.rename_items(items, dry_run=True, progress_callback=update_progress)

    _display_preview(preview_summary.results, dry_run=True)

    # Check if there are any changes to make
    changes = [r for r in preview_summary.results if not r.skipped and r.success]
    if not changes:
        return

    # Ask about execution
    action_choice = show_menu(
        "What would you like to do?",
        [
            ("Execute", "Rename the files"),
            ("Cancel", "Exit without renaming"),
        ],
        default=1,
    )

    if action_choice != 1:
        console.print("[yellow]Cancelled[/]")
        return

    # Execute renames
    console.print()
    with _create_progress() as progress:
        task = progress.add_task("Renaming", total=len(items), filename="")

        def update_progress(current, total, filename):
            progress.update(task, completed=current, filename=filename[:40])

        summary = service.rename_items(items, dry_run=False, progress_callback=update_progress)

    console.print()
    console.print(Panel(
        f"[bold green]Rename Complete[/]\n\n"
        f"Files renamed: [green]{summary.renamed}[/]\n"
        f"Files skipped: [dim]{summary.skipped}[/]\n"
        f"Errors: [red]{summary.failed}[/]",
        border_style="green",
    ))


@app.command("file")
def rename_file(
    path: Path = typer.Argument(
        ...,
        help="Path to file to rename",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Rename a single file."""
    from datetime import datetime
    from guessit import guessit

    from jackmediaman.models.quality import QualityParser

    console.print()
    console.print(f"[cyan]File:[/] {path.name}")

    # Use guessit to parse the filename
    guess = guessit(path.name)
    media_type = guess.get("type")
    quality_parser = QualityParser()
    quality = quality_parser.parse(path.name)

    stat = path.stat()
    is_symlink = path.is_symlink()

    item = None

    if media_type == "episode":
        # TV Episode
        show_name = guess.get("title", "Unknown")
        season = guess.get("season", 1)
        episode = guess.get("episode")

        # Handle multiple episodes
        if isinstance(episode, list):
            episode_numbers = episode
        elif episode:
            episode_numbers = [episode]
        else:
            console.print("[red]Could not detect episode number from filename[/]")
            return

        item = Episode(
            path=path,
            filename=path.name,
            size_bytes=stat.st_size,
            quality=quality,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            is_symlink=is_symlink,
            symlink_target=path.resolve() if is_symlink else None,
            series_name=show_name,
            season_number=season,
            episode_numbers=episode_numbers,
        )
        console.print(f"[dim]Detected:[/] TV Episode - {show_name} S{season:02d}E{episode_numbers[0]:02d}")

    elif media_type == "movie":
        # Movie
        title = guess.get("title", "Unknown")
        year = guess.get("year")

        item = Movie(
            path=path,
            filename=path.name,
            size_bytes=stat.st_size,
            quality=quality,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            is_symlink=is_symlink,
            symlink_target=path.resolve() if is_symlink else None,
            title=title,
            year=year,
        )
        year_str = f" ({year})" if year else ""
        console.print(f"[dim]Detected:[/] Movie - {title}{year_str}")

    else:
        console.print("[red]Could not identify media type from filename[/]")
        console.print("[dim]Expected TV episode (S01E01) or movie format[/]")
        return

    # Generate rename preview
    service = RenameService()
    summary = service.rename_items([item], dry_run=True)

    if not summary.results:
        console.print("[yellow]Could not generate rename[/]")
        return

    result = summary.results[0]

    if result.skipped:
        console.print("\n[green]File already named correctly![/]")
        return

    if result.error:
        console.print(f"\n[red]Error: {result.error}[/]")
        return

    console.print()
    console.print(f"[red]Current:[/] {result.old_path.name}")
    console.print(f"[green]New:[/]     {result.new_path.name}")

    # Confirm and execute
    if not yes:
        console.print()
        if not confirm_action("Rename this file?", default=True):
            console.print("[yellow]Cancelled[/]")
            return

    # Execute the rename
    summary = service.rename_items([item], dry_run=False)
    result = summary.results[0]

    if result.success:
        console.print("\n[green]✓ File renamed successfully![/]")
    else:
        console.print(f"\n[red]✗ Rename failed: {result.error}[/]")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Rename media files to standardized format."""
    if ctx.invoked_subcommand is None:
        _run_interactive_rename()
