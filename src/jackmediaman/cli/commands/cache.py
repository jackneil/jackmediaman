"""Cache management CLI commands."""

from datetime import datetime
from enum import Enum

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jackmediaman.core.config import get_settings
from jackmediaman.core.metadata_cache import MetadataCache
from jackmediaman.core.tmdb_cache import TMDbCache
from jackmediaman.cli.interactive import confirm_action

app = typer.Typer(help="Manage metadata and API caches")
console = Console()


class CacheType(str, Enum):
    """Cache type for clear command."""
    all = "all"
    metadata = "metadata"
    tmdb = "tmdb"


def _get_metadata_cache() -> MetadataCache:
    """Get metadata cache instance."""
    settings = get_settings()
    return MetadataCache(settings.cache_dir / "metadata.db")


def _get_tmdb_cache() -> TMDbCache:
    """Get TMDb cache instance."""
    settings = get_settings()
    return TMDbCache(settings.cache_dir / "tmdb.db")


def _format_age(iso_timestamp: str) -> str:
    """Format ISO timestamp as human-readable age."""
    if not iso_timestamp:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        delta = datetime.now() - dt

        if delta.days > 365:
            years = delta.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif delta.days > 30:
            months = delta.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds > 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif delta.seconds > 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "just now"
    except (ValueError, TypeError):
        return iso_timestamp[:19] if iso_timestamp else "N/A"


@app.command("stats")
def stats() -> None:
    """Show cache statistics for all caches."""
    # FFprobe Metadata Cache
    metadata_cache = _get_metadata_cache()
    metadata_stats = metadata_cache.stats()

    console.print()
    console.print(Panel(
        "[bold]FFprobe Metadata Cache[/]",
        border_style="cyan",
    ))
    console.print()

    table = Table(show_header=False, box=None)
    table.add_column("Property", style="dim")
    table.add_column("Value", style="cyan")

    table.add_row("Cached files", str(metadata_stats["entries"]))
    table.add_row("Database size", f"{metadata_stats['db_size_mb']} MB")

    if metadata_stats["oldest_entry"]:
        table.add_row("Oldest entry", _format_age(metadata_stats["oldest_entry"]))
    if metadata_stats["newest_entry"]:
        table.add_row("Newest entry", _format_age(metadata_stats["newest_entry"]))

    console.print(table)
    console.print()

    # TMDb API Cache
    tmdb_cache = _get_tmdb_cache()
    tmdb_stats = tmdb_cache.stats()

    console.print(Panel(
        "[bold]TMDb API Cache[/]",
        border_style="yellow",
    ))
    console.print()

    table = Table(show_header=False, box=None)
    table.add_column("Property", style="dim")
    table.add_column("Value", style="yellow")

    table.add_row("Movie searches", str(tmdb_stats["movie_searches"]))
    table.add_row("TV show searches", str(tmdb_stats["tv_searches"]))
    table.add_row("Episode titles", str(tmdb_stats["episode_titles"]))
    table.add_row("Movie details", str(tmdb_stats["movie_details"]))
    table.add_row("Total entries", str(tmdb_stats["entries"]))
    table.add_row("Database size", f"{tmdb_stats['db_size_mb']} MB")

    if tmdb_stats["oldest_entry"]:
        table.add_row("Oldest entry", _format_age(tmdb_stats["oldest_entry"]))
    if tmdb_stats["newest_entry"]:
        table.add_row("Newest entry", _format_age(tmdb_stats["newest_entry"]))

    console.print(table)
    console.print()


@app.command("clear")
def clear(
    cache_type: CacheType = typer.Option(
        CacheType.all,
        "--type",
        "-t",
        help="Which cache to clear: all, metadata, tmdb",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Clear cache entries."""
    total_entries = 0
    caches_to_clear = []

    if cache_type in (CacheType.all, CacheType.metadata):
        metadata_cache = _get_metadata_cache()
        metadata_stats = metadata_cache.stats()
        if metadata_stats["entries"] > 0:
            caches_to_clear.append(("FFprobe Metadata", metadata_cache, metadata_stats["entries"]))
            total_entries += metadata_stats["entries"]

    if cache_type in (CacheType.all, CacheType.tmdb):
        tmdb_cache = _get_tmdb_cache()
        tmdb_stats = tmdb_cache.stats()
        if tmdb_stats["entries"] > 0:
            caches_to_clear.append(("TMDb API", tmdb_cache, tmdb_stats["entries"]))
            total_entries += tmdb_stats["entries"]

    if total_entries == 0:
        console.print("[yellow]Selected cache(s) already empty[/]")
        return

    console.print()
    for name, _, count in caches_to_clear:
        console.print(f"[bold]{name} Cache:[/] {count} entries")
    console.print(f"[bold]Total:[/] {total_entries} entries")
    console.print()

    if not yes:
        prompt = f"Clear {cache_type.value} cache{'s' if cache_type == CacheType.all else ''}?"
        if not confirm_action(prompt, default=False):
            console.print("[yellow]Cancelled[/]")
            return

    total_cleared = 0
    for name, cache, _ in caches_to_clear:
        cleared = cache.clear()
        console.print(f"[green]Cleared {cleared} entries from {name} cache[/]")
        total_cleared += cleared

    if len(caches_to_clear) > 1:
        console.print(f"\n[bold green]Total cleared: {total_cleared} entries[/]")


@app.command("cleanup")
def cleanup() -> None:
    """Remove metadata cache entries for files that no longer exist."""
    cache = _get_metadata_cache()
    cache_stats = cache.stats()

    if cache_stats["entries"] == 0:
        console.print("[yellow]Metadata cache is empty, nothing to clean up[/]")
        return

    console.print(f"[dim]Checking {cache_stats['entries']} cached files...[/]")

    removed = cache.cleanup_stale()

    if removed == 0:
        console.print("[green]All cached files still exist, no cleanup needed[/]")
    else:
        console.print(f"[green]Removed {removed} stale entries from metadata cache[/]")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Manage metadata and API caches."""
    if ctx.invoked_subcommand is None:
        # Default to showing stats
        stats()
