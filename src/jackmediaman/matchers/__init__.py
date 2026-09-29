"""Matchers for finding duplicate media items."""

from jackmediaman.matchers.tv import TVMatcher
from jackmediaman.matchers.title_year import TitleYearMatcher
from jackmediaman.matchers.fuzzy import FuzzyMatcher
from jackmediaman.matchers.tmdb import TMDbMatcher

__all__ = ["TVMatcher", "TitleYearMatcher", "FuzzyMatcher", "TMDbMatcher"]
