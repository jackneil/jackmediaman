"""Tests for movie scanner."""

import pytest
from pathlib import Path

from jackmediaman.scanners.movies import MovieScanner, VIDEO_EXTENSIONS, EDITION_PATTERNS
from jackmediaman.models.media import Movie
from jackmediaman.models.quality import Resolution


class TestMovieScanner:
    """Tests for MovieScanner class."""

    @pytest.fixture
    def scanner(self):
        """Create a movie scanner."""
        return MovieScanner()

    def test_scan_finds_movies(self, scanner, tmp_media_library):
        """Scanner finds all movie files in library."""
        movies = list(scanner.scan(tmp_media_library / "Movies"))
        assert len(movies) >= 2  # At least Inception and The Matrix

    def test_scan_returns_movie_objects(self, scanner, tmp_media_library):
        """Scanner returns Movie objects."""
        movies = list(scanner.scan(tmp_media_library))
        assert all(isinstance(m, Movie) for m in movies)

    def test_scan_skips_non_video_files(self, scanner, tmp_path):
        """Scanner skips non-video files."""
        movie_dir = tmp_path / "Movies" / "Test Movie (2020)"
        movie_dir.mkdir(parents=True)
        (movie_dir / "Test.Movie.2020.txt").write_text("not a video")
        (movie_dir / "Test.Movie.2020.nfo").write_text("info file")
        (movie_dir / "Test.Movie.2020.srt").write_text("subtitles")

        movies = list(scanner.scan(tmp_path / "Movies"))
        assert len(movies) == 0

    def test_scan_includes_all_video_extensions(self, scanner, tmp_path):
        """Scanner includes all video extensions."""
        movie_dir = tmp_path / "Movies" / "Test Movie (2020)"
        movie_dir.mkdir(parents=True)

        for ext in [".mkv", ".mp4", ".avi"]:
            # Create files larger than 100MB threshold
            (movie_dir / f"Test.Movie.2020{ext}").write_bytes(b"0" * (100 * 1024 * 1024 + 1))

        movies = list(scanner.scan(tmp_path / "Movies"))
        assert len(movies) == 3

    def test_scan_nonexistent_directory(self, scanner, tmp_path):
        """Scanning nonexistent directory yields nothing."""
        movies = list(scanner.scan(tmp_path / "nonexistent"))
        assert len(movies) == 0

    def test_scan_extracts_title(self, scanner, tmp_media_library):
        """Scanner extracts movie title from folder."""
        movies = list(scanner.scan(tmp_media_library / "Movies"))
        titles = set(m.title for m in movies)
        assert "Inception" in titles

    def test_scan_extracts_year(self, scanner, tmp_media_library):
        """Scanner extracts year from folder."""
        movies = list(scanner.scan(tmp_media_library / "Movies"))
        years = set(m.year for m in movies if m.year)
        assert 2010 in years  # Inception

    def test_scan_parses_quality(self, scanner, tmp_media_library):
        """Scanner parses quality from filename."""
        movies = list(scanner.scan(tmp_media_library / "Movies"))
        # Find a 1080p movie
        movie_1080 = next((m for m in movies if "1080p" in m.filename), None)
        if movie_1080:
            assert movie_1080.quality.resolution == Resolution.FHD

    def test_scan_skips_sample_files(self, scanner, tmp_path):
        """Scanner skips sample files."""
        movie_dir = tmp_path / "Movies" / "Test Movie (2020)"
        movie_dir.mkdir(parents=True)

        # Create sample file (should be skipped)
        (movie_dir / "Sample-Test.Movie.2020.mkv").write_bytes(b"0" * (100 * 1024 * 1024 + 1))
        # Create regular file
        (movie_dir / "Test.Movie.2020.mkv").write_bytes(b"0" * (100 * 1024 * 1024 + 1))

        movies = list(scanner.scan(tmp_path / "Movies"))
        assert len(movies) == 1
        assert "sample" not in movies[0].filename.lower()

    def test_scan_skips_small_files(self, scanner, tmp_path):
        """Scanner skips files smaller than 100MB."""
        movie_dir = tmp_path / "Movies" / "Test Movie (2020)"
        movie_dir.mkdir(parents=True)

        # Create small file (should be skipped)
        (movie_dir / "Test.Movie.2020.mkv").write_bytes(b"0" * 1000)

        movies = list(scanner.scan(tmp_path / "Movies"))
        assert len(movies) == 0


class TestMovieScannerFolderParsing:
    """Tests for movie folder parsing."""

    @pytest.fixture
    def scanner(self):
        return MovieScanner()

    def test_parse_standard_format(self, scanner):
        """Parses 'Title (Year)' format."""
        title, year = scanner._parse_movie_folder("Inception (2010)")
        assert title == "Inception"
        assert year == 2010

    def test_parse_with_spaces(self, scanner):
        """Parses title with spaces."""
        title, year = scanner._parse_movie_folder("The Dark Knight (2008)")
        assert title == "The Dark Knight"
        assert year == 2008

    def test_parse_with_dots(self, scanner):
        """Parses title with dots."""
        title, year = scanner._parse_movie_folder("The.Dark.Knight.2008")
        assert title == "The Dark Knight"
        assert year == 2008

    def test_parse_no_year(self, scanner):
        """Parses folder without year."""
        title, year = scanner._parse_movie_folder("Some Movie")
        assert title == "Some Movie"
        assert year is None

    def test_parse_year_in_brackets(self, scanner):
        """Parses year in square brackets."""
        title, year = scanner._parse_movie_folder("Inception [2010]")
        assert title == "Inception"
        assert year == 2010

    def test_parse_year_in_braces(self, scanner):
        """Parses year in curly braces."""
        title, year = scanner._parse_movie_folder("Inception {2010}")
        assert title == "Inception"
        assert year == 2010

    def test_parse_year_no_brackets(self, scanner):
        """Parses year without any brackets."""
        title, year = scanner._parse_movie_folder("Inception 2010")
        assert title == "Inception"
        assert year == 2010

    def test_parse_with_quality_tags(self, scanner):
        """Parses folder with quality tags."""
        title, year = scanner._parse_movie_folder("Inception (2010) 1080p BluRay")
        assert title == "Inception"
        assert year == 2010

    def test_parse_invalid_year(self, scanner):
        """Ignores invalid years."""
        # Year 1234 is before movies existed
        title, year = scanner._parse_movie_folder("Movie 1234")
        assert title == "Movie 1234"
        assert year is None


class TestMovieScannerEditionDetection:
    """Tests for edition detection."""

    @pytest.fixture
    def scanner(self):
        return MovieScanner()

    def test_detect_directors_cut(self, scanner):
        """Detects director's cut."""
        assert scanner._detect_edition("Movie.Directors.Cut.mkv") == "directors_cut"
        assert scanner._detect_edition("Movie.Director's.Cut.mkv") == "directors_cut"
        assert scanner._detect_edition("Movie.DC.mkv") == "directors_cut"

    def test_detect_extended(self, scanner):
        """Detects extended edition."""
        assert scanner._detect_edition("Movie.Extended.mkv") == "extended"
        assert scanner._detect_edition("Movie.Extended.Cut.mkv") == "extended"
        assert scanner._detect_edition("Movie.Extended.Edition.mkv") == "extended"

    def test_detect_unrated(self, scanner):
        """Detects unrated version."""
        assert scanner._detect_edition("Movie.Unrated.mkv") == "unrated"
        assert scanner._detect_edition("Movie.Uncensored.mkv") == "unrated"

    def test_detect_theatrical(self, scanner):
        """Detects theatrical cut."""
        assert scanner._detect_edition("Movie.Theatrical.mkv") == "theatrical"
        assert scanner._detect_edition("Movie.Theatrical.Cut.mkv") == "theatrical"

    def test_detect_remastered(self, scanner):
        """Detects remastered version."""
        assert scanner._detect_edition("Movie.Remastered.mkv") == "remastered"
        assert scanner._detect_edition("Movie.Restored.mkv") == "remastered"

    def test_detect_imax(self, scanner):
        """Detects IMAX version."""
        assert scanner._detect_edition("Movie.IMAX.mkv") == "imax"

    def test_detect_3d(self, scanner):
        """Detects 3D version."""
        assert scanner._detect_edition("Movie.3D.mkv") == "3d"

    def test_detect_criterion(self, scanner):
        """Detects Criterion edition."""
        assert scanner._detect_edition("Movie.Criterion.mkv") == "criterion"

    def test_no_edition(self, scanner):
        """Returns None for regular files."""
        assert scanner._detect_edition("Movie.2020.1080p.BluRay.mkv") is None


class TestMovieScannerTitleCleaning:
    """Tests for title cleaning."""

    @pytest.fixture
    def scanner(self):
        return MovieScanner()

    def test_clean_quality_tags(self, scanner):
        """Removes quality tags from title."""
        assert scanner._clean_title("Movie 1080p BluRay") == "Movie"

    def test_clean_codec_tags(self, scanner):
        """Removes codec tags from title."""
        assert scanner._clean_title("Movie x264") == "Movie"
        assert scanner._clean_title("Movie x265 HEVC") == "Movie"

    def test_clean_release_tags(self, scanner):
        """Removes release tags from title."""
        assert scanner._clean_title("Movie PROPER") == "Movie"
        assert scanner._clean_title("Movie REPACK") == "Movie"

    def test_normalizes_whitespace(self, scanner):
        """Normalizes multiple spaces."""
        assert scanner._clean_title("Movie   Title") == "Movie Title"

    def test_strips_punctuation(self, scanner):
        """Strips trailing/leading punctuation."""
        assert scanner._clean_title("[Movie Title]") == "Movie Title"
        assert scanner._clean_title("Movie Title.") == "Movie Title"


class TestMovieScannerSymlinks:
    """Tests for symlink detection."""

    @pytest.fixture
    def scanner(self):
        return MovieScanner()

    def test_symlink_detection(self, scanner, tmp_path):
        """Scanner detects symlinks."""
        movies_dir = tmp_path / "Movies" / "Test Movie (2020)"
        movies_dir.mkdir(parents=True)

        # Create target file
        target = tmp_path / "torrents" / "movie.mkv"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"0" * (100 * 1024 * 1024 + 1))

        # Create symlink
        symlink = movies_dir / "Test.Movie.2020.mkv"
        symlink.symlink_to(target)

        movies = list(scanner.scan(tmp_path / "Movies"))
        assert len(movies) == 1
        assert movies[0].is_symlink is True
        assert movies[0].symlink_target is not None


class TestVideoExtensions:
    """Tests for VIDEO_EXTENSIONS constant."""

    def test_common_extensions_included(self):
        """Common video extensions are included."""
        assert ".mkv" in VIDEO_EXTENSIONS
        assert ".mp4" in VIDEO_EXTENSIONS
        assert ".avi" in VIDEO_EXTENSIONS
        assert ".m4v" in VIDEO_EXTENSIONS


class TestEditionPatterns:
    """Tests for EDITION_PATTERNS constant."""

    def test_common_editions_defined(self):
        """Common editions are defined."""
        assert "directors_cut" in EDITION_PATTERNS
        assert "extended" in EDITION_PATTERNS
        assert "theatrical" in EDITION_PATTERNS
        assert "remastered" in EDITION_PATTERNS
