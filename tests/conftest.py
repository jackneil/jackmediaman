"""Shared fixtures for JackMediaMan tests."""

import pytest
from pathlib import Path
from datetime import datetime
from typing import Generator
from unittest.mock import MagicMock, patch

from jackmediaman.models.media import Movie, Episode
from jackmediaman.models.quality import Quality, Resolution
from jackmediaman.models.duplicates import DuplicateGroup


# ============================================================
# Path and Filesystem Fixtures
# ============================================================

@pytest.fixture
def tmp_media_library(tmp_path: Path) -> Path:
    """Create a temporary media library structure."""
    # TV structure
    tv_dir = tmp_path / "TV Shows"
    show_dir = tv_dir / "Breaking Bad" / "Season 1"
    show_dir.mkdir(parents=True)

    # Movie structure with actual files > 100MB
    movies_dir = tmp_path / "Movies"
    movie_dir = movies_dir / "Inception (2010)"
    movie_dir.mkdir(parents=True)
    (movie_dir / "Inception.2010.1080p.BluRay.mkv").write_bytes(b"0" * (100 * 1024 * 1024 + 1))

    matrix_dir = movies_dir / "The Matrix (1999)"
    matrix_dir.mkdir(parents=True)
    (matrix_dir / "The.Matrix.1999.720p.BluRay.mkv").write_bytes(b"0" * (100 * 1024 * 1024 + 1))

    # Trash structure
    trash_dir = tmp_path / "trash"
    trash_dir.mkdir(parents=True)

    return tmp_path


@pytest.fixture
def tmp_tv_library(tmp_path: Path) -> Path:
    """Create a temporary TV library with sample episodes."""
    tv_dir = tmp_path / "TV Shows"

    # Show 1: Breaking Bad
    bb_s1 = tv_dir / "Breaking Bad" / "Season 1"
    bb_s1.mkdir(parents=True)
    (bb_s1 / "Breaking.Bad.S01E01.720p.BluRay.x264.mkv").write_bytes(b"0" * 500)
    (bb_s1 / "Breaking.Bad.S01E01.1080p.WEB-DL.x265.mkv").write_bytes(b"0" * 600)
    (bb_s1 / "Breaking.Bad.S01E02.720p.HDTV.mkv").write_bytes(b"0" * 400)

    # Show 2: The Office
    office_s1 = tv_dir / "The Office" / "Season 1"
    office_s1.mkdir(parents=True)
    (office_s1 / "The.Office.S01E01.1080p.WEB-DL.mkv").write_bytes(b"0" * 300)

    return tv_dir


@pytest.fixture
def tmp_movie_library(tmp_path: Path) -> Path:
    """Create a temporary movie library with sample movies."""
    movies_dir = tmp_path / "Movies"

    # Movie with duplicates
    inception_dir = movies_dir / "Inception (2010)"
    inception_dir.mkdir(parents=True)
    (inception_dir / "Inception.2010.1080p.BluRay.x264.mkv").write_bytes(b"0" * 800)
    (inception_dir / "Inception.2010.720p.WEB-DL.mkv").write_bytes(b"0" * 500)

    # Single movie
    matrix_dir = movies_dir / "The Matrix (1999)"
    matrix_dir.mkdir(parents=True)
    (matrix_dir / "The.Matrix.1999.1080p.BluRay.x264.mkv").write_bytes(b"0" * 700)

    return movies_dir


@pytest.fixture
def tmp_torrent_dir(tmp_path: Path) -> Path:
    """Create a temporary torrent directory."""
    torrent_dir = tmp_path / "torrents" / "completed"
    torrent_dir.mkdir(parents=True)
    return torrent_dir


@pytest.fixture
def tmp_trash_dir(tmp_path: Path) -> Path:
    """Create a temporary trash directory."""
    trash_dir = tmp_path / "trash"
    trash_dir.mkdir(parents=True)
    return trash_dir


# ============================================================
# Quality Fixtures
# ============================================================

@pytest.fixture
def quality_4k_bluray() -> Quality:
    """4K BluRay quality with HDR."""
    return Quality(
        resolution=Resolution.UHD,
        resolution_raw="2160p",
        source="BluRay",
        codec="x265",
        hdr=True,
    )


@pytest.fixture
def quality_1080p_webdl() -> Quality:
    """1080p WEB-DL quality."""
    return Quality(
        resolution=Resolution.FHD,
        resolution_raw="1080p",
        source="WEB-DL",
        codec="x264",
        hdr=False,
    )


@pytest.fixture
def quality_720p_hdtv() -> Quality:
    """720p HDTV quality."""
    return Quality(
        resolution=Resolution.HD,
        resolution_raw="720p",
        source="HDTV",
        codec="x264",
        hdr=False,
    )


@pytest.fixture
def quality_unknown() -> Quality:
    """Unknown quality."""
    return Quality(resolution=Resolution.UNKNOWN)


# ============================================================
# Model Fixtures
# ============================================================

@pytest.fixture
def sample_movie(tmp_path: Path, quality_1080p_webdl: Quality) -> Movie:
    """Create a sample Movie object."""
    movie_path = tmp_path / "Movies" / "Inception (2010)" / "Inception.2010.1080p.mkv"
    movie_path.parent.mkdir(parents=True, exist_ok=True)
    movie_path.write_bytes(b"0" * 200)

    return Movie(
        path=movie_path,
        filename=movie_path.name,
        size_bytes=200,
        quality=quality_1080p_webdl,
        created_at=datetime.now(),
        title="Inception",
        year=2010,
    )


@pytest.fixture
def sample_episode(tmp_path: Path, quality_1080p_webdl: Quality) -> Episode:
    """Create a sample Episode object."""
    ep_path = tmp_path / "TV Shows" / "Breaking Bad" / "Season 1" / "Breaking.Bad.S01E01.1080p.mkv"
    ep_path.parent.mkdir(parents=True, exist_ok=True)
    ep_path.write_bytes(b"0" * 150)

    return Episode(
        path=ep_path,
        filename=ep_path.name,
        size_bytes=150,
        quality=quality_1080p_webdl,
        created_at=datetime.now(),
        series_name="Breaking Bad",
        season_number=1,
        episode_numbers=[1],
    )


@pytest.fixture
def movie_duplicate_group(
    tmp_path: Path,
    quality_4k_bluray: Quality,
    quality_1080p_webdl: Quality,
    quality_720p_hdtv: Quality,
) -> DuplicateGroup:
    """Create a DuplicateGroup with three movie duplicates of varying quality."""
    movies_dir = tmp_path / "Movies" / "Inception (2010)"
    movies_dir.mkdir(parents=True, exist_ok=True)

    # Create files
    path_4k = movies_dir / "Inception.2010.2160p.BluRay.mkv"
    path_1080 = movies_dir / "Inception.2010.1080p.WEB-DL.mkv"
    path_720 = movies_dir / "Inception.2010.720p.HDTV.mkv"

    path_4k.write_bytes(b"0" * 400)
    path_1080.write_bytes(b"0" * 200)
    path_720.write_bytes(b"0" * 100)

    movies = [
        Movie(
            path=path_4k,
            filename=path_4k.name,
            size_bytes=400,
            quality=quality_4k_bluray,
            title="Inception",
            year=2010,
        ),
        Movie(
            path=path_1080,
            filename=path_1080.name,
            size_bytes=200,
            quality=quality_1080p_webdl,
            title="Inception",
            year=2010,
        ),
        Movie(
            path=path_720,
            filename=path_720.name,
            size_bytes=100,
            quality=quality_720p_hdtv,
            title="Inception",
            year=2010,
        ),
    ]

    group = DuplicateGroup(identity_key="movie:title:inception:2010")
    for movie in movies:
        group.add(movie)
    group.sort_by_quality()
    return group


# ============================================================
# Configuration Fixtures
# ============================================================

@pytest.fixture
def mock_settings(tmp_path: Path):
    """Create mock settings with temporary directories."""
    from jackmediaman.core.config import Settings

    return Settings(
        tv_dir=tmp_path / "TV Shows",
        movies_dir=tmp_path / "Movies",
        trash_dir=tmp_path / "trash",
        torrent_dir=tmp_path / "torrents" / "completed",
        cache_dir=tmp_path / "cache",
        tmdb_api_key=None,
        deluge_host="127.0.0.1",
        deluge_port=58846,
        deluge_username="",
        deluge_password="",
    )


@pytest.fixture
def patch_settings(mock_settings) -> Generator:
    """Patch get_settings to return mock settings."""
    with patch("jackmediaman.core.config.get_settings", return_value=mock_settings):
        yield mock_settings


# ============================================================
# Mock External Services
# ============================================================

@pytest.fixture
def mock_tmdb_client() -> MagicMock:
    """Create a mock TMDb client."""
    client = MagicMock()
    client.api_key = "test_api_key"
    client.search_movie.return_value = 27205  # Inception TMDb ID
    client.search_tv.return_value = 1396  # Breaking Bad TMDb ID
    client.get_episode_title.return_value = "Pilot"
    client.get_movie_details.return_value = {"title": "Inception", "year": "2010"}
    return client


@pytest.fixture
def mock_httpx_response() -> MagicMock:
    """Create a mock httpx response for TMDb API."""
    response = MagicMock()
    response.json.return_value = {
        "results": [{"id": 27205, "title": "Inception"}]
    }
    response.raise_for_status = MagicMock()
    return response


@pytest.fixture
def mock_deluge_rpc() -> MagicMock:
    """Create a mock Deluge RPC client."""
    rpc = MagicMock()
    rpc.connect = MagicMock()
    rpc.disconnect = MagicMock()
    rpc.call.return_value = {}  # Empty torrent list
    return rpc


# ============================================================
# Pytest Configuration
# ============================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "requires_network: marks tests that require network access")
