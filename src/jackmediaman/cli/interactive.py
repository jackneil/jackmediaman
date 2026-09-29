"""Rich-based interactive menu system for JackMediaMan.

Clean, organized, and visually appealing terminal UI.
"""

import os
import sys
from enum import Enum
from pathlib import Path
from typing import List, Optional, TypeVar

from rich.console import Console, Group
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich import box
from rich.columns import Columns
from rich.progress import Progress, SpinnerColumn, TextColumn

from jackmediaman import __version__
from jackmediaman.core.config import get_config_path

console = Console()
T = TypeVar("T", bound=Enum)

# ASCII Logo - compact version
LOGO = """
     ██╗███╗   ███╗███╗   ███╗
     ██║████╗ ████║████╗ ████║
     ██║██╔████╔██║██╔████╔██║
██   ██║██║╚██╔╝██║██║╚██╔╝██║
╚█████╔╝██║ ╚═╝ ██║██║ ╚═╝ ██║
 ╚════╝ ╚═╝     ╚═╝╚═╝     ╚═╝"""


def clear_screen() -> None:
    """Clear the terminal screen."""
    os.system("cls" if os.name == "nt" else "clear")


def show_header(subtitle: str = "") -> None:
    """Display the application header with optional subtitle."""
    # Get config path for display
    config_path = get_config_path()

    header_content = Text()
    header_content.append(LOGO, style="bold cyan")
    header_content.append(f"\n\n  Media Library Manager", style="dim")

    console.print(Panel(
        header_content,
        subtitle=f"[dim]v{__version__} | {config_path}[/]",
        border_style="cyan",
        padding=(0, 2),
    ))

    if subtitle:
        console.print(f"  [bold]{subtitle}[/]")
    console.print()


def show_status_bar() -> None:
    """Show service status indicators."""
    from jackmediaman.core.config import get_settings

    try:
        settings = get_settings()

        # Build status indicators
        services = []

        # TMDb
        if settings.tmdb_api_key:
            services.append("[green]● TMDb[/]")
        else:
            services.append("[dim]○ TMDb[/]")

        # Deluge: localhost can use auto-auth without credentials
        is_localhost = settings.deluge_host in ("127.0.0.1", "localhost", "::1")
        if is_localhost or settings.deluge_username:
            services.append("[green]● Deluge[/]")
        else:
            services.append("[dim]○ Deluge[/]")

        # OpenSubtitles - check both providers
        com_configured = bool(settings.opensubtitles_com_api_key)
        org_configured = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)

        if com_configured or org_configured:
            services.append("[green]● Subs[/]")
        else:
            services.append("[dim]○ Subs[/]")

        # Plex
        from jackmediaman.services.plex import PlexService
        plex = PlexService()
        if plex.is_configured:
            services.append("[green]● Plex[/]")
        else:
            services.append("[dim]○ Plex[/]")

        # Paths
        paths = []
        if settings.tv_dir.exists():
            paths.append("[green]● TV[/]")
        else:
            paths.append("[red]● TV[/]")

        if settings.movies_dir.exists():
            paths.append("[green]● Movies[/]")
        else:
            paths.append("[red]● Movies[/]")

        console.print(f"  Services: {' '.join(services)}  |  Paths: {' '.join(paths)}")
        console.print()

    except Exception:
        pass


def show_grouped_menu(groups: List[tuple], default: int = 1) -> int:
    """
    Show a menu with grouped sections.

    Args:
        groups: List of (group_name, options) tuples
                where options is list of (label, description) tuples
        default: Default selection (1-indexed)

    Returns:
        Selected option index (1-indexed global)
    """
    console.print()

    table = Table(
        show_header=False,
        box=None,
        padding=(0, 2),
        collapse_padding=True,
    )
    table.add_column("Num", style="cyan", width=5)
    table.add_column("Option", style="white", min_width=20)
    table.add_column("Description", style="dim")

    option_num = 1
    total_options = 0

    for group_name, options in groups:
        # Add group header
        if group_name:
            table.add_row("", f"[bold yellow]{group_name}[/]", "")

        for label, description in options:
            marker = "›" if option_num == default else " "
            table.add_row(f"{marker}[{option_num}]", label, description)
            option_num += 1
            total_options += 1

        # Add spacing between groups
        table.add_row("", "", "")

    # Add exit/back option
    table.add_row(" [0]", "[dim]Exit[/]", "Exit JackMediaMan")

    console.print(Panel(table, border_style="cyan", padding=(0, 1)))

    while True:
        choice = Prompt.ask(
            f"Select [0-{total_options}]",
            default=str(default),
        )
        try:
            idx = int(choice)
            if 0 <= idx <= total_options:
                return idx
        except ValueError:
            pass
        console.print("[red]Invalid selection[/]")


def show_menu(
    title: str,
    options: List[tuple],
    default: int = 1,
    show_back: bool = False,
) -> int:
    """
    Show a simple menu and get user selection.

    Args:
        title: Menu title
        options: List of (label, description) tuples
        default: Default selection (1-indexed)
        show_back: Whether to show "Back" option as 0

    Returns:
        Selected option index (1-indexed, or 0 for back)
    """
    console.print()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Num", style="cyan", width=5)
    table.add_column("Option", style="white")
    table.add_column("Description", style="dim")

    for i, (label, description) in enumerate(options, 1):
        marker = "›" if i == default else " "
        table.add_row(f"{marker}[{i}]", label, description)

    if show_back:
        table.add_row("", "", "")
        table.add_row(" [0]", "[dim]Back[/]", "Return to previous menu")

    console.print(Panel(
        table,
        title=f"[bold cyan]{title}[/]",
        border_style="cyan",
        padding=(0, 1),
    ))

    max_choice = len(options)
    min_choice = 0 if show_back else 1

    while True:
        choice = Prompt.ask(
            f"Select [{min_choice}-{max_choice}]",
            default=str(default),
        )
        try:
            idx = int(choice)
            if min_choice <= idx <= max_choice:
                return idx
        except ValueError:
            pass
        console.print("[red]Invalid selection[/]")


def show_enum_menu(
    title: str,
    enum_class: type[T],
    descriptions: dict,
    default: Optional[T] = None,
) -> T:
    """Show a menu for selecting an enum value."""
    options = [(e.value, descriptions.get(e, "")) for e in enum_class]
    default_idx = 1
    if default:
        for i, e in enumerate(enum_class, 1):
            if e == default:
                default_idx = i
                break

    choice = show_menu(title, options, default=default_idx)
    return list(enum_class)[choice - 1]


def confirm_action(message: str, default: bool = False) -> bool:
    """Ask for confirmation."""
    return Confirm.ask(message, default=default)


def get_path_input(prompt: str, must_exist: bool = True, default: str = "") -> Optional[Path]:
    """Get a path from user input."""
    while True:
        value = Prompt.ask(prompt, default=default)
        if not value:
            return None

        path = Path(value).expanduser().resolve()
        if must_exist and not path.exists():
            console.print(f"[red]Path does not exist: {path}[/]")
            continue
        return path


def show_spinner(message: str):
    """Return a progress context manager with a spinner."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    )


def show_success(message: str) -> None:
    """Show a success message."""
    console.print(f"[green]✓[/] {message}")


def show_error(message: str) -> None:
    """Show an error message."""
    console.print(f"[red]✗[/] {message}")


def show_warning(message: str) -> None:
    """Show a warning message."""
    console.print(f"[yellow]![/] {message}")


def show_info_panel(title: str, content: str) -> None:
    """Show an info panel."""
    console.print(Panel(content, title=f"[bold]{title}[/]", border_style="cyan"))


# =============================================================================
# MAIN MENU
# =============================================================================

def run_main_menu() -> None:
    """Run the main interactive menu loop."""
    while True:
        clear_screen()
        show_header()
        show_status_bar()

        choice = show_grouped_menu([
            ("LIBRARY OPERATIONS", [
                ("Process New Media", "Process completed torrent downloads"),
                ("Manage Torrents", "View/move stuck torrents in Deluge"),
                ("Clean Library", "Remove duplicates and consolidate folders"),
                ("Rename Files", "Rename media to standardized format"),
                ("Manage Subtitles", "Download subtitles for media"),
                ("Fetch Artwork", "Download poster artwork from TMDb"),
                ("Generate NFO Files", "Create Kodi-compatible metadata"),
            ]),
            ("STATUS & INFO", [
                ("Library Status", "View configuration and paths"),
                ("Service Health", "Test Deluge, TMDb, Plex, OpenSubtitles"),
                ("Activity Log", "View processing history and errors"),
                ("Repair Symlinks", "Fix broken symlinks in torrent directory"),
                ("View Trash", "Manage deleted files"),
            ]),
            ("CONFIGURATION", [
                ("Settings", "Configure paths and services"),
                ("Setup Wizard", "Initial setup for services"),
            ]),
        ], default=1)

        # Map choice to action
        actions = {
            1: menu_process,
            2: menu_torrents,
            3: menu_cleanup,
            4: menu_rename,
            5: menu_subtitles,
            6: menu_artwork,
            7: menu_nfo,
            8: menu_status,
            9: menu_service_health,
            10: menu_activity_log,
            11: menu_repair,
            12: menu_trash,
            13: menu_settings,
            14: menu_setup,
            0: lambda: sys.exit(0),
        }

        if choice in actions:
            if choice == 0:
                console.print("\n[cyan]Goodbye![/]\n")
            actions[choice]()


# =============================================================================
# PROCESS MENU
# =============================================================================

def menu_process() -> None:
    """Process new media submenu."""
    from jackmediaman.core.config import get_settings

    while True:
        clear_screen()
        show_header("Process New Media")

        settings = get_settings()
        torrent_dir = settings.torrent_dir

        # Analyze items in torrent directory
        analyzed_items = _analyze_torrent_items(torrent_dir)
        ready_count = len([i for i in analyzed_items if not i["is_processed"]])
        done_count = len([i for i in analyzed_items if i["is_processed"]])

        # Show torrent directory info
        if torrent_dir.exists():
            console.print(f"[dim]Torrent directory:[/] {torrent_dir}")
            console.print(f"[dim]Items:[/] {ready_count} ready, {done_count} already done")
        else:
            console.print(f"[yellow]Torrent directory not found:[/] {torrent_dir}")
        console.print()

        choice = show_grouped_menu([
            ("BATCH PROCESSING", [
                ("Process All", f"Process all {ready_count} new items at once"),
            ]),
            ("SINGLE ITEM", [
                ("Select One", "Pick a specific item to process"),
            ]),
            ("INDIVIDUAL STAGES", [
                ("Extract Only", "Extract archives (RAR, ZIP, 7z)"),
                ("Identify & Organize", "Identify media and organize into library"),
                ("Subtitles Only", "Download missing subtitles"),
                ("Artwork Only", "Download poster artwork"),
                ("NFO Only", "Generate NFO metadata files"),
            ]),
            ("OTHER", [
                ("Custom Path", "Enter a different path manually"),
            ]),
        ], default=1)

        if choice == 0:
            return

        # Choice 1: Batch Process All
        if choice == 1:
            if not analyzed_items:
                show_warning("No items found in torrent directory")
                _wait_for_enter()
                continue
            _run_batch_pipeline(torrent_dir, analyzed_items)
            _wait_for_enter()
            continue

        # Choice 2: Select One - pick single item and run full pipeline
        if choice == 2:
            if not analyzed_items:
                show_warning("No items found in torrent directory")
                _wait_for_enter()
                continue
            items = [i["path"] for i in analyzed_items]
            path = _select_torrent_item(torrent_dir, items)
            if path:
                _run_full_pipeline(path)
            _wait_for_enter()
            continue

        # Choices 3-7: Individual stages need path selection first
        if choice == 8:  # Custom Path
            path = get_path_input("Enter path to torrent/media", must_exist=True)
            if not path:
                continue
        else:
            if not analyzed_items:
                show_warning("No items found in torrent directory")
                _wait_for_enter()
                continue
            items = [i["path"] for i in analyzed_items]
            path = _select_torrent_item(torrent_dir, items)
            if not path:
                continue

        # Execute based on choice
        if choice == 3:  # Extract Only
            _run_extract_only(path)
        elif choice == 4:  # Identify & Organize
            _run_identify_organize(path)
        elif choice == 5:  # Subtitles Only
            _run_subtitles_only(path)
        elif choice == 6:  # Artwork Only
            _run_artwork_only(path)
        elif choice == 7:  # NFO Only
            _run_nfo_only(path)
        elif choice == 8:  # Custom Path - run full pipeline
            _run_full_pipeline(path)

        _wait_for_enter()


def _select_torrent_item(torrent_dir: Path, items: list) -> Optional[Path]:
    """Let user select an item from torrent directory."""
    if len(items) == 1:
        # Only one item, use it directly
        console.print(f"[dim]Using:[/] {items[0].name}")
        return items[0]

    console.print()
    options = [(item.name, "Dir" if item.is_dir() else item.suffix) for item in items[:15]]
    if len(items) > 15:
        options.append(("...", f"{len(items) - 15} more items"))

    choice = show_menu("Select item to process", options, default=1, show_back=True)
    if choice == 0:
        return None
    if choice > len(items):
        return get_path_input(f"Enter path in {torrent_dir}", must_exist=True, default=str(torrent_dir) + "/")

    return items[choice - 1]


def _get_action_mode():
    """Get action mode from user."""
    from jackmediaman.pipeline import ActionMode

    return show_enum_menu("Select action mode", ActionMode, {
        ActionMode.MOVE: "Move files (removes from source)",
        ActionMode.COPY: "Copy files (keeps source)",
        ActionMode.HARDLINK: "Hardlinks (same filesystem)",
        ActionMode.SYMLINK: "Symlinks (best for seeding)",
        ActionMode.KEEPLINK: "Move + leave symlink at source",
    }, default=ActionMode.SYMLINK)


def _run_full_pipeline(path: Path) -> None:
    """Run full processing pipeline."""
    console.print()
    action = _get_action_mode()

    console.print()
    console.print(Panel(
        f"[cyan]Path:[/]   {path}\n"
        f"[cyan]Action:[/] {action.value}\n"
        f"[cyan]Stages:[/] Extract → Identify → Organize → Subs → Artwork → NFO → Plex",
        title="[bold]Full Pipeline[/]",
        border_style="yellow",
    ))

    if not confirm_action("Proceed?", default=True):
        return

    console.print()
    try:
        from jackmediaman.cli.commands.process import process_torrent, Action
        process_torrent(path, Action(action.value), dry_run=False)
    except Exception as e:
        show_error(f"Processing failed: {e}")


def _run_extract_only(path: Path) -> None:
    """Run extraction stage only."""
    console.print()
    console.print(Panel(
        f"[cyan]Path:[/] {path}\n"
        f"[cyan]Stage:[/] Extract archives only",
        title="[bold]Extract Only[/]",
        border_style="yellow",
    ))

    if not confirm_action("Proceed?", default=True):
        return

    console.print()
    try:
        from jackmediaman.cli.commands.process import process_torrent, Action
        # Run with all stages disabled except extraction
        process_torrent(
            path, Action.symlink, dry_run=False,
            no_tmdb=True, no_subtitles=True, no_artwork=True, no_plex=True
        )
    except Exception as e:
        show_error(f"Extraction failed: {e}")


def _run_identify_organize(path: Path) -> None:
    """Run identify and organize stages only."""
    console.print()
    action = _get_action_mode()

    console.print()
    console.print(Panel(
        f"[cyan]Path:[/]   {path}\n"
        f"[cyan]Action:[/] {action.value}\n"
        f"[cyan]Stage:[/] Identify & Organize only",
        title="[bold]Identify & Organize[/]",
        border_style="yellow",
    ))

    if not confirm_action("Proceed?", default=True):
        return

    console.print()
    try:
        from jackmediaman.cli.commands.process import process_torrent, Action
        process_torrent(
            path, Action(action.value), dry_run=False,
            no_extract=True, no_subtitles=True, no_artwork=True, no_plex=True
        )
    except Exception as e:
        show_error(f"Processing failed: {e}")


def _run_subtitles_only(path: Path) -> None:
    """Download subtitles only."""
    console.print()
    console.print(Panel(
        f"[cyan]Path:[/] {path}\n"
        f"[cyan]Stage:[/] Download subtitles only",
        title="[bold]Subtitles Only[/]",
        border_style="yellow",
    ))

    if not confirm_action("Proceed?", default=True):
        return

    console.print()
    try:
        from jackmediaman.cli.commands import subtitles
        if path.is_file():
            subtitles.download(path)
        else:
            subtitles.scan(path)
    except Exception as e:
        show_error(f"Subtitle download failed: {e}")


def _run_artwork_only(path: Path) -> None:
    """Download artwork only."""
    console.print()
    console.print(Panel(
        f"[cyan]Path:[/] {path}\n"
        f"[cyan]Stage:[/] Download artwork only",
        title="[bold]Artwork Only[/]",
        border_style="yellow",
    ))

    if not confirm_action("Proceed?", default=True):
        return

    console.print()
    try:
        from jackmediaman.cli.commands import artwork
        artwork.download(path)
    except Exception as e:
        show_error(f"Artwork download failed: {e}")


def _run_nfo_only(path: Path) -> None:
    """Generate NFO metadata files only."""
    console.print()
    console.print(Panel(
        f"[cyan]Path:[/] {path}\n"
        f"[cyan]Stage:[/] Generate NFO metadata files only",
        title="[bold]NFO Only[/]",
        border_style="yellow",
    ))

    if not confirm_action("Proceed?", default=True):
        return

    console.print()
    try:
        from jackmediaman.cli.commands import nfo
        from jackmediaman.cli.commands.nfo import MediaType as NFOMediaType
        nfo.generate(path=path, media_type=NFOMediaType.both, refresh=False, dry_run=False)
    except Exception as e:
        show_error(f"NFO generation failed: {e}")


# =============================================================================
# BATCH PROCESSING
# =============================================================================

def _get_item_size(path: Path) -> int:
    """Get total size of a path (file or directory) in bytes."""
    if path.is_file():
        return path.stat().st_size
    total = 0
    try:
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except (PermissionError, OSError):
        pass
    return total


def _format_size(size_bytes: int) -> str:
    """Format size in human-readable format."""
    if size_bytes >= 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
    elif size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.0f} MB"
    else:
        return f"{size_bytes / 1024:.0f} KB"


def _analyze_torrent_items(torrent_dir: Path) -> List[dict]:
    """Analyze all items in torrent directory.

    Returns list of dicts with:
    - path: Path to item
    - name: Display name
    - is_symlink: True if it's a symlink
    - symlink_target: Where symlink points (if applicable)
    - size_bytes: Total size
    - size_str: Human-readable size
    - is_processed: True if already a symlink (already processed)
    """
    items = []

    if not torrent_dir.exists():
        return items

    for path in sorted(torrent_dir.iterdir()):
        # Skip hidden files
        if path.name.startswith("."):
            continue

        # Only include directories and media files
        if not path.is_dir():
            if path.suffix.lower() not in ('.mkv', '.mp4', '.avi', '.rar', '.zip', '.7z'):
                continue

        is_symlink = path.is_symlink()
        symlink_target = None
        if is_symlink:
            try:
                symlink_target = path.resolve()
            except (OSError, ValueError):
                pass

        size_bytes = _get_item_size(path)

        items.append({
            "path": path,
            "name": path.name,
            "is_symlink": is_symlink,
            "symlink_target": symlink_target,
            "size_bytes": size_bytes,
            "size_str": _format_size(size_bytes),
            "is_processed": is_symlink,  # Symlinks are considered already processed
        })

    return items


def _run_batch_pipeline(torrent_dir: Path, items: List[dict]) -> None:
    """Run batch processing pipeline for all items."""
    from jackmediaman.pipeline import ActionMode

    console.print()

    # Step 1: Ask for action mode first
    action = _get_action_mode()

    # Step 2: Display preview with toggle
    show_all = False

    while True:
        clear_screen()
        show_header("Batch Processing")

        # Filter items based on show_all toggle
        if show_all:
            display_items = items
            filter_text = "Showing: All items"
        else:
            display_items = [i for i in items if not i["is_processed"]]
            filter_text = "Showing: New only"

        # Count stats
        ready_count = len([i for i in items if not i["is_processed"]])
        done_count = len([i for i in items if i["is_processed"]])
        total_size = sum(i["size_bytes"] for i in display_items)

        # Summary panel
        console.print(Panel(
            f"[cyan]Action:[/]  {action.value}\n"
            f"[cyan]Items:[/]   {ready_count} ready, {done_count} already done\n"
            f"[cyan]Size:[/]    {_format_size(total_size)}\n"
            f"[dim]{filter_text}[/]",
            title="[bold]Batch Processing Preview[/]",
            border_style="yellow",
        ))
        console.print()

        if not display_items:
            console.print("[dim]No items to display[/]")
            console.print()
        else:
            # Build table
            table = Table(show_header=True, header_style="bold cyan", box=box.ROUNDED)
            table.add_column("Name", style="white", no_wrap=False, max_width=50)
            table.add_column("Type", style="white", width=6)
            table.add_column("Size", style="magenta", justify="right", width=10)
            table.add_column("Status", style="white", width=14)

            for item in display_items[:20]:  # Show max 20 items
                item_type = "[cyan]link[/]" if item["is_symlink"] else "real"
                status = "[dim]Already done[/]" if item["is_processed"] else "[green]Ready[/]"

                # Truncate name if too long
                name = item["name"]
                if len(name) > 50:
                    name = name[:47] + "..."

                table.add_row(name, item_type, item["size_str"], status)

            if len(display_items) > 20:
                table.add_row(f"[dim]... and {len(display_items) - 20} more[/]", "", "", "")

            console.print(table)

        console.print()

        # Menu options
        if ready_count > 0:
            console.print(f"  [bold cyan][1][/] Proceed with {ready_count} items")
        else:
            console.print("  [dim][1] No items to process[/]")
        console.print(f"  [bold cyan][2][/] Toggle: {'Show new only' if show_all else 'Show all items'}")
        console.print("  [bold cyan][0][/] Cancel")
        console.print()

        choice = Prompt.ask("Select", default="0")

        if choice == "0":
            return
        elif choice == "2":
            show_all = not show_all
            continue
        elif choice == "1" and ready_count > 0:
            break
        # Invalid choice, loop again

    # Step 3: Process all ready items
    items_to_process = [i for i in items if not i["is_processed"]]

    console.print()
    console.print(f"[bold]Processing {len(items_to_process)} items...[/]")
    console.print()

    from jackmediaman.cli.commands.process import process_torrent, Action

    success_count = 0
    fail_count = 0

    for i, item in enumerate(items_to_process, 1):
        console.print(f"[cyan][{i}/{len(items_to_process)}][/] {item['name']}")

        try:
            process_torrent(item["path"], Action(action.value), dry_run=False)
            success_count += 1
            console.print(f"  [green]✓ Done[/]")
        except Exception as e:
            fail_count += 1
            console.print(f"  [red]✗ Failed: {e}[/]")

        console.print()

    # Summary
    console.print(Panel(
        f"[green]Succeeded:[/] {success_count}\n"
        f"[red]Failed:[/]    {fail_count}",
        title="[bold]Batch Processing Complete[/]",
        border_style="green" if fail_count == 0 else "yellow",
    ))


# =============================================================================
# TORRENTS MENU
# =============================================================================

def menu_torrents() -> None:
    """Manage Deluge torrents submenu."""
    while True:
        clear_screen()
        show_header("Manage Torrents")

        choice = show_menu(
            "Torrent Options",
            [
                ("List All Torrents", "View all torrents and their status"),
                ("Move Completed", "Move stuck torrents to completed folder"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        from jackmediaman.cli.commands import torrents

        console.print()

        if choice == 1:
            torrents.list_torrents()
        elif choice == 2:
            # Show preview first (dry_run=True), then offer to execute
            torrents.move_completed(dry_run=True)
            console.print()
            if confirm_action("Move these torrents now?", default=True):
                console.print()
                torrents.move_completed(dry_run=False)

        _wait_for_enter()


# =============================================================================
# CLEAN LIBRARY MENU
# =============================================================================

def menu_cleanup() -> None:
    """Clean library - find and remove duplicate files and folders."""
    while True:
        clear_screen()
        show_header("Clean Library")

        choice = show_menu(
            "Cleanup Options",
            [
                ("Find Duplicate Files", "Scan for duplicate episodes/movies"),
                ("Clean Duplicate Files", "Remove lower quality duplicates"),
                ("Find Duplicate Folders", "Scan for folders with same content"),
                ("Merge Duplicate Folders", "Consolidate into single folder"),
                ("Full Cleanup (Dry Run)", "Preview all cleanup actions"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        console.print()

        if choice == 1:
            # Find duplicate files (scan only)
            from jackmediaman.cli.commands import duplicates
            duplicates.scan(
                media_type=duplicates.MediaType.both,
                movie_matcher=duplicates.MovieMatcher.title_year,
                protector=duplicates.ProtectorType.symlink,
                editions_as_dupes=True,
            )
        elif choice == 2:
            # Clean duplicate files (interactive)
            from jackmediaman.cli.commands import duplicates
            duplicates.clean(
                media_type=duplicates.MediaType.both,
                movie_matcher=duplicates.MovieMatcher.title_year,
                protector=duplicates.ProtectorType.symlink,
                editions_as_dupes=True,
                dry_run=False,
                interactive=True,
                rename_files=False,
            )
        elif choice == 3:
            # Find duplicate folders
            import typer
            from jackmediaman.cli.commands import folders
            from jackmediaman.cli.commands.folders import MediaType
            console.print("[cyan]Scanning movie folders...[/]")
            try:
                folders.scan(media_type=MediaType.movies, no_tmdb=False)
            except typer.Exit:
                pass  # Directory not found, continue
            console.print()
            console.print("[cyan]Scanning TV folders...[/]")
            try:
                folders.scan(media_type=MediaType.tv, no_tmdb=False)
            except typer.Exit:
                pass  # Directory not found, continue
        elif choice == 4:
            # Merge duplicate folders
            import typer
            from jackmediaman.cli.commands import folders
            from jackmediaman.cli.commands.folders import MediaType
            if confirm_action("Consolidate all duplicate folders?", default=False):
                console.print("[cyan]Consolidating movie folders...[/]")
                try:
                    folders.consolidate(media_type=MediaType.movies, dry_run=False, yes=True)
                except typer.Exit:
                    pass
                console.print()
                console.print("[cyan]Consolidating TV folders...[/]")
                try:
                    folders.consolidate(media_type=MediaType.tv, dry_run=False, yes=True)
                except typer.Exit:
                    pass
        elif choice == 5:
            # Full cleanup dry run
            import typer
            from jackmediaman.cli.commands import duplicates
            from jackmediaman.cli.commands import folders
            from jackmediaman.cli.commands.folders import MediaType

            console.print("[bold cyan]Preview: Duplicate Files[/]")
            console.print()
            try:
                duplicates.clean(
                    media_type=duplicates.MediaType.both,
                    movie_matcher=duplicates.MovieMatcher.title_year,
                    protector=duplicates.ProtectorType.symlink,
                    editions_as_dupes=True,
                    dry_run=True,
                    interactive=False,
                    rename_files=False,
                )
            except typer.Exit:
                pass
            console.print()
            console.print("[bold cyan]Preview: Duplicate Folders[/]")
            console.print()
            try:
                folders.consolidate(media_type=MediaType.movies, dry_run=True, yes=True)
            except typer.Exit:
                pass
            try:
                folders.consolidate(media_type=MediaType.tv, dry_run=True, yes=True)
            except typer.Exit:
                pass

        _wait_for_enter()


# =============================================================================
# RENAME MENU
# =============================================================================

def menu_rename() -> None:
    """Rename files submenu."""
    while True:
        clear_screen()
        show_header("Rename Media Files")

        show_info_panel("Naming Format",
            "[cyan]Movies:[/] Movie Name (Year)/Movie Name (Year).ext\n"
            "[cyan]TV:[/]     Show/Season 01/Show - S01E01 - Title.ext"
        )
        console.print()

        choice = show_menu(
            "Rename Options",
            [
                ("Preview Changes", "Dry run - show what would change"),
                ("Rename Library", "Apply renames to entire library"),
                ("Single File", "Rename a specific file"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        from jackmediaman.cli.commands import rename
        from jackmediaman.cli.commands.rename import MediaType

        console.print()

        if choice == 1:
            # Pass explicit media_type to avoid Typer default issues
            rename.preview(media_type=MediaType.both)
        elif choice == 2:
            if confirm_action("Apply renames to entire library?", default=False):
                rename.execute(media_type=MediaType.both, yes=False)
        elif choice == 3:
            path = get_path_input("Enter file path", must_exist=True)
            if path:
                rename.rename_file(path=path, yes=False)

        _wait_for_enter()


# =============================================================================
# SUBTITLES MENU
# =============================================================================

def menu_subtitles() -> None:
    """Subtitles submenu."""
    while True:
        clear_screen()
        show_header("Manage Subtitles")

        choice = show_menu(
            "Subtitle Options",
            [
                ("Scan Library", "Find and download missing subtitles"),
                ("Single File", "Download for specific file"),
                ("Check API Status", "Test OpenSubtitles connection"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        from jackmediaman.cli.commands import subtitles
        from jackmediaman.cli.commands.subtitles import MediaType as SubsMediaType
        from jackmediaman.cli.commands.status import check_opensubtitles

        console.print()

        if choice == 1:
            subtitles.download(path=None, media_type=SubsMediaType.both, language=None, overwrite=False, dry_run=False)
        elif choice == 2:
            path = get_path_input("Enter media file path", must_exist=True)
            if path:
                subtitles.download(path=path, media_type=None, language=None, overwrite=False, dry_run=False)
        elif choice == 3:
            check_opensubtitles()

        _wait_for_enter()


# =============================================================================
# ARTWORK MENU
# =============================================================================

def menu_artwork() -> None:
    """Artwork submenu."""
    while True:
        clear_screen()
        show_header("Fetch Artwork")

        choice = show_menu(
            "Artwork Options",
            [
                ("Scan Library", "Download missing posters"),
                ("Single Item", "Download for specific movie/show"),
                ("Check TMDb Status", "Test API connection"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        from jackmediaman.cli.commands import artwork
        from jackmediaman.cli.commands.status import check_tmdb

        console.print()

        if choice == 1:
            artwork.download(path=None, media_type=None, refresh=False, dry_run=False)
        elif choice == 2:
            path = get_path_input("Enter movie/show directory", must_exist=True)
            if path:
                artwork.download(path=path, media_type=None, refresh=False, dry_run=False)
        elif choice == 3:
            check_tmdb()

        _wait_for_enter()


# =============================================================================
# NFO MENU
# =============================================================================

def menu_nfo() -> None:
    """NFO metadata submenu."""
    while True:
        clear_screen()
        show_header("NFO Metadata Files")

        show_info_panel("About NFO Files",
            "NFO files provide metadata to Kodi and other media players:\n"
            "[dim]• movie.nfo - Movie folder metadata\n"
            "• tvshow.nfo - TV show root metadata\n"
            "• episode.nfo - Individual episode metadata[/]"
        )
        console.print()

        choice = show_menu(
            "NFO Options",
            [
                ("Scan Library", "Find items missing NFO files"),
                ("Generate All", "Generate missing NFO files"),
                ("Regenerate All", "Refresh all NFO files"),
                ("Single Item", "Generate for specific folder"),
                ("Check Status", "Show NFO coverage statistics"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        from jackmediaman.cli.commands import nfo
        from jackmediaman.cli.commands.nfo import MediaType as NFOMediaType

        console.print()

        if choice == 1:
            nfo.scan(media_type=NFOMediaType.both)
        elif choice == 2:
            nfo.generate(path=None, media_type=NFOMediaType.both, refresh=False, dry_run=False)
        elif choice == 3:
            if confirm_action("Regenerate ALL NFO files? This will overwrite existing files.", default=False):
                nfo.generate(path=None, media_type=NFOMediaType.both, refresh=True, dry_run=False)
        elif choice == 4:
            path = get_path_input("Enter movie/show directory", must_exist=True)
            if path:
                nfo.generate(path=path, media_type=NFOMediaType.both, refresh=False, dry_run=False)
        elif choice == 5:
            nfo.status()

        _wait_for_enter()


# =============================================================================
# STATUS MENU
# =============================================================================

def menu_status() -> None:
    """Status submenu."""
    clear_screen()
    show_header("Library Status")

    from jackmediaman.cli.commands.status import show_config

    console.print()
    show_config()
    _wait_for_enter()


def menu_service_health() -> None:
    """Service health check submenu."""
    while True:
        clear_screen()
        show_header("Service Health")

        choice = show_menu(
            "Health Checks",
            [
                ("Test All Services", "Check everything"),
                ("Deluge", "Test daemon connection"),
                ("TMDb", "Test API key"),
                ("Plex", "Test server connection"),
                ("OpenSubtitles", "Test API connection"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        from jackmediaman.cli.commands import status

        console.print()

        if choice == 1:
            status.check_deluge()
            console.print()
            status.check_tmdb()
            console.print()
            status.check_plex()
            console.print()
            status.check_opensubtitles()
        elif choice == 2:
            status.check_deluge()
        elif choice == 3:
            status.check_tmdb()
        elif choice == 4:
            status.check_plex()
        elif choice == 5:
            status.check_opensubtitles()

        _wait_for_enter()


# =============================================================================
# ACTIVITY LOG MENU
# =============================================================================

def menu_activity_log() -> None:
    """Activity log viewer submenu."""
    from jackmediaman.core.operations_db import get_operations_db

    while True:
        clear_screen()
        show_header("Activity Log")

        choice = show_menu(
            "Activity Log Options",
            [
                ("Recent Activity", "View last 50 log entries"),
                ("Errors Only", "View recent errors"),
                ("Search by Path", "Find logs for a specific file"),
                ("View Session", "View logs for a session ID"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        console.print()
        db = get_operations_db()

        if choice == 1:
            # Recent activity
            _show_activity_entries(db.get_recent_activity(limit=50))
        elif choice == 2:
            # Errors only
            _show_activity_entries(db.get_recent_activity(limit=50, level="ERROR"))
        elif choice == 3:
            # Search by path
            path = Prompt.ask("Enter path or filename to search")
            if path:
                entries = db.get_activity_for_file(path)
                if entries:
                    _show_activity_entries(entries)
                else:
                    console.print("[dim]No entries found for that path[/]")
        elif choice == 4:
            # View session
            session_id = Prompt.ask("Enter session ID (8 chars)")
            if session_id:
                entries = db.get_session_activity(session_id)
                if entries:
                    _show_activity_entries(entries)
                else:
                    console.print("[dim]No entries found for that session[/]")

        _wait_for_enter()


def _show_activity_entries(entries: list) -> None:
    """Display activity log entries in a formatted way."""
    if not entries:
        console.print("[dim]No activity entries found[/]")
        return

    console.print(f"[dim]Found {len(entries)} entries[/]\n")

    for entry in entries:
        # Format timestamp
        timestamp = entry.get("timestamp", "")[:19]  # Trim microseconds

        # Format level with color
        level = entry.get("level", "INFO")
        level_style = {
            "INFO": "[cyan]INFO[/]",
            "WARNING": "[yellow]WARN[/]",
            "ERROR": "[red]ERROR[/]",
            "DEBUG": "[dim]DEBUG[/]",
        }.get(level, level)

        # Category
        category = entry.get("category", "")

        # Message
        message = entry.get("message", "")

        # Main line
        console.print(f"[dim]{timestamp}[/] {level_style} [magenta]{category}[/] {message}")

        # Source path (if present)
        source_path = entry.get("source_path")
        if source_path:
            # Show just filename if it's a full path
            display_path = source_path
            if "/" in source_path:
                display_path = source_path.split("/")[-1]
            console.print(f"  [dim]└─ {display_path}[/]")

        # Session ID (if present)
        session_id = entry.get("session_id")
        if session_id:
            console.print(f"  [dim]   session: {session_id}[/]")

        # Details (if present and non-empty)
        details = entry.get("details")
        if details:
            try:
                import json
                details_dict = json.loads(details)
                details_str = ", ".join(f"{k}={v}" for k, v in details_dict.items())
                console.print(f"  [dim]   {details_str}[/]")
            except (json.JSONDecodeError, TypeError):
                console.print(f"  [dim]   {details}[/]")

        # Traceback (if present, for errors)
        traceback_str = entry.get("traceback")
        if traceback_str:
            console.print(Panel(
                traceback_str,
                title="[red]Traceback[/]",
                border_style="red",
                expand=False,
            ))

        console.print()  # Blank line between entries


# =============================================================================
# REPAIR MENU
# =============================================================================

def menu_repair() -> None:
    """Repair symlinks submenu."""
    while True:
        clear_screen()
        show_header("Repair Symlinks")

        show_info_panel("About",
            "Fixes broken symlinks in your torrent directory.\n"
            "[dim]Common cause: files renamed after keeplink creation\n"
            "This tool finds and fixes these broken links.[/]"
        )
        console.print()

        choice = show_menu(
            "Repair Options",
            [
                ("Scan Symlinks", "Find all broken symlinks"),
                ("Preview Fixes", "Dry run - show what would be fixed"),
                ("Repair All", "Fix all broken symlinks"),
                ("Database Stats", "View operations database statistics"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        from jackmediaman.cli.commands import repair

        console.print()

        if choice == 1:
            repair.scan_symlinks(directory=None, show_valid=False)
        elif choice == 2:
            repair.repair_symlinks(
                torrent_dir=None,
                media_dir=None,
                dry_run=True,
                strict=False,
                no_db=False,
            )
        elif choice == 3:
            if confirm_action("Fix all broken symlinks?", default=True):
                repair.repair_symlinks(
                    torrent_dir=None,
                    media_dir=None,
                    dry_run=False,
                    strict=False,
                    no_db=False,
                )
        elif choice == 4:
            repair.database_stats()

        _wait_for_enter()


# =============================================================================
# TRASH MENU
# =============================================================================

def menu_trash() -> None:
    """Trash management submenu."""
    while True:
        clear_screen()
        show_header("Trash Management")

        choice = show_menu(
            "Trash Options",
            [
                ("View Contents", "List files in trash"),
                ("Empty Trash", "Permanently delete all"),
                ("Restore File", "Restore a deleted file"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        from jackmediaman.cli.commands import status, trash

        console.print()

        if choice == 1:
            status.check_trash()
        elif choice == 2:
            if confirm_action("Permanently delete all files in trash?", default=False):
                status.empty_trash(older_than=None, force=True)
        elif choice == 3:
            trash.list_trash()
            file_number = Prompt.ask("Enter file number to restore (or Enter to cancel)")
            if file_number:
                try:
                    trash.restore_file(file_number=int(file_number))
                except ValueError:
                    console.print("[red]Invalid number[/]")

        _wait_for_enter()


# =============================================================================
# SETTINGS MENU
# =============================================================================

def menu_settings() -> None:
    """Settings submenu."""
    while True:
        clear_screen()
        show_header("Settings")

        choice = show_menu(
            "Settings",
            [
                ("View All Settings", "Show current configuration"),
                ("Edit Paths", "Configure media directories"),
                ("Edit Services", "Configure API keys"),
                ("Edit Processing", "Configure behavior options"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        if choice == 1:
            _show_all_settings()
        elif choice == 2:
            _edit_path_settings()
        elif choice == 3:
            _edit_service_settings()
        elif choice == 4:
            _edit_processing_settings()

        _wait_for_enter()


def _show_all_settings() -> None:
    """Display all current settings."""
    from jackmediaman.core.config import get_settings

    settings = get_settings()

    console.print()

    # Paths table
    paths_table = Table(title="[bold]Media Paths[/]", box=box.ROUNDED, border_style="cyan")
    paths_table.add_column("Setting", style="cyan")
    paths_table.add_column("Path")
    paths_table.add_column("Status")

    for name, path in [
        ("TV Shows", settings.tv_dir),
        ("Movies", settings.movies_dir),
        ("Trash", settings.trash_dir),
        ("Torrents", settings.torrent_dir),
    ]:
        status = "[green]OK[/]" if path.exists() else "[red]Missing[/]"
        paths_table.add_row(name, str(path), status)

    console.print(paths_table)
    console.print()

    # Services table
    services_table = Table(title="[bold]Services[/]", box=box.ROUNDED, border_style="cyan")
    services_table.add_column("Service", style="cyan")
    services_table.add_column("Status")
    services_table.add_column("Details", style="dim")

    # TMDb
    if settings.tmdb_api_key:
        services_table.add_row("TMDb", "[green]Configured[/]", f"Key: {settings.tmdb_api_key[:8]}...")
    else:
        services_table.add_row("TMDb", "[dim]Not configured[/]", "Run: jmm setup tmdb")

    # Deluge: localhost can use auto-auth without credentials
    is_localhost = settings.deluge_host in ("127.0.0.1", "localhost", "::1")
    if is_localhost or settings.deluge_username:
        services_table.add_row("Deluge", "[green]Configured[/]", f"{settings.deluge_host}:{settings.deluge_port}")
    else:
        services_table.add_row("Deluge", "[dim]Not configured[/]", "Run: jmm setup deluge")

    # OpenSubtitles - check both providers
    com_configured = bool(settings.opensubtitles_com_api_key)
    org_configured = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)
    if com_configured or org_configured:
        parts = []
        if com_configured:
            parts.append(".com")
        if org_configured:
            parts.append(f".org ({settings.opensubtitles_org_username})")
        services_table.add_row("OpenSubtitles", "[green]Configured[/]", " + ".join(parts))
    else:
        services_table.add_row("OpenSubtitles", "[dim]Not configured[/]", "Run: jmm setup opensubtitles")

    console.print(services_table)


def _edit_path_settings() -> None:
    """Edit path settings."""
    from jackmediaman.core.config import get_settings
    from jackmediaman.core.settings_manager import SettingsManager

    settings = get_settings()
    manager = SettingsManager()

    console.print()
    console.print("[dim]Press Enter to keep current value[/]\n")

    new_tv = Prompt.ask("TV Directory", default=str(settings.tv_dir))
    new_movies = Prompt.ask("Movies Directory", default=str(settings.movies_dir))
    new_trash = Prompt.ask("Trash Directory", default=str(settings.trash_dir))
    new_torrent = Prompt.ask("Torrent Directory", default=str(settings.torrent_dir))

    updates = {
        "tv_dir": new_tv,
        "movies_dir": new_movies,
        "trash_dir": new_trash,
        "torrent_dir": new_torrent,
    }

    console.print()
    if confirm_action("Save changes?", default=True):
        for key, value in updates.items():
            manager.update_setting(key, value)
        show_success("Settings saved!")
    else:
        console.print("[dim]Cancelled[/]")


def _edit_service_settings() -> None:
    """Edit service settings - redirects to setup."""
    choice = show_menu(
        "Configure Service",
        [
            ("TMDb", "Movie/TV database API"),
            ("Deluge", "Torrent daemon connection"),
            ("OpenSubtitles", "Subtitle downloads"),
        ],
        default=1,
        show_back=True,
    )

    if choice == 0:
        return

    from jackmediaman.cli.commands import setup

    console.print()

    if choice == 1:
        setup.setup_tmdb()
    elif choice == 2:
        setup.setup_deluge()
    elif choice == 3:
        setup.setup_opensubtitles()


def _edit_processing_settings() -> None:
    """Edit processing settings."""
    from jackmediaman.core.config import get_settings
    from jackmediaman.core.settings_manager import SettingsManager

    settings = get_settings()
    manager = SettingsManager()

    console.print()

    ffprobe = Confirm.ask("Enable FFprobe for quality detection?", default=settings.ffprobe_enabled)
    sub_langs = Prompt.ask("Subtitle languages (comma-separated)", default=",".join(settings.subtitle_languages))

    console.print()
    if confirm_action("Save changes?", default=True):
        manager.update_setting("ffprobe_enabled", str(ffprobe).lower())
        manager.update_setting("subtitle_languages", sub_langs)
        show_success("Settings saved!")
    else:
        console.print("[dim]Cancelled[/]")


# =============================================================================
# SETUP MENU
# =============================================================================

def menu_setup() -> None:
    """Setup wizard submenu."""
    while True:
        clear_screen()
        show_header("Setup Wizard")

        choice = show_menu(
            "Setup Options",
            [
                ("Full Setup", "Configure all services"),
                ("TMDb", "Movie/TV database API key"),
                ("Deluge", "Torrent daemon connection"),
                ("OpenSubtitles", "Subtitle API key"),
                ("Plex", "Auto-discover Plex settings"),
            ],
            default=1,
            show_back=True,
        )

        if choice == 0:
            return

        from jackmediaman.cli.commands import setup

        console.print()

        if choice == 1:
            setup.setup_init()
        elif choice == 2:
            setup.setup_tmdb()
        elif choice == 3:
            setup.setup_deluge()
        elif choice == 4:
            setup.setup_opensubtitles()
        elif choice == 5:
            setup.setup_plex()

        _wait_for_enter()


# =============================================================================
# UTILITIES
# =============================================================================

def _wait_for_enter() -> None:
    """Wait for user to press Enter."""
    console.print()
    Prompt.ask("[dim]Press Enter to continue[/]", default="")


# =============================================================================
# DUPLICATE GROUP HANDLING
# =============================================================================

def show_duplicate_group_choice(
    group,  # DuplicateGroup
    show_details: bool = True,
    remaining_groups: int = 0,
) -> str:
    """Show a duplicate group and ask what to do."""
    console.print()
    console.print(f"[bold cyan]Duplicate Group:[/] {group.display_name}")
    if remaining_groups > 0:
        console.print(f"[dim]({remaining_groups} more groups remaining)[/]")
    console.print()

    table = Table(box=box.ROUNDED, border_style="cyan")
    table.add_column("#", style="dim", width=3)
    table.add_column("File", style="white")
    table.add_column("Quality", style="yellow")
    table.add_column("Size", style="magenta", justify="right")
    table.add_column("Action", justify="center")

    for i, item in enumerate(group.items, 1):
        action = group.get_action(item)
        action_style = {
            "KEEP": "[bold green]KEEP[/]",
            "PROTECTED": "[yellow]PROTECTED[/]",
            "REMOVE": "[red]REMOVE[/]",
        }.get(action, action)

        table.add_row(
            str(i),
            item.filename,
            str(item.quality),
            f"{item.size_mb:.1f} MB",
            action_style,
        )

        if show_details and item.is_protected:
            table.add_row("", f"[dim]  └─ {item.protection_reason}[/]", "", "", "")

    console.print(table)
    console.print()

    removable = group.removable_items
    if not removable:
        show_warning("No files to remove in this group")
        return "skip"

    console.print(f"[dim]Will remove {len(removable)} file(s), freeing {group.removable_size_bytes / 1024 / 1024:.1f} MB[/]")
    console.print()

    choice = show_menu(
        "Action",
        [
            ("Clean", "Move duplicates to trash"),
            ("Skip", "Skip this group"),
            ("Clean All", "Clean ALL remaining"),
            ("Skip All", "Skip ALL remaining"),
            ("Quit", "Stop processing"),
        ],
        default=1,
    )

    return ["clean", "skip", "clean_all", "skip_all", "quit"][choice - 1]


def show_batch_confirmation(groups: list, action: str) -> bool:
    """Show summary and confirm batch action."""
    total_files = sum(len(g.removable_items) for g in groups)
    total_bytes = sum(g.removable_size_bytes for g in groups)
    total_mb = total_bytes / (1024 * 1024)

    console.print()
    if action == "clean":
        console.print(Panel(
            f"[bold]Groups:[/] {len(groups)}\n"
            f"[bold]Files to remove:[/] {total_files}\n"
            f"[bold]Space to free:[/] {total_mb:.1f} MB",
            title="[bold yellow]Batch Clean[/]",
            border_style="yellow",
        ))
        return confirm_action("Proceed with cleaning ALL remaining groups?", default=False)
    else:
        console.print(f"[dim]Skipping {len(groups)} remaining groups[/]")
        return True


# =============================================================================
# ENTRY POINT
# =============================================================================

def run_interactive() -> None:
    """Main entry point for interactive mode."""
    try:
        run_main_menu()
    except KeyboardInterrupt:
        console.print("\n[cyan]Goodbye![/]\n")
        sys.exit(0)


if __name__ == "__main__":
    run_interactive()
