"""Torrents command for managing Deluge torrents."""

from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from jackmediaman.services.torrents import TorrentService

app = typer.Typer(help="Manage Deluge torrents")
console = Console()


def _get_state_style(state: str) -> str:
    """Get Rich style for torrent state."""
    state_lower = state.lower()
    if state_lower == "seeding":
        return "green"
    elif state_lower == "downloading":
        return "blue"
    elif state_lower == "paused":
        return "yellow"
    elif state_lower in ("error", "queued"):
        return "red"
    return "white"


def _get_folder_name(save_path: Path) -> tuple[str, str]:
    """Get the folder name and style from save path."""
    folder = save_path.name
    folder_lower = folder.lower()
    if "downloading" in folder_lower:
        return folder, "yellow"
    elif "completed" in folder_lower:
        return folder, "green"
    return folder, "dim"


def _truncate(text: str, max_len: int = 45) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


MEDIA_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.flv', '.webm'}


def _get_file_type(path: Path) -> str:
    """Detect file type: real, symlink, or hardlink.

    For directories, checks the largest media file to determine type.
    """
    if not path.exists():
        return "missing"
    if path.is_symlink():
        return "symlink"
    # Check for hardlink (nlink > 1 for files)
    if path.is_file() and path.stat().st_nlink > 1:
        return "hardlink"
    # For directories, find the largest media file and check that
    if path.is_dir():
        try:
            media_files = []
            for f in path.rglob("*"):
                if f.is_file() and f.suffix.lower() in MEDIA_EXTENSIONS:
                    try:
                        size = f.stat().st_size if not f.is_symlink() else 0
                        media_files.append((f, size))
                    except (OSError, PermissionError):
                        media_files.append((f, 0))

            if media_files:
                # Sort by size descending, check the largest
                media_files.sort(key=lambda x: x[1], reverse=True)
                largest = media_files[0][0]
                if largest.is_symlink():
                    return "symlink"
                if largest.stat().st_nlink > 1:
                    return "hardlink"
        except (PermissionError, OSError):
            pass
    return "real"


def _get_file_type_display(file_type: str) -> str:
    """Get styled display for file type."""
    styles = {
        "symlink": "[cyan]symlink[/]",
        "hardlink": "[yellow]hardlink[/]",
        "missing": "[red]missing[/]",
        "real": "real",
    }
    return styles.get(file_type, file_type)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Manage Deluge torrents.

    Without a subcommand, lists all torrents.
    """
    if ctx.invoked_subcommand is None:
        list_torrents()


@app.command("list")
def list_torrents() -> None:
    """List all torrents with their status."""
    console.print()

    service = TorrentService()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Connecting to Deluge...", total=None)

        if not service.connect():
            console.print("[red]Failed to connect to Deluge daemon[/]")
            console.print()
            console.print("Run [cyan]jmm setup deluge[/] to configure connection settings")
            console.print()
            return

        progress.add_task("Fetching torrents...", total=None)
        torrents = service.get_torrents()

    if not torrents:
        console.print("[dim]No torrents found[/]")
        console.print()
        service.disconnect()
        return

    # Detect file types with progress indicator
    file_types: dict[str, str] = {}
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Checking file types...", total=None)
        for torrent in torrents:
            torrent_path = torrent.save_path / torrent.name
            file_types[torrent.torrent_id] = _get_file_type(torrent_path)

    # Count torrents needing move
    needs_move = [t for t in torrents if service.needs_move(t)]
    needs_move_size = sum(t.total_size for t in needs_move)
    needs_move_gb = needs_move_size / (1024 * 1024 * 1024)

    # Summary panel
    console.print(
        Panel(
            f"[bold]{len(torrents)} torrents[/]",
            title="[bold cyan]Deluge Torrents[/]",
            border_style="cyan",
        )
    )
    console.print()

    # Build table - expand to full terminal width
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Name", style="white", overflow="ellipsis", no_wrap=True, ratio=3)
    table.add_column("State", width=11, no_wrap=True)
    table.add_column("Folder", width=12, no_wrap=True)
    table.add_column("Type", width=8, no_wrap=True)
    table.add_column("Size", style="magenta", justify="right", width=6, no_wrap=True)

    for torrent in torrents:
        state_style = _get_state_style(torrent.state)
        folder, folder_style = _get_folder_name(torrent.save_path)
        file_type = file_types.get(torrent.torrent_id, "real")
        type_display = _get_file_type_display(file_type)

        table.add_row(
            torrent.name,
            f"[{state_style}]{torrent.state}[/]",
            f"[{folder_style}]{folder}[/]",
            type_display,
            f"{torrent.size_gb:.1f}G",
        )

    console.print(table)
    console.print()

    # Show hint if there are torrents needing move
    if needs_move:
        console.print(
            f"[yellow]{len(needs_move)} completed torrents in downloading folder "
            f"({needs_move_gb:.2f} GB)[/]"
        )
        console.print("[dim]Run [cyan]jmm torrents move[/] to move them to completed folder[/]")
        console.print()

    service.disconnect()


@app.command("move")
def move_completed(
    dry_run: bool = typer.Option(
        True,
        "--dry-run/--execute",
        help="Show what would be done without making changes",
    ),
) -> None:
    """Move completed torrents to the completed folder.

    By default, runs in dry-run mode to show what would be moved.
    Use --execute to actually move the torrents.

    Examples:
        jmm torrents move           # Show what would be moved
        jmm torrents move --execute # Actually move torrents
    """
    console.print()

    service = TorrentService()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Connecting to Deluge...", total=None)

        if not service.connect():
            console.print("[red]Failed to connect to Deluge daemon[/]")
            console.print()
            console.print("Run [cyan]jmm setup deluge[/] to configure connection settings")
            console.print()
            return

        progress.add_task("Checking torrents...", total=None)
        torrents = service.get_torrents_needing_move()

    if not torrents:
        console.print("[green]No torrents need to be moved[/]")
        console.print("[dim]All completed torrents are already in the completed folder[/]")
        console.print()
        service.disconnect()
        return

    # Calculate totals
    total_size = sum(t.total_size for t in torrents)
    total_gb = total_size / (1024 * 1024 * 1024)

    # Header
    mode_text = (
        "[yellow]DRY RUN - No files will be moved[/]"
        if dry_run
        else "[green]EXECUTE MODE - Files will be moved[/]"
    )
    console.print(
        Panel(
            f"{mode_text}\n\n"
            f"[bold]{len(torrents)} torrents[/] to move ({total_gb:.2f} GB)\n"
            f"[dim]From:[/] {service.download_path}\n"
            f"[dim]To:[/] {service.completed_path}",
            title="[bold cyan]Move Completed Torrents[/]",
            border_style="cyan",
        )
    )
    console.print()

    # Build table
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Name", style="white", no_wrap=False, max_width=50)
    table.add_column("Size", style="magenta", justify="right", width=10)
    table.add_column("Status", style="white", width=12)

    if dry_run:
        # Just show what would be moved
        for torrent in torrents:
            table.add_row(
                _truncate(torrent.name, 50),
                f"{torrent.size_gb:.2f} GB",
                "[yellow]Will move[/]",
            )
        console.print(table)
        console.print()
        console.print(
            f"[dim]Run [cyan]jmm torrents move --execute[/] to move "
            f"{len(torrents)} torrents ({total_gb:.2f} GB)[/]"
        )
    else:
        # Actually move
        results = service.move_completed(dry_run=False)

        success_count = 0
        fail_count = 0

        for result in results:
            if result.success:
                status = "[green]Moved[/]"
                success_count += 1
            else:
                status = f"[red]Failed: {result.error}[/]"
                fail_count += 1

            table.add_row(
                _truncate(result.torrent.name, 50),
                f"{result.torrent.size_gb:.2f} GB",
                status,
            )

        console.print(table)
        console.print()

        if fail_count == 0:
            console.print(f"[green]Successfully moved {success_count} torrents[/]")
        else:
            console.print(
                f"[yellow]Moved {success_count} torrents, {fail_count} failed[/]"
            )

    console.print()
    service.disconnect()
