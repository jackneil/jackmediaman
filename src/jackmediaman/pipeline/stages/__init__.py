"""Pipeline stages for torrent processing."""

from jackmediaman.pipeline.stages.extractor import ExtractorStage
from jackmediaman.pipeline.stages.identifier import IdentifierStage
from jackmediaman.pipeline.stages.organizer import OrganizerStage
from jackmediaman.pipeline.stages.linker import LinkerStage
from jackmediaman.pipeline.stages.subtitles import SubtitleStage
from jackmediaman.pipeline.stages.artwork import ArtworkStage
from jackmediaman.pipeline.stages.nfo import NFOStage
from jackmediaman.pipeline.stages.plex_notifier import PlexNotifierStage

__all__ = [
    "ExtractorStage",
    "IdentifierStage",
    "OrganizerStage",
    "LinkerStage",
    "SubtitleStage",
    "ArtworkStage",
    "NFOStage",
    "PlexNotifierStage",
]
