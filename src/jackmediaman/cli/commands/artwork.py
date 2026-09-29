"""Artwork command for downloading poster images from TMDb."""

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
from jackmediaman.services.artwork import ArtworkService, ArtworkResult

app = typer.Typer(help="Download poster artwork for media files")
console = Console()


class MediaType(str, Enum):
    """Type of media to process."""

    tv = "tv"
    movies = "movies"
    both = "both"


def _check_api_key() -> bool:
    """Check if TMDb API key is configured.

    Returns True if configured, False otherwise.
    """
    settings = get_settings()

    if settings.tmdb_api_key:
        return True

    console.print()
    console.print("[yellow]TMDb API key not configured[/]")
    console.print()
    console.print("Run [cyan]jmm setup tmdb[/] to configure interactively")
    console.print()
    return False


def _create_progress() -> Progress:
    """Create a progress bar for downloads."""
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("•"),
        TimeRemainingColumn(),
        TextColumn("[dim]{task.fields[name]}"),
        console=console,
    )


def _display_results(results: List[ArtworkResult], dry_run: bool = False) -> None:
    """Display artwork download results."""
    downloaded = [r for r in results if r.success and not r.skipped]
    skipped = [r for r in results if r.skipped]
    failed = [r for r in results if not r.success and not r.skipped]

    console.print()
    mode_text = "[yellow]DRY RUN - No files downloaded[/]" if dry_run else ""
    console.print(
        Panel(
            f"[bold]Artwork Download Results[/]\n"
            f"Downloaded: [green]{len(downloaded)}[/]\n"
            f"Skipped: [dim]{len(skipped)}[/]\n"
            f"Failed: [red]{len(failed)}[/]\n"
            f"{mode_text}",
            title="[bold cyan]Results[/]",
            border_style="cyan",
        )
    )

    # Show downloaded items
    if downloaded:
        console.print()
        table = Table(title="Downloaded Posters", show_header=True)
        table.add_column("Type", style="cyan")
        table.add_column("Path", style="white")

        for result in downloaded[:20]:
            table.add_row(
                result.artwork_type.replace("_", " ").title(),
                str(result.path.name),
            )

        if len(downloaded) > 20:
            table.add_row("", f"[dim]... and {len(downloaded) - 20} more[/]")

        console.print(table)

    # Show failed downloads
    if failed:
        console.print()
        console.print("[bold red]Failed Downloads:[/]")
        for result in failed[:10]:
            console.print(f"  [red]•[/] {result.media_path.name}: {result.error}")

        if len(failed) > 10:
            console.print(f"  [dim]... and {len(failed) - 10} more failures[/]")

    # Show skipped summary
    if skipped:
        console.print()
        console.print(f"[dim]Skipped {len(skipped)} items (posters already exist)[/]")


@app.command("download")
def download(
    path: Optional[Path] = typer.Argument(
        None,
        help="Specific folder to download artwork for",
    ),
    media_type: Optional[MediaType] = typer.Option(
        None,
        "--type",
        "-t",
        help="Media type to process (movies, tv, or both). Use instead of path for library-wide.",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        "-r",
        help="Re-download even if poster exists (get potentially newer image)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be downloaded without actually downloading",
    ),
) -> None:
    """Download poster artwork for media files.

    Examples:

        jmm artwork download                    Download missing posters
        jmm artwork download --type movies      Movies only
        jmm artwork download --type tv          TV shows only
        jmm artwork download --refresh          Replace existing with fresh
        jmm artwork download /path/to/movie     Specific folder
    """
    if not _check_api_key():
        raise typer.Exit(1)

    console.print()
    console.print(
        Panel(
            "[bold]JackMediaMan - Artwork Downloader[/]\n\n"
            "Download poster images from TMDb",
            border_style="cyan",
        )
    )

    service = ArtworkService()
    results: List[ArtworkResult] = []

    if path:
        # Specific folder
        path = path.resolve()
        if not path.exists():
            console.print(f"\n[red]Path not found: {path}[/]\n")
            raise typer.Exit(1)

        if not path.is_dir():
            console.print(f"\n[red]Path must be a directory: {path}[/]\n")
            raise typer.Exit(1)

        console.print(f"\n[dim]Processing: {path.name}[/]")

        # Determine if it's a movie or TV show folder
        # Check if it has season subfolders (TV) or video files directly (movie)
        has_season_folders = any(
            d.is_dir() and d.name.lower().startswith(("season", "s"))
            for d in path.iterdir()
        )

        if has_season_folders:
            # TV show folder
            if not dry_run:
                results = service.download_show_artwork(
                    show_folder=path,
                    show_name=path.name,
                    overwrite=refresh,
                )
            else:
                # For dry run, just report what would happen
                results = [
                    ArtworkResult(
                        path=path / "poster.jpg",
                        media_path=path,
                        artwork_type="show_poster",
                        success=True,
                        skipped=(path / "poster.jpg").exists() and not refresh,
                        skip_reason="Would download" if not (path / "poster.jpg").exists() or refresh else "Poster exists",
                    )
                ]
        else:
            # Movie folder - find video file
            video_extensions = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".ts", ".mov"}
            video_file = None
            for f in path.iterdir():
                if f.is_file() and f.suffix.lower() in video_extensions:
                    video_file = f
                    break

            if not video_file:
                console.print(f"\n[red]No video file found in: {path}[/]\n")
                raise typer.Exit(1)

            title, year = service._parse_movie_name(path.name)

            if not dry_run:
                result = service.download_movie_poster(
                    movie_path=video_file,
                    title=title,
                    year=year,
                    overwrite=refresh,
                )
                results = [result]
            else:
                poster_path = path / "poster.jpg"
                results = [
                    ArtworkResult(
                        path=poster_path,
                        media_path=video_file,
                        artwork_type="movie_poster",
                        success=True,
                        skipped=poster_path.exists() and not refresh,
                        skip_reason="Would download" if not poster_path.exists() or refresh else "Poster exists",
                    )
                ]

    elif media_type:
        # Library-wide download
        with _create_progress() as progress:
            task = progress.add_task(
                "Downloading", total=None, name="Scanning..."
            )

            def update_progress(current: int, total: int, name: str) -> None:
                progress.update(
                    task,
                    total=total,
                    completed=current,
                    name=name[:40],
                )

            if not dry_run:
                results = service.download_for_library(
                    media_type=media_type.value,
                    overwrite=refresh,
                    progress_callback=update_progress,
                )
            else:
                # Dry run - get stats instead
                stats = service.get_artwork_stats()
                if media_type.value in ("movies", "both"):
                    for i in range(stats["movies"]["missing_poster"]):
                        results.append(
                            ArtworkResult(
                                path=Path("movie/poster.jpg"),
                                media_path=Path("movie"),
                                artwork_type="movie_poster",
                                success=True,
                            )
                        )
                    for i in range(stats["movies"]["with_poster"]):
                        results.append(
                            ArtworkResult(
                                path=Path("movie/poster.jpg"),
                                media_path=Path("movie"),
                                artwork_type="movie_poster",
                                success=True,
                                skipped=not refresh,
                                skip_reason="Poster exists",
                            )
                        )
                if media_type.value in ("tv", "both"):
                    for i in range(stats["tv"]["missing_poster"]):
                        results.append(
                            ArtworkResult(
                                path=Path("show/poster.jpg"),
                                media_path=Path("show"),
                                artwork_type="show_poster",
                                success=True,
                            )
                        )
                    for i in range(stats["tv"]["with_poster"]):
                        results.append(
                            ArtworkResult(
                                path=Path("show/poster.jpg"),
                                media_path=Path("show"),
                                artwork_type="show_poster",
                                success=True,
                                skipped=not refresh,
                                skip_reason="Poster exists",
                            )
                        )

    else:
        # Default: both
        with _create_progress() as progress:
            task = progress.add_task(
                "Downloading", total=None, name="Scanning..."
            )

            def update_progress(current: int, total: int, name: str) -> None:
                progress.update(
                    task,
                    total=total,
                    completed=current,
                    name=name[:40],
                )

            if not dry_run:
                results = service.download_for_library(
                    media_type="both",
                    overwrite=refresh,
                    progress_callback=update_progress,
                )
            else:
                stats = service.get_artwork_stats()
                missing = stats["movies"]["missing_poster"] + stats["tv"]["missing_poster"]
                existing = stats["movies"]["with_poster"] + stats["tv"]["with_poster"]
                console.print(f"\n[dim]Would download {missing} posters, skip {existing} existing[/]")
                return

    _display_results(results, dry_run)
    console.print()


@app.command("status")
def status() -> None:
    """Show artwork coverage statistics for the library."""
    console.print()
    console.print(Panel("[bold]Artwork Coverage[/]", border_style="cyan"))
    console.print()

    service = ArtworkService()
    stats = service.get_artwork_stats()

    # Movies table
    console.print("[bold cyan]Movies[/]")
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="white")

    movies = stats["movies"]
    if movies["total"] > 0:
        coverage = (movies["with_poster"] / movies["total"]) * 100
        table.add_row("Total movies", str(movies["total"]))
        table.add_row("With poster", f"[green]{movies['with_poster']}[/]")
        table.add_row("Missing poster", f"[yellow]{movies['missing_poster']}[/]")
        table.add_row("Coverage", f"{coverage:.0f}%")
    else:
        table.add_row("Total movies", "0")

    console.print(table)
    console.print()

    # TV shows table
    console.print("[bold cyan]TV Shows[/]")
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="white")

    tv = stats["tv"]
    if tv["total"] > 0:
        coverage = (tv["with_poster"] / tv["total"]) * 100
        table.add_row("Total shows", str(tv["total"]))
        table.add_row("With poster", f"[green]{tv['with_poster']}[/]")
        table.add_row("Missing poster", f"[yellow]{tv['missing_poster']}[/]")
        table.add_row("Coverage", f"{coverage:.0f}%")
        if tv["seasons"] > 0:
            season_coverage = (tv["seasons_with_poster"] / tv["seasons"]) * 100
            table.add_row("", "")
            table.add_row("Total seasons", str(tv["seasons"]))
            table.add_row("With poster", f"[green]{tv['seasons_with_poster']}[/]")
            table.add_row("Season coverage", f"{season_coverage:.0f}%")
    else:
        table.add_row("Total shows", "0")

    console.print(table)
    console.print()

    # Hint
    total_missing = movies["missing_poster"] + tv["missing_poster"]
    if total_missing > 0:
        console.print(f"[dim]Run `jmm artwork download` to download {total_missing} missing posters[/]")
        console.print()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Download poster artwork for media files."""
    if ctx.invoked_subcommand is None:
        # Show status by default
        ctx.invoke(status)
