"""Quality parsing and scoring for media files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from jackmediaman.core.ffprobe import MediaMetadata


class Resolution(IntEnum):
    """Video resolution rankings (higher = better)."""

    UNKNOWN = 0
    SD = 1  # 480p and below
    HD = 2  # 720p
    FHD = 3  # 1080p
    UHD = 4  # 2160p/4K


@dataclass(frozen=True)
class Quality:
    """Immutable quality descriptor for media files."""

    resolution: Resolution = Resolution.UNKNOWN
    resolution_raw: Optional[str] = None
    source: Optional[str] = None
    codec: Optional[str] = None
    hdr: bool = False
    audio: Optional[str] = None

    @property
    def score(self) -> int:
        """Calculate numeric quality score for comparison (higher = better)."""
        base = self.resolution.value * 1000

        # Source scores
        source_scores = {
            "remux": 80,
            "bluray": 60,
            "blu-ray": 60,
            "bdrip": 55,
            "brrip": 55,
            "web-dl": 40,
            "webdl": 40,
            "webrip": 35,
            "hdtv": 25,
            "hdrip": 25,
            "dvdrip": 15,
            "dvd": 10,
            "cam": 1,
            "ts": 2,
            "tc": 3,
            "scr": 5,
        }
        source_bonus = 0
        if self.source:
            source_bonus = source_scores.get(self.source.lower(), 0)

        # Codec scores
        codec_scores = {
            "av1": 15,
            "x265": 12,
            "hevc": 12,
            "h265": 12,
            "x264": 10,
            "h264": 10,
            "avc": 10,
            "xvid": 5,
            "divx": 5,
        }
        codec_bonus = 0
        if self.codec:
            codec_bonus = codec_scores.get(self.codec.lower(), 0)

        # HDR bonus
        hdr_bonus = 20 if self.hdr else 0

        return base + source_bonus + codec_bonus + hdr_bonus

    def __lt__(self, other: "Quality") -> bool:
        return self.score < other.score

    def __gt__(self, other: "Quality") -> bool:
        return self.score > other.score

    def __str__(self) -> str:
        parts = []
        if self.resolution_raw:
            parts.append(self.resolution_raw)
        elif self.resolution != Resolution.UNKNOWN:
            parts.append(self.resolution.name)
        if self.hdr:
            parts.append("HDR")
        if self.source:
            parts.append(self.source)
        if self.codec:
            parts.append(self.codec)
        return " ".join(parts) if parts else "Unknown"

    @classmethod
    def from_metadata(cls, metadata: MediaMetadata) -> Quality:
        """Create Quality from ffprobe MediaMetadata.

        Args:
            metadata: MediaMetadata from ffprobe

        Returns:
            Quality instance with data from metadata
        """
        # Detect resolution from dimensions
        resolution = cls._resolution_from_dimensions(metadata.width, metadata.height)

        # Detect HDR from color metadata
        hdr = cls._detect_hdr(metadata)

        return cls(
            resolution=resolution,
            resolution_raw=metadata.resolution_raw,
            source=None,  # Cannot detect source from metadata
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


class QualityParser:
    """Parse quality information from media filenames.

    Examples:
        >>> parser = QualityParser()
        >>> q = parser.parse("Movie.2020.1080p.BluRay.x264.mkv")
        >>> q.resolution.name
        'FHD'
        >>> q.source
        'BluRay'
        >>> q.codec
        'x264'

        >>> q = parser.parse("Show.S01E01.2160p.WEB-DL.HDR.HEVC.mkv")
        >>> q.resolution.name
        'UHD'
        >>> q.hdr
        True

        >>> q = parser.parse("Movie.720p.HDTV.mkv")
        >>> q.resolution.name
        'HD'
    """

    RESOLUTION_PATTERNS = [
        (r"\b2160p\b", Resolution.UHD, "2160p"),
        (r"\b4[kK]\b", Resolution.UHD, "4K"),
        (r"\bUHD\b", Resolution.UHD, "UHD"),
        (r"\b1080p\b", Resolution.FHD, "1080p"),
        (r"\b1080i\b", Resolution.FHD, "1080i"),
        (r"\b720p\b", Resolution.HD, "720p"),
        (r"\b480p\b", Resolution.SD, "480p"),
        (r"\b576p\b", Resolution.SD, "576p"),
        (r"\bDVD(?:Rip)?\b", Resolution.SD, "DVD"),
    ]

    SOURCE_PATTERNS = [
        (r"\b(REMUX|Remux)\b", "Remux"),
        (r"\b(BluRay|Blu-Ray|BDRip|BRRip)\b", "BluRay"),
        (r"\b(WEB-DL|WEBDL)\b", "WEB-DL"),
        (r"\b(WEBRip|WEB-Rip)\b", "WEBRip"),
        (r"\b(HDTV|HDRip|PDTV)\b", "HDTV"),
        (r"\b(DVDRip|DVD-Rip)\b", "DVDRip"),
        (r"\b(CAM|CAMRip|HDCAM)\b", "CAM"),
        (r"\b(TS|TELESYNC|HDTS)\b", "TS"),
    ]

    CODEC_PATTERNS = [
        (r"\b(x265|[Hh]\.?265|HEVC)\b", "x265"),
        (r"\b(x264|[Hh]\.?264|AVC)\b", "x264"),
        (r"\b(AV1)\b", "AV1"),
        (r"\b(XviD)\b", "XviD"),
        (r"\b(DivX)\b", "DivX"),
    ]

    HDR_PATTERNS = [
        r"\bHDR10\+?\b",
        r"\bDolby[\s.]?Vision\b",
        r"\bDV\b",
        r"\bHDR\b",
    ]

    AUDIO_PATTERNS = [
        (r"\b(DTS-HD[\s.]?MA)\b", "DTS-HD MA"),
        (r"\b(TrueHD[\s.]?Atmos|Atmos)\b", "Atmos"),
        (r"\b(TrueHD)\b", "TrueHD"),
        (r"\b(DTS-HD)\b", "DTS-HD"),
        (r"\b(DTS)\b", "DTS"),
        (r"\b(DD\+|DDP|E-?AC-?3)(?:\b|(?=\.))", "DD+"),
        (r"\b(DD5\.1|AC3|AC-3)\b", "DD"),
        (r"\b(AAC)\b", "AAC"),
    ]

    @classmethod
    def parse(cls, filename: str) -> Quality:
        """Parse quality information from a filename."""
        # Parse resolution
        resolution = Resolution.UNKNOWN
        resolution_raw = None
        for pattern, res, raw in cls.RESOLUTION_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                resolution = res
                resolution_raw = raw
                break

        # Parse source
        source = None
        for pattern, src in cls.SOURCE_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                source = src
                break

        # Parse codec
        codec = None
        for pattern, c in cls.CODEC_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                codec = c
                break

        # Parse HDR
        hdr = any(
            re.search(pattern, filename, re.IGNORECASE) for pattern in cls.HDR_PATTERNS
        )

        # Parse audio
        audio = None
        for pattern, aud in cls.AUDIO_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                audio = aud
                break

        return Quality(
            resolution=resolution,
            resolution_raw=resolution_raw,
            source=source,
            codec=codec,
            hdr=hdr,
            audio=audio,
        )
