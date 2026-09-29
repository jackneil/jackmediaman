"""Tests for quality parsing and scoring."""

import pytest
from jackmediaman.models.quality import Quality, QualityParser, Resolution


class TestQualityParser:
    """Tests for QualityParser."""

    def test_parse_4k_resolution(self):
        """Test parsing 4K resolution."""
        result = QualityParser.parse("Movie.2021.2160p.BluRay.x265.mkv")
        assert result.resolution == Resolution.UHD
        assert result.resolution_raw == "2160p"

    def test_parse_1080p_resolution(self):
        """Test parsing 1080p resolution."""
        result = QualityParser.parse("Show.S01E01.1080p.WEB-DL.mkv")
        assert result.resolution == Resolution.FHD
        assert result.resolution_raw == "1080p"

    def test_parse_720p_resolution(self):
        """Test parsing 720p resolution."""
        result = QualityParser.parse("Movie.720p.HDTV.mkv")
        assert result.resolution == Resolution.HD
        assert result.resolution_raw == "720p"

    def test_parse_source_bluray(self):
        """Test parsing BluRay source."""
        result = QualityParser.parse("Movie.1080p.BluRay.x264.mkv")
        assert result.source == "BluRay"

    def test_parse_source_webdl(self):
        """Test parsing WEB-DL source."""
        result = QualityParser.parse("Show.S01E01.1080p.WEB-DL.mkv")
        assert result.source == "WEB-DL"

    def test_parse_codec_x265(self):
        """Test parsing x265 codec."""
        result = QualityParser.parse("Movie.2160p.BluRay.x265.mkv")
        assert result.codec == "x265"

    def test_parse_codec_hevc(self):
        """Test parsing HEVC codec."""
        result = QualityParser.parse("Movie.2160p.BluRay.HEVC.mkv")
        assert result.codec == "x265"  # Normalized to x265

    def test_parse_hdr(self):
        """Test parsing HDR."""
        result = QualityParser.parse("Movie.2160p.BluRay.HDR.x265.mkv")
        assert result.hdr is True

    def test_parse_hdr10(self):
        """Test parsing HDR10."""
        result = QualityParser.parse("Movie.2160p.BluRay.HDR10.x265.mkv")
        assert result.hdr is True

    def test_parse_dolby_vision(self):
        """Test parsing Dolby Vision."""
        result = QualityParser.parse("Movie.2160p.BluRay.DolbyVision.x265.mkv")
        assert result.hdr is True

    def test_parse_no_quality_info(self):
        """Test parsing file with no quality info."""
        result = QualityParser.parse("random_movie.mkv")
        assert result.resolution == Resolution.UNKNOWN
        assert result.source is None
        assert result.codec is None


class TestQualityScore:
    """Tests for Quality scoring."""

    def test_4k_beats_1080p(self):
        """4K should score higher than 1080p."""
        q4k = Quality(resolution=Resolution.UHD)
        q1080p = Quality(resolution=Resolution.FHD)
        assert q4k.score > q1080p.score

    def test_1080p_beats_720p(self):
        """1080p should score higher than 720p."""
        q1080p = Quality(resolution=Resolution.FHD)
        q720p = Quality(resolution=Resolution.HD)
        assert q1080p.score > q720p.score

    def test_bluray_beats_webdl(self):
        """BluRay source should score higher than WEB-DL."""
        qbr = Quality(resolution=Resolution.FHD, source="BluRay")
        qweb = Quality(resolution=Resolution.FHD, source="WEB-DL")
        assert qbr.score > qweb.score

    def test_hdr_bonus(self):
        """HDR should add bonus points."""
        qhdr = Quality(resolution=Resolution.UHD, hdr=True)
        qnon = Quality(resolution=Resolution.UHD, hdr=False)
        assert qhdr.score > qnon.score

    def test_x265_beats_x264(self):
        """x265 should score higher than x264."""
        q265 = Quality(resolution=Resolution.FHD, codec="x265")
        q264 = Quality(resolution=Resolution.FHD, codec="x264")
        assert q265.score > q264.score

    def test_quality_comparison(self):
        """Test Quality comparison operators."""
        high = Quality(resolution=Resolution.UHD, source="BluRay", hdr=True)
        low = Quality(resolution=Resolution.HD, source="HDTV")
        assert high > low
        assert low < high


class TestQualityString:
    """Tests for Quality string representation."""

    def test_full_quality_string(self):
        """Test string representation with all info."""
        q = Quality(
            resolution=Resolution.UHD,
            resolution_raw="2160p",
            source="BluRay",
            codec="x265",
            hdr=True,
        )
        s = str(q)
        assert "2160p" in s
        assert "HDR" in s
        assert "BluRay" in s
        assert "x265" in s

    def test_minimal_quality_string(self):
        """Test string representation with minimal info."""
        q = Quality(resolution=Resolution.UNKNOWN)
        assert str(q) == "Unknown"
