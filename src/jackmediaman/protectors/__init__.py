"""Protectors for preventing removal of actively seeding files."""

from jackmediaman.protectors.symlink import SymlinkProtector
from jackmediaman.protectors.deluge import DelugeProtector

__all__ = ["SymlinkProtector", "DelugeProtector"]
