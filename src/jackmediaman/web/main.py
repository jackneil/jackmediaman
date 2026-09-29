"""FastAPI application for JackMediaMan web interface."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from jackmediaman import __version__

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False
    FastAPI = None  # type: ignore


def check_dependencies() -> None:
    """Check that required dependencies are installed."""
    if not HAS_FASTAPI:
        raise ImportError(
            "Web dependencies not installed. Install with: pip install jackmediaman[web]"
        )


# Background task manager for command execution
class TaskManager:
    """Manages background command execution tasks."""

    def __init__(self) -> None:
        self.tasks: dict[str, dict] = {}
        self._counter = 0

    def create_task(self, command: str) -> str:
        """Create a new task and return its ID."""
        self._counter += 1
        task_id = f"task_{self._counter}"
        self.tasks[task_id] = {
            "id": task_id,
            "command": command,
            "status": "pending",
            "output": [],
            "result": None,
        }
        return task_id

    def update_task(self, task_id: str, **kwargs) -> None:
        """Update task state."""
        if task_id in self.tasks:
            self.tasks[task_id].update(kwargs)

    def get_task(self, task_id: str) -> dict | None:
        """Get task by ID."""
        return self.tasks.get(task_id)


task_manager = TaskManager()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown - cleanup any running tasks
    pass


def create_app() -> "FastAPI":
    """Create and configure the FastAPI application."""
    check_dependencies()

    app = FastAPI(
        title="JackMediaMan",
        description="Media library manager API",
        version=__version__,
        lifespan=lifespan,
    )

    # CORS middleware for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Import and include API routes
    from .api.routes import router as api_router
    app.include_router(api_router, prefix="/api")

    # Serve static files (built React app)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and (static_dir / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.get("/{path:path}")
        async def serve_spa(path: str):
            """Serve the SPA for all non-API routes."""
            file_path = static_dir / path
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
            return FileResponse(static_dir / "index.html")
    else:
        @app.get("/")
        async def root():
            """Root endpoint when no static files are present."""
            return {
                "name": "JackMediaMan API",
                "version": __version__,
                "docs": "/docs",
                "message": "Web UI not built. Run 'npm run build' in frontend/ directory.",
            }

    return app


# Global app instance
app = create_app() if HAS_FASTAPI else None


def start_server(host: str = "0.0.0.0", port: int = 8080) -> None:
    """Start the web server."""
    check_dependencies()

    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    console.print()
    console.print(Panel(
        f"[bold cyan]JackMediaMan Web Server[/]\n\n"
        f"API: [link=http://localhost:{port}/api]http://localhost:{port}/api[/link]\n"
        f"Docs: [link=http://localhost:{port}/docs]http://localhost:{port}/docs[/link]\n"
        f"UI: [link=http://localhost:{port}]http://localhost:{port}[/link]",
        border_style="cyan",
    ))
    console.print()

    uvicorn.run(
        "jackmediaman.web.main:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    start_server()
