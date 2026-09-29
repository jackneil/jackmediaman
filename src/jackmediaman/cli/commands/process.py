"""Process command for handling completed torrent downloads."""

import traceback
import uuid
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from jackmediaman.core.operations_db import get_operations_db
from jackmediaman.pipeline import (
    ActionMode,
    Pipeline,
    ProcessContext,
    ProcessResult,
)
from jackmediaman.pipeline.stages import (
    ArtworkStage,
    ExtractorStage,
    IdentifierStage,
    LinkerStage,
    NFOStage,
    OrganizerStage,
    PlexNotifierStage,
    SubtitleStage,
)

app = typer.Typer(help="Process completed torrent downloads")
console = Console()


class Action(str, Enum):
    """File action mode."""

    move = "move"
    copy = "copy"
    hardlink = "hardlink"
    symlink = "symlink"
    keeplink = "keeplink"


def _display_results(result: ProcessResult, context: ProcessContext, dry_run: bool) -> None:
    """Display processing results."""
    console.print()

    # Status panel
    if result.success:
        status_style = "green"
        status_text = "SUCCESS"
    else:
        status_style = "red"
        status_text = "FAILED"

    mode_text = "[yellow]DRY RUN[/]" if dry_run else ""

    console.print(
        Panel(
            f"[bold {status_style}]{status_text}[/]\n\n"
            f"Files processed: [cyan]{result.files_processed}[/]\n"
            f"Files failed: [red]{result.files_failed}[/]\n"
            f"{mode_text}",
            title="[bold]Processing Results[/]",
            border_style="cyan",
        )
    )

    # Stage breakdown
    if result.stage_outputs:
        console.print()
        table = Table(title="Stage Results", show_header=True)
        table.add_column("Stage", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Details", style="dim")

        for stage_name, output in result.stage_outputs:
            status_emoji = {
                "success": "[green]✓[/]",
                "partial": "[yellow]⚠[/]",
                "failed": "[red]✗[/]",
                "skipped": "[dim]-[/]",
            }.get(output.result.value, "?")

            table.add_row(
                stage_name.title(),
                f"{status_emoji} {output.result.value}",
                output.message,
            )

        console.print(table)

    # Show file mappings in dry run
    if dry_run and context.file_mappings:
        console.print()
        console.print("[bold]File Mappings (Dry Run):[/]")
        for mapping in context.file_mappings[:10]:
            console.print(f"  [dim]{mapping.source.name}[/]")
            console.print(f"    → [cyan]{mapping.destination}[/]")

        if len(context.file_mappings) > 10:
            console.print(f"  [dim]... and {len(context.file_mappings) - 10} more[/]")

    # Show errors
    if result.errors:
        console.print()
        console.print("[bold red]Errors:[/]")
        for error in result.errors[:5]:
            path_text = f" ({error.path.name})" if error.path else ""
            console.print(f"  [red]•[/] [{error.stage}]{path_text}: {error.error}")

        if len(result.errors) > 5:
            console.print(f"  [dim]... and {len(result.errors) - 5} more errors[/]")


@app.command("run")
def process_torrent(
    path: Path = typer.Argument(
        ...,
        help="Path to completed torrent (file or directory)",
        exists=True,
    ),
    action: Action = typer.Option(
        Action.symlink,
        "--action",
        "-a",
        help="How to handle files: move, copy, hardlink, symlink, keeplink",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without making changes",
    ),
    no_extract: bool = typer.Option(
        False,
        "--no-extract",
        help="Skip archive extraction (process video files directly)",
    ),
    no_tmdb: bool = typer.Option(
        False,
        "--no-tmdb",
        help="Skip TMDb lookup for metadata",
    ),
    no_subtitles: bool = typer.Option(
        False,
        "--no-subtitles",
        help="Skip automatic subtitle download",
    ),
    no_artwork: bool = typer.Option(
        False,
        "--no-artwork",
        help="Skip automatic artwork download",
    ),
    no_nfo: bool = typer.Option(
        False,
        "--no-nfo",
        help="Skip automatic NFO metadata file generation",
    ),
    no_plex: bool = typer.Option(
        False,
        "--no-plex",
        help="Skip Plex library notification",
    ),
) -> None:
    """
    Process a completed torrent download.

    This command is designed to be called by Deluge's Execute plugin
    on torrent completion. It will:

    1. Extract any archives (RAR, ZIP, 7z)
    2. Identify media type (movie or TV show)
    3. Organize into library structure
    4. Create links/copies based on --action
    5. Download subtitles (if configured)
    6. Download poster artwork (if configured)
    7. Generate NFO metadata files (if configured)
    8. Notify Plex to scan (if configured)

    Examples:

        # Process with symlinks (default, keeps original for seeding)
        jmm process run /downloads/completed/Movie.2024.1080p.BluRay

        # Move files (removes from download location)
        jmm process run /downloads/completed/Movie.2024 --action move

        # Keep seeding with keeplink (moves file, leaves symlink)
        jmm process run /downloads/completed/Movie.2024 --action keeplink

        # Dry run to preview
        jmm process run /downloads/completed/Movie.2024 --dry-run
    """
    # Generate session ID for logging
    session_id = str(uuid.uuid4())[:8]
    db = get_operations_db()

    # Log process start
    db.log_activity(
        "INFO",
        "process",
        f"Processing triggered: {path.name}",
        source_path=str(path),
        session_id=session_id,
    )

    console.print()
    console.print(
        Panel(
            "[bold]JackMediaMan - Torrent Processor[/]\n\n"
            f"Source: [cyan]{path}[/]\n"
            f"Action: [yellow]{action.value}[/]"
            + (" [dim](dry run)[/]" if dry_run else ""),
            border_style="cyan",
        )
    )

    # Build pipeline stages
    stages = []

    if not no_extract:
        stages.append(ExtractorStage())

    stages.append(IdentifierStage(use_tmdb=not no_tmdb))
    stages.append(OrganizerStage())
    stages.append(LinkerStage(action=ActionMode(action.value)))

    if not no_subtitles:
        stages.append(SubtitleStage())

    if not no_artwork:
        stages.append(ArtworkStage())

    if not no_nfo:
        stages.append(NFOStage())

    if not no_plex:
        stages.append(PlexNotifierStage())

    # Create pipeline and context
    pipeline = Pipeline(stages)
    context = ProcessContext(
        source_path=path.resolve(),
        action=ActionMode(action.value),
        dry_run=dry_run,
        session_id=session_id,
        skip_extraction=no_extract,
        skip_tmdb=no_tmdb,
        skip_subtitles=no_subtitles,
        skip_artwork=no_artwork,
        skip_nfo=no_nfo,
        skip_plex=no_plex,
    )

    # Execute with progress display
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing...", total=len(stages))

        def update_progress(stage_name: str, status: str) -> None:
            progress.update(task, description=f"{stage_name}: {status}")
            if status in ("success", "partial", "failed", "skipped"):
                progress.advance(task)

        try:
            result = pipeline.execute(context, progress_callback=update_progress)
        except Exception as e:
            # Log fatal error with traceback
            db.log_activity(
                "ERROR",
                "process",
                f"Processing failed with exception: {e}",
                source_path=str(path),
                traceback_str=traceback.format_exc(),
                session_id=session_id,
            )
            raise

    # Log completion
    if result.success:
        db.log_activity(
            "INFO",
            "process",
            f"Processing complete: {result.files_processed} files processed",
            source_path=str(path),
            session_id=session_id,
        )
    else:
        error_summary = "; ".join(e.error[:50] for e in result.errors[:3])
        db.log_activity(
            "ERROR",
            "process",
            f"Processing failed: {result.files_failed} files failed - {error_summary}",
            source_path=str(path),
            session_id=session_id,
        )

    # Display results
    _display_results(result, context, dry_run)

    if not result.success:
        raise typer.Exit(1)

    console.print()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Process completed torrent downloads."""
    if ctx.invoked_subcommand is None:
        console.print()
        console.print("[yellow]Usage: jmm process run <path> [OPTIONS][/]")
        console.print()
        console.print("Run 'jmm process run --help' for more information.")
        console.print()
