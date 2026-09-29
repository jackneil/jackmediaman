"""Plex notification stage for the processing pipeline."""

from typing import Optional

from jackmediaman.core.logging import get_logger
from jackmediaman.pipeline.context import ProcessContext
from jackmediaman.pipeline.base import StageOutput, StageResult

logger = get_logger("pipeline.plex")


class PlexNotifierStage:
    """Notify Plex of new media after file operations.

    This stage runs after the linker stage and triggers Plex to scan
    the specific directories where files were added. Uses path-specific
    scanning for fast updates rather than full library scans.

    Plex is assumed to be running locally (localhost:32400) by default,
    but remote servers are also supported via configuration.
    """

    name = "plex_notifier"

    def __init__(self):
        """Initialize the Plex notifier stage."""
        self._service: Optional["PlexService"] = None

    def _get_service(self) -> Optional["PlexService"]:
        """Lazy-load Plex service."""
        if self._service is None:
            try:
                from jackmediaman.services.plex import PlexService

                self._service = PlexService()
            except ImportError:
                return None
        return self._service

    def validate(self, context: ProcessContext) -> bool:
        """Check if we should run this stage.

        Returns False if:
        - Dry run mode (no actual changes to notify about)
        - No successful file operations
        - Plex not configured or disabled
        - skip_plex flag is set
        """
        # Skip in dry run mode
        if context.dry_run:
            return False

        # Skip if explicitly disabled
        if getattr(context, "skip_plex", False):
            return False

        # Only run if there are successful operations
        successful_ops = [op for op in context.completed_operations if op.success]
        if not successful_ops:
            return False

        # Check if Plex is configured
        service = self._get_service()
        if not service or not service.is_configured:
            return False

        return True

    def execute(self, context: ProcessContext) -> StageOutput:
        """Notify Plex about completed file operations.

        Collects destination paths from successful operations and
        triggers path-specific scans in Plex. Failures are logged
        as warnings but don't fail the stage.
        """
        service = self._get_service()
        if not service:
            return StageOutput(
                result=StageResult.SKIPPED,
                message="Plex service not available",
            )

        # Collect destination paths from successful operations
        paths = [
            op.destination
            for op in context.completed_operations
            if op.success and op.destination
        ]

        if not paths:
            return StageOutput(
                result=StageResult.SKIPPED,
                message="No paths to notify",
            )

        # Notify Plex about all paths
        results = service.notify_paths(paths)

        successful = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)

        # Log failures as warnings but don't fail the stage
        for result in results:
            if not result.success and result.error:
                context.add_error(
                    stage=self.name,
                    error=f"Plex notification failed for {result.path}: {result.error}",
                    path=result.path,
                    recoverable=True,  # Plex errors shouldn't fail the pipeline
                )

        # Collect unique libraries that were notified
        libraries = list(set(r.library for r in results if r.library))

        if successful == 0 and failed > 0:
            return StageOutput(
                result=StageResult.PARTIAL,
                message=f"Plex notification failed for {failed} paths",
                items_processed=0,
                items_failed=failed,
            )

        message = f"Notified Plex: {successful} paths"
        if libraries:
            message += f" ({', '.join(libraries)})"

        return StageOutput(
            result=StageResult.SUCCESS,
            message=message,
            items_processed=successful,
            items_failed=failed,
        )

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        """No rollback needed for notifications."""
        return True
