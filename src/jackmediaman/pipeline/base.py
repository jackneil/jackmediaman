"""Pipeline orchestrator and stage protocol for torrent processing."""

import json
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Protocol, Any

from jackmediaman.core.logging import get_logger
from jackmediaman.core.operations_db import get_operations_db
from jackmediaman.pipeline.context import ProcessContext, StageError

logger = get_logger("pipeline")


class StageResult(str, Enum):
    """Result of a pipeline stage."""

    SUCCESS = "success"
    PARTIAL = "partial"  # Some items processed, some errors
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StageOutput:
    """Output from a pipeline stage."""

    result: StageResult
    message: str
    items_processed: int = 0
    items_failed: int = 0
    rollback_data: Optional[dict] = None  # Data needed for rollback


class PipelineStage(Protocol):
    """Protocol for pipeline stages."""

    name: str

    def execute(self, context: ProcessContext) -> StageOutput:
        """Execute the stage, modifying context in place."""
        ...

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        """Rollback changes made by this stage. Returns True if successful."""
        ...

    def validate(self, context: ProcessContext) -> bool:
        """Validate prerequisites for this stage. Returns True if valid."""
        ...


@dataclass
class ProcessResult:
    """Final result of pipeline execution."""

    success: bool
    message: str
    files_processed: int = 0
    files_failed: int = 0
    errors: List[StageError] = field(default_factory=list)
    stage_outputs: List[tuple] = field(default_factory=list)  # (stage_name, StageOutput)

    @property
    def summary(self) -> str:
        """Get a summary of the results."""
        if self.success:
            return f"Successfully processed {self.files_processed} files"
        return f"Failed: {self.message} ({self.files_failed} errors)"


class Pipeline:
    """Orchestrates pipeline stages with error handling and rollback."""

    def __init__(self, stages: List[PipelineStage]):
        """
        Initialize the pipeline.

        Args:
            stages: List of stages to execute in order
        """
        self.stages = stages
        self._completed_stages: List[tuple[PipelineStage, StageOutput]] = []

    def execute(
        self,
        context: ProcessContext,
        progress_callback: Optional[Callable[[str, str], None]] = None,
    ) -> ProcessResult:
        """
        Execute all stages in sequence.

        Args:
            context: ProcessContext with input parameters
            progress_callback: Optional callback(stage_name, status) for progress

        Returns:
            ProcessResult with success/failure and details
        """
        self._completed_stages = []
        db = get_operations_db()

        for stage in self.stages:
            # Validate prerequisites
            if not stage.validate(context):
                if progress_callback:
                    progress_callback(stage.name, "skipped (prerequisites not met)")
                db.log_activity(
                    "INFO",
                    "stage",
                    f"Stage skipped (prerequisites not met): {stage.name}",
                    source_path=str(context.source_path),
                    session_id=context.session_id,
                )
                continue

            # Execute stage
            if progress_callback:
                progress_callback(stage.name, "running...")

            db.log_activity(
                "INFO",
                "stage",
                f"Stage starting: {stage.name}",
                source_path=str(context.source_path),
                session_id=context.session_id,
            )

            try:
                output = stage.execute(context)
            except Exception as e:
                # Stage threw an unexpected exception
                output = StageOutput(
                    result=StageResult.FAILED,
                    message=str(e),
                )
                context.add_error(
                    stage=stage.name,
                    error=str(e),
                    recoverable=False,
                )
                # Log exception with traceback
                db.log_activity(
                    "ERROR",
                    "stage",
                    f"Stage exception: {stage.name} - {e}",
                    source_path=str(context.source_path),
                    traceback_str=traceback.format_exc(),
                    session_id=context.session_id,
                )

            self._completed_stages.append((stage, output))

            # Log stage completion
            db.log_activity(
                "INFO" if output.result in (StageResult.SUCCESS, StageResult.SKIPPED) else "WARNING" if output.result == StageResult.PARTIAL else "ERROR",
                "stage",
                f"Stage complete: {stage.name} - {output.result.value} ({output.items_processed} items)",
                source_path=str(context.source_path),
                details=json.dumps({"items_processed": output.items_processed, "items_failed": output.items_failed, "message": output.message}),
                session_id=context.session_id,
            )

            if progress_callback:
                progress_callback(stage.name, output.result.value)

            # Check if we should abort
            if output.result == StageResult.FAILED:
                # Attempt rollback
                self.rollback(context)
                return ProcessResult(
                    success=False,
                    message=output.message,
                    errors=context.errors,
                    stage_outputs=[(s.name, o) for s, o in self._completed_stages],
                )

            # Check for fatal errors in context
            if context.has_fatal_errors():
                self.rollback(context)
                return ProcessResult(
                    success=False,
                    message="Fatal error encountered",
                    errors=context.errors,
                    stage_outputs=[(s.name, o) for s, o in self._completed_stages],
                )

        # Calculate totals
        total_processed = sum(o.items_processed for _, o in self._completed_stages)
        total_failed = sum(o.items_failed for _, o in self._completed_stages)

        return ProcessResult(
            success=True,
            message="Pipeline completed successfully",
            files_processed=total_processed,
            files_failed=total_failed,
            errors=context.errors,
            stage_outputs=[(s.name, o) for s, o in self._completed_stages],
        )

    def rollback(self, context: ProcessContext) -> None:
        """Rollback all completed stages in reverse order."""
        for stage, output in reversed(self._completed_stages):
            if output.rollback_data:
                try:
                    stage.rollback(context, output.rollback_data)
                except Exception:
                    # Rollback failed, log but continue
                    pass
