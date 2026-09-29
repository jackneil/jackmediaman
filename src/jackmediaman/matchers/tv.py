"""TV episode matcher - groups episodes by show/season/episode."""

from collections import defaultdict
from typing import Dict, List

from jackmediaman.models.media import Episode, MediaItem
from jackmediaman.models.duplicates import DuplicateGroup


class TVMatcher:
    """Match TV episodes by series, season, and episode number."""

    name = "tv"
    description = "Match episodes by show name, season, and episode number"

    def match(self, items: List[MediaItem]) -> List[DuplicateGroup]:
        """Group episodes that are duplicates of each other."""
        # Filter to only episodes
        episodes = [item for item in items if isinstance(item, Episode)]

        # Group by identity key
        groups: Dict[str, List[Episode]] = defaultdict(list)
        for episode in episodes:
            groups[episode.identity_key].append(episode)

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
