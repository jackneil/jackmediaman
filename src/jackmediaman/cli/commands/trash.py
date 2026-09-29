"""Trash management commands."""

from datetime import datetime

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jackmediaman.services.cleaner import CleanupService
from jackmediaman.cli.interactive import confirm_action

app = typer.Typer(help="Manage trash directory")
console = Console()


@app.command("list")
def list_trash() -> None:
    """List contents of trash directory."""
    cleaner = CleanupService()
    files = cleaner.list_trash()

    if not files:
        console.print("\n[dim]Trash is empty[/]\n")
        return

    total_size = sum(f.stat().st_size for f, _ in files if f.exists())
    total_gb = total_size / (1024 * 1024 * 1024)

    console.print()
    console.print(Panel(
        f"[bold]{len(files)} files in trash[/]\n"
        f"[dim]Total size: {total_gb:.2f} GB[/]",
        title="[bold cyan]Trash Contents[/]",
        border_style="cyan",
    ))
    console.print()

    table = Table(show_header=True)
    table.add_column("#", style="dim", justify="right")
    table.add_column("Date", style="dim")
    table.add_column("File", style="white")
    table.add_column("Size", style="magenta", justify="right")

    for i, (path, timestamp) in enumerate(files[:30], 1):
        if not path.exists():
            continue
        size_mb = path.stat().st_size / (1024 * 1024)
        # Remove timestamp prefix from filename for display
        parts = path.name.split("_", 2)
        display_name = parts[2] if len(parts) >= 3 else path.name
        table.add_row(
            str(i),
            timestamp.strftime("%Y-%m-%d %H:%M"),
            display_name[:50] + "..." if len(display_name) > 50 else display_name,
            f"{size_mb:.1f} MB",
        )

    if len(files) > 30:
        table.add_row("", "", f"[dim]... and {len(files) - 30} more files[/]", "")

    console.print(table)
    console.print()
    console.print("[dim]Use 'jmm trash clear' to permanently delete files[/]")
    console.print("[dim]Use 'jmm trash restore <number>' to restore a file[/]")
    console.print()


@app.command("clear")
def clear_trash(
    days: int = typer.Option(
        None,
        "--days",
        "-d",
        help="Only delete files older than N days",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Permanently delete files from trash.

    By default, asks for confirmation before deleting.
    Use --yes to skip the confirmation prompt.
    Use --days N to only delete files older than N days.
    """
    cleaner = CleanupService()
    files = cleaner.list_trash()

    if not files:
        console.print("\n[dim]Trash is already empty[/]\n")
        return

    # Count files that would be deleted
    if days:
        cutoff = datetime.now().timestamp() - (days * 86400)
        files_to_delete = [
            (f, ts) for f, ts in files
            if f.exists() and f.stat().st_mtime <= cutoff
        ]
        if not files_to_delete:
            console.print(f"\n[dim]No files older than {days} days in trash[/]\n")
            return
        count = len(files_to_delete)
        message = f"Permanently delete {count} files older than {days} days?"
    else:
        count = len(files)
        message = f"Permanently delete {count} files from trash?"

    # Calculate size
    total_size = sum(f.stat().st_size for f, _ in files if f.exists())
    total_gb = total_size / (1024 * 1024 * 1024)

    console.print()
    console.print(Panel(
        f"[bold red]Warning: This action cannot be undone![/]\n\n"
        f"Files to delete: {count}\n"
        f"Total size: {total_gb:.2f} GB",
        title="[bold red]Confirm Delete[/]",
        border_style="red",
    ))

    if not yes:
        if not confirm_action(message, default=False):
            console.print("[dim]Cancelled[/]\n")
            return

    deleted = cleaner.empty_trash(older_than_days=days)
    console.print(f"\n[green]Permanently deleted {deleted} files[/]\n")


@app.command("restore")
def restore_file(
    file_number: int = typer.Argument(
        ...,
        help="File number from 'jmm trash list' to restore",
    ),
) -> None:
    """Restore a file from trash.

    Use 'jmm trash list' to see file numbers, then restore using:
    jmm trash restore <number>
    """
    cleaner = CleanupService()
    files = cleaner.list_trash()

    if not files:
        console.print("\n[red]Trash is empty[/]\n")
        raise typer.Exit(1)

    if file_number < 1 or file_number > len(files):
        console.print(f"\n[red]Invalid file number. Must be 1-{len(files)}[/]\n")
        raise typer.Exit(1)

    trash_path, timestamp = files[file_number - 1]

    # Parse original filename from trash name (format: YYYYMMDD_HHMMSS_originalname.ext)
    parts = trash_path.name.split("_", 2)
    if len(parts) >= 3:
        original_name = parts[2]
    else:
        original_name = trash_path.name

    console.print()
    console.print(f"[bold]File to restore:[/] {original_name}")
    console.print(f"[dim]Trashed on:[/] {timestamp.strftime('%Y-%m-%d %H:%M')}")
    console.print()

    # Ask user where to restore
    from rich.prompt import Prompt
    dest_str = Prompt.ask(
        "Enter destination path (leave empty to skip)",
        default="",
    )

    if not dest_str:
        console.print("[dim]Cancelled[/]\n")
        return

    from pathlib import Path
    dest_path = Path(dest_str).expanduser()

    # If user provides a directory, append the original filename
    if dest_path.is_dir():
        dest_path = dest_path / original_name
    elif not dest_path.parent.exists():
        console.print(f"[red]Parent directory does not exist: {dest_path.parent}[/]\n")
        raise typer.Exit(1)

    if dest_path.exists():
        if not confirm_action(f"File already exists at {dest_path}. Overwrite?", default=False):
            console.print("[dim]Cancelled[/]\n")
            return

    success = cleaner.restore_from_trash(trash_path, dest_path)

    if success:
        console.print(f"\n[green]Restored to: {dest_path}[/]\n")
    else:
        console.print(f"\n[red]Failed to restore file[/]\n")
        raise typer.Exit(1)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Manage trash directory.

    \b
    Commands:
      jmm trash list           - Show files in trash
      jmm trash clear          - Permanently delete all trash
      jmm trash clear --days N - Delete files older than N days
      jmm trash restore N      - Restore file number N
    """
    if ctx.invoked_subcommand is None:
        # Default to listing trash
        list_trash()
