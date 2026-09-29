"""Tests for pipeline base module."""

import pytest

from jackmediaman.pipeline.base import (
    Pipeline,
    PipelineStage,
    ProcessResult,
    StageOutput,
    StageResult,
)
from jackmediaman.pipeline.context import ActionMode, ProcessContext, StageError


class TestStageResult:
    """Tests for StageResult enum."""

    def test_all_results_exist(self):
        """Verify all stage results are defined."""
        assert StageResult.SUCCESS.value == "success"
        assert StageResult.PARTIAL.value == "partial"
        assert StageResult.FAILED.value == "failed"
        assert StageResult.SKIPPED.value == "skipped"


class TestStageOutput:
    """Tests for StageOutput dataclass."""

    def test_create_success_output(self):
        """Create a successful stage output."""
        output = StageOutput(
            result=StageResult.SUCCESS,
            message="Processed 5 files",
            items_processed=5,
        )
        assert output.result == StageResult.SUCCESS
        assert output.items_processed == 5
        assert output.items_failed == 0

    def test_create_partial_output(self):
        """Create a partial success output."""
        output = StageOutput(
            result=StageResult.PARTIAL,
            message="Some files failed",
            items_processed=3,
            items_failed=2,
        )
        assert output.result == StageResult.PARTIAL
        assert output.items_processed == 3
        assert output.items_failed == 2

    def test_create_skipped_output(self):
        """Create a skipped stage output."""
        output = StageOutput(
            result=StageResult.SKIPPED,
            message="No archives to extract",
        )
        assert output.result == StageResult.SKIPPED


class TestProcessResult:
    """Tests for ProcessResult dataclass."""

    def test_create_success_result(self):
        """Create a successful process result."""
        result = ProcessResult(
            success=True,
            message="Processed successfully",
            files_processed=10,
        )
        assert result.success is True
        assert result.files_processed == 10

    def test_create_failed_result(self):
        """Create a failed process result."""
        errors = [StageError(stage="extractor", error="Corrupt archive")]
        result = ProcessResult(
            success=False,
            message="Extraction failed",
            files_processed=0,
            errors=errors,
        )
        assert result.success is False
        assert len(result.errors) == 1


class MockStage(PipelineStage):
    """Mock stage for testing."""

    def __init__(self, name: str, result: StageResult = StageResult.SUCCESS):
        self.name = name
        self._result = result
        self.execute_called = False
        self.rollback_called = False

    def validate(self, context: ProcessContext) -> bool:
        return True

    def execute(self, context: ProcessContext) -> StageOutput:
        self.execute_called = True
        return StageOutput(
            result=self._result,
            message=f"{self.name} executed",
        )

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        self.rollback_called = True
        return True


class FailingStage(PipelineStage):
    """Stage that always fails."""

    name = "failing"

    def validate(self, context: ProcessContext) -> bool:
        return True

    def execute(self, context: ProcessContext) -> StageOutput:
        context.add_error("failing", "Intentional failure")
        return StageOutput(
            result=StageResult.FAILED,
            message="Stage failed",
        )

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        return True


class TestPipeline:
    """Tests for Pipeline class."""

    def test_execute_empty_pipeline(self, tmp_path):
        """Execute pipeline with no stages."""
        pipeline = Pipeline([])
        context = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
        )
        result = pipeline.execute(context)
        assert result.success is True

    def test_execute_single_stage(self, tmp_path):
        """Execute pipeline with one successful stage."""
        stage = MockStage("extractor")
        pipeline = Pipeline([stage])
        context = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
        )
        result = pipeline.execute(context)

        assert result.success is True
        assert stage.execute_called is True
        assert len(result.stage_outputs) == 1
        assert result.stage_outputs[0][0] == "extractor"

    def test_execute_multiple_stages(self, tmp_path):
        """Execute pipeline with multiple stages."""
        stages = [
            MockStage("extractor"),
            MockStage("identifier"),
            MockStage("organizer"),
        ]
        pipeline = Pipeline(stages)
        context = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
        )
        result = pipeline.execute(context)

        assert result.success is True
        assert all(s.execute_called for s in stages)
        assert len(result.stage_outputs) == 3

    def test_stage_failure_stops_pipeline(self, tmp_path):
        """Failing stage stops further execution."""
        stages = [
            MockStage("extractor"),
            FailingStage(),
            MockStage("organizer"),
        ]
        pipeline = Pipeline(stages)
        context = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
        )
        result = pipeline.execute(context)

        assert result.success is False
        assert stages[0].execute_called is True
        assert stages[2].execute_called is False  # Should not run after failure

    def test_progress_callback(self, tmp_path):
        """Progress callback is called for each stage."""
        stages = [
            MockStage("extractor"),
            MockStage("identifier"),
        ]
        pipeline = Pipeline(stages)
        context = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
        )

        callbacks = []

        def callback(stage_name: str, status: str):
            callbacks.append((stage_name, status))

        result = pipeline.execute(context, progress_callback=callback)

        assert result.success is True
        # Should have callbacks for each stage
        assert len(callbacks) >= 2

    def test_partial_success_continues(self, tmp_path):
        """Partial success allows pipeline to continue."""
        partial_stage = MockStage("extractor", StageResult.PARTIAL)
        next_stage = MockStage("identifier")
        pipeline = Pipeline([partial_stage, next_stage])
        context = ProcessContext(
            source_path=tmp_path,
            action=ActionMode.SYMLINK,
        )
        result = pipeline.execute(context)

        # Partial success should allow continuation
        assert next_stage.execute_called is True
