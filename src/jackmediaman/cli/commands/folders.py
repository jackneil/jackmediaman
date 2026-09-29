"""Folders command for finding and consolidating duplicate media folders."""

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
)
from rich.table import Table
from rich.prompt import Confirm

from jackmediaman.core.config import get_settings
from jackmediaman.models.folders import FolderGroup, ConsolidationResult
from jackmediaman.services.folder_consolidator import FolderConsolidator

app = typer.Typer(help="Find and consolidate duplicate media folders")
console = Console()


class MediaType(str, Enum):
    """Type of media to scan."""
    tv = "tv"
    movies = "movies"


def _display_folder_groups(groups: List[FolderGroup]) -> None:
    """Display duplicate folder groups in a Rich table."""
    if not groups:
        console.print("\n[green]No duplicate folders found![/green]\n")
        return

    # Summary stats
    total_folders = sum(g.count for g in groups)
    total_duplicates = sum(g.count - 1 for g in groups)
    total_bytes = sum(g.total_size_bytes for g in groups)
    total_gb = total_bytes / (1024 * 1024 * 1024)

    console.print()
    console.print(Panel(
        f"[bold]Found {len(groups)} groups with duplicates[/]\n"
        f"[dim]{total_duplicates} duplicate folders found ({total_gb:.2f} GB total)[/]",
        title="[bold cyan]Folder Scan Results[/]",
        border_style="cyan",
    ))
    console.print()

    # Detailed table
    table = Table(
        title="Duplicate Folder Groups",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Canonical Name", style="white", no_wrap=False, ratio=2)
    table.add_column("Folder", style="dim", ratio=3)
    table.add_column("Files", justify="right", width=6)
    table.add_column("Size", style="magenta", justify="right", width=10)
    table.add_column("Action", style="green", width=12)

    for group in groups:
        best = group.best_folder
        first_row = True

        for folder in sorted(group.folders, key=lambda f: (f != best, f.name)):
            is_best = folder == best
            action = "[bold green]KEEP[/]" if is_best else "[red]MERGE[/]"
            size_gb = folder.size_bytes / (1024 * 1024 * 1024)

            table.add_row(
                group.canonical_name if first_row else "",
                folder.name,
                str(folder.file_count),
                f"{size_gb:.2f} GB" if size_gb >= 1 else f"{folder.size_bytes / (1024*1024):.1f} MB",
                action,
            )
            first_row = False
        table.add_section()

    console.print(table)


def _display_consolidation_results(results: List[ConsolidationResult], dry_run: bool) -> None:
    """Display consolidation results."""
    prefix = "[DRY RUN] " if dry_run else ""

    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    total_files = sum(r.files_moved for r in successful)
    total_folders = sum(r.folders_removed for r in successful)

    console.print()
    if dry_run:
        console.print(Panel(
            f"[bold]{prefix}Would consolidate {len(successful)} folder groups[/]\n"
            f"[dim]{total_files} files would be moved, {total_folders} folders would be removed[/]",
            title="[bold yellow]Dry Run Results[/]",
            border_style="yellow",
        ))
    else:
        console.print(Panel(
            f"[bold]Consolidated {len(successful)} folder groups[/]\n"
            f"[dim]{total_files} files moved, {total_folders} folders removed[/]",
            title="[bold green]Consolidation Complete[/]",
            border_style="green",
        ))

    if failed:
        console.print()
        console.print("[red]Failed consolidations:[/]")
        for result in failed:
            console.print(f"  - {result.group.canonical_name}")
            for error in result.errors:
                console.print(f"    [dim red]{error}[/]")


@app.command("scan")
def scan(
    media_type: MediaType = typer.Option(
        MediaType.movies,
        "--type", "-t",
        help="Type of media to scan (movies or tv)",
    ),
    no_tmdb: bool = typer.Option(
        False,
        "--no-tmdb",
        help="Skip TMDb lookup (faster but less accurate)",
    ),
) -> None:
    """Scan for duplicate media folders.

    Finds folders that contain the same movie or TV show but have
    different names (e.g., "Movie Title (2020)" vs "Movie Title 2020").
    """
    settings = get_settings()

    # Determine which directory to scan
    if media_type == MediaType.movies:
        scan_dir = settings.movies_dir
        dir_name = "movies"
    else:
        scan_dir = settings.tv_dir
        dir_name = "TV shows"

    if not scan_dir.exists():
        console.print(f"[red]Error:[/] {dir_name.title()} directory not found: {scan_dir}")
        raise typer.Exit(1)

    console.print()
    console.print(f"[cyan]Scanning {dir_name} for duplicate folders...[/]")

    consolidator = FolderConsolidator()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[name]}[/]"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning...", total=None, name="")

        def update_progress(current: int, total: int, name: str) -> None:
            progress.update(task, completed=current, total=total, name=name[:50])

        groups = consolidator.find_duplicate_folders(
            media_type=media_type.value,
            tmdb_lookup=not no_tmdb,
            progress_callback=update_progress,
        )

    _display_folder_groups(groups)


@app.command("consolidate")
def consolidate(
    media_type: MediaType = typer.Option(
        MediaType.movies,
        "--type", "-t",
        help="Type of media to consolidate (movies or tv)",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--execute",
        help="Preview changes without executing (default: dry-run)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes", "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Consolidate duplicate media folders.

    Merges files from duplicate folders into a single canonical folder
    and removes the empty duplicate folders.

    By default runs in dry-run mode. Use --execute to actually perform changes.
    """
    settings = get_settings()

    # Determine which directory to scan
    if media_type == MediaType.movies:
        scan_dir = settings.movies_dir
        dir_name = "movies"
    else:
        scan_dir = settings.tv_dir
        dir_name = "TV shows"

    if not scan_dir.exists():
        console.print(f"[red]Error:[/] {dir_name.title()} directory not found: {scan_dir}")
        raise typer.Exit(1)

    console.print()
    mode_str = "[yellow]DRY RUN[/]" if dry_run else "[red]EXECUTE[/]"
    console.print(f"[cyan]Consolidating duplicate {dir_name} folders...[/] ({mode_str})")

    consolidator = FolderConsolidator()

    # First scan for duplicates
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[name]}[/]"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning...", total=None, name="")

        def update_progress(current: int, total: int, name: str) -> None:
            progress.update(task, completed=current, total=total, name=name[:50])

        groups = consolidator.find_duplicate_folders(
            media_type=media_type.value,
            tmdb_lookup=True,
            progress_callback=update_progress,
        )

    if not groups:
        console.print("\n[green]No duplicate folders found![/green]\n")
        return

    # Show what will be consolidated
    _display_folder_groups(groups)

    # Confirm if not dry-run and not --yes
    if not dry_run and not yes:
        console.print()
        if not Confirm.ask(
            f"[yellow]This will consolidate {len(groups)} folder groups. Continue?[/]",
            default=False,
        ):
            console.print("[dim]Cancelled.[/]")
            return

    # Perform consolidation
    console.print()
    results = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[dim]{task.fields[name]}[/]"),
        console=console,
    ) as progress:
        task = progress.add_task("Consolidating...", total=len(groups), name="")

        for i, group in enumerate(groups):
            progress.update(task, completed=i, name=group.canonical_name[:50])

            result = consolidator.consolidate_group(group, dry_run=dry_run)
            results.append(result)

        progress.update(task, completed=len(groups))

    _display_consolidation_results(results, dry_run)

    if dry_run:
        console.print()
        console.print("[dim]Run with --execute to perform these changes.[/]")
