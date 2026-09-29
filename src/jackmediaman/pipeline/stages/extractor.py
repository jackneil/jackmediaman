"""Extractor stage for archive extraction from torrent downloads."""

import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional, Set

from jackmediaman.core.logging import get_logger
from jackmediaman.pipeline.context import ProcessContext
from jackmediaman.pipeline.base import StageOutput, StageResult

logger = get_logger("pipeline.extractor")


class ExtractorStage:
    """Extract archives from torrent downloads."""

    name = "extractor"

    # Supported archive formats
    ARCHIVE_EXTENSIONS = {".rar", ".zip", ".7z", ".tar", ".tar.gz", ".tgz"}

    # Patterns to skip (sample files, proofs, etc.)
    SAMPLE_PATTERNS = [
        re.compile(r"\bsample\b", re.IGNORECASE),
        re.compile(r"\bproof\b", re.IGNORECASE),
        re.compile(r"\bscreens?\b", re.IGNORECASE),
    ]

    # Extensions to skip
    SKIP_EXTENSIONS = {".nfo", ".txt", ".sfv", ".par2", ".par", ".jpg", ".png", ".gif"}

    # Video extensions to look for
    VIDEO_EXTENSIONS = {".mkv", ".mp4", ".avi", ".m4v", ".wmv", ".ts", ".mov"}

    def __init__(
        self,
        work_dir: Optional[Path] = None,
        max_depth: int = 3,
        cleanup_on_success: bool = False,
    ):
        """
        Initialize the extractor stage.

        Args:
            work_dir: Directory for extraction (uses temp if not specified)
            max_depth: Maximum nested archive depth to extract
            cleanup_on_success: Delete archives after successful extraction
        """
        self.work_dir = work_dir
        self.max_depth = max_depth
        self.cleanup_on_success = cleanup_on_success

    def validate(self, context: ProcessContext) -> bool:
        """Check if extraction should run."""
        # Skip if disabled
        if context.skip_extraction:
            return False

        # Check if source path exists
        if not context.source_path.exists():
            return False

        # Check if there are archives to extract
        if context.source_path.is_file():
            return context.source_path.suffix.lower() in self.ARCHIVE_EXTENSIONS

        # Directory: check for archives
        return self._has_archives(context.source_path)

    def execute(self, context: ProcessContext) -> StageOutput:
        """
        Extract archives and populate context.extracted_files.

        Handles:
        - RAR archives (including multi-part .r00, .r01, etc.)
        - ZIP files
        - 7z archives
        - Nested archives (recursively)
        - Sample file filtering
        """
        # Set up work directory
        if self.work_dir:
            work_dir = self.work_dir
            work_dir.mkdir(parents=True, exist_ok=True)
        else:
            work_dir = Path(tempfile.mkdtemp(prefix="jmm_extract_"))

        context.work_dir = work_dir
        context._cleanup_paths.append(work_dir)

        try:
            # Find all archives
            archives = self._find_archives(context.source_path)

            if not archives:
                # No archives, just find video files directly
                video_files = self._find_video_files(context.source_path)
                context.extracted_files = video_files
                return StageOutput(
                    result=StageResult.SUCCESS,
                    message="No archives found, using existing files",
                    items_processed=len(video_files),
                )

            # Extract archives
            extracted = []
            failed = []

            for archive in archives:
                try:
                    files = self._extract_archive(archive, work_dir)
                    extracted.extend(files)
                except Exception as e:
                    failed.append((archive, str(e)))
                    context.add_error(
                        stage=self.name,
                        error=f"Failed to extract {archive.name}: {e}",
                        path=archive,
                    )

            # Handle nested archives (recursively)
            for depth in range(self.max_depth):
                nested_archives = [
                    f for f in extracted if f.suffix.lower() in self.ARCHIVE_EXTENSIONS
                ]
                if not nested_archives:
                    break

                for nested in nested_archives:
                    try:
                        nested_files = self._extract_archive(nested, work_dir)
                        extracted.extend(nested_files)
                    except Exception:
                        pass  # Nested extraction failures are not critical

                    # Remove the nested archive from extracted list
                    if nested in extracted:
                        extracted.remove(nested)

            # Filter to video files only, excluding samples
            video_files = [
                f
                for f in extracted
                if f.suffix.lower() in self.VIDEO_EXTENSIONS
                and not self._is_sample_file(f)
            ]

            context.extracted_files = video_files

            # Also add video files from source directory (non-archived)
            if context.source_path.is_dir():
                direct_videos = self._find_video_files(context.source_path)
                for v in direct_videos:
                    if v not in context.extracted_files:
                        context.extracted_files.append(v)

            if failed and not video_files:
                return StageOutput(
                    result=StageResult.FAILED,
                    message=f"All extractions failed: {failed[0][1]}",
                    items_failed=len(failed),
                    rollback_data={"work_dir": str(work_dir)},
                )

            return StageOutput(
                result=StageResult.SUCCESS if not failed else StageResult.PARTIAL,
                message=f"Extracted {len(video_files)} video files",
                items_processed=len(video_files),
                items_failed=len(failed),
                rollback_data={"work_dir": str(work_dir)},
            )

        except Exception as e:
            return StageOutput(
                result=StageResult.FAILED,
                message=str(e),
                rollback_data={"work_dir": str(work_dir)},
            )

    def rollback(self, context: ProcessContext, rollback_data: dict) -> bool:
        """Clean up extracted files."""
        work_dir = rollback_data.get("work_dir")
        if work_dir:
            work_path = Path(work_dir)
            if work_path.exists():
                shutil.rmtree(work_path, ignore_errors=True)
        return True

    def _has_archives(self, directory: Path) -> bool:
        """Check if directory contains archives."""
        for ext in self.ARCHIVE_EXTENSIONS:
            if list(directory.glob(f"*{ext}")):
                return True
        return False

    def _find_archives(self, path: Path) -> List[Path]:
        """Find all archives in path."""
        if path.is_file():
            if path.suffix.lower() in self.ARCHIVE_EXTENSIONS:
                return [path]
            return []

        archives = []
        seen_rars: Set[str] = set()

        for file in path.rglob("*"):
            if not file.is_file():
                continue

            ext = file.suffix.lower()

            # Handle multi-part RAR: only include .rar or .part01.rar
            if ext == ".rar":
                # Check if it's a part file
                if ".part" in file.stem.lower():
                    # Only include part1 or part01
                    if re.search(r"\.part0?1$", file.stem, re.IGNORECASE):
                        archives.append(file)
                        seen_rars.add(file.stem.split(".part")[0])
                else:
                    # Regular .rar file
                    base_name = file.stem
                    if base_name not in seen_rars:
                        archives.append(file)
            elif ext in self.ARCHIVE_EXTENSIONS:
                archives.append(file)

        return archives

    def _find_video_files(self, path: Path) -> List[Path]:
        """Find all video files in path."""
        if path.is_file():
            if path.suffix.lower() in self.VIDEO_EXTENSIONS:
                return [path]
            return []

        videos = []
        for file in path.rglob("*"):
            if (
                file.is_file()
                and file.suffix.lower() in self.VIDEO_EXTENSIONS
                and not self._is_sample_file(file)
            ):
                videos.append(file)

        return videos

    def _is_sample_file(self, path: Path) -> bool:
        """Check if file is a sample/proof file to skip."""
        name = path.name.lower()
        for pattern in self.SAMPLE_PATTERNS:
            if pattern.search(name):
                return True
        return False

    def _extract_archive(self, archive: Path, dest: Path) -> List[Path]:
        """Extract an archive and return list of extracted files."""
        ext = archive.suffix.lower()

        # Create unique subdirectory for this archive
        extract_dir = dest / archive.stem
        extract_dir.mkdir(parents=True, exist_ok=True)

        if ext == ".zip":
            return self._extract_zip(archive, extract_dir)
        elif ext == ".rar":
            return self._extract_rar(archive, extract_dir)
        elif ext == ".7z":
            return self._extract_7z(archive, extract_dir)
        elif ext in {".tar", ".tar.gz", ".tgz"}:
            return self._extract_tar(archive, extract_dir)
        else:
            raise ValueError(f"Unsupported archive format: {ext}")

    def _extract_zip(self, archive: Path, dest: Path) -> List[Path]:
        """Extract ZIP using zipfile module."""
        extracted = []
        with zipfile.ZipFile(archive, "r") as zf:
            for member in zf.namelist():
                if member.endswith("/"):  # Skip directories
                    continue
                zf.extract(member, dest)
                extracted.append(dest / member)
        return extracted

    def _extract_rar(self, archive: Path, dest: Path) -> List[Path]:
        """Extract RAR archive using unrar or 7z."""
        # Try unrar first
        try:
            result = subprocess.run(
                ["unrar", "x", "-y", str(archive), str(dest)],
                capture_output=True,
                timeout=600,
            )
            if result.returncode == 0:
                return list(dest.rglob("*") if dest.exists() else [])
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fall back to 7z
        try:
            result = subprocess.run(
                ["7z", "x", f"-o{dest}", "-y", str(archive)],
                capture_output=True,
                timeout=600,
            )
            if result.returncode == 0:
                return list(f for f in dest.rglob("*") if f.is_file())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Try rarfile module
        try:
            import rarfile

            with rarfile.RarFile(archive) as rf:
                rf.extractall(dest)
                return list(f for f in dest.rglob("*") if f.is_file())
        except ImportError:
            raise RuntimeError(
                "RAR extraction requires unrar, 7z, or rarfile package"
            )

    def _extract_7z(self, archive: Path, dest: Path) -> List[Path]:
        """Extract 7z archive using 7z or py7zr."""
        # Try 7z command first
        try:
            result = subprocess.run(
                ["7z", "x", f"-o{dest}", "-y", str(archive)],
                capture_output=True,
                timeout=600,
            )
            if result.returncode == 0:
                return list(f for f in dest.rglob("*") if f.is_file())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fall back to py7zr
        try:
            import py7zr

            with py7zr.SevenZipFile(archive, "r") as sz:
                sz.extractall(dest)
                return list(f for f in dest.rglob("*") if f.is_file())
        except ImportError:
            raise RuntimeError("7z extraction requires 7z command or py7zr package")

    def _extract_tar(self, archive: Path, dest: Path) -> List[Path]:
        """Extract tar archive."""
        import tarfile

        with tarfile.open(archive, "r:*") as tf:
            tf.extractall(dest)
            return list(f for f in dest.rglob("*") if f.is_file())
