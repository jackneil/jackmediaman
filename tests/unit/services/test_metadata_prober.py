"""Tests for metadata prober service."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jackmediaman.core.ffprobe import FFprobeError, MediaMetadata
from jackmediaman.models.quality import Resolution
from jackmediaman.services.metadata_prober import (
    MetadataProber,
    get_metadata_prober,
)


class TestMetadataProberAvailability:
    """Tests for MetadataProber availability."""

    def test_is_available_delegates_to_ffprobe(self):
        """is_available delegates to FFprobeService."""
        mock_ffprobe = MagicMock()
        mock_ffprobe.is_available = True

        prober = MetadataProber(ffprobe=mock_ffprobe)

        assert prober.is_available is True

    def test_is_available_false(self):
        """Returns False when ffprobe not available."""
        mock_ffprobe = MagicMock()
        mock_ffprobe.is_available = False

        prober = MetadataProber(ffprobe=mock_ffprobe)

        assert prober.is_available is False


class TestMetadataProberProbe:
    """Tests for single file probing."""

    @pytest.fixture
    def mock_ffprobe(self):
        """Create mock FFprobe service."""
        mock = MagicMock()
        mock.is_available = True
        mock.probe.return_value = MediaMetadata(
            width=1920,
            height=1080,
            video_codec="x264",
            audio_codec="AAC",
            audio_channels=2,
        )
        return mock

    @pytest.fixture
    def mock_cache(self):
        """Create mock cache."""
        mock = MagicMock()
        mock.get.return_value = None
        return mock

    def test_probe_no_cache(self, mock_ffprobe, tmp_path):
        """Probes file without cache."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        prober = MetadataProber(ffprobe=mock_ffprobe, cache=None)
        result = prober.probe(video_file)

        assert result is not None
        assert result.width == 1920
        mock_ffprobe.probe.assert_called_once_with(video_file)

    def test_probe_with_cache_miss(self, mock_ffprobe, mock_cache, tmp_path):
        """Probes file on cache miss and caches result."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        prober = MetadataProber(ffprobe=mock_ffprobe, cache=mock_cache)
        result = prober.probe(video_file)

        assert result is not None
        mock_cache.get.assert_called_once_with(video_file)
        mock_ffprobe.probe.assert_called_once()
        mock_cache.set.assert_called_once()

    def test_probe_with_cache_hit(self, mock_ffprobe, mock_cache, tmp_path):
        """Returns cached metadata on cache hit."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        cached_metadata = MediaMetadata(
            width=3840,
            height=2160,
            video_codec="x265",
        )
        mock_cache.get.return_value = cached_metadata

        prober = MetadataProber(ffprobe=mock_ffprobe, cache=mock_cache)
        result = prober.probe(video_file)

        assert result.width == 3840
        mock_ffprobe.probe.assert_not_called()

    def test_probe_ffprobe_error(self, mock_ffprobe, tmp_path):
        """Returns None on FFprobe error."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        mock_ffprobe.probe.side_effect = FFprobeError("Test error")

        prober = MetadataProber(ffprobe=mock_ffprobe, cache=None)
        result = prober.probe(video_file)

        assert result is None


class TestMetadataProberProbeQuality:
    """Tests for probe_quality method."""

    @pytest.fixture
    def prober_1080p(self):
        """Create prober that returns 1080p metadata."""
        mock_ffprobe = MagicMock()
        mock_ffprobe.is_available = True
        mock_ffprobe.probe.return_value = MediaMetadata(
            width=1920,
            height=1080,
            video_codec="x264",
        )
        return MetadataProber(ffprobe=mock_ffprobe, cache=None)

    @pytest.fixture
    def prober_4k_hdr(self):
        """Create prober that returns 4K HDR metadata."""
        mock_ffprobe = MagicMock()
        mock_ffprobe.is_available = True
        mock_ffprobe.probe.return_value = MediaMetadata(
            width=3840,
            height=2160,
            video_codec="x265",
            color_transfer="smpte2084",
            color_primaries="bt2020",
        )
        return MetadataProber(ffprobe=mock_ffprobe, cache=None)

    def test_probe_quality_1080p(self, prober_1080p, tmp_path):
        """Converts metadata to Quality for 1080p."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        quality = prober_1080p.probe_quality(video_file)

        assert quality is not None
        assert quality.resolution == Resolution.FHD
        assert quality.resolution_raw == "1080p"
        assert quality.codec == "x264"
        assert quality.hdr is False

    def test_probe_quality_4k_hdr(self, prober_4k_hdr, tmp_path):
        """Converts metadata to Quality for 4K HDR."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        quality = prober_4k_hdr.probe_quality(video_file)

        assert quality is not None
        assert quality.resolution == Resolution.UHD
        assert quality.resolution_raw == "2160p"
        assert quality.hdr is True

    def test_probe_quality_returns_none_on_error(self, tmp_path):
        """Returns None when probe fails."""
        mock_ffprobe = MagicMock()
        mock_ffprobe.probe.side_effect = FFprobeError("Test error")

        prober = MetadataProber(ffprobe=mock_ffprobe, cache=None)
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        quality = prober.probe_quality(video_file)

        assert quality is None


class TestMetadataProberBatch:
    """Tests for batch probing."""

    @pytest.fixture
    def mock_ffprobe(self):
        """Create mock FFprobe service."""
        mock = MagicMock()
        mock.is_available = True
        mock.probe.return_value = MediaMetadata(
            width=1920,
            height=1080,
            video_codec="x264",
        )
        return mock

    def test_probe_batch_empty(self, mock_ffprobe):
        """Returns empty dict for empty input."""
        prober = MetadataProber(ffprobe=mock_ffprobe, cache=None)
        results = prober.probe_batch([])

        assert results == {}

    def test_probe_batch_single_file(self, mock_ffprobe, tmp_path):
        """Probes single file in batch."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        prober = MetadataProber(ffprobe=mock_ffprobe, cache=None)
        results = prober.probe_batch([video_file])

        assert video_file in results
        assert results[video_file].width == 1920

    def test_probe_batch_multiple_files(self, mock_ffprobe, tmp_path):
        """Probes multiple files in batch."""
        files = []
        for i in range(3):
            video_file = tmp_path / f"video{i}.mkv"
            video_file.write_bytes(b"0" * 1000)
            files.append(video_file)

        prober = MetadataProber(ffprobe=mock_ffprobe, cache=None, max_workers=2)
        results = prober.probe_batch(files)

        assert len(results) == 3
        for f in files:
            assert f in results

    def test_probe_batch_with_cache_hits(self, mock_ffprobe, tmp_path):
        """Uses cached results in batch probing."""
        mock_cache = MagicMock()
        cached_metadata = MediaMetadata(width=3840, height=2160, video_codec="x265")

        files = []
        for i in range(3):
            video_file = tmp_path / f"video{i}.mkv"
            video_file.write_bytes(b"0" * 1000)
            files.append(video_file)

        # First file is cached, others are not
        mock_cache.get.side_effect = [cached_metadata, None, None]

        prober = MetadataProber(ffprobe=mock_ffprobe, cache=mock_cache)
        results = prober.probe_batch(files)

        # First file should have cached result
        assert results[files[0]].width == 3840
        # Others should be probed
        assert results[files[1]].width == 1920

    def test_probe_batch_progress_callback(self, mock_ffprobe, tmp_path):
        """Calls progress callback during batch probing."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        callback = MagicMock()
        prober = MetadataProber(ffprobe=mock_ffprobe, cache=None)
        prober.probe_batch([video_file], progress_callback=callback)

        callback.assert_called()

    def test_probe_batch_quality(self, mock_ffprobe, tmp_path):
        """probe_batch_quality returns Quality objects."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        prober = MetadataProber(ffprobe=mock_ffprobe, cache=None)
        results = prober.probe_batch_quality([video_file])

        assert video_file in results
        quality = results[video_file]
        assert quality.resolution == Resolution.FHD


class TestMetadataProberResolutionDetection:
    """Tests for resolution detection from dimensions."""

    def test_resolution_4k(self):
        """Detects 4K/UHD from dimensions."""
        result = MetadataProber._resolution_from_dimensions(3840, 2160)
        assert result == Resolution.UHD

    def test_resolution_1080p(self):
        """Detects 1080p/FHD from dimensions."""
        result = MetadataProber._resolution_from_dimensions(1920, 1080)
        assert result == Resolution.FHD

    def test_resolution_720p(self):
        """Detects 720p/HD from dimensions."""
        result = MetadataProber._resolution_from_dimensions(1280, 720)
        assert result == Resolution.HD

    def test_resolution_480p(self):
        """Detects 480p/SD from dimensions."""
        result = MetadataProber._resolution_from_dimensions(720, 480)
        assert result == Resolution.SD

    def test_resolution_zero(self):
        """Returns UNKNOWN for zero dimensions."""
        result = MetadataProber._resolution_from_dimensions(0, 0)
        assert result == Resolution.UNKNOWN

    def test_resolution_vertical_video(self):
        """Handles vertical video correctly."""
        # 1080p vertical video (1080x1920)
        result = MetadataProber._resolution_from_dimensions(1080, 1920)
        assert result == Resolution.FHD


class TestMetadataProberHDRDetection:
    """Tests for HDR detection."""

    def test_detect_hdr10(self):
        """Detects HDR10 from color metadata."""
        metadata = MediaMetadata(
            width=3840,
            height=2160,
            video_codec="x265",
            color_transfer="smpte2084",
            color_primaries="bt2020",
        )
        result = MetadataProber._detect_hdr(metadata)
        assert result is True

    def test_detect_hlg(self):
        """Detects HLG from color metadata."""
        metadata = MediaMetadata(
            width=3840,
            height=2160,
            video_codec="x265",
            color_transfer="arib-std-b67",
            color_primaries="bt2020",
        )
        result = MetadataProber._detect_hdr(metadata)
        assert result is True

    def test_detect_sdr(self):
        """Detects SDR (no HDR) from color metadata."""
        metadata = MediaMetadata(
            width=1920,
            height=1080,
            video_codec="x264",
            color_transfer="bt709",
            color_primaries="bt709",
        )
        result = MetadataProber._detect_hdr(metadata)
        assert result is False

    def test_detect_hdr_none_values(self):
        """Handles None color values."""
        metadata = MediaMetadata(
            width=1920,
            height=1080,
            video_codec="x264",
            color_transfer=None,
            color_primaries=None,
        )
        result = MetadataProber._detect_hdr(metadata)
        assert result is False


class TestGetMetadataProber:
    """Tests for factory function."""

    def test_get_metadata_prober_with_cache(self, tmp_path):
        """Creates prober with caching enabled."""
        prober = get_metadata_prober(
            cache_enabled=True,
            cache_path=tmp_path / "test.db",
        )

        assert prober._cache is not None

    def test_get_metadata_prober_no_cache(self):
        """Creates prober with caching disabled."""
        prober = get_metadata_prober(cache_enabled=False)

        assert prober._cache is None

    def test_get_metadata_prober_custom_workers(self):
        """Creates prober with custom worker count."""
        prober = get_metadata_prober(cache_enabled=False, max_workers=8)

        assert prober._max_workers == 8
