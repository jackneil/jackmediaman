"""Fuzzy matcher for movies - uses Levenshtein distance for title matching."""

from collections import defaultdict
from typing import Dict, List, Set

from jackmediaman.models.media import MediaItem, Movie
from jackmediaman.models.duplicates import DuplicateGroup


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate the Levenshtein distance between two strings.

    The Levenshtein distance is the minimum number of single-character
    edits (insertions, deletions, or substitutions) required to change
    one string into the other.

    Examples:
        >>> levenshtein_distance("hello", "hello")
        0
        >>> levenshtein_distance("cat", "bat")
        1
        >>> levenshtein_distance("kitten", "sitting")
        3
        >>> levenshtein_distance("", "abc")
        3
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Calculate cost of insertions, deletions, substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """Calculate similarity ratio between two strings (0.0 to 1.0).

    Returns 1.0 for identical strings and 0.0 for completely different strings.
    Comparison is case-insensitive.

    Examples:
        >>> similarity_ratio("hello", "hello")
        1.0
        >>> similarity_ratio("Hello", "hello")
        1.0
        >>> similarity_ratio("abc", "xyz")
        0.0
        >>> similarity_ratio("hello", "hallo")
        0.8
    """
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    distance = levenshtein_distance(s1.lower(), s2.lower())
    max_len = max(len(s1), len(s2))
    return 1.0 - (distance / max_len)


def normalize_title(title: str) -> str:
    """Normalize a title for comparison.

    Removes common prefixes (the, a, an) and special characters,
    converts to lowercase, and normalizes whitespace.

    Examples:
        >>> normalize_title("The Matrix")
        'matrix'
        >>> normalize_title("A Beautiful Mind")
        'beautiful mind'
        >>> normalize_title("Spider-Man: No Way Home")
        'spider man no way home'
        >>> normalize_title("2001: A Space Odyssey")
        '2001 space odyssey'
    """
    # Convert to lowercase
    normalized = title.lower()
    # Remove common prefixes
    for prefix in ["the ", "a ", "an "]:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    # Remove special characters, keep only alphanumeric and spaces
    normalized = "".join(c if c.isalnum() or c == " " else " " for c in normalized)
    # Normalize whitespace
    normalized = " ".join(normalized.split())
    return normalized


class FuzzyMatcher:
    """Match movies using fuzzy title matching."""

    name = "fuzzy"
    description = "Match movies using fuzzy title comparison (handles naming variations)"

    def __init__(
        self,
        threshold: float = 0.85,
        include_editions_as_dupes: bool = True,
    ):
        """
        Initialize the matcher.

        Args:
            threshold: Minimum similarity ratio to consider a match (0.0-1.0)
            include_editions_as_dupes: If True, different editions are considered duplicates.
        """
        self.threshold = threshold
        self.include_editions_as_dupes = include_editions_as_dupes

    def match(self, items: List[MediaItem]) -> List[DuplicateGroup]:
        """Group movies that are duplicates based on fuzzy matching."""
        # Filter to only movies
        movies = [item for item in items if isinstance(item, Movie)]

        if not movies:
            return []

        # Track which movies have been assigned to a group
        assigned: Set[int] = set()
        groups: List[DuplicateGroup] = []

        for i, movie in enumerate(movies):
            if i in assigned:
                continue

            # Start a new group with this movie
            group_items = [movie]
            assigned.add(i)

            # Find all movies that match this one
            for j, other in enumerate(movies):
                if j <= i or j in assigned:
                    continue

                if self._is_match(movie, other):
                    group_items.append(other)
                    assigned.add(j)

            # Only create group if there are duplicates
            if len(group_items) > 1:
                group = DuplicateGroup(identity_key=movie.identity_key)
                for item in group_items:
                    group.add(item)
                group.sort_by_quality()
                groups.append(group)

        return groups

    def _is_match(self, movie1: Movie, movie2: Movie) -> bool:
        """Check if two movies should be considered duplicates."""
        # Normalize titles
        title1 = normalize_title(movie1.title)
        title2 = normalize_title(movie2.title)

        # Check title similarity
        if similarity_ratio(title1, title2) < self.threshold:
            return False

        # Check year compatibility (if both have years)
        if movie1.year and movie2.year:
            # Allow 1 year difference for regional release variations
            if abs(movie1.year - movie2.year) > 1:
                return False

        # Check edition compatibility
        if not self.include_editions_as_dupes:
            if movie1.edition != movie2.edition:
                return False

        return True
