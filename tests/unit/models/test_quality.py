"""Tests for quality parsing and scoring."""

import pytest
from jackmediaman.models.quality import Quality, QualityParser, Resolution


class TestResolution:
    """Tests for Resolution enum."""

    def test_resolution_ordering(self):
        """Resolution values are ordered correctly."""
        assert Resolution.UHD > Resolution.FHD
        assert Resolution.FHD > Resolution.HD
        assert Resolution.HD > Resolution.SD
        assert Resolution.SD > Resolution.UNKNOWN

    def test_resolution_values(self):
        """Resolution has expected integer values."""
        assert Resolution.UNKNOWN.value == 0
        assert Resolution.SD.value == 1
        assert Resolution.HD.value == 2
        assert Resolution.FHD.value == 3
        assert Resolution.UHD.value == 4


class TestQualityParser:
    """Tests for QualityParser."""

    def test_parse_4k_resolution(self):
        """Test parsing 4K resolution."""
        result = QualityParser.parse("Movie.2021.2160p.BluRay.x265.mkv")
        assert result.resolution == Resolution.UHD
        assert result.resolution_raw == "2160p"

    def test_parse_4k_alternative(self):
        """Test parsing 4K notation."""
        result = QualityParser.parse("Movie.2021.4K.BluRay.x265.mkv")
        assert result.resolution == Resolution.UHD
        assert result.resolution_raw == "4K"

    def test_parse_uhd_notation(self):
        """Test parsing UHD notation."""
        result = QualityParser.parse("Movie.2021.UHD.BluRay.x265.mkv")
        assert result.resolution == Resolution.UHD

    def test_parse_1080p_resolution(self):
        """Test parsing 1080p resolution."""
        result = QualityParser.parse("Show.S01E01.1080p.WEB-DL.mkv")
        assert result.resolution == Resolution.FHD
        assert result.resolution_raw == "1080p"

    def test_parse_1080i_resolution(self):
        """Test parsing 1080i (interlaced)."""
        result = QualityParser.parse("Show.S01E01.1080i.HDTV.mkv")
        assert result.resolution == Resolution.FHD
        assert result.resolution_raw == "1080i"

    def test_parse_720p_resolution(self):
        """Test parsing 720p resolution."""
        result = QualityParser.parse("Movie.720p.HDTV.mkv")
        assert result.resolution == Resolution.HD
        assert result.resolution_raw == "720p"

    def test_parse_480p_resolution(self):
        """Test parsing 480p resolution."""
        result = QualityParser.parse("Movie.480p.DVDRip.mkv")
        assert result.resolution == Resolution.SD
        assert result.resolution_raw == "480p"

    def test_parse_source_bluray(self):
        """Test parsing BluRay source."""
        result = QualityParser.parse("Movie.1080p.BluRay.x264.mkv")
        assert result.source == "BluRay"

    def test_parse_source_bluray_alternative(self):
        """Test parsing Blu-Ray notation."""
        result = QualityParser.parse("Movie.1080p.Blu-Ray.x264.mkv")
        assert result.source == "BluRay"

    def test_parse_source_webdl(self):
        """Test parsing WEB-DL source."""
        result = QualityParser.parse("Show.S01E01.1080p.WEB-DL.mkv")
        assert result.source == "WEB-DL"

    def test_parse_source_webrip(self):
        """Test parsing WEBRip source."""
        result = QualityParser.parse("Show.S01E01.1080p.WEBRip.mkv")
        assert result.source == "WEBRip"

    def test_parse_source_hdtv(self):
        """Test parsing HDTV source."""
        result = QualityParser.parse("Show.S01E01.720p.HDTV.mkv")
        assert result.source == "HDTV"

    def test_parse_source_remux(self):
        """Test parsing Remux source."""
        result = QualityParser.parse("Movie.1080p.REMUX.x264.mkv")
        assert result.source == "Remux"

    def test_parse_codec_x265(self):
        """Test parsing x265 codec."""
        result = QualityParser.parse("Movie.2160p.BluRay.x265.mkv")
        assert result.codec == "x265"

    def test_parse_codec_hevc(self):
        """Test parsing HEVC codec."""
        result = QualityParser.parse("Movie.2160p.BluRay.HEVC.mkv")
        assert result.codec == "x265"  # Normalized to x265

    def test_parse_codec_h265(self):
        """Test parsing H.265 codec."""
        result = QualityParser.parse("Movie.2160p.BluRay.H.265.mkv")
        assert result.codec == "x265"

    def test_parse_codec_x264(self):
        """Test parsing x264 codec."""
        result = QualityParser.parse("Movie.1080p.BluRay.x264.mkv")
        assert result.codec == "x264"

    def test_parse_codec_av1(self):
        """Test parsing AV1 codec."""
        result = QualityParser.parse("Movie.1080p.WEB-DL.AV1.mkv")
        assert result.codec == "AV1"

    def test_parse_hdr(self):
        """Test parsing HDR."""
        result = QualityParser.parse("Movie.2160p.BluRay.HDR.x265.mkv")
        assert result.hdr is True

    def test_parse_hdr10(self):
        """Test parsing HDR10."""
        result = QualityParser.parse("Movie.2160p.BluRay.HDR10.x265.mkv")
        assert result.hdr is True

    def test_parse_hdr10_plus(self):
        """Test parsing HDR10+."""
        result = QualityParser.parse("Movie.2160p.BluRay.HDR10+.x265.mkv")
        assert result.hdr is True

    def test_parse_dolby_vision(self):
        """Test parsing Dolby Vision."""
        result = QualityParser.parse("Movie.2160p.BluRay.DolbyVision.x265.mkv")
        assert result.hdr is True

    def test_parse_dv_notation(self):
        """Test parsing DV (Dolby Vision) notation."""
        result = QualityParser.parse("Movie.2160p.BluRay.DV.x265.mkv")
        assert result.hdr is True

    def test_parse_audio_atmos(self):
        """Test parsing Atmos audio."""
        result = QualityParser.parse("Movie.2160p.BluRay.TrueHD.Atmos.mkv")
        assert result.audio == "Atmos"

    def test_parse_audio_dts_hd_ma(self):
        """Test parsing DTS-HD MA audio."""
        result = QualityParser.parse("Movie.1080p.BluRay.DTS-HD.MA.mkv")
        assert result.audio == "DTS-HD MA"

    def test_parse_audio_ddplus(self):
        """Test parsing DD+ audio."""
        result = QualityParser.parse("Movie.1080p.WEB-DL.DD+.mkv")
        assert result.audio == "DD+"

    def test_parse_no_quality_info(self):
        """Test parsing file with no quality info."""
        result = QualityParser.parse("random_movie.mkv")
        assert result.resolution == Resolution.UNKNOWN
        assert result.source is None
        assert result.codec is None
        assert result.hdr is False

    def test_parse_case_insensitive(self):
        """Test parsing is case insensitive."""
        result = QualityParser.parse("movie.1080P.bluray.X265.mkv")
        assert result.resolution == Resolution.FHD
        assert result.source == "BluRay"
        assert result.codec == "x265"


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

    def test_720p_beats_sd(self):
        """720p should score higher than SD."""
        q720p = Quality(resolution=Resolution.HD)
        qsd = Quality(resolution=Resolution.SD)
        assert q720p.score > qsd.score

    def test_bluray_beats_webdl(self):
        """BluRay source should score higher than WEB-DL."""
        qbr = Quality(resolution=Resolution.FHD, source="BluRay")
        qweb = Quality(resolution=Resolution.FHD, source="WEB-DL")
        assert qbr.score > qweb.score

    def test_webdl_beats_hdtv(self):
        """WEB-DL should score higher than HDTV."""
        qweb = Quality(resolution=Resolution.FHD, source="WEB-DL")
        qhdtv = Quality(resolution=Resolution.FHD, source="HDTV")
        assert qweb.score > qhdtv.score

    def test_remux_beats_bluray(self):
        """Remux should score higher than BluRay."""
        qremux = Quality(resolution=Resolution.FHD, source="Remux")
        qbr = Quality(resolution=Resolution.FHD, source="BluRay")
        assert qremux.score > qbr.score

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

    def test_av1_beats_x265(self):
        """AV1 should score higher than x265."""
        qav1 = Quality(resolution=Resolution.FHD, codec="AV1")
        q265 = Quality(resolution=Resolution.FHD, codec="x265")
        assert qav1.score > q265.score

    def test_resolution_dominates_other_factors(self):
        """Higher resolution should beat lower resolution even with better source."""
        q4k_hdtv = Quality(resolution=Resolution.UHD, source="HDTV")
        q1080p_remux = Quality(resolution=Resolution.FHD, source="Remux")
        assert q4k_hdtv.score > q1080p_remux.score


class TestQualityComparison:
    """Tests for Quality comparison operators."""

    def test_quality_less_than(self):
        """Test < operator."""
        low = Quality(resolution=Resolution.HD)
        high = Quality(resolution=Resolution.UHD)
        assert low < high

    def test_quality_greater_than(self):
        """Test > operator."""
        low = Quality(resolution=Resolution.HD)
        high = Quality(resolution=Resolution.UHD)
        assert high > low

    def test_quality_comparison_same_score(self):
        """Equal scores don't satisfy < or >."""
        q1 = Quality(resolution=Resolution.FHD)
        q2 = Quality(resolution=Resolution.FHD)
        assert not (q1 < q2)
        assert not (q1 > q2)


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

    def test_resolution_only_string(self):
        """Test string with only resolution."""
        q = Quality(resolution=Resolution.FHD, resolution_raw="1080p")
        assert str(q) == "1080p"

    def test_resolution_name_fallback(self):
        """Test resolution name used when no raw value."""
        q = Quality(resolution=Resolution.FHD)
        assert "FHD" in str(q)
