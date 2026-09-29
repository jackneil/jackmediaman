"""Pipeline module for processing completed torrent downloads."""

from jackmediaman.pipeline.context import (
    ProcessContext,
    ActionMode,
    IdentifiedMedia,
    FileMapping,
    LinkOperation,
    StageError,
)
from jackmediaman.pipeline.base import (
    Pipeline,
    PipelineStage,
    StageResult,
    StageOutput,
    ProcessResult,
)

__all__ = [
    # Context and data models
    "ProcessContext",
    "ActionMode",
    "IdentifiedMedia",
    "FileMapping",
    "LinkOperation",
    "StageError",
    # Pipeline orchestration
    "Pipeline",
    "PipelineStage",
    "StageResult",
    "StageOutput",
    "ProcessResult",
]
