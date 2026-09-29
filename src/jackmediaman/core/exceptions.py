"""Custom exceptions for JackMediaMan."""


class JackMediaManError(Exception):
    """Base exception for all JackMediaMan errors."""

    pass


class ConfigError(JackMediaManError):
    """Configuration-related errors."""

    pass


class ScannerError(JackMediaManError):
    """Scanner-related errors."""

    pass


class MatcherError(JackMediaManError):
    """Matcher-related errors."""

    pass


class ProtectorError(JackMediaManError):
    """Protector-related errors."""

    pass


class CleanupError(JackMediaManError):
    """Cleanup-related errors."""

    pass


class DelugeConnectionError(ProtectorError):
    """Failed to connect to Deluge daemon."""

    pass


class TMDbError(MatcherError):
    """TMDb API-related errors."""

    pass


class OpenSubtitlesError(JackMediaManError):
    """OpenSubtitles API-related errors."""

    pass


class OpenSubtitlesQuotaError(OpenSubtitlesError):
    """OpenSubtitles download quota used up; further requests are pointless."""

    pass
