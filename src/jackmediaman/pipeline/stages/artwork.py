"""Artwork stage for automatic poster downloading after organization."""

from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger
from jackmediaman.models.media import MediaType
from jackmediaman.pipeline.context import ProcessContext
from jackmediaman.pipeline.base import StageOutput, StageResult

logger = get_logger("pipeline.artwork")


class ArtworkStage:
    """Download poster artwork for organized media files."""

    name = "artwork"

    def __init__(self):
        """Initialize the artwork stage."""
        self._service = None

    def validate(self, context: ProcessContext) -> bool:
        """Check if artwork download should run."""
        # Skip if disabled
        if context.skip_artwork:
            return False

        # Skip if no successful operations
        successful_ops = [op for op in context.completed_operations if op.success]
        if not successful_ops:
            return False

        # Check if TMDb is configured
        settings = get_settings()
        if not settings.tmdb_api_key:
            return False

        return True

    def execute(self, context: ProcessContext) -> StageOutput:
        """Download poster artwork for organized files."""
        # Lazy load artwork service
        if self._service is None:
            try:
                from jackmediaman.services.artwork import ArtworkService

                self._service = ArtworkService()
            except Exception as e:
                return StageOutput(
                    result=StageResult.SKIPPED,
                    message=f"Artwork service not available: {e}",
                )

        downloaded = 0
        failed = 0
        processed_folders = set()

        # Process each successfully linked file
        for mapping in context.file_mappings:
            # Find the corresponding operation
            operation = next(
                (
                    op
                    for op in context.completed_operations
                    if op.source == mapping.source and op.success
                ),
                None,
            )

            if not operation:
                continue

            destination = operation.destination
            if not destination.exists():
                continue

            # Get the folder (movie folder or show folder)
            folder = destination.parent

            # For TV shows, go up one level to show folder (not season folder)
            if mapping.identified.media_type == MediaType.EPISODE:
                folder = folder.parent  # From Season XX to Show folder

            # Skip if we already processed this folder
            if folder in processed_folders:
                continue
            processed_folders.add(folder)

            try:
                if mapping.identified.media_type == MediaType.MOVIE:
                    result = self._service.download_movie_poster(
                        movie_path=destination,
                        title=mapping.identified.canonical_title or mapping.media_item.title,
                        year=mapping.identified.canonical_year,
                        tmdb_id=mapping.identified.tmdb_id,
                        overwrite=False,
                    )
                    if result.success and not result.skipped:
                        downloaded += 1
                    elif not result.success:
                        failed += 1
                else:
                    # TV show: download show poster and season poster
                    results = self._service.download_show_artwork(
                        show_folder=folder,
                        show_name=mapping.identified.canonical_title
                        or mapping.media_item.series_name,
                        tmdb_id=mapping.identified.tmdb_id,
                        overwrite=False,
                    )
                    for result in results:
                        if result.success and not result.skipped:
                            downloaded += 1
                        elif not result.success:
                            failed += 1

            except Exception as e:
                failed += 1
                context.add_error(
                    stage=self.name,
                    error=f"Artwork download failed for {folder.name}: {e}",
                    path=folder,
                    recoverable=True,
                )

        if downloaded == 0 and failed == 0:
            return StageOutput(
                result=StageResult.SKIPPED,
                message="No artwork needed or found",
            )

        return StageOutput(
            result=StageResult.SUCCESS if failed == 0 else StageResult.PARTIAL,
            message=f"Downloaded {downloaded} posters",
            items_processed=downloaded,
            items_failed=failed,
        )

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        """No rollback for artwork (they're just additional files)."""
        return True
