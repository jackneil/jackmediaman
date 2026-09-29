"""Repair commands for fixing broken symlinks and other issues."""

import os
import re
from pathlib import Path
from typing import List, Optional, Tuple, TYPE_CHECKING

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger
from jackmediaman.core.operations_db import get_operations_db
from jackmediaman.services.folder_consolidator import FolderConsolidator

if TYPE_CHECKING:
    from jackmediaman.services.metadata_prober import MetadataProber

app = typer.Typer(help="Repair broken symlinks and other issues")
console = Console()
logger = get_logger("cli.repair")

# Resolution tag pattern - matches [1080p], [720p], [960p], [640p], etc.
# Uses generic \d{3,4}p to match ANY resolution (960p, 640p, 540p, etc.)
RESOLUTION_TAG_PATTERN = re.compile(r"\s*\[(?:\d{3,4}p|4K|UHD)\]", re.IGNORECASE)

# Pattern to extract resolution from filename
RESOLUTION_EXTRACT_PATTERN = re.compile(r"\[(\d{3,4}p|4K|UHD)\]", re.IGNORECASE)

# Pattern to extract show name and S##E## from filename
EPISODE_PATTERN = re.compile(r'^(.+?)\s*-?\s*[Ss](\d{1,2})[Ee](\d{1,3})', re.IGNORECASE)


def extract_resolution_from_filename(stem: str) -> Optional[str]:
    """
    Extract resolution tag from filename stem.

    Examples:
        'Title [1080p]' -> '1080p'
        'Title [2160p]' -> '2160p'
        'Title' -> None
    """
    match = RESOLUTION_EXTRACT_PATTERN.search(stem)
    return match.group(1).lower() if match else None


def extract_episode_info(stem: str) -> Optional[Tuple[str, int, int]]:
    """
    Extract show name, season, and episode from filename.

    Args:
        stem: Filename stem (without extension)

    Returns:
        Tuple of (show_name, season, episode) or None if not parseable

    Examples:
        'Stranger Things - S03E02 - Chapter Two' -> ('Stranger Things', 3, 2)
        'Euphoria (US) - S01E06 - The Next Episode' -> ('Euphoria (US)', 1, 6)
        '1883 - S01E05 - The Fangs of Freedom' -> ('1883', 1, 5)
    """
    match = EPISODE_PATTERN.match(stem)
    if match:
        show_name = match.group(1).strip(' -')
        season = int(match.group(2))
        episode = int(match.group(3))
        return (show_name, season, episode)
    return None


def _show_names_match(name1: str, name2: str) -> bool:
    """
    Check if two show names likely refer to the same show.

    Handles:
    - Case differences: 'stranger things' vs 'Stranger Things'
    - Parenthetical info: 'Euphoria (US)' vs 'Euphoria'
    - Extra whitespace

    Args:
        name1: First show name
        name2: Second show name

    Returns:
        True if names likely refer to the same show
    """
    # Normalize: lowercase, strip whitespace
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()

    if n1 == n2:
        return True

    # Remove parenthetical info and compare
    n1_base = re.sub(r'\s*\([^)]+\)\s*', '', n1).strip()
    n2_base = re.sub(r'\s*\([^)]+\)\s*', '', n2).strip()

    if n1_base == n2_base:
        return True

    # Check if one contains the other (for partial matches)
    if n1_base and n2_base:
        if n1_base in n2_base or n2_base in n1_base:
            return True

    return False


def _resolution_matches(quality_resolution_raw: Optional[str], expected: str) -> bool:
    """Check if a resolution from quality matches expected resolution."""
    if not quality_resolution_raw:
        return False
    # Normalize both to lowercase for comparison
    return quality_resolution_raw.lower() == expected.lower()


# Cache for Deluge connection status and torrent data
_deluge_cache: Optional[dict] = None
_deluge_connection_failed: bool = False


def get_file_size_from_deluge(target_path: Path) -> Optional[int]:
    """
    Look up file size from Deluge by finding the torrent that contains this file.

    Uses caching to avoid repeated connection attempts if Deluge is unavailable.

    Args:
        target_path: Path to the file (from broken symlink target)

    Returns:
        File size in bytes, or None if not found
    """
    global _deluge_cache, _deluge_connection_failed

    # Skip if we already know Deluge connection failed
    if _deluge_connection_failed:
        return None

    # Use cached torrent data if available
    if _deluge_cache is not None:
        return _search_deluge_cache(target_path, _deluge_cache)

    try:
        from jackmediaman.services.deluge_client import create_deluge_client

        settings = get_settings()
        client = create_deluge_client(
            settings.deluge_host,
            settings.deluge_port,
            settings.deluge_username,
            settings.deluge_password,
        )

        # Set shorter timeout for connection
        import socket
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(5.0)  # 5 second timeout

        try:
            client.connect()

            # Get all torrents with files info (cache this)
            result = client.call(
                "core.get_torrents_status",
                {},
                ["save_path", "files"],
            )

            client.disconnect()
        finally:
            socket.setdefaulttimeout(old_timeout)

        # Cache the result for future lookups
        _deluge_cache = result
        logger.debug(f"Cached {len(result)} torrents from Deluge")

        return _search_deluge_cache(target_path, result)

    except Exception as e:
        logger.debug(f"Could not query Deluge for file size: {e}")
        _deluge_connection_failed = True
        return None


def _search_deluge_cache(target_path: Path, cache: dict) -> Optional[int]:
    """Search cached Deluge torrent data for a matching file."""
    for torrent_id, torrent_data in cache.items():
        save_path_raw = torrent_data.get(b"save_path") or torrent_data.get("save_path")
        files_raw = torrent_data.get(b"files") or torrent_data.get("files")

        if not save_path_raw or not files_raw:
            continue

        # Handle bytes vs string
        if isinstance(save_path_raw, bytes):
            save_path_raw = save_path_raw.decode("utf-8")

        save_path = Path(save_path_raw)

        for file_info in files_raw:
            file_path_raw = file_info.get(b"path") or file_info.get("path")
            file_size = file_info.get(b"size") or file_info.get("size")

            if not file_path_raw:
                continue

            if isinstance(file_path_raw, bytes):
                file_path_raw = file_path_raw.decode("utf-8")

            full_path = save_path / file_path_raw

            # Check if this matches our target
            if full_path == target_path or full_path.resolve() == target_path.resolve():
                logger.debug(f"Found file size from Deluge cache: {target_path} = {file_size} bytes")
                return file_size

    logger.debug(f"File not found in Deluge cache: {target_path}")
    return None


def find_broken_symlinks(directory: Path, recursive: bool = True) -> List[Tuple[Path, Path]]:
    """
    Find all broken symlinks in directory.

    Args:
        directory: Directory to scan
        recursive: Whether to scan recursively

    Returns:
        List of (symlink_path, broken_target) tuples
    """
    broken = []
    glob_pattern = "**/*" if recursive else "*"

    for path in directory.glob(glob_pattern):
        if path.is_symlink() and not path.exists():
            try:
                target = Path(os.readlink(path))
                # Make absolute if relative
                if not target.is_absolute():
                    target = (path.parent / target).resolve()
                broken.append((path, target))
            except OSError:
                # Can't read symlink, skip
                pass

    return broken


def find_matching_file(
    broken_target: Path,
    search_dirs: List[Path],
    strict: bool = False,
    prober: Optional["MetadataProber"] = None,
    expected_size: Optional[int] = None,
) -> Optional[Path]:
    """
    Find a file that matches the broken symlink target.

    Tries several strategies:
    1. Exact match in same directory (file may have moved back)
    2. File with resolution tag added (e.g., "Title.mkv" -> "Title [1080p].mkv")
    3. Prefix match in search directories
    4. Flexible match by show name + S##E## (handles different episode titles)
    5. If expected_size provided, use it to verify/filter candidates
    6. If prober provided and multiple candidates, verify resolution with ffprobe

    Args:
        broken_target: The broken target path
        search_dirs: Directories to search in
        strict: If True, only match in same directory
        prober: Optional MetadataProber for resolution verification
        expected_size: Optional expected file size in bytes for verification

    Returns:
        Path to matching file, or None
    """
    target_dir = broken_target.parent
    target_stem = broken_target.stem  # e.g., "Show - S01E01 - Title"
    target_ext = broken_target.suffix  # e.g., ".mkv"

    # Collect all candidates
    candidates: List[Path] = []

    # Strategy 1: Check same directory for exact match or with resolution tag
    if target_dir.exists():
        # Try exact filename first
        if broken_target.exists() and not broken_target.is_symlink():
            return broken_target

        # Try with resolution tags
        for f in target_dir.glob(f"{target_stem}*{target_ext}"):
            if f.exists() and not f.is_symlink() and f.is_file():
                # Check if difference is just a resolution tag
                diff = f.stem[len(target_stem):]
                if not diff or RESOLUTION_TAG_PATTERN.fullmatch(diff):
                    candidates.append(f)

    # If we have a single match from same directory, return it
    if len(candidates) == 1:
        return candidates[0]

    if not strict:
        # Strategy 2: Search in provided directories
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue

            # Look for files with same extension and similar name
            for f in search_dir.rglob(f"*{target_ext}"):
                if not f.is_file() or f.is_symlink():
                    continue

                # Skip if already in candidates
                if f in candidates:
                    continue

                # Check if the stem starts with our target stem
                if f.stem.startswith(target_stem):
                    diff = f.stem[len(target_stem):]
                    if not diff or RESOLUTION_TAG_PATTERN.fullmatch(diff):
                        candidates.append(f)
                        continue

                # Also check if target stem starts with file stem (reversed)
                # This catches cases where resolution was removed
                if target_stem.startswith(f.stem):
                    diff = target_stem[len(f.stem):]
                    if not diff or RESOLUTION_TAG_PATTERN.fullmatch(diff):
                        candidates.append(f)

        # Strategy 3: Flexible matching by show name + S##E##
        # This handles cases where episode titles differ
        if not candidates:
            target_info = extract_episode_info(target_stem)
            if target_info:
                target_show, target_season, target_ep = target_info
                logger.debug(f"Strategy 3: Looking for {target_show} S{target_season:02d}E{target_ep:02d}")

                for search_dir in search_dirs:
                    if not search_dir.exists():
                        continue

                    for f in search_dir.rglob(f"*{target_ext}"):
                        if not f.is_file() or f.is_symlink():
                            continue
                        if f in candidates:
                            continue

                        file_info = extract_episode_info(f.stem)
                        if file_info:
                            file_show, file_season, file_ep = file_info
                            # Match if show name is similar and season/episode match exactly
                            if (file_season == target_season and
                                file_ep == target_ep and
                                _show_names_match(target_show, file_show)):
                                logger.debug(f"Strategy 3: Found match {f.name}")
                                candidates.append(f)

    if not candidates:
        return None

    # If we have expected_size, use it to filter candidates (highest confidence)
    if expected_size:
        size_matches = []
        for candidate in candidates:
            try:
                candidate_size = candidate.stat().st_size
                if candidate_size == expected_size:
                    size_matches.append(candidate)
                    logger.debug(f"Size match: {candidate.name} ({candidate_size} bytes)")
            except OSError:
                continue

        if len(size_matches) == 1:
            logger.debug(f"Single size match found: {size_matches[0].name}")
            return size_matches[0]
        elif size_matches:
            # Narrow down candidates to those with matching size
            candidates = size_matches
            logger.debug(f"Filtered to {len(candidates)} size-matched candidates")

    # If only one candidate, return it
    if len(candidates) == 1:
        return candidates[0]

    # Multiple candidates - try to pick the best one
    # First, check if the broken target had a resolution tag we can use
    expected_res = extract_resolution_from_filename(target_stem)

    if expected_res:
        # Look for candidate with matching resolution in filename
        for candidate in candidates:
            candidate_res = extract_resolution_from_filename(candidate.stem)
            if candidate_res and candidate_res == expected_res:
                return candidate

    # If we have a prober, use ffprobe to verify resolution
    if prober and prober.is_available:
        for candidate in candidates:
            quality = prober.probe_quality(candidate)
            if quality and quality.resolution_raw:
                # If broken target has resolution, match it
                if expected_res and _resolution_matches(quality.resolution_raw, expected_res):
                    logger.debug(f"FFprobe matched {candidate.name} with resolution {quality.resolution_raw}")
                    return candidate

                # If candidate filename has resolution, verify it matches the file
                candidate_filename_res = extract_resolution_from_filename(candidate.stem)
                if candidate_filename_res and _resolution_matches(quality.resolution_raw, candidate_filename_res):
                    # This candidate's filename resolution matches its actual resolution
                    logger.debug(f"FFprobe verified {candidate.name} resolution matches filename")
                    return candidate

    # Fall back to first candidate (prefer same directory)
    same_dir_candidates = [c for c in candidates if c.parent == target_dir]
    if same_dir_candidates:
        return same_dir_candidates[0]

    return candidates[0]


def fix_symlink(symlink_path: Path, new_target: Path, dry_run: bool = False) -> bool:
    """
    Fix a broken symlink to point to new target.

    Args:
        symlink_path: Path to the symlink
        new_target: New target path
        dry_run: If True, don't actually modify

    Returns:
        True if successful
    """
    if dry_run:
        return True

    try:
        # Remove old symlink
        symlink_path.unlink()

        # Create new symlink (use relative path if possible)
        try:
            rel_target = os.path.relpath(new_target, symlink_path.parent)
            os.symlink(rel_target, symlink_path)
        except ValueError:
            # Different drives on Windows, use absolute
            os.symlink(str(new_target), str(symlink_path))

        return True
    except OSError as e:
        logger.error(f"Failed to fix symlink {symlink_path}: {e}")
        return False


@app.command("symlinks")
def repair_symlinks(
    torrent_dir: Optional[Path] = typer.Option(
        None,
        "--torrent-dir", "-t",
        help="Directory to scan for broken symlinks",
    ),
    media_dir: Optional[Path] = typer.Option(
        None,
        "--media-dir", "-m",
        help="Media directory to search for matches",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run", "-n",
        help="Preview changes without applying",
    ),
    strict: bool = typer.Option(
        False,
        "--strict", "-s",
        help="Only match files in same directory",
    ),
    no_db: bool = typer.Option(
        False,
        "--no-db",
        help="Don't update operations database",
    ),
    skip_ffprobe: bool = typer.Option(
        False,
        "--skip-ffprobe",
        help="Skip ffprobe resolution verification (faster but less accurate)",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed matching information",
    ),
) -> None:
    """Find and fix broken symlinks in torrent directories."""
    settings = get_settings()

    # Default directories
    if torrent_dir is None:
        torrent_dir = Path.home() / "torrents" / "completed"

    if not torrent_dir.exists():
        console.print(f"[red]Directory not found: {torrent_dir}[/]")
        raise typer.Exit(1)

    # Build search directories
    search_dirs = []
    if media_dir:
        search_dirs.append(media_dir)
    else:
        # Use configured media directories
        if settings.tv_dir.exists():
            search_dirs.append(settings.tv_dir)
        if settings.movies_dir.exists():
            search_dirs.append(settings.movies_dir)

    # Warn if no search directories found
    if not search_dirs:
        console.print()
        console.print("[yellow]Warning: No search directories found![/]")
        console.print(f"[yellow]  tv_dir: {settings.tv_dir} (exists: {settings.tv_dir.exists()})[/]")
        console.print(f"[yellow]  movies_dir: {settings.movies_dir} (exists: {settings.movies_dir.exists()})[/]")
        console.print("[yellow]  Check your config.toml paths or use --media-dir[/]")
        console.print()

    # Initialize prober for resolution verification
    prober = None
    if not skip_ffprobe:
        try:
            from jackmediaman.core.metadata_cache import MetadataCache
            from jackmediaman.services.metadata_prober import MetadataProber

            cache = MetadataCache()  # Uses default ~/.jackmediaman/metadata.db
            prober = MetadataProber(cache=cache)
            if not prober.is_available:
                console.print("[yellow]Warning: ffprobe not available, skipping resolution verification[/]")
                prober = None
        except Exception as e:
            logger.debug(f"Could not initialize prober: {e}")

    console.print()
    console.print(Panel(
        f"[bold]Symlink Repair[/]\n\n"
        f"Scanning: {torrent_dir}\n"
        f"Search dirs: {', '.join(str(d) for d in search_dirs) or 'None'}\n"
        f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n"
        f"FFprobe: {'enabled' if prober else 'disabled'}",
        border_style="cyan",
    ))
    console.print()

    # Find broken symlinks
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Scanning for broken symlinks...", total=None)
        broken = find_broken_symlinks(torrent_dir)
        progress.update(task, completed=True)

    if not broken:
        console.print("[green]No broken symlinks found![/]")
        return

    console.print(f"Found [yellow]{len(broken)}[/] broken symlinks")
    console.print()

    # Initialize database
    ops_db = None
    if not no_db:
        try:
            ops_db = get_operations_db()
        except Exception as e:
            console.print(f"[yellow]Warning: Could not open operations database: {e}[/]")

    # Find matches and fix
    results_table = Table(title="Repair Results")
    results_table.add_column("Symlink", style="cyan", no_wrap=True, max_width=40)
    results_table.add_column("Status", style="bold")
    results_table.add_column("Match", max_width=50)

    fixed = 0
    failed = 0
    no_match = 0

    for symlink_path, broken_target in broken:
        if verbose:
            console.print(f"\n[dim]Searching for: {broken_target.name}[/]")
            console.print(f"[dim]  Target dir: {broken_target.parent}[/]")
            target_info = extract_episode_info(broken_target.stem)
            if target_info:
                show, season, ep = target_info
                console.print(f"[dim]  Parsed: {show} S{season:02d}E{ep:02d}[/]")

        # Try to get expected file size for verification
        expected_size = None

        # First try getting size from database
        if ops_db:
            try:
                expected_size = ops_db.get_symlink_target_size(symlink_path)
                if expected_size and verbose:
                    console.print(f"[dim]  Expected size (DB): {expected_size:,} bytes[/]")
            except Exception:
                pass

        # If not in DB, try getting from Deluge
        if expected_size is None:
            expected_size = get_file_size_from_deluge(broken_target)
            if expected_size and verbose:
                console.print(f"[dim]  Expected size (Deluge): {expected_size:,} bytes[/]")

        # Try to find matching file
        match = find_matching_file(
            broken_target,
            search_dirs,
            strict=strict,
            prober=prober,
            expected_size=expected_size,
        )

        if verbose and match:
            console.print(f"[dim]  Found: {match}[/]")
        elif verbose and not match:
            console.print(f"[dim]  No match found in: {', '.join(str(d) for d in search_dirs)}[/]")

        if match:
            success = fix_symlink(symlink_path, match, dry_run=dry_run)
            if success:
                fixed += 1
                status = "[green]FIXED[/]" if not dry_run else "[blue]WOULD FIX[/]"
                results_table.add_row(
                    str(symlink_path.name),
                    status,
                    str(match.name),
                )

                # Log to database
                if ops_db and not dry_run:
                    try:
                        op_id = ops_db.log_operation(
                            op_type="repair_symlink",
                            source=symlink_path,
                            dest=match,
                            success=True,
                        )
                        ops_db.update_symlink_target(symlink_path, match)
                    except Exception:
                        pass
            else:
                failed += 1
                results_table.add_row(
                    str(symlink_path.name),
                    "[red]FAILED[/]",
                    f"Error fixing -> {match.name}",
                )
        else:
            no_match += 1
            results_table.add_row(
                str(symlink_path.name),
                "[yellow]NO MATCH[/]",
                f"Expected: {broken_target.name}",
            )

            # Mark as invalid in database
            if ops_db:
                try:
                    ops_db.mark_symlink_invalid(symlink_path)
                except Exception:
                    pass

    console.print(results_table)
    console.print()

    # Summary
    summary = []
    if dry_run:
        summary.append(f"[blue]Would fix: {fixed}[/]")
    else:
        summary.append(f"[green]Fixed: {fixed}[/]")
    if failed:
        summary.append(f"[red]Failed: {failed}[/]")
    if no_match:
        summary.append(f"[yellow]No match: {no_match}[/]")

    console.print(" | ".join(summary))
    console.print()

    if dry_run and fixed > 0:
        console.print("[dim]Run without --dry-run to apply fixes[/]")


@app.command("scan")
def scan_symlinks(
    directory: Optional[Path] = typer.Option(
        None,
        "--dir", "-d",
        help="Directory to scan",
    ),
    show_valid: bool = typer.Option(
        False,
        "--all", "-a",
        help="Show all symlinks, not just broken ones",
    ),
) -> None:
    """Scan and report on symlinks in a directory."""
    if directory is None:
        directory = Path.home() / "torrents" / "completed"

    if not directory.exists():
        console.print(f"[red]Directory not found: {directory}[/]")
        raise typer.Exit(1)

    console.print(f"\nScanning [cyan]{directory}[/] for symlinks...\n")

    # Find all symlinks
    symlinks = []
    for path in directory.rglob("*"):
        if path.is_symlink():
            try:
                target = Path(os.readlink(path))
                if not target.is_absolute():
                    target = (path.parent / target).resolve()
                is_valid = path.exists()
                symlinks.append((path, target, is_valid))
            except OSError:
                symlinks.append((path, Path("(unreadable)"), False))

    if not symlinks:
        console.print("[dim]No symlinks found[/]")
        return

    # Filter if not showing all
    if not show_valid:
        symlinks = [(p, t, v) for p, t, v in symlinks if not v]

    if not symlinks:
        console.print("[green]All symlinks are valid![/]")
        return

    # Display results
    table = Table(title=f"Symlinks in {directory.name}")
    table.add_column("Symlink", style="cyan")
    table.add_column("Status")
    table.add_column("Target")

    valid_count = 0
    broken_count = 0

    for symlink_path, target, is_valid in symlinks:
        rel_path = symlink_path.relative_to(directory) if symlink_path.is_relative_to(directory) else symlink_path

        if is_valid:
            valid_count += 1
            status = "[green]OK[/]"
        else:
            broken_count += 1
            status = "[red]BROKEN[/]"

        table.add_row(
            str(rel_path),
            status,
            str(target.name) if target.name != "(unreadable)" else "[red](unreadable)[/]",
        )

    console.print(table)
    console.print()
    console.print(f"Total: {len(symlinks)} | [green]Valid: {valid_count}[/] | [red]Broken: {broken_count}[/]")


@app.command("db-stats")
def database_stats() -> None:
    """Show operations database statistics."""
    try:
        ops_db = get_operations_db()
        stats = ops_db.get_stats()
    except Exception as e:
        console.print(f"[red]Error opening database: {e}[/]")
        raise typer.Exit(1)

    console.print()
    console.print(Panel("[bold]Operations Database Statistics[/]", border_style="cyan"))
    console.print()

    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="bold")

    table.add_row("Total Operations", str(stats["total_operations"]))
    table.add_row("Total Symlinks", str(stats["total_symlinks"]))
    table.add_row("Valid Symlinks", str(stats["valid_symlinks"]))
    table.add_row("Tracked Files", str(stats["tracked_files"]))

    console.print(table)

    if stats["operations_by_type"]:
        console.print()
        console.print("[bold]Operations by Type:[/]")
        for op_type, count in stats["operations_by_type"].items():
            console.print(f"  {op_type}: {count}")

    console.print()


@app.command("folders")
def consolidate_folders(
    tv_dir: Optional[Path] = typer.Option(
        None,
        "--tv-dir", "-t",
        help="TV shows directory to consolidate",
    ),
    torrent_dir: Optional[Path] = typer.Option(
        None,
        "--torrent-dir",
        help="Torrent directory (for updating symlinks)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run", "-n",
        help="Preview changes without applying",
    ),
    show: Optional[str] = typer.Option(
        None,
        "--show", "-s",
        help="Only consolidate specific show (by folder name)",
    ),
) -> None:
    """Consolidate season folder variants (e.g., 'Season.05' -> 'Season 05')."""
    settings = get_settings()

    if tv_dir is None:
        tv_dir = settings.tv_dir

    if not tv_dir.exists():
        console.print(f"[red]TV directory not found: {tv_dir}[/]")
        raise typer.Exit(1)

    if torrent_dir is None:
        torrent_dir = settings.torrent_dir

    console.print()
    console.print(Panel(
        f"[bold]Season Folder Consolidation[/]\n\n"
        f"TV directory: {tv_dir}\n"
        f"Torrent directory: {torrent_dir}\n"
        f"Mode: {'DRY RUN' if dry_run else 'LIVE'}",
        border_style="cyan",
    ))
    console.print()

    # Use the FolderConsolidator service
    consolidator = FolderConsolidator(tv_dir=tv_dir)
    shows_to_process = consolidator.find_season_folder_variants(show_filter=show)

    if not shows_to_process:
        console.print("[green]No duplicate season folders found![/]")
        return

    console.print(f"Found [yellow]{len(shows_to_process)}[/] seasons with duplicate folders\n")

    # Display what will be done
    for show_folder, season_num, folders in shows_to_process:
        canonical = show_folder / f"Season {season_num:02d}"

        console.print(f"[bold]{show_folder.name}[/] Season {season_num:02d}:")
        for folder in folders:
            marker = "[green]✓[/]" if folder == canonical else "[yellow]→[/]"
            file_count = len([f for f in folder.iterdir() if f.is_file()])
            console.print(f"  {marker} {folder.name} ({file_count} files)")

        if dry_run:
            console.print(f"  [blue]Would consolidate to:[/] Season {season_num:02d}")
        else:
            console.print(f"  [green]Consolidating to:[/] Season {season_num:02d}")
        console.print()

    if dry_run:
        console.print("[blue]DRY RUN - no changes made[/]")
        return

    # Perform consolidation using service
    result = consolidator.consolidate_season_folders(
        torrent_dir=torrent_dir,
        show_filter=show,
    )

    # Summary
    console.print()
    console.print(f"[green]Done![/]")
    console.print(f"  Files moved: {result.files_moved}")
    console.print(f"  Folders removed: {result.folders_removed}")
    console.print(f"  Symlinks updated: {result.symlinks_updated}")

    console.print()
    if result.files_moved > 0:
        console.print("[dim]Run 'jmm duplicates scan' to find and resolve any duplicates[/]")
