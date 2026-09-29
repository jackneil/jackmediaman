"""FFprobe service for extracting media metadata."""

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class FFprobeError(Exception):
    """Base exception for ffprobe errors."""

    pass


class FFprobeNotFoundError(FFprobeError):
    """ffprobe executable not found."""

    pass


class FFprobeTimeoutError(FFprobeError):
    """ffprobe operation timed out."""

    pass


class FFprobeExecutionError(FFprobeError):
    """ffprobe execution failed."""

    pass


@dataclass
class MediaMetadata:
    """Raw metadata extracted from ffprobe."""

    width: int
    height: int
    video_codec: str
    video_profile: Optional[str] = None
    color_transfer: Optional[str] = None
    color_primaries: Optional[str] = None
    audio_codec: Optional[str] = None
    audio_channels: Optional[int] = None
    duration_seconds: Optional[float] = None
    bit_rate: Optional[int] = None
    file_hash: Optional[str] = None

    @property
    def resolution_raw(self) -> str:
        """Get resolution as string like '2160p' or '1080p'."""
        height = min(self.width, self.height)  # Handle vertical video
        return f"{height}p"


class FFprobeService:
    """Low-level service for calling ffprobe and parsing output."""

    # Codec name normalization map
    CODEC_MAP = {
        "hevc": "x265",
        "h265": "x265",
        "libx265": "x265",
        "h264": "x264",
        "avc": "x264",
        "libx264": "x264",
        "av1": "AV1",
        "libaom-av1": "AV1",
        "libsvtav1": "AV1",
        "vp9": "VP9",
        "libvpx-vp9": "VP9",
        "mpeg4": "MPEG4",
        "xvid": "XviD",
        "divx": "DivX",
        "msmpeg4v3": "DivX",
        "mpeg2video": "MPEG2",
    }

    # Audio codec normalization map
    AUDIO_CODEC_MAP = {
        "truehd": "TrueHD",
        "dts": "DTS",
        "eac3": "DD+",
        "ac3": "DD",
        "aac": "AAC",
        "flac": "FLAC",
        "opus": "Opus",
        "vorbis": "Vorbis",
        "mp3": "MP3",
        "pcm_s16le": "PCM",
        "pcm_s24le": "PCM",
    }

    # Audio priority for selecting best track
    AUDIO_PRIORITY = [
        "Atmos",
        "DTS:X",
        "DTS-HD MA",
        "TrueHD",
        "DTS-HD",
        "DD+",
        "DTS",
        "DD",
        "FLAC",
        "AAC",
        "Opus",
        "MP3",
    ]

    # Common locations where ffprobe may be installed
    COMMON_PATHS = [
        "/usr/bin/ffprobe",
        "/usr/local/bin/ffprobe",
        "/opt/homebrew/bin/ffprobe",
        "/snap/bin/ffprobe",
    ]

    def __init__(self, ffprobe_path: Optional[str] = None, timeout: float = 30.0):
        """Initialize FFprobe service.

        Args:
            ffprobe_path: Custom path to ffprobe executable (optional)
            timeout: Maximum time in seconds for ffprobe to complete
        """
        self._custom_path = ffprobe_path
        self._timeout = timeout
        self._ffprobe_path: Optional[str] = None
        self._available: Optional[bool] = None

    @property
    def is_available(self) -> bool:
        """Check if ffprobe is available on the system (cached)."""
        if self._available is None:
            self._ffprobe_path = self._find_ffprobe()
            self._available = self._ffprobe_path is not None
        return self._available

    def _find_ffprobe(self) -> Optional[str]:
        """Find ffprobe executable.

        Search order:
        1. Custom path if provided and exists
        2. shutil.which (PATH search)
        3. Common installation locations
        """
        # Try custom path first
        if self._custom_path:
            custom = Path(self._custom_path)
            if custom.exists() and custom.is_file():
                return str(custom)

        # Try PATH search
        path_result = shutil.which("ffprobe")
        if path_result:
            return path_result

        # Try common locations
        for common_path in self.COMMON_PATHS:
            p = Path(common_path)
            if p.exists() and p.is_file():
                return str(p)

        return None

    def probe(self, path: Path) -> MediaMetadata:
        """Run ffprobe on a file and return parsed metadata.

        Args:
            path: Path to the media file

        Returns:
            MediaMetadata with extracted information

        Raises:
            FFprobeNotFoundError: If ffprobe is not installed
            FFprobeTimeoutError: If ffprobe takes too long
            FFprobeExecutionError: If ffprobe fails to run
        """
        if not self.is_available:
            raise FFprobeNotFoundError("ffprobe not found in PATH")

        if not path.exists():
            raise FFprobeExecutionError(f"File not found: {path}")

        cmd = [
            self._ffprobe_path or "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
        except subprocess.TimeoutExpired:
            raise FFprobeTimeoutError(f"Timeout probing {path}")
        except FileNotFoundError:
            raise FFprobeNotFoundError("ffprobe executable not found")

        if result.returncode != 0:
            raise FFprobeExecutionError(f"ffprobe failed: {result.stderr}")

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise FFprobeExecutionError(f"Failed to parse ffprobe output: {e}")

        return self._parse_output(data, path)

    def _parse_output(self, data: dict, path: Path) -> MediaMetadata:
        """Parse ffprobe JSON output into MediaMetadata."""
        streams = data.get("streams", [])
        format_info = data.get("format", {})

        # Find primary video stream
        video_stream = self._select_video_stream(streams)
        if not video_stream:
            raise FFprobeExecutionError("No video stream found")

        # Extract video properties
        width = video_stream.get("width") or video_stream.get("coded_width") or 0
        height = video_stream.get("height") or video_stream.get("coded_height") or 0
        video_codec = video_stream.get("codec_name", "")
        video_profile = video_stream.get("profile")
        color_transfer = video_stream.get("color_transfer")
        color_primaries = video_stream.get("color_primaries")

        # Extract audio properties
        audio_codec, audio_channels = self._extract_audio(streams)

        # Extract format properties
        duration = None
        if "duration" in format_info:
            try:
                duration = float(format_info["duration"])
            except (ValueError, TypeError):
                pass

        bit_rate = None
        if "bit_rate" in format_info:
            try:
                bit_rate = int(format_info["bit_rate"])
            except (ValueError, TypeError):
                pass

        # Compute file hash for cache invalidation
        file_hash = self._compute_file_hash(path)

        return MediaMetadata(
            width=width,
            height=height,
            video_codec=self._normalize_video_codec(video_codec),
            video_profile=video_profile,
            color_transfer=color_transfer,
            color_primaries=color_primaries,
            audio_codec=audio_codec,
            audio_channels=audio_channels,
            duration_seconds=duration,
            bit_rate=bit_rate,
            file_hash=file_hash,
        )

    def _select_video_stream(self, streams: list) -> Optional[dict]:
        """Select the primary video stream from multiple streams."""
        video_streams = [s for s in streams if s.get("codec_type") == "video"]

        if not video_streams:
            return None

        # Prefer stream marked as default
        for stream in video_streams:
            if stream.get("disposition", {}).get("default", 0) == 1:
                return stream

        # Fall back to highest resolution stream
        return max(
            video_streams,
            key=lambda s: s.get("width", 0) * s.get("height", 0),
            default=None,
        )

    def _extract_audio(self, streams: list) -> tuple[Optional[str], Optional[int]]:
        """Extract best audio codec and channel count from streams."""
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]

        if not audio_streams:
            return None, None

        detected = []
        for stream in audio_streams:
            codec_name = stream.get("codec_name", "").lower()
            profile = stream.get("profile", "")
            title = stream.get("tags", {}).get("title", "")
            channels = stream.get("channels")

            # Check for Atmos in title
            if "atmos" in title.lower():
                detected.append(("Atmos", channels))
                continue

            # DTS variants
            if codec_name == "dts":
                if "MA" in profile:
                    detected.append(("DTS-HD MA", channels))
                elif "HD" in profile:
                    detected.append(("DTS-HD", channels))
                elif "X" in profile:
                    detected.append(("DTS:X", channels))
                else:
                    detected.append(("DTS", channels))
                continue

            # Standard codec mapping
            if codec_name in self.AUDIO_CODEC_MAP:
                detected.append((self.AUDIO_CODEC_MAP[codec_name], channels))

        if not detected:
            return None, None

        # Return highest priority codec
        for priority_codec in self.AUDIO_PRIORITY:
            for codec, channels in detected:
                if codec == priority_codec:
                    return codec, channels

        # Return first detected if none match priority
        return detected[0]

    def _normalize_video_codec(self, codec_name: str) -> str:
        """Normalize ffprobe codec name to standard format."""
        codec_lower = codec_name.lower()
        return self.CODEC_MAP.get(codec_lower, codec_name.upper() if codec_name else "")

    def _compute_file_hash(self, path: Path, chunk_size: int = 65536) -> str:
        """Compute fast hash of file for cache invalidation.

        Uses first 64KB + last 64KB + file size for speed.
        """
        file_size = path.stat().st_size
        hasher = hashlib.md5()

        with open(path, "rb") as f:
            # Read first chunk
            hasher.update(f.read(chunk_size))

            # Read last chunk if file is large enough
            if file_size > chunk_size * 2:
                f.seek(-chunk_size, 2)  # Seek from end
                hasher.update(f.read(chunk_size))

        # Include file size in hash
        hasher.update(str(file_size).encode())

        return hasher.hexdigest()
