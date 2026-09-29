"""NFO stage for automatic metadata file generation after organization."""

from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger
from jackmediaman.models.media import MediaType
from jackmediaman.pipeline.context import ProcessContext
from jackmediaman.pipeline.base import StageOutput, StageResult

logger = get_logger("pipeline.nfo")


class NFOStage:
    """Generate NFO metadata files for organized media files."""

    name = "nfo"

    def __init__(self):
        """Initialize the NFO stage."""
        self._service = None

    def validate(self, context: ProcessContext) -> bool:
        """Check if NFO generation should run."""
        # Skip if disabled
        if context.skip_nfo:
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
        """Generate NFO files for organized media."""
        # Lazy load NFO service
        if self._service is None:
            try:
                from jackmediaman.services.nfo import NFOService

                self._service = NFOService()
            except Exception as e:
                return StageOutput(
                    result=StageResult.SKIPPED,
                    message=f"NFO service not available: {e}",
                )

        generated = 0
        skipped = 0
        failed = 0
        processed_folders = set()
        processed_show_folders = set()

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

            # Get the folder (movie folder or season folder)
            folder = destination.parent

            try:
                if mapping.identified.media_type == MediaType.MOVIE:
                    # Skip if we already processed this folder
                    if folder in processed_folders:
                        continue
                    processed_folders.add(folder)

                    result = self._service.generate_movie_nfo(
                        folder=folder,
                        title=mapping.identified.canonical_title
                        or mapping.media_item.title,
                        year=mapping.identified.canonical_year,
                        tmdb_id=mapping.identified.tmdb_id,
                        overwrite=False,
                    )

                    if result.success:
                        generated += 1
                    elif result.skipped:
                        skipped += 1
                    else:
                        failed += 1

                else:
                    # TV show: generate show NFO (once per show) + episode NFO
                    show_folder = folder.parent  # From Season XX to Show folder

                    # Generate tvshow.nfo once per show
                    if show_folder not in processed_show_folders:
                        processed_show_folders.add(show_folder)

                        show_result = self._service.generate_show_nfo(
                            folder=show_folder,
                            show_name=mapping.identified.canonical_title
                            or mapping.media_item.series_name,
                            tmdb_id=mapping.identified.tmdb_id,
                            overwrite=False,
                        )

                        if show_result.success:
                            generated += 1
                        elif show_result.skipped:
                            skipped += 1
                        else:
                            failed += 1

                    # Generate episode NFO
                    # Skip if we already processed this exact file
                    if destination in processed_folders:
                        continue
                    processed_folders.add(destination)

                    episode_result = self._service.generate_episode_nfo(
                        video_file=destination,
                        show_name=mapping.identified.canonical_title
                        or mapping.media_item.series_name,
                        season=mapping.media_item.season_number,
                        episode=mapping.media_item.episode_number,
                        tmdb_id=mapping.identified.tmdb_id,
                        overwrite=False,
                    )

                    if episode_result.success:
                        generated += 1
                    elif episode_result.skipped:
                        skipped += 1
                    else:
                        failed += 1

            except Exception as e:
                failed += 1
                context.add_error(
                    stage=self.name,
                    error=f"NFO generation failed for {folder.name}: {e}",
                    path=folder,
                    recoverable=True,
                )

        if generated == 0 and failed == 0:
            if skipped > 0:
                return StageOutput(
                    result=StageResult.SKIPPED,
                    message=f"All {skipped} NFO files already exist",
                )
            return StageOutput(
                result=StageResult.SKIPPED,
                message="No NFO files needed",
            )

        return StageOutput(
            result=StageResult.SUCCESS if failed == 0 else StageResult.PARTIAL,
            message=f"Generated {generated} NFO files ({skipped} skipped)",
            items_processed=generated,
            items_failed=failed,
        )

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        """No rollback for NFO files (they're just additional metadata files)."""
        return True
