"""Linker stage for file operations (move/copy/hardlink/symlink/keeplink)."""

import os
import shutil
from pathlib import Path
from typing import List, Optional

from jackmediaman.core.logging import get_logger
from jackmediaman.core.operations_db import get_operations_db
from jackmediaman.pipeline.context import (
    ActionMode,
    FileMapping,
    LinkOperation,
    ProcessContext,
)
from jackmediaman.pipeline.base import StageOutput, StageResult

logger = get_logger("pipeline.linker")


class LinkerStage:
    """Execute file operations (move/copy/hardlink/symlink/keeplink)."""

    name = "linker"

    def __init__(self, action: Optional[ActionMode] = None):
        """
        Initialize the linker stage.

        Args:
            action: Default action mode (overridden by context.action)
        """
        self.default_action = action or ActionMode.SYMLINK

    def validate(self, context: ProcessContext) -> bool:
        """Check if linking should run."""
        return len(context.file_mappings) > 0

    def execute(self, context: ProcessContext) -> StageOutput:
        """
        Execute file operations based on action mode.

        Actions:
        - move: shutil.move(src, dst)
        - copy: shutil.copy2(src, dst)
        - hardlink: os.link(src, dst)
        - symlink: os.symlink(src, dst)
        - keeplink: move to dst, create symlink at src pointing to dst
        """
        action = context.action or self.default_action
        operations: List[LinkOperation] = []
        failed = []
        db = get_operations_db()

        for mapping in context.file_mappings:
            if context.dry_run:
                # Dry run: just record what would happen
                operations.append(
                    LinkOperation(
                        source=mapping.source,
                        destination=mapping.destination,
                        action=action,
                        success=True,
                    )
                )
                continue

            try:
                operation = self._execute_operation(mapping, action)
                operations.append(operation)
                if operation.success:
                    # Log successful file operation
                    db.log_activity(
                        "INFO",
                        "linker",
                        f"{action.value}: {mapping.source.name} -> {mapping.destination.parent.name}/",
                        source_path=str(mapping.source),
                        session_id=context.session_id,
                    )
                else:
                    failed.append((mapping.source, operation.error))
                    context.add_error(
                        stage=self.name,
                        error=operation.error or "Unknown error",
                        path=mapping.source,
                    )
                    db.log_activity(
                        "ERROR",
                        "linker",
                        f"{action.value} failed: {mapping.source.name} - {operation.error}",
                        source_path=str(mapping.source),
                        session_id=context.session_id,
                    )
            except Exception as e:
                failed.append((mapping.source, str(e)))
                context.add_error(
                    stage=self.name,
                    error=str(e),
                    path=mapping.source,
                )
                operations.append(
                    LinkOperation(
                        source=mapping.source,
                        destination=mapping.destination,
                        action=action,
                        success=False,
                        error=str(e),
                    )
                )
                db.log_activity(
                    "ERROR",
                    "linker",
                    f"{action.value} exception: {mapping.source.name} - {e}",
                    source_path=str(mapping.source),
                    session_id=context.session_id,
                )

        context.completed_operations = operations

        successful = [op for op in operations if op.success]
        if not successful:
            return StageOutput(
                result=StageResult.FAILED,
                message="No files could be linked",
                items_failed=len(failed),
                rollback_data={"operations": [self._op_to_dict(op) for op in operations]},
            )

        return StageOutput(
            result=StageResult.SUCCESS if not failed else StageResult.PARTIAL,
            message=f"Linked {len(successful)} files using {action.value}",
            items_processed=len(successful),
            items_failed=len(failed),
            rollback_data={"operations": [self._op_to_dict(op) for op in successful]},
        )

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        """Reverse completed operations."""
        operations = rollback_data.get("operations", [])

        for op_data in reversed(operations):
            try:
                self._rollback_operation(op_data)
            except Exception:
                pass  # Best effort rollback

        return True

    def _execute_operation(
        self, mapping: FileMapping, action: ActionMode
    ) -> LinkOperation:
        """Execute a single file operation."""
        # Create destination directories
        for directory in mapping.create_directories:
            directory.mkdir(parents=True, exist_ok=True)

        # Check if destination already exists
        if mapping.destination.exists():
            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=action,
                success=False,
                error=f"Destination already exists: {mapping.destination}",
            )

        # Execute based on action mode
        if action == ActionMode.MOVE:
            return self._execute_move(mapping)
        elif action == ActionMode.COPY:
            return self._execute_copy(mapping)
        elif action == ActionMode.HARDLINK:
            return self._execute_hardlink(mapping)
        elif action == ActionMode.SYMLINK:
            return self._execute_symlink(mapping)
        elif action == ActionMode.KEEPLINK:
            return self._execute_keeplink(mapping)
        else:
            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=action,
                success=False,
                error=f"Unknown action mode: {action}",
            )

    def _execute_move(self, mapping: FileMapping) -> LinkOperation:
        """Move file to destination."""
        try:
            shutil.move(str(mapping.source), str(mapping.destination))

            # Log to operations database
            try:
                ops_db = get_operations_db()
                ops_db.log_operation(
                    op_type="move",
                    source=mapping.source,
                    dest=mapping.destination,
                    success=True,
                )
                ops_db.log_media_file(current_path=mapping.destination, original_path=mapping.source)
            except Exception as db_err:
                logger.warning(f"Failed to log move operation to DB: {db_err}")

            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=ActionMode.MOVE,
                success=True,
            )
        except Exception as e:
            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=ActionMode.MOVE,
                success=False,
                error=str(e),
            )

    def _execute_copy(self, mapping: FileMapping) -> LinkOperation:
        """Copy file to destination."""
        try:
            shutil.copy2(str(mapping.source), str(mapping.destination))

            # Log to operations database
            try:
                ops_db = get_operations_db()
                ops_db.log_operation(
                    op_type="copy",
                    source=mapping.source,
                    dest=mapping.destination,
                    success=True,
                )
                ops_db.log_media_file(current_path=mapping.destination, original_path=mapping.source)
            except Exception as db_err:
                logger.warning(f"Failed to log copy operation to DB: {db_err}")

            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=ActionMode.COPY,
                success=True,
            )
        except Exception as e:
            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=ActionMode.COPY,
                success=False,
                error=str(e),
            )

    def _execute_hardlink(self, mapping: FileMapping) -> LinkOperation:
        """Create hardlink at destination."""
        try:
            os.link(str(mapping.source), str(mapping.destination))
            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=ActionMode.HARDLINK,
                success=True,
            )
        except Exception as e:
            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=ActionMode.HARDLINK,
                success=False,
                error=str(e),
            )

    def _execute_symlink(self, mapping: FileMapping) -> LinkOperation:
        """Create symlink at destination pointing to source."""
        try:
            # Use absolute path for symlink target
            target = mapping.source.resolve()
            os.symlink(str(target), str(mapping.destination))

            # Log to operations database
            try:
                ops_db = get_operations_db()
                op_id = ops_db.log_operation(
                    op_type="symlink",
                    source=mapping.source,
                    dest=mapping.destination,
                    success=True,
                )
                # Get target file size for verification during repair
                target_size = target.stat().st_size if target.exists() else None
                ops_db.log_symlink(
                    symlink_path=mapping.destination,
                    target_path=target,
                    operation_id=op_id,
                    target_size=target_size,
                )
            except Exception as db_err:
                logger.warning(f"Failed to log symlink operation to DB: {db_err}")

            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=ActionMode.SYMLINK,
                success=True,
            )
        except Exception as e:
            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=ActionMode.SYMLINK,
                success=False,
                error=str(e),
            )

    def _execute_keeplink(self, mapping: FileMapping) -> LinkOperation:
        """Move to destination, leave symlink at source for seeding."""
        try:
            # Store original location
            original = mapping.source.resolve()

            # Move file to destination
            shutil.move(str(mapping.source), str(mapping.destination))

            # Create symlink at original location pointing to new location
            dest_resolved = mapping.destination.resolve()
            os.symlink(str(dest_resolved), str(original))

            # Log to operations database
            try:
                ops_db = get_operations_db()
                op_id = ops_db.log_operation(
                    op_type="keeplink",
                    source=mapping.source,
                    dest=mapping.destination,
                    success=True,
                )
                # Log the media file's new location
                ops_db.log_media_file(current_path=mapping.destination, original_path=original)
                # Get target file size for verification during repair
                target_size = dest_resolved.stat().st_size if dest_resolved.exists() else None
                # Log the symlink relationship (symlink at original points to destination)
                ops_db.log_symlink(
                    symlink_path=original,
                    target_path=dest_resolved,
                    operation_id=op_id,
                    target_size=target_size,
                )
                logger.info(f"KEEPLINK logged: {original} -> {dest_resolved} (size={target_size})")
            except Exception as db_err:
                logger.warning(f"Failed to log keeplink operation to DB: {db_err}")

            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=ActionMode.KEEPLINK,
                success=True,
                original_link=original,
            )
        except Exception as e:
            return LinkOperation(
                source=mapping.source,
                destination=mapping.destination,
                action=ActionMode.KEEPLINK,
                success=False,
                error=str(e),
            )

    def _rollback_operation(self, op_data: dict) -> None:
        """Rollback a single operation."""
        action = ActionMode(op_data["action"])
        source = Path(op_data["source"])
        destination = Path(op_data["destination"])

        if action == ActionMode.MOVE:
            # Move back
            if destination.exists():
                shutil.move(str(destination), str(source))
        elif action == ActionMode.COPY:
            # Delete copy
            if destination.exists():
                destination.unlink()
        elif action == ActionMode.HARDLINK:
            # Unlink
            if destination.exists():
                destination.unlink()
        elif action == ActionMode.SYMLINK:
            # Remove symlink
            if destination.is_symlink():
                destination.unlink()
        elif action == ActionMode.KEEPLINK:
            # Move back from destination, remove symlink at source
            original_link = op_data.get("original_link")
            if original_link:
                link_path = Path(original_link)
                if link_path.is_symlink():
                    link_path.unlink()
            if destination.exists():
                shutil.move(str(destination), str(source))

    def _op_to_dict(self, op: LinkOperation) -> dict:
        """Convert LinkOperation to dict for rollback data."""
        return {
            "source": str(op.source),
            "destination": str(op.destination),
            "action": op.action.value,
            "original_link": str(op.original_link) if op.original_link else None,
        }
