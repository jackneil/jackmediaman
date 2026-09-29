"""Tests for FFprobe service."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from jackmediaman.core.ffprobe import (
    FFprobeError,
    FFprobeExecutionError,
    FFprobeNotFoundError,
    FFprobeService,
    FFprobeTimeoutError,
    MediaMetadata,
)


class TestMediaMetadata:
    """Tests for MediaMetadata dataclass."""

    def test_resolution_raw_1080p(self):
        """Computes correct resolution string for 1080p."""
        meta = MediaMetadata(width=1920, height=1080, video_codec="x264")
        assert meta.resolution_raw == "1080p"

    def test_resolution_raw_2160p(self):
        """Computes correct resolution string for 4K."""
        meta = MediaMetadata(width=3840, height=2160, video_codec="x265")
        assert meta.resolution_raw == "2160p"

    def test_resolution_raw_720p(self):
        """Computes correct resolution string for 720p."""
        meta = MediaMetadata(width=1280, height=720, video_codec="x264")
        assert meta.resolution_raw == "720p"

    def test_resolution_raw_vertical_video(self):
        """Handles vertical video (portrait mode)."""
        # 1080p vertical video
        meta = MediaMetadata(width=1080, height=1920, video_codec="x264")
        assert meta.resolution_raw == "1080p"

    def test_optional_fields(self):
        """Optional fields default to None."""
        meta = MediaMetadata(width=1920, height=1080, video_codec="x264")
        assert meta.video_profile is None
        assert meta.color_transfer is None
        assert meta.audio_codec is None
        assert meta.duration_seconds is None

    def test_all_fields(self):
        """All fields can be set."""
        meta = MediaMetadata(
            width=3840,
            height=2160,
            video_codec="x265",
            video_profile="Main 10",
            color_transfer="smpte2084",
            color_primaries="bt2020",
            audio_codec="TrueHD",
            audio_channels=8,
            duration_seconds=7200.5,
            bit_rate=25000000,
            file_hash="abc123",
        )
        assert meta.width == 3840
        assert meta.height == 2160
        assert meta.video_profile == "Main 10"
        assert meta.color_transfer == "smpte2084"
        assert meta.audio_channels == 8
        assert meta.file_hash == "abc123"


class TestFFprobeServiceAvailability:
    """Tests for FFprobe availability checks."""

    @patch("shutil.which")
    def test_is_available_true(self, mock_which):
        """Returns True when ffprobe is found."""
        mock_which.return_value = "/usr/bin/ffprobe"
        service = FFprobeService()
        assert service.is_available is True

    @patch("shutil.which")
    def test_is_available_false(self, mock_which):
        """Returns False when ffprobe is not found."""
        mock_which.return_value = None
        service = FFprobeService()
        assert service.is_available is False

    @patch("shutil.which")
    def test_is_available_cached(self, mock_which):
        """Availability check is cached."""
        mock_which.return_value = "/usr/bin/ffprobe"
        service = FFprobeService()
        _ = service.is_available
        _ = service.is_available
        # Should only call which once
        assert mock_which.call_count == 1


class TestFFprobeServiceProbe:
    """Tests for FFprobe probe method."""

    @pytest.fixture
    def service(self):
        """Create FFprobe service with mocked availability."""
        svc = FFprobeService(timeout=10.0)
        svc._available = True
        svc._ffprobe_path = "/usr/bin/ffprobe"
        return svc

    @pytest.fixture
    def sample_ffprobe_output(self):
        """Sample ffprobe JSON output."""
        return {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "hevc",
                    "profile": "Main 10",
                    "width": 3840,
                    "height": 2160,
                    "color_transfer": "smpte2084",
                    "color_primaries": "bt2020",
                    "disposition": {"default": 1},
                },
                {
                    "codec_type": "audio",
                    "codec_name": "truehd",
                    "channels": 8,
                    "tags": {"title": "English - TrueHD Atmos"},
                },
            ],
            "format": {
                "duration": "7200.5",
                "bit_rate": "25000000",
            },
        }

    def test_probe_not_available(self, tmp_path):
        """Raises error when ffprobe not available."""
        service = FFprobeService()
        service._available = False

        with pytest.raises(FFprobeNotFoundError):
            service.probe(tmp_path / "video.mkv")

    def test_probe_file_not_found(self, service, tmp_path):
        """Raises error when file doesn't exist."""
        with pytest.raises(FFprobeExecutionError, match="File not found"):
            service.probe(tmp_path / "nonexistent.mkv")

    @patch("subprocess.run")
    def test_probe_success(self, mock_run, service, tmp_path, sample_ffprobe_output):
        """Successfully probes video file."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(sample_ffprobe_output),
            stderr="",
        )

        metadata = service.probe(video_file)

        assert metadata.width == 3840
        assert metadata.height == 2160
        assert metadata.video_codec == "x265"  # Normalized from hevc
        assert metadata.color_transfer == "smpte2084"
        assert metadata.audio_channels == 8

    @patch("subprocess.run")
    def test_probe_timeout(self, mock_run, service, tmp_path):
        """Raises error on timeout."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffprobe", timeout=10)

        with pytest.raises(FFprobeTimeoutError):
            service.probe(video_file)

    @patch("subprocess.run")
    def test_probe_execution_failed(self, mock_run, service, tmp_path):
        """Raises error when ffprobe fails."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Invalid data found",
        )

        with pytest.raises(FFprobeExecutionError, match="ffprobe failed"):
            service.probe(video_file)

    @patch("subprocess.run")
    def test_probe_invalid_json(self, mock_run, service, tmp_path):
        """Raises error on invalid JSON output."""
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="not valid json",
            stderr="",
        )

        with pytest.raises(FFprobeExecutionError, match="parse"):
            service.probe(video_file)


class TestFFprobeServiceCodecNormalization:
    """Tests for codec name normalization."""

    @pytest.fixture
    def service(self):
        """Create FFprobe service."""
        return FFprobeService()

    def test_normalize_hevc_to_x265(self, service):
        """Normalizes HEVC to x265."""
        assert service._normalize_video_codec("hevc") == "x265"
        assert service._normalize_video_codec("HEVC") == "x265"
        assert service._normalize_video_codec("h265") == "x265"

    def test_normalize_h264_to_x264(self, service):
        """Normalizes H264 to x264."""
        assert service._normalize_video_codec("h264") == "x264"
        assert service._normalize_video_codec("avc") == "x264"

    def test_normalize_av1(self, service):
        """Normalizes AV1 variants."""
        assert service._normalize_video_codec("av1") == "AV1"
        assert service._normalize_video_codec("libaom-av1") == "AV1"

    def test_unknown_codec_uppercase(self, service):
        """Unknown codecs are uppercased."""
        assert service._normalize_video_codec("somecodec") == "SOMECODEC"

    def test_empty_codec(self, service):
        """Empty codec returns empty string."""
        assert service._normalize_video_codec("") == ""


class TestFFprobeServiceAudioExtraction:
    """Tests for audio stream extraction."""

    @pytest.fixture
    def service(self):
        """Create FFprobe service."""
        return FFprobeService()

    def test_extract_audio_no_streams(self, service):
        """Returns None when no audio streams."""
        codec, channels = service._extract_audio([])
        assert codec is None
        assert channels is None

    def test_extract_audio_single_aac(self, service):
        """Extracts single AAC stream."""
        streams = [
            {"codec_type": "audio", "codec_name": "aac", "channels": 2}
        ]
        codec, channels = service._extract_audio(streams)
        assert codec == "AAC"
        assert channels == 2

    def test_extract_audio_atmos_in_title(self, service):
        """Detects Atmos from stream title."""
        streams = [
            {
                "codec_type": "audio",
                "codec_name": "truehd",
                "channels": 8,
                "tags": {"title": "English - TrueHD Atmos"},
            }
        ]
        codec, channels = service._extract_audio(streams)
        assert codec == "Atmos"
        assert channels == 8

    def test_extract_audio_dts_hd_ma(self, service):
        """Detects DTS-HD MA from profile."""
        streams = [
            {
                "codec_type": "audio",
                "codec_name": "dts",
                "profile": "DTS-HD MA",
                "channels": 8,
            }
        ]
        codec, channels = service._extract_audio(streams)
        assert codec == "DTS-HD MA"
        assert channels == 8

    def test_extract_audio_priority_order(self, service):
        """Selects highest priority audio codec."""
        streams = [
            {"codec_type": "audio", "codec_name": "aac", "channels": 2},
            {"codec_type": "audio", "codec_name": "ac3", "channels": 6},
            {"codec_type": "audio", "codec_name": "truehd", "channels": 8},
        ]
        codec, channels = service._extract_audio(streams)
        # TrueHD has higher priority than DD (ac3) and AAC
        assert codec == "TrueHD"
        assert channels == 8


class TestFFprobeServiceVideoStreamSelection:
    """Tests for video stream selection."""

    @pytest.fixture
    def service(self):
        """Create FFprobe service."""
        return FFprobeService()

    def test_select_video_no_streams(self, service):
        """Returns None when no video streams."""
        result = service._select_video_stream([])
        assert result is None

    def test_select_video_single_stream(self, service):
        """Selects single video stream."""
        streams = [
            {"codec_type": "video", "width": 1920, "height": 1080}
        ]
        result = service._select_video_stream(streams)
        assert result["width"] == 1920

    def test_select_video_prefers_default(self, service):
        """Prefers stream marked as default."""
        streams = [
            {"codec_type": "video", "width": 1280, "height": 720, "disposition": {}},
            {"codec_type": "video", "width": 1920, "height": 1080, "disposition": {"default": 1}},
        ]
        result = service._select_video_stream(streams)
        assert result["width"] == 1920

    def test_select_video_highest_resolution_fallback(self, service):
        """Falls back to highest resolution if no default."""
        streams = [
            {"codec_type": "video", "width": 1280, "height": 720},
            {"codec_type": "video", "width": 3840, "height": 2160},
            {"codec_type": "video", "width": 1920, "height": 1080},
        ]
        result = service._select_video_stream(streams)
        assert result["width"] == 3840


class TestFFprobeServiceFileHash:
    """Tests for file hash computation."""

    def test_compute_file_hash(self, tmp_path):
        """Computes consistent hash for file."""
        service = FFprobeService()
        video_file = tmp_path / "video.mkv"
        video_file.write_bytes(b"0" * 1000)

        hash1 = service._compute_file_hash(video_file)
        hash2 = service._compute_file_hash(video_file)

        assert hash1 == hash2
        assert len(hash1) == 32  # MD5 hex length

    def test_compute_file_hash_different_content(self, tmp_path):
        """Different content produces different hash."""
        service = FFprobeService()

        file1 = tmp_path / "video1.mkv"
        file2 = tmp_path / "video2.mkv"
        file1.write_bytes(b"0" * 1000)
        file2.write_bytes(b"1" * 1000)

        hash1 = service._compute_file_hash(file1)
        hash2 = service._compute_file_hash(file2)

        assert hash1 != hash2

    def test_compute_file_hash_large_file(self, tmp_path):
        """Handles large files (samples first and last chunks)."""
        service = FFprobeService()
        video_file = tmp_path / "large.mkv"
        # File larger than 2 chunks
        video_file.write_bytes(b"A" * 65536 + b"B" * 65536 + b"C" * 65536)

        hash_result = service._compute_file_hash(video_file)

        assert len(hash_result) == 32
