"""Organizer stage for calculating destination paths."""

from pathlib import Path
from typing import Optional

from jackmediaman.core.config import get_settings
from jackmediaman.core.logging import get_logger
from jackmediaman.core.utils import sanitize_filename, get_resolution_tag
from jackmediaman.models.media import Episode, MediaType, Movie
from jackmediaman.pipeline.context import FileMapping, IdentifiedMedia, ProcessContext
from jackmediaman.pipeline.base import StageOutput, StageResult

logger = get_logger("pipeline.organizer")


class OrganizerStage:
    """Determine destination paths for media files."""

    name = "organizer"

    def __init__(
        self,
        movies_dir: Optional[Path] = None,
        tv_dir: Optional[Path] = None,
    ):
        """
        Initialize the organizer stage.

        Args:
            movies_dir: Path to movies library (uses settings if not specified)
            tv_dir: Path to TV library (uses settings if not specified)
        """
        settings = get_settings()
        self.movies_dir = movies_dir or settings.movies_dir
        self.tv_dir = tv_dir or settings.tv_dir

    def validate(self, context: ProcessContext) -> bool:
        """Check if organization should run."""
        return len(context.identified_media) > 0

    def execute(self, context: ProcessContext) -> StageOutput:
        """
        Calculate destination paths for all identified media.

        Movies: {movies_dir}/Movie Name (Year)/Movie Name (Year).ext
        TV:     {tv_dir}/Show Name/Season XX/Show - S01E01 - Title.ext
        """
        mappings = []
        failed = []

        for identified in context.identified_media:
            try:
                mapping = self._create_mapping(identified)
                mappings.append(mapping)
            except Exception as e:
                failed.append((identified.source_path, str(e)))
                context.add_error(
                    stage=self.name,
                    error=f"Failed to organize {identified.source_path.name}: {e}",
                    path=identified.source_path,
                )

        context.file_mappings = mappings

        if not mappings:
            return StageOutput(
                result=StageResult.FAILED,
                message="No files could be organized",
                items_failed=len(failed),
            )

        return StageOutput(
            result=StageResult.SUCCESS if not failed else StageResult.PARTIAL,
            message=f"Organized {len(mappings)} files",
            items_processed=len(mappings),
            items_failed=len(failed),
        )

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        """No rollback needed for organization (just path calculation)."""
        return True

    def _create_mapping(self, identified: IdentifiedMedia) -> FileMapping:
        """Create file mapping for identified media."""
        if identified.media_type == MediaType.EPISODE:
            return self._organize_episode(identified)
        else:
            return self._organize_movie(identified)

    def _organize_movie(self, identified: IdentifiedMedia) -> FileMapping:
        """Calculate movie destination path."""
        movie = identified.media_item
        assert isinstance(movie, Movie)

        # Get canonical info
        title = identified.canonical_title or movie.title
        year = identified.canonical_year or movie.year

        # Sanitize for filesystem
        safe_title = sanitize_filename(title)

        # Build folder and filename
        if year:
            folder_name = f"{safe_title} ({year})"
        else:
            folder_name = safe_title

        # Get extension from original file
        ext = identified.source_path.suffix

        # Generate filename with resolution tag if available
        filename = folder_name
        resolution_tag = self._get_resolution_tag(movie)
        if resolution_tag:
            filename = f"{filename} [{resolution_tag}]"
        filename = f"{filename}{ext}"

        # Build full paths
        movie_folder = self.movies_dir / folder_name
        destination = movie_folder / filename

        return FileMapping(
            source=identified.source_path,
            destination=destination,
            media_item=movie,
            identified=identified,
            create_directories=[movie_folder],
        )

    def _organize_episode(self, identified: IdentifiedMedia) -> FileMapping:
        """Calculate TV episode destination path."""
        episode = identified.media_item
        assert isinstance(episode, Episode)

        # Get canonical info
        series_name = identified.canonical_title or episode.series_name
        season = episode.season_number
        episodes = episode.episode_numbers

        # Sanitize for filesystem
        safe_series = sanitize_filename(series_name)

        # Build episode code
        if len(episodes) == 1:
            ep_code = f"S{season:02d}E{episodes[0]:02d}"
        else:
            ep_code = f"S{season:02d}E{episodes[0]:02d}-E{episodes[-1]:02d}"

        # Get extension
        ext = identified.source_path.suffix

        # Build filename
        filename = f"{safe_series} - {ep_code}"
        resolution_tag = self._get_resolution_tag(episode)
        if resolution_tag:
            filename = f"{filename} [{resolution_tag}]"
        filename = f"{filename}{ext}"

        # Build full paths
        show_folder = self.tv_dir / safe_series
        season_folder = show_folder / f"Season {season:02d}"
        destination = season_folder / filename

        return FileMapping(
            source=identified.source_path,
            destination=destination,
            media_item=episode,
            identified=identified,
            create_directories=[show_folder, season_folder],
        )

    def _get_resolution_tag(self, item) -> Optional[str]:
        """Get resolution tag for filename."""
        return get_resolution_tag(item)
