"""NFO command for generating Kodi-compatible metadata files."""

from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    BarColumn,
    MofNCompleteColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from jackmediaman.core.config import get_settings
from jackmediaman.models.nfo import NFOType, NFOResult, NFOBatchResult
from jackmediaman.services.nfo import NFOService

app = typer.Typer(help="Generate Kodi-compatible NFO metadata files")
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
    """Create a progress bar for operations."""
    return Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]|[/]"),
        TimeElapsedColumn(),
        TextColumn("[dim]|[/]"),
        TimeRemainingColumn(),
        TextColumn("[dim]{task.fields[name]}[/]"),
        console=console,
    )


def _display_results(batch: NFOBatchResult, dry_run: bool = False) -> None:
    """Display NFO generation results."""
    console.print()
    mode_text = "[yellow]DRY RUN - No files written[/]" if dry_run else ""
    console.print(
        Panel(
            f"[bold]NFO Generation Results[/]\n"
            f"Generated: [green]{batch.generated}[/]\n"
            f"Skipped: [dim]{batch.skipped}[/]\n"
            f"Failed: [red]{batch.failed}[/]\n"
            f"{mode_text}",
            title="[bold cyan]Results[/]",
            border_style="cyan",
        )
    )

    # Show generated items
    generated = [r for r in batch.results if r.success and not r.skipped]
    if generated:
        console.print()
        table = Table(title="Generated NFO Files", show_header=True)
        table.add_column("Type", style="cyan")
        table.add_column("Path", style="white")

        for result in generated[:20]:
            nfo_type = result.nfo_type.value if result.nfo_type else "unknown"
            table.add_row(
                nfo_type,
                result.path.name,
            )

        if len(generated) > 20:
            table.add_row("", f"[dim]... and {len(generated) - 20} more[/]")

        console.print(table)

    # Show failed
    failed = [r for r in batch.results if not r.success and not r.skipped]
    if failed:
        console.print()
        console.print("[bold red]Failed:[/]")
        for result in failed[:10]:
            console.print(f"  [red][/] {result.path.parent.name}: {result.reason}")

        if len(failed) > 10:
            console.print(f"  [dim]... and {len(failed) - 10} more failures[/]")

    # Show skipped summary
    if batch.skipped > 0:
        console.print()
        console.print(f"[dim]Skipped {batch.skipped} items (NFO already exists)[/]")


@app.command("scan")
def scan(
    media_type: MediaType = typer.Option(
        MediaType.both,
        "--type",
        "-t",
        help="Media type to scan (movies, tv, or both)",
    ),
) -> None:
    """Scan library for missing NFO files.

    Shows which movies and TV shows are missing NFO metadata files.

    Examples:

        jmm nfo scan                    Scan all media
        jmm nfo scan --type movies      Scan movies only
        jmm nfo scan --type tv          Scan TV shows only
    """
    if not _check_api_key():
        raise typer.Exit(1)

    console.print()
    console.print(
        Panel(
            "[bold]JackMediaMan - NFO Scanner[/]\n\n"
            "Scanning library for missing NFO files",
            border_style="cyan",
        )
    )

    service = NFOService()
    results = service.scan_library(media_type=media_type.value)

    missing = [r for r in results if r.needs_nfo]
    have_nfo = [r for r in results if not r.needs_nfo]

    console.print()

    if media_type.value in ("movies", "both"):
        movie_results = [r for r in results if r.media_type == NFOType.MOVIE]
        movie_missing = [r for r in movie_results if r.needs_nfo]
        movie_have = [r for r in movie_results if not r.needs_nfo]

        console.print("[bold cyan]Movies[/]")
        if movie_results:
            console.print(
                f"  Total: {len(movie_results)} | "
                f"[green]With NFO: {len(movie_have)}[/] | "
                f"[yellow]Missing: {len(movie_missing)}[/]"
            )
        else:
            console.print("  [dim]No movies found[/]")
        console.print()

    if media_type.value in ("tv", "both"):
        tv_results = [r for r in results if r.media_type == NFOType.TVSHOW]
        tv_missing = [r for r in tv_results if r.needs_nfo]
        tv_have = [r for r in tv_results if not r.needs_nfo]

        console.print("[bold cyan]TV Shows[/]")
        if tv_results:
            console.print(
                f"  Total: {len(tv_results)} | "
                f"[green]With NFO: {len(tv_have)}[/] | "
                f"[yellow]Missing: {len(tv_missing)}[/]"
            )
        else:
            console.print("  [dim]No TV shows found[/]")
        console.print()

    # Show missing items
    if missing:
        console.print("[bold]Missing NFO files:[/]")
        table = Table(show_header=True)
        table.add_column("Type", style="cyan")
        table.add_column("Title", style="white")

        for result in missing[:30]:
            table.add_row(
                result.media_type.value,
                result.title,
            )

        if len(missing) > 30:
            table.add_row("", f"[dim]... and {len(missing) - 30} more[/]")

        console.print(table)
        console.print()
        console.print(f"[dim]Run `jmm nfo generate` to create {len(missing)} missing NFO files[/]")
    else:
        console.print("[green]All media has NFO files![/]")

    console.print()


@app.command("generate")
def generate(
    path: Optional[Path] = typer.Argument(
        None,
        help="Specific folder to generate NFO for",
    ),
    media_type: MediaType = typer.Option(
        MediaType.both,
        "--type",
        "-t",
        help="Media type to process (movies, tv, or both). Use instead of path for library-wide.",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        "-r",
        help="Regenerate existing NFO files (fetch fresh metadata)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be generated without writing files",
    ),
) -> None:
    """Generate NFO metadata files for library.

    Creates Kodi-compatible .nfo XML files with movie/show metadata
    from TMDb (title, year, plot, rating, genres, etc.).

    Examples:

        jmm nfo generate                    Generate missing NFOs
        jmm nfo generate --type movies      Movies only
        jmm nfo generate --type tv          TV shows only
        jmm nfo generate --refresh          Regenerate ALL NFOs
        jmm nfo generate /path/to/movie     Specific folder
        jmm nfo generate --dry-run          Preview only
    """
    if not _check_api_key():
        raise typer.Exit(1)

    console.print()
    console.print(
        Panel(
            "[bold]JackMediaMan - NFO Generator[/]\n\n"
            "Generate Kodi-compatible NFO metadata files from TMDb",
            border_style="cyan",
        )
    )

    service = NFOService()
    batch = NFOBatchResult()

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
        has_season_folders = any(
            d.is_dir() and d.name.lower().startswith(("season", "s"))
            for d in path.iterdir()
        )

        if has_season_folders:
            # TV show folder
            if not dry_run:
                result = service.generate_show_nfo(
                    folder=path,
                    show_name=path.name,
                    overwrite=refresh,
                )
                batch.add(result)
            else:
                nfo_path = path / "tvshow.nfo"
                batch.add(
                    NFOResult(
                        path=nfo_path,
                        success=not nfo_path.exists() or refresh,
                        skipped=nfo_path.exists() and not refresh,
                        reason="exists" if nfo_path.exists() and not refresh else None,
                        nfo_type=NFOType.TVSHOW,
                    )
                )
        else:
            # Movie folder
            title, year = service._parse_movie_name(path.name)
            if not dry_run:
                result = service.generate_movie_nfo(
                    folder=path,
                    title=title,
                    year=year,
                    overwrite=refresh,
                )
                batch.add(result)
            else:
                nfo_path = path / "movie.nfo"
                batch.add(
                    NFOResult(
                        path=nfo_path,
                        success=not nfo_path.exists() or refresh,
                        skipped=nfo_path.exists() and not refresh,
                        reason="exists" if nfo_path.exists() and not refresh else None,
                        nfo_type=NFOType.MOVIE,
                    )
                )

    else:
        # Library-wide generation
        if dry_run:
            # For dry run, just show stats
            stats = service.get_nfo_stats()
            movies_missing = stats["movies"]["missing_nfo"]
            movies_existing = stats["movies"]["with_nfo"]
            tv_missing = stats["tv"]["missing_nfo"]
            tv_existing = stats["tv"]["with_nfo"]

            would_generate = 0
            would_skip = 0

            if media_type.value in ("movies", "both"):
                if refresh:
                    would_generate += movies_missing + movies_existing
                else:
                    would_generate += movies_missing
                    would_skip += movies_existing

            if media_type.value in ("tv", "both"):
                if refresh:
                    would_generate += tv_missing + tv_existing
                else:
                    would_generate += tv_missing
                    would_skip += tv_existing

            console.print()
            console.print(
                f"[yellow]DRY RUN[/]: Would generate [green]{would_generate}[/] NFO files, "
                f"skip [dim]{would_skip}[/] existing"
            )
            console.print()
            return

        with _create_progress() as progress:
            task = progress.add_task(
                "Generating NFOs", total=None, name="Scanning..."
            )

            def update_progress(current: int, total: int, name: str) -> None:
                progress.update(
                    task,
                    total=total,
                    completed=current,
                    name=name[:40],
                )

            batch = service.generate_for_library(
                media_type=media_type.value,
                overwrite=refresh,
                progress_callback=update_progress,
            )

    _display_results(batch, dry_run)
    console.print()


@app.command("status")
def status() -> None:
    """Show NFO coverage statistics for the library."""
    console.print()
    console.print(Panel("[bold]NFO Coverage[/]", border_style="cyan"))
    console.print()

    service = NFOService()
    stats = service.get_nfo_stats()

    # Movies table
    console.print("[bold cyan]Movies[/]")
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="white")

    movies = stats["movies"]
    if movies["total"] > 0:
        coverage = (movies["with_nfo"] / movies["total"]) * 100
        table.add_row("Total movies", str(movies["total"]))
        table.add_row("With NFO", f"[green]{movies['with_nfo']}[/]")
        table.add_row("Missing NFO", f"[yellow]{movies['missing_nfo']}[/]")
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
        coverage = (tv["with_nfo"] / tv["total"]) * 100
        table.add_row("Total shows", str(tv["total"]))
        table.add_row("With NFO", f"[green]{tv['with_nfo']}[/]")
        table.add_row("Missing NFO", f"[yellow]{tv['missing_nfo']}[/]")
        table.add_row("Coverage", f"{coverage:.0f}%")
    else:
        table.add_row("Total shows", "0")

    console.print(table)
    console.print()

    # Hint
    total_missing = movies["missing_nfo"] + tv["missing_nfo"]
    if total_missing > 0:
        console.print(f"[dim]Run `jmm nfo generate` to create {total_missing} missing NFO files[/]")
        console.print()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Generate Kodi-compatible NFO metadata files."""
    if ctx.invoked_subcommand is None:
        # Show status by default
        ctx.invoke(status)
