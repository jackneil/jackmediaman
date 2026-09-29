"""Subtitle stage for automatic subtitle downloading after organization."""

from typing import Optional

from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger
from jackmediaman.pipeline.context import ProcessContext
from jackmediaman.pipeline.base import StageOutput, StageResult

logger = get_logger("pipeline.subtitles")


class SubtitleStage:
    """Download subtitles for organized media files."""

    name = "subtitles"

    def __init__(self):
        """Initialize the subtitle stage."""
        self._service = None

    def validate(self, context: ProcessContext) -> bool:
        """Check if subtitle download should run."""
        # Skip if disabled
        if context.skip_subtitles:
            return False

        # Skip if no successful operations
        successful_ops = [op for op in context.completed_operations if op.success]
        if not successful_ops:
            return False

        # Check if at least one OpenSubtitles provider is configured
        settings = get_settings()
        com_configured = bool(settings.opensubtitles_com_api_key)
        org_configured = bool(settings.opensubtitles_org_username and settings.opensubtitles_org_password)

        if not com_configured and not org_configured:
            return False

        return True

    def execute(self, context: ProcessContext) -> StageOutput:
        """Download subtitles for organized files."""
        # Lazy load subtitle service
        if self._service is None:
            try:
                from jackmediaman.services.subtitles import SubtitleService

                self._service = SubtitleService()
            except Exception as e:
                return StageOutput(
                    result=StageResult.SKIPPED,
                    message=f"Subtitle service not available: {e}",
                )

        settings = get_settings()
        languages = [
            lang.strip()
            for lang in settings.subtitle_languages.split(",")
            if lang.strip()
        ]

        if not languages:
            languages = ["en"]

        downloaded = 0
        failed = 0

        # Process each successfully linked file
        for operation in context.completed_operations:
            if not operation.success:
                continue

            destination = operation.destination
            if not destination.exists():
                continue

            try:
                result = self._service.download_for_file(
                    path=destination,
                    languages=languages,
                    overwrite=False,
                )
                if result.success:
                    downloaded += 1
                elif not result.skipped:
                    failed += 1
            except Exception as e:
                failed += 1
                context.add_error(
                    stage=self.name,
                    error=f"Subtitle download failed for {destination.name}: {e}",
                    path=destination,
                    recoverable=True,
                )

        if downloaded == 0 and failed == 0:
            return StageOutput(
                result=StageResult.SKIPPED,
                message="No subtitles needed or found",
            )

        return StageOutput(
            result=StageResult.SUCCESS if failed == 0 else StageResult.PARTIAL,
            message=f"Downloaded {downloaded} subtitles",
            items_processed=downloaded,
            items_failed=failed,
        )

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        """No rollback for subtitles (they're just additional files)."""
        return True
