"""Title/Year matcher for movies - groups by parsed title and year."""

from collections import defaultdict
from typing import Dict, List, Optional

from jackmediaman.models.media import MediaItem, Movie
from jackmediaman.models.duplicates import DuplicateGroup


class TitleYearMatcher:
    """Match movies by title and year parsing."""

    name = "title_year"
    description = "Match movies by parsed title and year from folder/filename"

    def __init__(self, include_editions_as_dupes: bool = True):
        """
        Initialize the matcher.

        Args:
            include_editions_as_dupes: If True, different editions are considered duplicates.
                                       If False, Director's Cut and Theatrical are separate.
        """
        self.include_editions_as_dupes = include_editions_as_dupes

    def match(self, items: List[MediaItem]) -> List[DuplicateGroup]:
        """Group movies that are duplicates of each other."""
        # Filter to only movies
        movies = [item for item in items if isinstance(item, Movie)]

        # Group by identity key (optionally including edition)
        groups: Dict[str, List[Movie]] = defaultdict(list)
        for movie in movies:
            key = self._get_match_key(movie)
            groups[key].append(movie)

        # Create DuplicateGroup objects for groups with duplicates
        result = []
        for key, group_items in groups.items():
            if len(group_items) > 1:
                group = DuplicateGroup(identity_key=key)
                for item in group_items:
                    group.add(item)
                group.sort_by_quality()
                result.append(group)

        return result

    def _get_match_key(self, movie: Movie) -> str:
        """Get the matching key for a movie."""
        base_key = movie.identity_key

        if not self.include_editions_as_dupes and movie.edition:
            return f"{base_key}:{movie.edition}"

        return base_key
