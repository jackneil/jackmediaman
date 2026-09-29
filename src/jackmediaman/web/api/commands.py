"""Command execution API endpoints."""

import asyncio
import subprocess
import sys
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

router = APIRouter()


class CommandInfo(BaseModel):
    """Information about an available command."""

    name: str
    description: str
    subcommands: Optional[list[str]] = None


class CommandExecuteRequest(BaseModel):
    """Request to execute a command."""

    args: list[str] = []
    dry_run: bool = False


class JobStatus(BaseModel):
    """Status of a running job."""

    id: str
    command: str
    status: str  # 'pending', 'running', 'completed', 'failed'
    output: list[str]
    exit_code: Optional[int] = None


# In-memory job storage (for simplicity)
jobs: dict[str, JobStatus] = {}


# Available commands and their metadata
COMMANDS = {
    "process": CommandInfo(
        name="process",
        description="Process completed torrent downloads",
        subcommands=["run"],
    ),
    "duplicates": CommandInfo(
        name="duplicates",
        description="Find and clean duplicate media files",
        subcommands=["scan", "clean"],
    ),
    "rename": CommandInfo(
        name="rename",
        description="Rename media files to standardized format",
        subcommands=["scan", "file"],
    ),
    "subtitles": CommandInfo(
        name="subtitles",
        description="Download subtitles for media files",
        subcommands=["scan", "download"],
    ),
    "artwork": CommandInfo(
        name="artwork",
        description="Download poster artwork from TMDb",
        subcommands=["scan", "download"],
    ),
    "status": CommandInfo(
        name="status",
        description="Check status of library and configuration",
        subcommands=["config", "deluge", "tmdb", "trash"],
    ),
    "setup": CommandInfo(
        name="setup",
        description="Configure external services",
        subcommands=["init", "tmdb", "deluge", "opensubtitles", "plex"],
    ),
    "trash": CommandInfo(
        name="trash",
        description="Manage trash directory",
        subcommands=["list", "restore", "empty"],
    ),
    "torrents": CommandInfo(
        name="torrents",
        description="Manage Deluge torrents",
        subcommands=["list", "pause", "resume"],
    ),
}


@router.get("/", response_model=list[CommandInfo])
async def list_commands():
    """List all available commands."""
    return list(COMMANDS.values())


@router.get("/{name}", response_model=CommandInfo)
async def get_command(name: str):
    """Get details about a specific command."""
    if name not in COMMANDS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Command '{name}' not found")
    return COMMANDS[name]


async def run_command_async(job_id: str, command: str, args: list[str]) -> None:
    """Run a command asynchronously and update job status."""
    job = jobs[job_id]
    job.status = "running"

    try:
        # Build the full command
        cmd = [sys.executable, "-m", "jackmediaman.cli.app", command] + args

        # Run the command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        # Read output line by line
        while True:
            line = await process.stdout.readline()
            if not line:
                break
            job.output.append(line.decode().rstrip())

        await process.wait()
        job.exit_code = process.returncode
        job.status = "completed" if process.returncode == 0 else "failed"

    except Exception as e:
        job.output.append(f"Error: {str(e)}")
        job.status = "failed"
        job.exit_code = -1


@router.post("/{name}/execute", response_model=JobStatus)
async def execute_command(
    name: str,
    request: CommandExecuteRequest,
    background_tasks: BackgroundTasks,
):
    """Execute a command asynchronously."""
    if name not in COMMANDS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Command '{name}' not found")

    # Create job
    job_id = str(uuid4())[:8]
    args = request.args.copy()
    if request.dry_run:
        args.append("--dry-run")

    job = JobStatus(
        id=job_id,
        command=f"jmm {name} {' '.join(args)}",
        status="pending",
        output=[],
    )
    jobs[job_id] = job

    # Start background task
    background_tasks.add_task(run_command_async, job_id, name, args)

    return job


@router.get("/{name}/status/{job_id}", response_model=JobStatus)
async def get_job_status(name: str, job_id: str):
    """Get status of a running job."""
    if job_id not in jobs:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return jobs[job_id]


@router.get("/jobs/", response_model=list[JobStatus])
async def list_jobs():
    """List all jobs."""
    return list(jobs.values())
