"""Duplicates command for finding and cleaning duplicate media files."""

from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from jackmediaman.core.config import get_settings
from jackmediaman.models.duplicates import DuplicateGroup
from jackmediaman.scanners.tv import TVScanner
from jackmediaman.scanners.movies import MovieScanner
from jackmediaman.matchers.tv import TVMatcher
from jackmediaman.matchers.title_year import TitleYearMatcher
from jackmediaman.matchers.fuzzy import FuzzyMatcher
from jackmediaman.matchers.tmdb import TMDbMatcher
from jackmediaman.protectors.symlink import SymlinkProtector
from jackmediaman.protectors.symlink_target import SymlinkTargetProtector
from jackmediaman.protectors.deluge import DelugeProtector
from jackmediaman.services.finder import DuplicateFinder
from jackmediaman.services.cleaner import CleanupService
from jackmediaman.services.renamer import RenameService
from jackmediaman.services.metadata_prober import get_metadata_prober
from jackmediaman.services.folder_consolidator import FolderConsolidator
from jackmediaman.cli.interactive import show_menu, confirm_action, show_duplicate_group_choice, show_batch_confirmation

app = typer.Typer(help="Find and clean duplicate media files")
console = Console()


class MediaType(str, Enum):
    """Type of media to scan."""
    tv = "tv"
    movies = "movies"
    both = "both"


class MovieMatcher(str, Enum):
    """Movie matching strategy."""
    title_year = "title_year"
    fuzzy = "fuzzy"
    tmdb = "tmdb"


class ProtectorType(str, Enum):
    """Protection method."""
    symlink = "symlink"
    deluge = "deluge"
    both = "both"
    none = "none"


def _display_results(groups: List[DuplicateGroup]) -> None:
    """Display duplicate groups in a Rich table."""
    if not groups:
        console.print("\n[green]No duplicates found![/green]\n")
        return

    # Summary table
    total_removable = sum(len(g.removable_items) for g in groups)
    total_bytes = sum(g.removable_size_bytes for g in groups)
    total_gb = total_bytes / (1024 * 1024 * 1024)

    console.print()
    console.print(Panel(
        f"[bold]Found {len(groups)} duplicate groups[/]\n"
        f"[dim]{total_removable} files can be removed, freeing {total_gb:.2f} GB[/]",
        title="[bold cyan]Scan Results[/]",
        border_style="cyan",
    ))
    console.print()

    # Detailed table - expand to full terminal width
    table = Table(
        title="Duplicate Groups",
        show_header=True,
        header_style="bold cyan",
        expand=True,
    )
    table.add_column("Media", style="white", no_wrap=True, ratio=2)
    table.add_column("File", style="dim", ratio=3)
    table.add_column("Quality", style="yellow", width=12)
    table.add_column("Size", style="magenta", justify="right", width=10)
    table.add_column("Action", style="green", width=16)

    for group in groups:
        first_row = True
        for item in group.items:
            action = group.get_action(item)
            action_display = {
                "KEEP": "[bold green]KEEP[/]",
                "PROTECTED": "[yellow]PROTECTED[/]",
                "REMOVE": "[red]REMOVE[/]",
                "REMOVE (symlink)": "[red]REMOVE[/] [dim](symlink)[/]",
            }.get(action, action)

            table.add_row(
                group.display_name if first_row else "",
                item.filename[:80] + "..." if len(item.filename) > 80 else item.filename,
                str(item.quality),
                f"{item.size_mb:.1f} MB",
                action_display,
            )
            first_row = False
        table.add_section()

    console.print(table)


def _run_interactive_scan() -> tuple:
    """Run interactive mode to get scan options."""
    console.print()
    console.print(Panel(
        "[bold]JackMediaMan - Duplicate Finder[/]\n\n"
        "Find and clean duplicate media files in your library.",
        border_style="cyan",
    ))

    # Select media type
    media_choice = show_menu(
        "What would you like to scan?",
        [
            ("TV Shows", "Scan TV shows library for duplicate episodes"),
            ("Movies", "Scan movies library for duplicate movies"),
            ("Both", "Scan both TV shows and movies"),
        ],
        default=3,
    )
    media_type = [MediaType.tv, MediaType.movies, MediaType.both][media_choice - 1]

    # Select movie matcher (if scanning movies)
    movie_matcher = MovieMatcher.title_year
    if media_type in (MediaType.movies, MediaType.both):
        matcher_choice = show_menu(
            "How should movies be matched?",
            [
                ("Title/Year", "Match by parsed title and year (fast)"),
                ("Fuzzy", "Match with fuzzy title comparison (handles variations)"),
                ("TMDb", "Match using TMDb API lookup (most accurate)"),
            ],
            default=1,
        )
        movie_matcher = [MovieMatcher.title_year, MovieMatcher.fuzzy, MovieMatcher.tmdb][matcher_choice - 1]

    # Select protector
    protector_choice = show_menu(
        "How should seeding files be protected?",
        [
            ("Symlink", "Protect files that are symlinks to torrent directory"),
            ("Deluge", "Query Deluge daemon for actively seeding files"),
            ("Both", "Use both symlink detection and Deluge API"),
            ("None", "Don't protect any files"),
        ],
        default=1,
    )
    protector = [ProtectorType.symlink, ProtectorType.deluge, ProtectorType.both, ProtectorType.none][protector_choice - 1]

    # Edition handling
    edition_choice = show_menu(
        "How should different editions be handled?",
        [
            ("As duplicates", "Treat Director's Cut, Extended, etc. as duplicates"),
            ("Keep separate", "Different editions are NOT duplicates"),
        ],
        default=1,
    )
    editions_as_dupes = edition_choice == 1

    return media_type, movie_matcher, protector, editions_as_dupes


def _rename_kept_files(groups: List[DuplicateGroup], dry_run: bool = False) -> None:
    """Rename the kept files from duplicate groups to standardized format."""
    # Collect kept items from all groups
    kept_items = []
    for group in groups:
        # The kept item is the first one (highest quality after sort)
        if group.items:
            kept_item = group.items[0]
            # Only rename if not protected (protected files are symlinks to torrents)
            if not kept_item.is_protected:
                kept_items.append(kept_item)

    if not kept_items:
        console.print("[dim]No files to rename[/]")
        return

    console.print(f"\n[bold cyan]Renaming {len(kept_items)} kept files...[/]\n")

    service = RenameService()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Renaming...", total=len(kept_items))

        def update_progress(current, total, filename):
            progress.update(task, completed=current, description=f"Renaming {filename[:30]}...")

        summary = service.rename_items(kept_items, dry_run=dry_run, progress_callback=update_progress)

    console.print(
        f"[green]Renamed {summary.renamed} files, "
        f"skipped {summary.skipped} (already correct), "
        f"errors: {summary.failed}[/]"
    )


def _build_protectors(protector_type: ProtectorType) -> list:
    """Build list of protectors based on selection."""
    protectors = []
    # Always protect files that are targets of symlinks in the library
    protectors.append(SymlinkTargetProtector())
    if protector_type in (ProtectorType.symlink, ProtectorType.both):
        protectors.append(SymlinkProtector())
    if protector_type in (ProtectorType.deluge, ProtectorType.both):
        protectors.append(DelugeProtector())
    return protectors


def _scan_media(
    media_type: MediaType,
    movie_matcher: MovieMatcher,
    protector_type: ProtectorType,
    editions_as_dupes: bool,
    broken_links: Optional[List[Path]] = None,
) -> List[DuplicateGroup]:
    """Scan media and return duplicate groups.

    Uses ffprobe for accurate quality detection when enabled in settings.
    Results are cached in SQLite for fast subsequent scans.
    Dangling symlinks skipped by the scanners are appended to broken_links if given.
    """
    settings = get_settings()
    protectors = _build_protectors(protector_type)
    all_groups = []

    # Create metadata prober for accurate quality detection (with caching)
    prober = None
    if settings.ffprobe_enabled:
        prober = get_metadata_prober(
            cache_enabled=True,
            max_workers=settings.ffprobe_workers,
        )
        if not prober.is_available:
            console.print("[yellow]Warning: ffprobe not found, using filename-based quality detection[/]")
            prober = None

    # Consolidate season folder variants before scanning TV
    if media_type in (MediaType.tv, MediaType.both):
        consolidator = FolderConsolidator(tv_dir=settings.tv_dir)
        variants = consolidator.find_season_folder_variants()
        if variants:
            console.print(f"[yellow]Found {len(variants)} season folder variants to consolidate...[/]")
            result = consolidator.consolidate_season_folders(
                torrent_dir=settings.torrent_dir,
            )
            if result.files_moved > 0:
                console.print(
                    f"[green]Consolidated {result.files_moved} files from "
                    f"{result.folders_removed} duplicate folders[/]"
                )
            console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        # Scan TV Shows
        if media_type in (MediaType.tv, MediaType.both):
            task = progress.add_task("Scanning TV Shows...", total=None)

            tv_scanner = TVScanner(metadata_prober=prober)

            if prober:
                # Use ffprobe-based scanning with progress
                def tv_progress(current, total, filename):
                    progress.update(task, description=f"Probing TV: {filename[:30]}... ({current}/{total})")

                items = tv_scanner.scan_with_metadata(settings.tv_dir, progress_callback=tv_progress)
            else:
                # Fall back to filename-based scanning
                items = list(tv_scanner.scan(settings.tv_dir))

            if broken_links is not None:
                broken_links.extend(tv_scanner.broken_links)

            # Apply protectors
            for protector in protectors:
                protector.protect(items)

            # Find duplicates
            tv_matcher = TVMatcher()
            groups = tv_matcher.match(items)
            all_groups.extend(groups)
            progress.update(task, description=f"[green]TV Shows: {len(groups)} duplicate groups[/]")

        # Scan Movies
        if media_type in (MediaType.movies, MediaType.both):
            task = progress.add_task("Scanning Movies...", total=None)

            movie_scanner = MovieScanner(metadata_prober=prober)

            if prober:
                # Use ffprobe-based scanning with progress
                def movie_progress(current, total, filename):
                    progress.update(task, description=f"Probing Movies: {filename[:30]}... ({current}/{total})")

                items = movie_scanner.scan_with_metadata(settings.movies_dir, progress_callback=movie_progress)
            else:
                # Fall back to filename-based scanning
                items = list(movie_scanner.scan(settings.movies_dir))

            if broken_links is not None:
                broken_links.extend(movie_scanner.broken_links)

            # Apply protectors
            for protector in protectors:
                protector.protect(items)

            # Select matcher
            if movie_matcher == MovieMatcher.fuzzy:
                matcher = FuzzyMatcher(include_editions_as_dupes=editions_as_dupes)
            elif movie_matcher == MovieMatcher.tmdb:
                matcher = TMDbMatcher(include_editions_as_dupes=editions_as_dupes)
            else:
                matcher = TitleYearMatcher(include_editions_as_dupes=editions_as_dupes)

            groups = matcher.match(items)
            all_groups.extend(groups)
            progress.update(task, description=f"[green]Movies: {len(groups)} duplicate groups[/]")

    return all_groups


@app.command("scan")
def scan(
    media_type: MediaType = typer.Option(
        MediaType.both,
        "--type", "-t",
        help="Type of media to scan",
    ),
    movie_matcher: MovieMatcher = typer.Option(
        MovieMatcher.title_year,
        "--matcher", "-m",
        help="Movie matching strategy",
    ),
    protector: ProtectorType = typer.Option(
        ProtectorType.symlink,
        "--protector", "-p",
        help="Protection method for seeding files",
    ),
    editions_as_dupes: bool = typer.Option(
        True,
        "--editions-as-dupes/--editions-separate",
        help="Treat different editions as duplicates",
    ),
) -> None:
    """Scan media library and display duplicates found."""
    broken_links: List[Path] = []
    groups = _scan_media(media_type, movie_matcher, protector, editions_as_dupes, broken_links)
    _display_results(groups)

    if broken_links:
        console.print(f"[yellow]{len(broken_links)} broken links skipped:[/]")
        for link in broken_links:
            console.print(f"  [dim]{link}[/]")
        console.print()


@app.command("clean")
def clean(
    media_type: MediaType = typer.Option(
        MediaType.both,
        "--type", "-t",
        help="Type of media to scan",
    ),
    movie_matcher: MovieMatcher = typer.Option(
        MovieMatcher.title_year,
        "--matcher", "-m",
        help="Movie matching strategy",
    ),
    protector: ProtectorType = typer.Option(
        ProtectorType.symlink,
        "--protector", "-p",
        help="Protection method for seeding files",
    ),
    editions_as_dupes: bool = typer.Option(
        True,
        "--editions-as-dupes/--editions-separate",
        help="Treat different editions as duplicates",
    ),
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--execute",
        help="Show what would be done without making changes",
    ),
    interactive: bool = typer.Option(
        True,
        "--interactive/--auto",
        help="Ask for confirmation before each removal",
    ),
    rename_files: bool = typer.Option(
        False,
        "--rename/--no-rename",
        help="Also rename kept files to standardized format after cleanup",
    ),
) -> None:
    """Clean up duplicates by moving to trash."""
    # Scan for duplicates
    groups = _scan_media(media_type, movie_matcher, protector, editions_as_dupes)

    if not groups:
        console.print("\n[green]No duplicates found![/]\n")
        return

    _display_results(groups)

    # Filter to groups with removable items
    actionable_groups = [g for g in groups if g.removable_items]
    if not actionable_groups:
        console.print("\n[yellow]No files to remove (all protected or best quality)[/]\n")
        return

    if dry_run:
        console.print("\n[yellow]DRY RUN - No files will be moved[/]\n")
        if confirm_action("Would you like to execute cleanup?", default=False):
            dry_run = False
        else:
            return

    cleaner = CleanupService()

    if interactive:
        # Process each group interactively
        cleaned = 0
        skipped = 0
        i = 0
        while i < len(actionable_groups):
            group = actionable_groups[i]
            remaining = len(actionable_groups) - i - 1
            action = show_duplicate_group_choice(group, remaining_groups=remaining)

            if action == "clean":
                results = cleaner.cleanup_group(group, dry_run=False)
                cleaned += len([r for r in results if r.success])
                i += 1
            elif action == "skip":
                skipped += 1
                i += 1
            elif action == "clean_all":
                # Clean all remaining groups (including current)
                remaining_groups = actionable_groups[i:]
                if show_batch_confirmation(remaining_groups, "clean"):
                    for g in remaining_groups:
                        results = cleaner.cleanup_group(g, dry_run=False)
                        cleaned += len([r for r in results if r.success])
                    break
                # If not confirmed, continue with current group
            elif action == "skip_all":
                # Skip all remaining groups
                remaining_groups = actionable_groups[i:]
                show_batch_confirmation(remaining_groups, "skip")
                skipped += len(remaining_groups)
                break
            elif action == "quit":
                break

        console.print(f"\n[green]Cleaned {cleaned} files, skipped {skipped} groups[/]\n")
    else:
        # Process all groups automatically
        summary = cleaner.cleanup_groups(actionable_groups, dry_run=False)
        console.print(
            f"\n[green]Cleaned {summary.total_files_removed} files, "
            f"freed {summary.total_gb_freed:.2f} GB[/]\n"
        )

    # Rename kept files if requested
    if rename_files:
        _rename_kept_files(actionable_groups, dry_run=False)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Find and clean duplicate media files."""
    if ctx.invoked_subcommand is None:
        # Interactive mode
        media_type, movie_matcher, protector, editions_as_dupes = _run_interactive_scan()

        # Scan
        groups = _scan_media(media_type, movie_matcher, protector, editions_as_dupes)
        _display_results(groups)

        # Ask about cleanup
        actionable = [g for g in groups if g.removable_items]
        if actionable:
            if confirm_action("\nWould you like to clean up these duplicates?", default=False):
                cleaner = CleanupService()
                cleaned = 0
                skipped = 0
                i = 0
                while i < len(actionable):
                    group = actionable[i]
                    remaining = len(actionable) - i - 1
                    action = show_duplicate_group_choice(group, remaining_groups=remaining)

                    if action == "clean":
                        results = cleaner.cleanup_group(group, dry_run=False)
                        cleaned += len([r for r in results if r.success])
                        i += 1
                    elif action == "skip":
                        skipped += 1
                        i += 1
                    elif action == "clean_all":
                        remaining_groups = actionable[i:]
                        if show_batch_confirmation(remaining_groups, "clean"):
                            for g in remaining_groups:
                                results = cleaner.cleanup_group(g, dry_run=False)
                                cleaned += len([r for r in results if r.success])
                            break
                    elif action == "skip_all":
                        remaining_groups = actionable[i:]
                        show_batch_confirmation(remaining_groups, "skip")
                        skipped += len(remaining_groups)
                        break
                    elif action == "quit":
                        break

                console.print(f"\n[green]Cleaned {cleaned} files, skipped {skipped} groups[/]\n")
