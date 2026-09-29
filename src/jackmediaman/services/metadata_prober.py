"""High-level metadata probing service combining ffprobe with caching."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional

from jackmediaman.core.config import get_settings
from jackmediaman.core.ffprobe import (
    FFprobeError,
    FFprobeService,
    MediaMetadata,
)
from jackmediaman.core.metadata_cache import MetadataCache
from jackmediaman.models.quality import Quality, Resolution

logger = logging.getLogger(__name__)


class MetadataProber:
    """High-level service for probing media metadata with caching.

    Combines FFprobeService for extraction and MetadataCache for persistence.
    Supports parallel batch probing for large libraries.
    """

    def __init__(
        self,
        cache: Optional[MetadataCache] = None,
        ffprobe: Optional[FFprobeService] = None,
        max_workers: int = 4,
    ):
        """Initialize metadata prober.

        Args:
            cache: Metadata cache instance. If None, caching is disabled.
            ffprobe: FFprobe service instance. If None, creates default.
            max_workers: Maximum parallel ffprobe processes for batch operations.
        """
        self._cache = cache
        self._ffprobe = ffprobe or FFprobeService()
        self._max_workers = max_workers

    @property
    def is_available(self) -> bool:
        """Check if ffprobe is available."""
        return self._ffprobe.is_available

    def probe(self, path: Path) -> Optional[MediaMetadata]:
        """Probe a single file for metadata.

        Checks cache first, then runs ffprobe if needed.

        Args:
            path: Path to media file

        Returns:
            MediaMetadata if successful, None on error
        """
        # Check cache first
        if self._cache:
            cached = self._cache.get(path)
            if cached is not None:
                return cached

        # Run ffprobe
        try:
            metadata = self._ffprobe.probe(path)

            # Cache result
            if self._cache:
                self._cache.set(path, metadata)

            return metadata

        except FFprobeError as e:
            logger.warning(f"FFprobe failed for {path}: {e}")
            return None

    def probe_quality(self, path: Path) -> Optional[Quality]:
        """Probe a file and return Quality object.

        Args:
            path: Path to media file

        Returns:
            Quality object if successful, None on error
        """
        metadata = self.probe(path)
        if metadata is None:
            return None

        return self._metadata_to_quality(metadata)

    def probe_batch(
        self,
        paths: List[Path],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[Path, Optional[MediaMetadata]]:
        """Probe multiple files in parallel.

        Args:
            paths: List of file paths to probe
            progress_callback: Optional callback(current, total, filename)

        Returns:
            Dictionary mapping paths to their metadata (or None on error)
        """
        if not paths:
            return {}

        results: Dict[Path, Optional[MediaMetadata]] = {}
        total = len(paths)

        # Separate cached and uncached paths
        uncached_paths = []
        for path in paths:
            if self._cache:
                cached = self._cache.get(path)
                if cached is not None:
                    results[path] = cached
                    continue
            uncached_paths.append(path)

        # Report cached results
        cached_count = len(results)
        if cached_count > 0 and progress_callback:
            progress_callback(cached_count, total, f"(cached: {cached_count})")

        # Probe uncached files in parallel
        if uncached_paths:
            with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
                future_to_path = {
                    executor.submit(self._probe_single, p): p for p in uncached_paths
                }

                for future in as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        metadata = future.result()
                        results[path] = metadata
                    except Exception as e:
                        logger.error(f"Error probing {path}: {e}")
                        results[path] = None

                    if progress_callback:
                        progress_callback(len(results), total, path.name)

        return results

    def probe_batch_quality(
        self,
        paths: List[Path],
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Dict[Path, Optional[Quality]]:
        """Probe multiple files and return Quality objects.

        Args:
            paths: List of file paths to probe
            progress_callback: Optional callback(current, total, filename)

        Returns:
            Dictionary mapping paths to Quality objects (or None on error)
        """
        metadata_results = self.probe_batch(paths, progress_callback)

        return {
            path: self._metadata_to_quality(meta) if meta else None
            for path, meta in metadata_results.items()
        }

    def _probe_single(self, path: Path) -> Optional[MediaMetadata]:
        """Probe a single file (for use in thread pool)."""
        try:
            metadata = self._ffprobe.probe(path)

            # Cache result
            if self._cache:
                self._cache.set(path, metadata)

            return metadata

        except FFprobeError as e:
            logger.warning(f"FFprobe failed for {path}: {e}")
            return None

    def _metadata_to_quality(self, metadata: MediaMetadata) -> Quality:
        """Convert MediaMetadata to Quality object."""
        # Detect resolution from dimensions
        resolution = self._resolution_from_dimensions(metadata.width, metadata.height)

        # Detect HDR from color metadata
        hdr = self._detect_hdr(metadata)

        return Quality(
            resolution=resolution,
            resolution_raw=metadata.resolution_raw,
            source=None,  # Cannot detect from metadata
            codec=metadata.video_codec,
            hdr=hdr,
            audio=metadata.audio_codec,
        )

    @staticmethod
    def _resolution_from_dimensions(width: int, height: int) -> Resolution:
        """Map video dimensions to Resolution enum."""
        if width == 0 or height == 0:
            return Resolution.UNKNOWN

        # Use the smaller dimension (handles vertical video)
        short_edge = min(width, height)

        if short_edge >= 2160:
            return Resolution.UHD
        elif short_edge >= 1080:
            return Resolution.FHD
        elif short_edge >= 720:
            return Resolution.HD
        else:
            return Resolution.SD

    @staticmethod
    def _detect_hdr(metadata: MediaMetadata) -> bool:
        """Detect HDR from color metadata."""
        color_transfer = (metadata.color_transfer or "").lower()
        color_primaries = (metadata.color_primaries or "").lower()

        # HDR10/HDR10+: PQ transfer function with BT.2020 primaries
        if color_transfer == "smpte2084" and color_primaries == "bt2020":
            return True

        # HLG (Hybrid Log-Gamma)
        if color_transfer == "arib-std-b67":
            return True

        return False


def get_metadata_prober(
    cache_enabled: bool = True,
    cache_path: Optional[Path] = None,
    max_workers: int = 4,
    ffprobe_path: Optional[str] = None,
) -> MetadataProber:
    """Factory function to create a configured MetadataProber.

    Args:
        cache_enabled: Whether to enable caching
        cache_path: Custom cache database path
        max_workers: Parallel workers for batch operations
        ffprobe_path: Custom path to ffprobe executable (uses settings if not provided)

    Returns:
        Configured MetadataProber instance
    """
    # Get ffprobe path from settings if not provided
    if ffprobe_path is None:
        settings = get_settings()
        if settings.ffprobe_path:
            ffprobe_path = str(settings.ffprobe_path)

    cache = MetadataCache(cache_path) if cache_enabled else None
    ffprobe = FFprobeService(ffprobe_path=ffprobe_path)

    return MetadataProber(
        cache=cache,
        ffprobe=ffprobe,
        max_workers=max_workers,
    )
