"""OpenSubtitles service for automatic subtitle downloads.

Supports both OpenSubtitles.org (XML-RPC) and OpenSubtitles.com (REST API).
"""

import base64
import gzip
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Protocol
from xmlrpc.client import ServerProxy

import httpx

from jackmediaman.core.config import get_settings, save_setting
from jackmediaman.core.exceptions import OpenSubtitlesError, OpenSubtitlesQuotaError


# Video file extensions to process
VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".ts", ".mov"}

# Text OpenSubtitles.org serves non-VIP accounts instead of the real subtitle
PLACEHOLDER_MARKERS = ("osdb.link/vip", "opensubtitles.org vip")

# Only files this small are read when checking for placeholders on disk
PLACEHOLDER_MAX_BYTES = 64 * 1024

_SRT_TIMING = re.compile(
    r"(\d+):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d+):(\d{2}):(\d{2})[,.](\d{1,3})"
)


def is_placeholder_subtitle(text: str) -> bool:
    """Return True if subtitle text is an ad/placeholder rather than a real subtitle.

    Placeholders are: empty text, anything carrying the OpenSubtitles VIP ad,
    or at most 2 cues spanning an hour or more with under 300 chars of text.

    >>> ad = (
    ...     "1\\n00:00:00,001 --> 04:00:00,003\\n"
    ...     "Become OpenSubtitles.org VIP Member\\n"
    ...     "to get subtitles -> osdb.link/vip\\n"
    ... )
    >>> len(ad.encode())
    102
    >>> is_placeholder_subtitle(ad)
    True
    >>> is_placeholder_subtitle("1\\n00:00:00,001 --> 04:00:00,003\\nSome other ad\\n")
    True
    >>> real = (
    ...     "1\\n00:00:01,000 --> 00:00:03,000\\nHello there.\\n\\n"
    ...     "2\\n00:00:04,000 --> 00:00:06,000\\nGeneral Kenobi.\\n\\n"
    ...     "3\\n00:42:10,500 --> 00:42:12,000\\nYou are a bold one.\\n"
    ... )
    >>> is_placeholder_subtitle(real)
    False
    >>> is_placeholder_subtitle("1\\n00:00:01,000 --> 00:00:03,000\\nHi\\n")
    False
    >>> is_placeholder_subtitle("")
    True
    >>> is_placeholder_subtitle("  \\n\\t ")
    True
    """
    if not text or not text.strip():
        return True

    lower = text.lower()
    if any(marker in lower for marker in PLACEHOLDER_MARKERS):
        return True

    cues = _SRT_TIMING.findall(text)
    if not cues or len(cues) > 2 or len(text.strip()) >= 300:
        return False

    def seconds(h: str, m: str, s: str, ms: str) -> float:
        return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

    start = seconds(*cues[0][:4])
    end = seconds(*cues[-1][4:])
    return end - start >= 3600


def is_placeholder_subtitle_file(path: Path) -> bool:
    """Return True if a subtitle file on disk is a placeholder (see is_placeholder_subtitle).

    Files larger than PLACEHOLDER_MAX_BYTES are never read and count as real.

    >>> import tempfile
    >>> d = Path(tempfile.mkdtemp())
    >>> ad = d / "a.en.srt"
    >>> _ = ad.write_text("1\\n00:00:00,001 --> 04:00:00,003\\nosdb.link/vip\\n")
    >>> is_placeholder_subtitle_file(ad)
    True
    >>> real = d / "b.en.srt"
    >>> _ = real.write_text("1\\n00:00:01,000 --> 00:00:03,000\\nHello\\n")
    >>> is_placeholder_subtitle_file(real)
    False
    >>> is_placeholder_subtitle_file(d / "missing.srt")
    False
    >>> import shutil; shutil.rmtree(d)
    """
    try:
        if path.stat().st_size > PLACEHOLDER_MAX_BYTES:
            return False
        return is_placeholder_subtitle(path.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return False


def subtitle_exists(path: Path) -> bool:
    """Return True if a real (non-placeholder) subtitle file exists at path.

    >>> import tempfile
    >>> d = Path(tempfile.mkdtemp())
    >>> subtitle_exists(d / "v.en.srt")
    False
    >>> _ = (d / "v.en.srt").write_text("1\\n00:00:00,001 --> 04:00:00,003\\nosdb.link/vip\\n")
    >>> subtitle_exists(d / "v.en.srt")
    False
    >>> _ = (d / "v.en.srt").write_text("1\\n00:00:01,000 --> 00:00:03,000\\nHello\\n")
    >>> subtitle_exists(d / "v.en.srt")
    True
    >>> import shutil; shutil.rmtree(d)
    """
    return path.exists() and not is_placeholder_subtitle_file(path)


def find_placeholder_subtitles(directory: Path) -> List[Path]:
    """Find placeholder .srt files under a directory.

    >>> import tempfile
    >>> d = Path(tempfile.mkdtemp())
    >>> (d / "Show").mkdir()
    >>> _ = (d / "Show" / "ep.en.srt").write_text("osdb.link/vip")
    >>> _ = (d / "Show" / "ep2.en.srt").write_text("1\\n00:00:01,000 --> 00:00:02,000\\nHi\\n")
    >>> _ = (d / "Show" / "ep.mkv").write_text("not a subtitle")
    >>> [p.name for p in find_placeholder_subtitles(d)]
    ['ep.en.srt']
    >>> find_placeholder_subtitles(d / "nope")
    []
    >>> import shutil; shutil.rmtree(d)
    """
    if not directory.exists():
        return []
    return sorted(
        p
        for p in directory.rglob("*")
        if p.suffix.lower() == ".srt" and p.is_file() and is_placeholder_subtitle_file(p)
    )

# Language code mappings (ISO 639-1 <-> ISO 639-2)
# OpenSubtitles.org uses 3-letter codes, .com uses 2-letter codes
LANG_2_TO_3 = {
    "en": "eng", "es": "spa", "fr": "fre", "de": "ger", "it": "ita",
    "pt": "por", "ru": "rus", "ja": "jpn", "zh": "chi", "ko": "kor",
    "ar": "ara", "nl": "dut", "pl": "pol", "sv": "swe", "da": "dan",
    "fi": "fin", "no": "nor", "cs": "cze", "el": "ell", "he": "heb",
    "hu": "hun", "ro": "rum", "tr": "tur", "vi": "vie", "th": "tha",
    "id": "ind", "ms": "may", "hi": "hin", "bn": "ben", "uk": "ukr",
    "bg": "bul", "hr": "hrv", "sk": "slo", "sl": "slv", "et": "est",
    "lv": "lav", "lt": "lit", "sr": "srp", "ca": "cat", "gl": "glg",
    "eu": "baq", "is": "ice", "fa": "per", "pb": "pob",  # Portuguese (BR)
}
LANG_3_TO_2 = {v: k for k, v in LANG_2_TO_3.items()}


def normalize_lang_codes(languages: list[str]) -> set[str]:
    """Expand language codes to include both 2-letter and 3-letter forms.

    This ensures matching works regardless of which format the API returns.
    """
    result = set()
    for lang in languages:
        lang_lower = lang.lower()
        result.add(lang_lower)
        # Add the alternative form
        if lang_lower in LANG_2_TO_3:
            result.add(LANG_2_TO_3[lang_lower])
        elif lang_lower in LANG_3_TO_2:
            result.add(LANG_3_TO_2[lang_lower])
    return result


@dataclass
class SubtitleResult:
    """Result of a subtitle search/download operation."""

    video_path: Path
    subtitle_path: Optional[Path] = None
    language: str = ""
    success: bool = False
    error: Optional[str] = None
    skipped: bool = False
    skip_reason: Optional[str] = None
    provider: str = ""  # Which provider found it: "com" or "org"


class OpenSubtitlesClientProtocol(Protocol):
    """Protocol for OpenSubtitles clients."""

    def login(self) -> bool: ...
    def search(self, path: Path, languages: List[str]) -> List[dict]: ...
    def download(self, subtitle_id: str | int) -> Optional[str]: ...


def compute_hash(path: Path) -> str:
    """Compute OpenSubtitles hash for a video file.

    The OpenSubtitles hash is computed from:
    - First 64KB of file
    - Last 64KB of file
    - File size

    Args:
        path: Path to video file

    Returns:
        Hash string in hexadecimal format
    """
    file_size = path.stat().st_size
    hash_value = file_size

    with open(path, "rb") as f:
        # First 64KB
        for _ in range(65536 // 8):
            buffer = f.read(8)
            if len(buffer) == 8:
                hash_value += int.from_bytes(buffer, byteorder="little")
                hash_value &= 0xFFFFFFFFFFFFFFFF

        # Last 64KB
        f.seek(max(0, file_size - 65536), 0)
        for _ in range(65536 // 8):
            buffer = f.read(8)
            if len(buffer) == 8:
                hash_value += int.from_bytes(buffer, byteorder="little")
                hash_value &= 0xFFFFFFFFFFFFFFFF

    return format(hash_value, "016x")


class OpenSubtitlesOrgClient:
    """Client for OpenSubtitles.org XML-RPC API."""

    BASE_URL = "https://api.opensubtitles.org/xml-rpc"
    USER_AGENT = "JackMediaMan v0.3.0"
    RATE_LIMIT_DELAY = 1.0

    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        settings = get_settings()
        self.username = username or settings.opensubtitles_org_username or ""
        self.password = password or settings.opensubtitles_org_password or ""
        self.server = ServerProxy(self.BASE_URL)
        self.token: Optional[str] = None
        self.last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def login(self) -> bool:
        """Login to get session token."""
        if not self.username or not self.password:
            return False

        self._rate_limit()
        try:
            result = self.server.LogIn(
                self.username, self.password, "en", self.USER_AGENT
            )
            if result.get("status", "").startswith("200"):
                self.token = result.get("token")
                return True
            return False
        except Exception:
            return False

    def validate_credentials(self) -> bool:
        """Validate credentials by attempting login."""
        return self.login()

    def _extract_search_query(self, path: Path) -> str:
        """Extract search query from filename.

        For TV: "Show Name S01E01"
        For movies: "Movie Name 2023"
        """
        import re
        name = path.stem

        # Try to extract TV pattern: Show Name S01E01
        tv_match = re.search(r'^(.+?)\s*-?\s*(S\d+E\d+)', name, re.IGNORECASE)
        if tv_match:
            show = tv_match.group(1).strip(' -')
            episode = tv_match.group(2).upper()
            return f"{show} {episode}"

        # For movies, try to get title and year
        movie_match = re.search(r'^(.+?)\s*[\(\[]?(\d{4})[\)\]]?', name)
        if movie_match:
            title = movie_match.group(1).strip(' -')
            year = movie_match.group(2)
            return f"{title} {year}"

        # Fallback: just use the filename (cleaned up)
        clean = re.sub(r'[\[\(].*?[\]\)]', '', name)  # Remove brackets
        clean = re.sub(r'\.(mkv|mp4|avi)$', '', clean, re.IGNORECASE)
        return clean.strip()

    def search(self, path: Path, languages: List[str]) -> List[dict]:
        """Search for subtitles by file hash, with query fallback."""
        if not self.token:
            if not self.login():
                raise OpenSubtitlesError("Not logged in to OpenSubtitles.org")

        self._rate_limit()
        file_hash = compute_hash(path)
        file_size = path.stat().st_size

        # Try hash search first (most accurate when it matches)
        try:
            result = self.server.SearchSubtitles(
                self.token,
                [
                    {
                        "sublanguageid": ",".join(languages),
                        "moviehash": file_hash,
                        "moviebytesize": str(file_size),
                    }
                ],
            )
            data = result.get("data")
            if data and isinstance(data, list) and len(data) > 0:
                return data
        except Exception:
            pass  # Fall through to query search

        # Fallback: search by query
        self._rate_limit()
        query = self._extract_search_query(path)

        try:
            result = self.server.SearchSubtitles(
                self.token,
                [
                    {
                        "sublanguageid": ",".join(languages),
                        "query": query,
                    }
                ],
            )
            data = result.get("data")
            if data and isinstance(data, list):
                return data
            return []
        except Exception as e:
            raise OpenSubtitlesError(f"Search failed: {e}") from e

    def download(self, subtitle_id: str | int) -> Optional[str]:
        """Download subtitle content (returns decoded SRT content)."""
        if not self.token:
            if not self.login():
                raise OpenSubtitlesError("Not logged in to OpenSubtitles.org")

        self._rate_limit()
        try:
            result = self.server.DownloadSubtitles(self.token, [str(subtitle_id)])
            data = result.get("data")
            if data and isinstance(data, list) and len(data) > 0:
                content = base64.b64decode(data[0]["data"])
                return gzip.decompress(content).decode("utf-8", errors="replace")
            return None
        except Exception as e:
            raise OpenSubtitlesError(f"Download failed: {e}") from e


def _quota_message(response: httpx.Response) -> str:
    """Build a readable quota-exceeded message from a .com /download response."""
    try:
        data = response.json()
    except ValueError:
        data = {}
    message = "OpenSubtitles.com download quota used up"
    if isinstance(data, dict):
        if data.get("message"):
            message = f"{message}: {data['message']}"
        reset = data.get("reset_time_utc") or data.get("reset_time")
        if reset:
            message = f"{message} (resets {reset})"
    return message


class OpenSubtitlesComClient:
    """Client for OpenSubtitles.com REST API.

    Requires API key for searching. Downloads require authentication
    with username/password to get a JWT token.
    """

    BASE_URL = "https://api.opensubtitles.com/api/v1"
    USER_AGENT = "JackMediaMan v0.3.0"
    RATE_LIMIT_DELAY = 1.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.opensubtitles_com_api_key or ""
        self.username = username or settings.opensubtitles_com_username or ""
        self.password = password or settings.opensubtitles_com_password or ""
        self.jwt_token = settings.opensubtitles_com_jwt_token or ""
        self.last_request_time = 0.0
        self.quota_exhausted = False  # Set once the API reports 0 downloads remaining

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.RATE_LIMIT_DELAY:
            time.sleep(self.RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _get_headers(self) -> dict:
        """Get headers for API requests."""
        return {
            "Api-Key": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": self.USER_AGENT,
        }

    def validate_credentials(self) -> bool:
        """Validate API key by making a test request."""
        if not self.api_key:
            return False

        self._rate_limit()
        try:
            # Use /infos/languages which only requires API key (not token)
            response = httpx.get(
                f"{self.BASE_URL}/infos/languages",
                headers=self._get_headers(),
                timeout=15.0,
                follow_redirects=True,
            )
            # 200 = valid API key, 401 = invalid
            return response.status_code == 200
        except Exception:
            return False

    def can_download(self) -> bool:
        """Check if this client can download (has username/password)."""
        return bool(self.username and self.password)

    def login(self) -> bool:
        """Login to get JWT token for downloads.

        Returns True if login successful, False otherwise.
        Token is cached in settings for reuse.
        """
        if not self.username or not self.password:
            return False

        self._rate_limit()
        try:
            response = httpx.post(
                f"{self.BASE_URL}/login",
                headers=self._get_headers(),
                json={"username": self.username, "password": self.password},
                timeout=15.0,
            )
            if response.status_code == 200:
                data = response.json()
                self.jwt_token = data.get("token", "")
                if self.jwt_token:
                    # Cache token in settings for future use
                    save_setting("opensubtitles_com_jwt_token", self.jwt_token)
                    return True
            return False
        except Exception:
            return False

    def _extract_search_query(self, path: Path) -> str:
        """Extract search query from filename.

        For TV: "Show Name S01E01"
        For movies: "Movie Name 2023"
        """
        import re
        name = path.stem

        # Try to extract TV pattern: Show Name S01E01
        tv_match = re.search(r'^(.+?)\s*-?\s*(S\d+E\d+)', name, re.IGNORECASE)
        if tv_match:
            show = tv_match.group(1).strip(' -')
            episode = tv_match.group(2).upper()
            return f"{show} {episode}"

        # For movies, try to get title and year
        movie_match = re.search(r'^(.+?)\s*[\(\[]?(\d{4})[\)\]]?', name)
        if movie_match:
            title = movie_match.group(1).strip(' -')
            year = movie_match.group(2)
            return f"{title} {year}"

        # Fallback: just use the filename (cleaned up)
        clean = re.sub(r'[\[\(].*?[\]\)]', '', name)  # Remove brackets
        clean = re.sub(r'\.(mkv|mp4|avi)$', '', clean, re.IGNORECASE)
        return clean.strip()

    def search(self, path: Path, languages: List[str]) -> List[dict]:
        """Search for subtitles by file hash, with query fallback."""
        self._rate_limit()
        file_hash = compute_hash(path)

        # Try hash search first (most accurate when it matches)
        try:
            response = httpx.get(
                f"{self.BASE_URL}/subtitles",
                headers=self._get_headers(),
                params={"moviehash": file_hash, "languages": ",".join(languages)},
                timeout=15.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            results = response.json().get("data", [])

            if results:
                return results
        except httpx.HTTPError:
            pass  # Fall through to query search

        # Fallback: search by filename query
        self._rate_limit()
        query = self._extract_search_query(path)

        try:
            response = httpx.get(
                f"{self.BASE_URL}/subtitles",
                headers=self._get_headers(),
                params={"query": query, "languages": ",".join(languages)},
                timeout=15.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            return response.json().get("data", [])
        except httpx.HTTPStatusError as e:
            raise OpenSubtitlesError(f"Search failed: HTTP {e.response.status_code}") from e
        except httpx.HTTPError as e:
            raise OpenSubtitlesError(f"Search failed: {e}") from e

    def download(self, file_id: str | int) -> Optional[str]:
        """Download subtitle content using JWT authentication.

        Requires username/password to be configured for login.
        Returns the subtitle content as a string.
        """
        # Check if we have credentials
        if not self.username or not self.password:
            raise OpenSubtitlesError(
                "OpenSubtitles.com downloads require username/password. "
                "Configure .com credentials or use .org for downloading."
            )

        # Login if we don't have a token
        if not self.jwt_token:
            if not self.login():
                raise OpenSubtitlesError("Failed to login to OpenSubtitles.com")

        self._rate_limit()

        # Make download request with JWT auth
        headers = self._get_headers()
        headers["Authorization"] = f"Bearer {self.jwt_token}"

        try:
            response = httpx.post(
                f"{self.BASE_URL}/download",
                headers=headers,
                json={"file_id": int(file_id)},
                timeout=30.0,
            )

            # If unauthorized, try logging in again (token may have expired)
            if response.status_code == 401:
                self.jwt_token = ""
                if not self.login():
                    raise OpenSubtitlesError("Failed to re-login to OpenSubtitles.com")
                headers["Authorization"] = f"Bearer {self.jwt_token}"
                response = httpx.post(
                    f"{self.BASE_URL}/download",
                    headers=headers,
                    json={"file_id": int(file_id)},
                    timeout=30.0,
                )

            # 406 = download quota used up for this period
            if response.status_code == 406:
                self.quota_exhausted = True
                raise OpenSubtitlesQuotaError(_quota_message(response))

            if response.status_code != 200:
                raise OpenSubtitlesError(
                    f"Download request failed: HTTP {response.status_code}"
                )

            # Get the download link from response
            data = response.json()
            remaining = data.get("remaining")
            if isinstance(remaining, int) and remaining <= 0:
                # This download still counts; any further request would be refused
                self.quota_exhausted = True
            download_link = data.get("link")
            if not download_link:
                raise OpenSubtitlesError("No download link in response")

            # Fetch the actual subtitle content
            self._rate_limit()
            content_response = httpx.get(download_link, timeout=30.0, follow_redirects=True)
            content_response.raise_for_status()

            return content_response.text

        except httpx.HTTPError as e:
            raise OpenSubtitlesError(f"Download failed: {e}") from e


def get_client() -> OpenSubtitlesOrgClient | OpenSubtitlesComClient:
    """Get the first configured OpenSubtitles client.

    Prefers .com (API key) if configured, otherwise .org.
    For fallback support, use SubtitleService instead.
    """
    settings = get_settings()
    if settings.opensubtitles_com_api_key:
        return OpenSubtitlesComClient()
    return OpenSubtitlesOrgClient()


# Legacy alias for backwards compatibility
OpenSubtitlesClient = OpenSubtitlesOrgClient


class SubtitleService:
    """Service for downloading and managing subtitles with fallback support."""

    def __init__(self, client: Optional[OpenSubtitlesOrgClient | OpenSubtitlesComClient] = None):
        """Initialize the subtitle service.

        Args:
            client: Optional client instance (if provided, no fallback)
        """
        from jackmediaman.core.logging import get_logger

        self.logger = get_logger("subtitles")
        self.settings = get_settings()

        # If client explicitly provided, use only that
        if client:
            self.clients = [
                ("com" if isinstance(client, OpenSubtitlesComClient) else "org", client)
            ]
        else:
            self.clients = self._get_clients()

        # Providers dropped for the rest of this run (served an ad placeholder)
        self.disabled_providers: set[str] = set()
        # Set when the run should stop (quota used up, or every provider disabled)
        self.stop_reason: Optional[str] = None

        self.logger.debug(f"Initialized with providers: {[name for name, _ in self.clients]}")

    def _disable_provider(self, provider_name: str, reason: str) -> None:
        """Stop using a provider for the rest of this run."""
        self.disabled_providers.add(provider_name)
        if all(name in self.disabled_providers for name, _ in self.clients):
            self.stop_reason = f"No usable subtitle providers left ({reason})"

    def _get_clients(self) -> List[tuple]:
        """Get list of (provider_name, client) for all configured providers.

        .com is tried first (faster API, but downloads require auth).
        .org is tried second (can search and download with username/password).
        """
        clients = []
        settings = self.settings

        # Add .com if API key is configured (search only, no downloads)
        if settings.opensubtitles_com_api_key:
            clients.append(("com", OpenSubtitlesComClient()))
            self.logger.debug("Added .com provider (API key)")

        # Add .org if username/password is configured (search + download)
        if settings.opensubtitles_org_username and settings.opensubtitles_org_password:
            clients.append(("org", OpenSubtitlesOrgClient()))
            self.logger.debug("Added .org provider (username/password)")

        return clients

    def _try_provider(
        self,
        provider_name: str,
        client: OpenSubtitlesOrgClient | OpenSubtitlesComClient,
        path: Path,
        languages: List[str],
    ) -> SubtitleResult:
        """Try to find and download subtitle from a single provider.

        Returns SubtitleResult with success=True if found, or error info if not.
        """
        self.logger.debug(f"Trying {provider_name} for {path.name}")

        try:
            # Search for subtitles
            results = client.search(path, languages)

            if not results:
                self.logger.debug(f"No results from {provider_name}")
                return SubtitleResult(
                    video_path=path,
                    success=False,
                    error=f"No results",
                    provider=provider_name,
                )

            # Filter results to only include requested languages
            # Normalize to handle both 2-letter (en) and 3-letter (eng) codes
            accepted_langs = normalize_lang_codes(languages)
            best = None
            for result in results:
                if isinstance(client, OpenSubtitlesComClient):
                    result_lang = result.get("attributes", {}).get("language", "")
                else:
                    result_lang = result.get("SubLanguageID", "")

                if result_lang.lower() in accepted_langs:
                    best = result
                    break

            if not best:
                self.logger.debug(f"No matching language from {provider_name}")
                return SubtitleResult(
                    video_path=path,
                    success=False,
                    error=f"No subtitles in requested languages",
                    provider=provider_name,
                )

            # Extract file ID and language based on provider format
            if isinstance(client, OpenSubtitlesComClient):
                attributes = best.get("attributes", {})
                files = attributes.get("files", [])
                if not files:
                    return SubtitleResult(
                        video_path=path,
                        success=False,
                        error="No subtitle files in result",
                        provider=provider_name,
                    )
                file_id = files[0].get("file_id")
                lang = attributes.get("language", languages[0])
            else:
                file_id = best.get("IDSubtitleFile")
                lang = best.get("SubLanguageID", languages[0])

            # Normalize language code to 2-letter format for filename (Plex expects this)
            lang_lower = lang.lower()
            if lang_lower in LANG_3_TO_2:
                lang = LANG_3_TO_2[lang_lower]

            if not file_id:
                return SubtitleResult(
                    video_path=path,
                    success=False,
                    error="No subtitle file ID in result",
                    provider=provider_name,
                )

            # Download subtitle content
            content = client.download(file_id)
            if not content:
                return SubtitleResult(
                    video_path=path,
                    success=False,
                    error="Failed to download subtitle content",
                    provider=provider_name,
                )

            # Never save an ad; this provider can't serve us, so drop it for the run
            if is_placeholder_subtitle(content):
                self.logger.warning(
                    f"OpenSubtitles.{provider_name} returned an ad instead of a subtitle "
                    f"for {path.name}; not saving it and skipping {provider_name} "
                    f"for the rest of this run"
                )
                self._disable_provider(
                    provider_name, f"OpenSubtitles.{provider_name} only serves ads"
                )
                return SubtitleResult(
                    video_path=path,
                    success=False,
                    error="Provider returned an ad instead of a subtitle",
                    provider=provider_name,
                )

            # Save subtitle file
            subtitle_path = path.with_suffix(f".{lang}.srt")
            subtitle_path.write_text(content, encoding="utf-8")

            if getattr(client, "quota_exhausted", False):
                self.stop_reason = "OpenSubtitles.com download quota used up"
                self.logger.warning(f"{self.stop_reason}; stopping this run")

            self.logger.info(f"Downloaded from {provider_name}: {path.name} ({lang})")
            return SubtitleResult(
                video_path=path,
                subtitle_path=subtitle_path,
                language=lang,
                success=True,
                provider=provider_name,
            )

        except OpenSubtitlesQuotaError as e:
            self.stop_reason = str(e)
            self.logger.warning(f"{e}; stopping this run")
            return SubtitleResult(
                video_path=path,
                success=False,
                error=str(e),
                provider=provider_name,
            )

        except OpenSubtitlesError as e:
            self.logger.debug(f"Error from {provider_name}: {e}")
            return SubtitleResult(
                video_path=path,
                success=False,
                error=str(e),
                provider=provider_name,
            )

    def download_for_file(
        self,
        path: Path,
        languages: Optional[List[str]] = None,
        overwrite: bool = False,
    ) -> SubtitleResult:
        """Download subtitles for a single video file.

        Tries each configured provider until one succeeds (fallback support).

        Args:
            path: Path to video file
            languages: Language codes to search for (defaults to settings)
            overwrite: Whether to overwrite existing subtitle files

        Returns:
            SubtitleResult with operation details including which provider was used
        """
        if languages is None:
            languages = [
                lang.strip() for lang in self.settings.subtitle_languages.split(",")
            ]

        # Check if subtitle already exists (an ad placeholder counts as missing)
        for lang in languages:
            subtitle_path = path.with_suffix(f".{lang}.srt")
            if subtitle_exists(subtitle_path) and not overwrite:
                self.logger.debug(f"Skipping (exists): {path.name}")
                return SubtitleResult(
                    video_path=path,
                    subtitle_path=subtitle_path,
                    language=lang,
                    success=True,
                    skipped=True,
                    skip_reason="Subtitle already exists",
                )

        if not self.clients:
            self.logger.warning("No subtitle providers configured")
            return SubtitleResult(
                video_path=path,
                success=False,
                error="No subtitle providers configured",
            )

        if self.stop_reason:
            return SubtitleResult(video_path=path, success=False, error=self.stop_reason)

        # Try each provider until one succeeds
        errors = []
        for provider_name, client in self.clients:
            if provider_name in self.disabled_providers:
                continue

            result = self._try_provider(provider_name, client, path, languages)

            if result.success:
                return result

            # Record failure for this provider
            errors.append(f"{provider_name}: {result.error}")

            if self.stop_reason:
                break

        # All providers failed
        all_errors = "; ".join(errors)
        self.logger.debug(f"Not found on any provider: {path.name}")
        return SubtitleResult(
            video_path=path,
            success=False,
            error=f"Not found ({all_errors})",
        )

    def download_for_directory(
        self,
        directory: Path,
        languages: Optional[List[str]] = None,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[SubtitleResult]:
        """Download subtitles for all video files in a directory.

        Args:
            directory: Directory to scan for video files
            languages: Language codes to search for
            overwrite: Whether to overwrite existing subtitle files
            progress_callback: Optional callback(current, total, filename)

        Returns:
            List of SubtitleResult for each video file
        """
        results = []
        video_files = [
            f
            for f in directory.rglob("*")
            if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
        ]

        for i, path in enumerate(video_files):
            if progress_callback:
                progress_callback(i + 1, len(video_files), path.name)

            result = self.download_for_file(path, languages, overwrite)
            results.append(result)

            if self.stop_reason:
                self.logger.warning(f"Stopping subtitle run: {self.stop_reason}")
                break

        return results

    def download_for_library(
        self,
        media_type: str = "both",
        languages: Optional[List[str]] = None,
        overwrite: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[SubtitleResult]:
        """Download subtitles for the entire media library.

        Args:
            media_type: "tv", "movies", or "both"
            languages: Language codes to search for
            overwrite: Whether to overwrite existing subtitle files
            progress_callback: Optional callback(current, total, filename)

        Returns:
            List of SubtitleResult for all video files
        """
        results = []

        if media_type in ("tv", "both"):
            if self.settings.tv_dir.exists():
                results.extend(
                    self.download_for_directory(
                        self.settings.tv_dir, languages, overwrite, progress_callback
                    )
                )

        if media_type in ("movies", "both") and not self.stop_reason:
            if self.settings.movies_dir.exists():
                results.extend(
                    self.download_for_directory(
                        self.settings.movies_dir, languages, overwrite, progress_callback
                    )
                )

        return results
